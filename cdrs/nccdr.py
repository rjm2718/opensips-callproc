#!/usr/bin/python

# 2013-06-15 Ryan Mitchell <rjm@tcl.net>
#
# Core Cdr/Call classes and processing: creates cdr records from opensips.acc transactions; this program
# simulates a dialog state machine to make proper cdrs from this transaction data.
#
# Also includes script code to run from cron to periodically create new netcall.calls records from acc data.
#
# * in order for this program to function correctly, the 'acc' opensips table must be capturing all data (at
#    present there are bugs and some problem calls are going partially unrecorded).
#
# * some business logic can go here -- see finalize() methods below; most notably we compute customer billing amount
#    for each call here -- but try to keep data raw and have output modules do various transforms and formatting for
#    rdsg billing, individual customers, and our internal website.
#
#
# TODO
#  - no anum/bnum ? wrap some routines with try/catch so entire program doesn't crash



import sys, time, os, getopt, re
from datetime import datetime
from datetime import timedelta
from collections import Counter
import logging as log

import NanpaDB, netcall, PhoneNumber

TESTMODE = False

test_rdata = []


################################################################################
## {{{ support routines


# load & preprocess raw acc table data
def _loadTxRows(callids):

    # make sure there are no duplicates
    s1 = set(callids)
    callids = list(s1)

    rdata = []

    if not TESTMODE:

        rdata = netcall.NetcallDB().getTxRows(callids)

    else:
        rdata = test_rdata


    rl = []
    for r in rdata:

        # some preprocessing steps here: opensips accounting (acc) is just messy and complicated.

        # we'll be sorting on prtime later, so much sure there is a good value (acc leaves prtime empty for some transactions,
        # but if that's the case then use time field.
        # Note: 'prtime' is the timestamp for when request was sent, 'time' is timestamp of response.
        if r['prtime'] == None or r['prtime'] == '0000-00-00 00:00:00' or r['prtime'] == '':
            r['prtime'] = r['time']

        # special case we want to flag: no routes available, there will be no to_tag in final invite reply and response==480
        # (XXX make sure you don't change the 480! TODO test this and make sure to differentiate between local no-routes-available-in-our-routing-table
        # vs we tried all our lcr routes and all failed)
        if (r['to_tag'] == None or r['to_tag'] == '') and int(r['sip_code']) == 480:
            r['t_branch_idx'] = 99
            r['dst_id'] = None

        rl.append(r)

    return rl



# sip response code to message (XXX warning: carriers are inconsistent in their use of the proper response code)
rc2str = {
    100: 'trying',
    180: 'ringing',
    181: 'forwarded',
    182: 'queued',
    183: 'session progress',
    200: 'OK',
    202: 'accepted',
    401: 'unauthorized',
    403: 'unauthorized',
    404: 'not found',
    407: 'unauthorized',
    408: 'timeout',
    480: 'routes unavailable',
    481: 'tx not found',
    486: 'busy',
    487: 'canceled',
}

def resp2message(rc):

    if rc in rc2str:
        return rc2str[rc]

    if rc < 200: return 'trying'
    if rc < 300: return 'OK'
    if rc < 400: return 'redirect'
    else: return 'failed'



## }}}
################################################################################


################################################################################
# {{{ Call: collection of Cdrs (ie branches) with same Call-Id.
#
# note: Call could be empty of Cdrs/transactions/etc.
# note: this is wacky, but to really get the call details you're interested in, you
#       need to get the fcdr (final branch that's relevant for customer billing) and
#       query that for details... maybe I'll change that someday.

#            if call.t_start:
#                if call.isConfirmedDialog() and call.t_start < now_2h:
#                    print ' * warn: connected call for more than 2 hours. callid=', call.callid
#                if not call.isConfirmedDialog() and call.t_start < now_1h:
#                    print ' * warn: incomplete for more than 1 hours. callid=', call.callid

class Call:
    'Call == collection of Cdrs (ie branches) with same Call-Id'

    def __init__(self, callid):

        self.callid = callid

        self.cdrs = []
        self.tags2cdrs = {}

        # branch of this call relevant for customer billing
        self.f_cdr = None

        # earliest timestamp (ie first invite of first transaction)
        self.t_start = None

    def addCdr(self, cdr):

        assert(cdr.callid == self.callid)

        if cdr.tag not in self.tags2cdrs:
            self.cdrs.append(cdr)
            self.tags2cdrs[cdr.tag] = cdr

    def getCdr(self, tag):
        return self.tags2cdrs[tag]

    def getAllCdrs(self):
        return self.cdrs

    def hasTag(self, tag):
        return tag in self.tags2cdrs

    def getAllTransactions(self):
        txs = []
        for cdr in self.cdrs:
            txs.extend(cdr.transactions)
        return txs

    # warning: most methods below this one are invalid before finalize() is called
    def finalize(self):

        if len(self.cdrs) > 0:

            self.cdrs.sort(key=lambda cdr: cdr.t_branch_idx)
            self.f_cdr = self.cdrs[-1]

            for cdr in self.cdrs:
                if not self.t_start or cdr.t_start < self.t_start:
                    self.t_start = cdr.t_start

        #print 'Call debug:'
        #print ' f_cdr=',self.f_cdr
        #print ' cdrs='
        #for cdr in self.cdrs:
        #    print '   ',cdr

    # the F-Cdr -- the billable/final branch. May return None.
    def getFCdr(self):
        return self.f_cdr

    # get remainder of Cdrs/branches that doesn't include the F-Cdr
    # (may return empty list)
    def getErrCdrs(self):
        cdrs0 = []
        for cdr in self.cdrs:
            if cdr!=self.f_cdr:
                cdrs0.append(cdr)
        return cdrs0

    # may return None, else timestamp of first packet in first branch
    def getEarliestTimestamp(self):
        return self.t_start

    # true if getFCdr() cdr is in a non-final/complete state; i.e. setup, or connected dialog.
    def isIncomplete(self):
        return not self.isComplete()

    def isComplete(self):
        return self.f_cdr and self.f_cdr.d_state==3

    def isConfirmedDialog(self):
        return self.f_cdr and self.f_cdr.d_state==2

    # return total call duration: final - start transactions, OR timeofday - start
    # for the case of an incomplete (possibly ongoing/active) call.  If no data
    # is available, return 0.
    def get_current_duration_seconds(self):

        if not self.t_start: return 0

        elif self.isIncomplete():
            now = datetime.now()
            return int((now - self.t_start).total_seconds())

        else:
            return self.f_cdr.s_total


# }}}
################################################################################


################################################################################
# {{{ Cdr (misnomer): one branch of serial-forking route attempts

# 1. in time range, collect all BYE requests plus INVITEs with final responses

# for each call-id, build the data structures:
#
# Track state of each entry to know what is missing ...
#
# > when done, see which calls have a BYE without the INVITE - should find them in an earlier time period (search by callid)
# > ditto, for other incomplete records, as this might show zombie dialogs or other problems

class Cdr:
    'Cdr == one branch of serial-forking route attempts'


    def __init__(self, callid, tag):

        #print 'creating Cdr with cid', cid

        self.callid = callid
        self.tag = tag # to-tag (or maybe from-tag from a BYE) to identify branch

        # t_* fields are datetime objects (with second resolution, thanks to opensips/mysql recording)

        self.t_start = None       # time of first invite
        self.t_confirm = None     # time of final reply for that invite (confirmation or end of dialog)
        self.t_end = None         # time of dialog end (bye message or same as t_confirm if dialog was never confirmed)
        self.s_setup = None       # seconds spent in call setup (calculated as t_confirm - t_start)
        self.s_connected = None   # seconds spent in confirmed dialog state (calculated as t_end - t_confirmed)
        self.s_total = None       # total seconds (calculated as t_end - t_start)
        self.s_connected_r = None # rounded s_connected per business rules (6/6, 60/6, etc)

        self.c_from = None  # from customer: 3 letter carrier code
        self.c_to = None    # to carrier: 3 letter carrier code
        self.anum = None    # caller-id number (original)
        self.anum2 = None   # caller-id number (modified as needed, e.g. BTN substitution)
        self.a_country = None
        self.a_state = None # from lookup table on anum
        self.a_lata  = None # from lookup table on anum
        self.a_ocn   = None # from lookup table on anum
        self.a_jtype = None # jurisdiction type ('I', 'D', 'U')
        self.bnum = None    # original dialed number
        self.b_lrn = None   # lrn from db lookup of bnum (or set equal to bnum if lrn dip n/a)
        self.b_country = None
        self.b_state = None # from lookup table on b_lrn
        self.b_lata  = None # from lookup table on b_lrn
        self.b_ocn   = None # from lookup table on b_lrn
        self.b_jtype = None # jurisdiction type ('I', 'D', 'U')
        self.xstate = None # 'intra' if a_state==b_state else 'inter'

        self.ruleid = None      # LCR rule id (from Roland's tables)
        self.call_price = 0.0 # computed total billing amount for each call
        self.ptgroup = 0     # price table group used for calculating billable amount
        self.cp_node = []    # CP (internal call processing node) that handled call (could be more than one value in case of mid-dialog failover)


        # identifies the branch; highest value should be last branch tried and relevant for the caller for final response
        self.t_branch_idx = 0

        # rows from acc table
        self.transactions = []

        # hash over tx rows, to avoid duplicates
        self.txhash = {}

        # true if we don't need to go search for more transactions in database (possibly outside of time window)
        #self.complete = False

        # dialog state: 0=? 1=early 2=confirmed 3=terminated, -1=incomplete
        self.d_state = 0


        self.status = 'unknown'
        self.last_rc = 0


    # advance dialog state per SIP rules, populate cdr fields
    # pass in tx rows one at a time, and in chronological order; pass in all tx rows for the same call-id, even though it may
    # have a to_tag for another branch (we want to see all branches so we can extract data)
    def process_tx(self, t):

        # check if any transaction is earlier than t_start
        if not self.t_start or t['prtime'] < self.t_start: self.t_start = t['prtime']

        # avoid duplicates: calculate hash over tx row
        t_ = t.copy()
        del(t_['id'])
        t_hash = hash(frozenset(t_.items()))
        if t_hash in self.txhash:
            #log.debug('- skipping dupe')
            return
        else: self.txhash[t_hash] = 1


        my_branch = t['tag'] == self.tag
        if not my_branch: return

        if t['t_branch_idx']:
            self.t_branch_idx = int(t['t_branch_idx'])

        if t['cp_node']:
            if not self.cp_node or self.cp_node[-1] != t['cp_node']:
                self.cp_node.append(t['cp_node'])

        mINV = t['method']=='INVITE'
        mBYE = t['method']=='BYE'
        rc = int(t['sip_code'])
        rc_provisional = (rc >= 300 and rc < 400) or rc < 200
        rc_ok = rc >= 200 and rc < 300
        rc_error = rc >= 400
        rc_final = rc_ok or rc_error

        #print 'debug: cs=',self.d_state,'  method=',t['method'],'  rc=',rc

        # dialog state logic: 0=? 1=early 2=confirmed 3=terminated, -1=incomplete

        ds = self.d_state  # current state
        ds_n = ds # next state

        if ds==-1: return  # ignore all other data until we find the remaining pieces (or maybe better to try our best with recording fields)

        if ds==0:

            if mINV and rc_provisional: ds_n = 1

            elif mINV and rc_ok:
                self.t_confirm = t['time']
                ds_n = 2

            elif mINV and rc_final:
                self.t_confirm = t['time']
                self.t_end = t['time']
                ds_n = 3

            elif mBYE: # not expected, but OK if we are missing earlier txs from acc table
                log.debug('dialog transition to illegal state; callid='+self.callid)
                ds_n = -1


        elif ds==1:

            if mINV and rc_ok:
                self.t_confirm = t['time']
                ds_n = 2

            elif mINV and rc_final:
                self.t_confirm = t['time']
                self.t_end = t['time']
                ds_n = 3

            elif mBYE: # not expected, but OK if we are missing earlier txs from acc table
                log.debug('dialog transition to illegal state; callid=%s',self.callid)
                ds_n = -1


        elif ds==2:

            if mBYE:
                self.t_end = t['time']
                if rc_ok:
                    ds_n = 3
                    self.status = 'completed'
                else:
                    log.error('wtf bye failed! .. now what?; callid=%s',self.callid)

            else:
                log.debug('reinvite? callid='+self.callid)


        elif ds==3:

            log.warning('unexpected tx after terminated dialog; callid=%s',self.callid)

        ###


        if ds_n > 0 and mINV:

            if 'src_id'     in t and t['src_id']     and not self.c_from:  self.c_from = t['src_id']
            if 'dst_id'     in t and t['dst_id']     and not self.c_to:    self.c_to   = t['dst_id']
            if 'caller_id'  in t and t['caller_id']  and not self.anum: self.anum = t['caller_id']
            if 'callee_id'  in t and t['callee_id']  and not self.bnum: self.bnum = t['callee_id']
            if 'callee_lrn' in t and t['callee_lrn'] and not self.b_lrn:    self.b_lrn = t['callee_lrn']
            if 'ruleid'     in t and t['ruleid']     and not self.ruleid:   self.ruleid = t['ruleid']

        if ds_n==2 or ds_n==3:
            self.last_rc = rc
            self.status = resp2message(rc)


        #
        self.d_state = ds_n


    # done feeding process_tx, now we can compute the computable fields and anything else
    def finalize(self):

        #print 'finalizing) c_from=%s c_to=%s tag=%s' % (self.c_from, self.c_to, self.tag)

        customer = netcall.getCustomerObject(self.c_from)

        if not customer:
            log.warning("no customer object found for c_from %s.  callid=%s", self.c_from, self.callid)
            log.warning(" --> FIX THIS so opensips always records c_from regardless")
            return
            #sys.exit(-1)

        if self.c_to: # c_to may be null if this all routes were tried and we're returning 480 to client
            terminator = netcall.getTerminatorObject(self.c_to)

        ## compute final times
        if self.t_confirm and self.t_start:
            self.s_setup = int((self.t_confirm - self.t_start).total_seconds())

        if self.t_confirm and self.t_end:
            self.s_connected = int((self.t_end - self.t_confirm).total_seconds())

        if self.t_start and self.t_end:
            self.s_total = int((self.t_end - self.t_start).total_seconds())


        # set anum to btn if needed
        btn_used = False
        self.anum2 = self.anum
        if (not PhoneNumber.isUSdomesticNumber(self.anum) and 
            not PhoneNumber.isInterationalNumber(self.anum)):

            btn_used = True
            log.debug("will use btn for anum %s", self.anum)

            if customer.btn:
                self.anum2 = customer.btn
            else:
                self.anum2 = '?BTN?'



        ## compute jurisdiction info

        # warn if b_lrn isn't set: the routing and LRN logic should always
        # set some value for b_lrn (but occassionally LRN dip fails or doesn't return a mapping)
        if not self.b_lrn:
            self.b_lrn = self.bnum
            log.warning('b_lrn not set. using bnum instead')


        # TODO: clarify what happens when BTN was substituted ...
        # call origination type - domestic or international?
        ed = PhoneNumber.num2codes(self.anum2)
        if ed:
            self.a_country = ed[2]
        # note: isUSdomesticNumber is lax compared to num2codes ... TODO implement logic to decide when to use
        # lax or strict parsing rules -- like in a Carrier subclass, since different carriers may have different
        # policies or can assume certain countries/defaults when numbers are ambiguous
        if PhoneNumber.isUSdomesticNumber(self.anum2): self.a_jtype = 'D'
        elif PhoneNumber.isInterationalNumber(self.anum2): self.a_jtype = 'I'
        else: self.a_jtype = 'U'
        if self.a_jtype == 'D' and self.a_country != 'US':
            log.warning('PhoneNumber num2codes & isUSdomesticNumber returning inconsistent result! lax parsing case? anum2=%s', self.anum2)

        # call destination type - domestic or international? (note: parsing bnum here less reliable than looking at lcr route used?)
        ed = PhoneNumber.num2codes(self.b_lrn)
        if ed:
            self.b_country = ed[2]
        if PhoneNumber.isUSdomesticNumber(self.b_lrn): self.b_jtype = 'D'
        elif PhoneNumber.isInterationalNumber(self.b_lrn): self.b_jtype = 'I'
        else: self.b_jtype = 'U'
        if self.b_jtype == 'D' and self.b_country != 'US':
            log.warning('PhoneNumber num2codes & isUSdomesticNumber returning inconsistent result! lax parsing case? b_lrn=%s', self.b_lrn)


        if self.b_jtype == 'D':
            ni = NanpaDB.getNumberInfo(self.b_lrn)
            if ni:
                self.b_state = ni['state']
                self.b_lata  = ni['lata']
                self.b_ocn   = ni['ocn']

        if self.a_jtype == 'D':
            ni = NanpaDB.getNumberInfo(self.anum)
            if ni:
                self.a_state = ni['state']
                self.a_lata  = ni['lata']
                self.a_ocn   = ni['ocn']


        # our business rule: international or different US states, consider interstate, otherwise (unknown jurisdictions) consider it to be intrastate
        self.xstate = 'unknown'
        if btn_used:
            self.xstate = 'unknown'
        elif self.a_jtype == 'U' or self.b_jtype == 'U':
            self.xstate == 'unknown'   # labeled as unknown, but will be billed as intra 
        elif self.a_jtype == 'I' and self.b_jtype == 'D':
            self.xstate = 'inter'
        elif self.a_state and self.b_state and self.a_state==self.b_state:
            self.xstate = 'intra'


        # given the customer object, have it compute the call_price for this call.
        self.s_connected_r = customer.calculateRoundedBillingSeconds(self.s_connected, cdr=self)
        (self.call_price, self.ptgroup) = customer.computeCallPrice(cdr=self)



    #####
    def __str__(self):

        fields = (  self.callid,
                    self.t_start,
                    self.s_setup,
                    self.s_connected,
                    (self.s_connected_r or 0),
                    self.c_from,
                    self.c_to,
                    self.bnum,
                    self.status,
                    self.last_rc,
                    self.t_branch_idx,
                    self.d_state,
                    self.call_price
                    )

        #return 'cid=%16.16s: s=[%s] c=[%s] e=[%s] /   from=%s to=%s' % fields
        return 'cid=%14.14s: s=[%s] %s/%s/%s / from=%s to=%s / bnum=%s  s=%s/%d b=%s s=%s c=%s' % fields


# }}}
################################################################################




################################################################################
# {{{ process_cdrs: convert transaction data in opensips.acc table into Call/Cdr objects.
#
# returns 2 lists of Call objects: one for complete and one for incomplete calls.
#
# define:
#   Cdr = one branch of a call (uniquely identified by to/from tags)
#   Call = all branches of a call that share a unique SIP Call-Id
#
#   If a Call has enough Cdr branches that complete the call (ie, terminated dialog, ie
#   final response to first invite or successful bye after connected dialog), then it
#   is considered 'complete', otherwise 'incomplete'.
#
def process_cdrs(callids):

    calls = {} # map of Call-Id strings to Call objects

    # create the Call objects immediately (added 2013/11/8), since there is a common case
    # where the callid is in the Redis cdr:callids queue but there are not yet any rows
    # in the acc table.
    for cid in callids:
        calls[cid] = Call(cid)

    # note: Cdr (misnamed) object represents a single branch of a call

    for r in _loadTxRows(callids): # return rows (each is a single sip transaction) from acc table

        cid = r['callid']
        method = r['method']
        ttag = r['to_tag']
        ftag = r['from_tag']
        bid = r['t_branch_idx']

        call = calls[cid]

        #tag = ttag + str(bid)
        tag = ttag
        if not tag: ttag = str(bid)

        # uniquely identify each branch: normally this will be the to tag (differs for each serially forked branch, as oppsed
        # to the from tag that is constant for each outbound request);for the case of BYE, this could be the from tag depending on
        # who sent it.  BUT the problem is servers along different branches may not populate the to tag in their response ... so
        # for the purposes of identification here we concat to tag with branch id.

        if not call.hasTag(tag):

            if method == 'BYE' and call.hasTag(ftag + bid): tag = ftag + bid
            else:
                # we could have a stranded BYE before seeing other txs, but don't worry about that for now
                call.addCdr( Cdr(cid, tag) )

        cdr = call.getCdr(tag)

        r['tag'] = tag

        cdr.transactions.append(r)



    # for each call, apply all transactions to all branches to Cdr objects can advance
    # their dialog state machines
    for call in calls.values():

        all_txs = call.getAllTransactions()

        # sort all transactions by prtime, then time, then id
        def cmpt1(left, right):
            if left['prtime'] > right['prtime']: return 1
            if left['prtime'] < right['prtime']: return -1
            if left['time'] > right['time']: return 1
            if left['time'] < right['time']: return -1
            if left['id'] > right['id']: return 1
            if left['id'] < right['id']: return -1
            return 0

        all_txs.sort(cmp = cmpt1) # order important for dialog state machine logic

        for cdr in call.getAllCdrs():

            for t in all_txs:
                cdr.process_tx(t)
            #print ': tag=%s d_state=%d' % (cdr.tag, cdr.d_state)

            if cdr.d_state > 0:
                cdr.finalize()
            else:
                log.debug('not finalizing incomplete Cdr')

        call.finalize()


    now = datetime.now()
    now_1h = now - timedelta(hours=1)
    now_2h = now - timedelta(hours=2)


    # incomplete if getFCdr d_state != 3 (ie: Cdr with highest branch id hasn't transitioned to a completed/final dialog state)
    completes = []
    incompletes = []

    for call in calls.values():

        if call.isIncomplete():
            incompletes.append(call)

        else:
            completes.append(call)


    return [completes, incompletes]

# }}}
################################################################################




##########################################################################
## {{{ py.test tests

def setup_module(m):

    global TESTMODE
    TESTMODE = True

    netcall.NetcallDB.TESTMODE = True


def set_test_data(rdata):
    del(test_rdata[:])
    test_rdata.extend(rdata)


def test_p1():

    set_test_data([
        {'callee_lrn': '15038289199', 'caller_id': '+15032222222', 'sip_reason': 'Forbidden', 't_branch_idx': '0', 'duration': 0L, 'sip_code': '403', 'id': 10152L, 'src_id': 'a22', 'ruleid': 204012L, 'setuptime': 0L, 'cp_node': 'g08', 'dst_id2': 'erl', 'method': 'INVITE', 'from_tag': 'as63dfc9e2', 'callee_id': '15039432980', 'callid': '44e9522b1f284b6c6203a4ba711867a8@70.102.5.22:5060', 'to_tag': 'aprqngfrt-v4irvo30000c6', 'created': None, 'dst_id': 'erl', 'prtime': datetime(2013, 6, 19, 22, 22, 14), 'time': datetime(2013, 6, 19, 22, 22, 14)},
        {'callee_lrn': '15038289199', 'caller_id': '+15032222222', 'sip_reason': 'Ringing', 't_branch_idx': '1', 'duration': 0L, 'sip_code': '180', 'id': 10154L, 'src_id': 'a22', 'ruleid': 204012L, 'setuptime': 0L, 'cp_node': 'g08', 'dst_id2': 'wds', 'method': 'INVITE', 'from_tag': 'as63dfc9e2', 'callee_id': '15039432980', 'callid':   '44e9522b1f284b6c6203a4ba711867a8@70.102.5.22:5060', 'to_tag': 'SDjugrf99-10829758', 'created': None, 'dst_id': 'wds', 'prtime': datetime(2013, 6, 19, 22, 22, 14), 'time': datetime(2013, 6, 19, 22, 22, 16)},
        {'callee_lrn': '15038289199', 'caller_id': '+15032222222', 'sip_reason': 'OK', 't_branch_idx': '1', 'duration': 0L, 'sip_code': '200', 'id': 10158L, 'src_id': 'a22', 'ruleid': 204012L, 'setuptime': 0L, 'cp_node': 'g08', 'dst_id2': 'wds', 'method': 'INVITE', 'from_tag': 'as63dfc9e2', 'callee_id': '15039432980', 'callid':        '44e9522b1f284b6c6203a4ba711867a8@70.102.5.22:5060', 'to_tag': 'SDjugrf99-10829758', 'created': None, 'dst_id': 'wds', 'prtime': datetime(2013, 6, 19, 22, 22, 14), 'time': datetime(2013, 6, 19, 22, 22, 17)},
        {'callee_lrn': '', 'caller_id': '+15032222222', 'sip_reason': 'OK', 't_branch_idx': '', 'duration': 0L, 'sip_code': '200', 'id': 10162L, 'src_id': 'a22', 'ruleid': 0L, 'setuptime': 0L, 'cp_node': 'g08', 'dst_id2': '', 'method': 'BYE', 'from_tag': 'as63dfc9e2', 'callee_id': '', 'callid':                                          '44e9522b1f284b6c6203a4ba711867a8@70.102.5.22:5060', 'to_tag': 'SDjugrf99-10829758', 'created': None, 'dst_id': '', 'prtime': None, 'time': datetime(2013, 6, 19, 22, 22, 23)},
        ])

    (bcalls, incompletes) = process_cdrs(['44e9522b1f284b6c6203a4ba711867a8@70.102.5.22:5060'])
    assert(len(bcalls)==1)
    assert(len(incompletes)==0)

    fcdr = bcalls[0].getFCdr()
    errs = bcalls[0].getErrCdrs()

    assert(len(errs)==1)
    ecdr = errs[0]

    #print fcdr
    #print ecdr

    #print fcdr.t_start
    #print fcdr.t_confirm
    #print fcdr.t_end
    #print fcdr.s_setup
    #print fcdr.s_connected
    #print fcdr.s_total
    assert(fcdr.s_total==9)
    assert(fcdr.s_setup==3)
    assert(fcdr.s_connected==6)



def test_p2():

    # here we have what looks like an extraneous response, but the final 480 is actually what was sent back to our customer
    # after no other routes were available to try.  So, 2 error branches: one branch to erl, the other to wds
    set_test_data([
        {'callee_lrn': '15038289199', 'caller_id': '+15032222222', 'sip_reason': 'Forbidden', 't_branch_idx': '0', 'duration': 0L, 'sip_code': '403', 'id': 10164L, 'src_id': 'a22', 'ruleid': 204012L, 'setuptime': 0L, 'cp_node': 'g08', 'dst_id2': 'erl', 'method': 'INVITE', 'from_tag': 'as4a819a50', 'callee_id': '15039432980', 'callid': '36f1b17621c025302eb7b69c043344f1@70.102.5.22:5060', 'to_tag': 'aprqngfrt-jvbfii30000c6', 'created': None, 'dst_id': 'erl', 'prtime': datetime(2013, 6, 19, 22, 25), 'time': datetime(2013, 6, 19, 22, 25)},
        {'callee_lrn': '15038289199', 'caller_id': '+15032222222', 'sip_reason': 'Request Timeout', 't_branch_idx': '1', 'duration': 0L, 'sip_code': '408', 'id': 10166L, 'src_id': 'a22', 'ruleid': 204012L, 'setuptime': 0L, 'cp_node': 'g08', 'dst_id2': 'wds', 'method': 'INVITE', 'from_tag': 'as4a819a50', 'callee_id': '15039432980', 'callid': '36f1b17621c025302eb7b69c043344f1@70.102.5.22:5060', 'to_tag': '01cb61382f57641c77c469cfc8891839-e91e', 'created': None, 'dst_id': 'wds', 'prtime': datetime(2013, 6, 19, 22, 25), 'time': datetime(2013, 6, 19, 22, 25, 5)},
        {'callee_lrn': '15038289199', 'caller_id': '+15032222222', 'sip_reason': 'Temporarily Unavailable', 't_branch_idx': '1', 'duration': 0L, 'sip_code': '480', 'id': 10170L, 'src_id': 'a22', 'ruleid': 204012L, 'setuptime': 0L, 'cp_node': 'g08', 'dst_id2': 'wds', 'method': 'INVITE', 'from_tag': 'as4a819a50', 'callee_id': '15039432980', 'callid': '36f1b17621c025302eb7b69c043344f1@70.102.5.22:5060', 'to_tag': '', 'created': None, 'dst_id': 'wds', 'prtime': datetime(2013, 6, 19, 22, 25), 'time': datetime(2013, 6, 19, 22, 25, 5)},
        ])

    (bcalls, incompletes) = process_cdrs(['36f1b17621c025302eb7b69c043344f1@70.102.5.22:5060'])
    assert(len(bcalls)==1)
    assert(len(incompletes)==0)

    fcdr = bcalls[0].getFCdr()
    errs = bcalls[0].getErrCdrs()


    #print fcdr

    assert(fcdr.t_branch_idx==99)
    assert(len(errs)==2)

    e0 = errs[0].t_branch_idx
    e1 = errs[1].t_branch_idx
    assert(e0 != e1 and ((e0==0 or e0==1) and (e1==0 or e1==1)))


def test_nanpa():

    ni = NanpaDB.getNumberInfo('+15412233333')
    assert(ni['state'] == 'OR')
    assert(ni['lata'] == '670')
    ni = NanpaDB.getNumberInfo('5039433333')
    assert(ni['state'] == 'OR')
    assert(ni['lata'] == '672')
    
def test_p3():

    set_test_data([
        {'callee_lrn': '15032060203', 'caller_id': '12123330002', 'sip_reason': 'Request Timeout', 't_branch_idx': '0', 'duration': 0L, 'sip_code': '408', 'id': 10614L, 'src_id': 'a22', 'ruleid': 54988L, 'setuptime': 0L, 'cp_node': 'g07', 'dst_id2': 'erl', 'method': 'INVITE', 'from_tag': 'as60a8cbfa', 'callee_id': '15036665555', 'callid': '16aac9fe7d3d04bb62443cc24625b424@70.102.5.22:5060', 'to_tag': '01cb61382f57641c77c469cfc8891839-c5aa', 'created': None, 'dst_id': 'erl', 'prtime': datetime(2013, 6, 21, 1, 29, 3), 'time': datetime(2013, 6, 21, 1, 29, 7)},
        {'callee_lrn': '15032060203', 'caller_id': '12123330002', 'sip_reason': 'Request Timeout', 't_branch_idx': '1', 'duration': 0L, 'sip_code': '408', 'id': 10634L, 'src_id': 'a22', 'ruleid': 54988L, 'setuptime': 0L, 'cp_node': 'g07', 'dst_id2': 'wds', 'method': 'INVITE', 'from_tag': 'as60a8cbfa', 'callee_id': '15036665555', 'callid': '16aac9fe7d3d04bb62443cc24625b424@70.102.5.22:5060', 'to_tag': '01cb61382f57641c77c469cfc8891839-5dbb', 'created': None, 'dst_id': 'wds', 'prtime': datetime(2013, 6, 21, 1, 29, 7), 'time': datetime(2013, 6, 21, 1, 29, 11)},
        {'callee_lrn': '15032060203', 'caller_id': '12123330002', 'sip_reason': 'Temporarily Unavailable', 't_branch_idx': '1', 'duration': 0L, 'sip_code': '480', 'id': 10638L, 'src_id': 'a22', 'ruleid': 54988L, 'setuptime': 0L, 'cp_node': 'g07', 'dst_id2': 'wds', 'method': 'INVITE', 'from_tag': 'as60a8cbfa', 'callee_id': '15036665555', 'callid': '16aac9fe7d3d04bb62443cc24625b424@70.102.5.22:5060', 'to_tag': '', 'created': None, 'dst_id': 'wds', 'prtime': datetime(2013, 6, 21, 1, 29, 7), 'time': datetime(2013, 6, 21, 1, 29, 11)},
        ])

    (bcalls, incompletes) = process_cdrs(['16aac9fe7d3d04bb62443cc24625b424@70.102.5.22:5060'])
    assert(len(bcalls)==1)
    assert(len(incompletes)==0)

    fcdr = bcalls[0].getFCdr()
    errs = bcalls[0].getErrCdrs()

    assert(fcdr.t_branch_idx==99)
    assert(len(errs)==2)


    assert(fcdr.last_rc==480)
    assert(fcdr.call_price==0.0)


def test_incomplete1():

    set_test_data([
        {'callee_lrn': '', 'caller_id': '+15032222222', 'sip_reason': 'OK', 't_branch_idx': '', 'duration': 0L, 'sip_code': '200', 'id': 10162L, 'src_id': 'a22', 'ruleid': 0L, 'setuptime': 0L, 'cp_node': 'g08', 'dst_id2': '', 'method': 'BYE', 'from_tag': 'as63dfc9e2', 'callee_id': '', 'callid':                                          '44e9522b1f284b6c6203a4ba711867a8@70.102.5.22:5060', 'to_tag': 'SDjugrf99-10829758', 'created': None, 'dst_id': '', 'prtime': None, 'time': datetime(2013, 6, 19, 22, 22, 23)},
        ])

    callid = '44e9522b1f284b6c6203a4ba711867a8@70.102.5.22:5060'
    (bcalls, incompletes) = process_cdrs([callid])
    assert(len(bcalls)==0)
    assert(len(incompletes)==1)

    fcdr = incompletes[0].getFCdr()
    assert(fcdr.callid == callid)

def test_500err():

    set_test_data([
        {'callee_lrn': '', 'caller_id': '', 'sip_reason': 'Server Internal Error', 't_branch_idx': '', 'duration': 0L, 'sip_code': '500', 'id': 11376206L, 'drgrpid': '', 'src_id': '', 'ruleid': 0L, 'setuptime': 0L, 'cp_node': '', 'dst_id2': '', 'method': 'INVITE', 'from_tag': '3596198315-322998', 'callee_id': '', 'callid': '579299693-3596198315-322991@LAX-MSC1S.mydomain.com', 'to_tag': '', 'created': None, 'dst_id': '', 'prtime': None, 'time': datetime(2013, 12, 16, 7, 58, 35)},
        {'callee_lrn': '', 'caller_id': '', 'sip_reason': 'Server Internal Error', 't_branch_idx': '', 'duration': 0L, 'sip_code': '500', 'id': 11376208L, 'drgrpid': '', 'src_id': '', 'ruleid': 0L, 'setuptime': 0L, 'cp_node': '', 'dst_id2': '', 'method': 'INVITE', 'from_tag': '3596198315-322998', 'callee_id': '', 'callid': '579299693-3596198315-322991@LAX-MSC1S.mydomain.com', 'to_tag': '', 'created': None, 'dst_id': '', 'prtime': None, 'time': datetime(2013, 12, 16, 7, 58, 35)}
        ])

    callid = '579299693-3596198315-322991@LAX-MSC1S.mydomain.com'
    (bcalls, incompletes) = process_cdrs([callid])
    assert(len(bcalls)==1)
    assert(len(incompletes)==0)

    fcdr = bcalls[0].getFCdr()
    #print fcdr
    assert(fcdr.callid == callid)

    assert(fcdr.last_rc == 500)

# }}}
##########################################################################









####
#### main script to populate netcall.calls table ...
####






def parseDate(ds):
    d = None
    try:
        d = datetime.strptime(ds, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            d = datetime.strptime(ds, '%Y-%m-%d')
        except ValueError as e:
            raise e

    return d


def cmdHelp(e=None):
    if e:
        print '***'
        print ' error=',e
        print '***'

    print ''
    print 'usage:'
    print ' -h | --help'
    print ' -v | --verbose'
    print " --dfrom   query acc table for calls that start from date"
    print " --dto     query acc table for calls that start earlier than date"
    print " --src_id  limit calls processed to this source (inbound customer) id"
    print " --limit   limit calls processed"
    sys.exit(-1)




if __name__ == '__main__':

    rl = log.getLogger()
    rl.setLevel(log.INFO)

    # default parameters overrid by command line
    p_dfrom = None
    p_dto   = None
    p_src_id = None   # 'vxb'
    p_limit = -1


    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hv', ['dfrom=', 'dto=', 'limit=', 'src_id=', 'help', 'summary', 'verbose'])

    except getopt.GetoptError as e:
        cmdHelp(e)

    try:

        for opt, arg in opts:

            if opt=='--dfrom':
                p_dfrom = parseDate(arg)
            if opt=='--dto':
                p_dto = parseDate(arg)

            if opt=='--src_id':
                p_src_id = arg

            if opt=='--limit':
                p_limit = int(arg)

            if opt=='--help' or opt=='-h':
                cmdHelp()

            if opt=='--verbose' or opt=='-v':
                rl = log.getLogger()
                rl.setLevel(log.DEBUG)

    except Exception as e:
        cmdHelp(e)


    if not p_dto:
        p_dto = datetime.now() - timedelta(minutes=5)

    if not p_dfrom:
        p_dfrom = p_dto - timedelta(hours=1)

    log.debug('date range ['+str(p_dfrom)+","+str(p_dto)+"]")

    t1 = time.time()

    db = netcall.NetcallDB()


    # * final answer on date range: given a date range, we are interested in calls that have terminated with the
    #    range.  great, because we can do an easier query and not miss any long duration (or long setup) calls; the
    #    only thing you do is if you find an incomplete call, go back to an earlier time to search for the starting
    #    transactions.  Forget about Redis new Call-Id queue ... nice idea but it's adding unecessary complexity.


    callids = db.getCallIds(p_dfrom, p_dto, p_src_id, p_limit)

    log.debug("looking at %d distinct call-ids", len(callids))
    if len(callids)==0:
        log.info("nothing to do, exiting")
        sys.exit(0)

    (calls, incompletes) = process_cdrs(callids)

    log.info("process_cdrs returned with %d complete and %d incomplete calls", len(calls), len(incompletes))

    # Note: this script is only recording completed calls (has an invite plus a final dialog-ending response); failed
    # branches stay in the acc table to be analyzed elsewhere.

    # Note: can ignore incompletes; any in-progress calls will be picked up in later date ranges

    # NOTE: race condition when a failed branch shows up as a complete call but in reality the switch is currently
    # trying a next route.  Three solutions: 1) don't have the date range too close to the current time (older than
    # 10 minutes would be good), or 2) have Opensips put a flag in the acc record to note that this tx response
    # was the final one returned to the client, or 3) just run this script at a later time and the writeCallRecord()
    # below will simply clobber the previous erroneous record.

    for call in calls:

        db.writeCallRecord(call)


    t2 = time.time()
    log.info("recorded calls in %.1f seconds", (t2-t1))

