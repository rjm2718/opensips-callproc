#!/usr/bin/python

# Netcall core classes
# (c) 2013 Telecom Logic, LLC.  <rjm@tcl.net>


# NetcallDB: general database routines
#
# Carrier: a terminating or originating SIP peer
#  - Customer: a Netcall customer that sends us traffic
#  - Terminator: a carrier we send traffic to
#
# test with py.test
#
# TODO
#  - persistent db handle ... app handles exception on idle disconnect by server or should we? the former, probably.
#  - Redis caching



import sys, time, os, getopt, re
import logging as log
from struct import pack
from datetime import datetime
from datetime import timedelta

import redis
import MySQLdb

import PhoneNumber, nccdr



###############################################################################
# {{{ class NetcallDB: ops for netcall & opensips databases



class NetcallDB():

    DBHOST = 'localhost'  # run on a26 or a27 or point to haproxy (but beware of haproxy closing idle connections)
    DBPORT = 3306

    os_dbuser = 'opensips'
    os_dbpswd = 'barf'
    os_dbname = 'opensips'

    nc_dbuser = 'netcall'
    nc_dbpswd = 'barf'
    nc_dbname = 'netcall'

    REDIS_H = 'a26'
    REDIS_P = 6379

    TESTMODE = False


    def __init__(self):

        self.os_conn = None
        self.nc_conn = None
        self.redis = None

    
    # warning: one thread per connection
    def _osc(self):
        if not self.os_conn:
            h = NetcallDB.DBHOST
            p = NetcallDB.DBPORT
            u = NetcallDB.os_dbuser
            s = NetcallDB.os_dbpswd
            n = NetcallDB.os_dbname
            if NetcallDB.TESTMODE:
                n = n + '_test'
            self.os_conn = MySQLdb.connect(host=h, port=p, user=u, passwd=s, db=n);
        return self.os_conn

    # warning: one thread per connection
    def _ncc(self):
        if not self.nc_conn:
            h = NetcallDB.DBHOST
            p = NetcallDB.DBPORT
            u = NetcallDB.nc_dbuser
            s = NetcallDB.nc_dbpswd
            n = NetcallDB.nc_dbname
            if NetcallDB.TESTMODE:
                n = n + '_test'
            self.nc_conn = MySQLdb.connect(host=h, port=p, user=u, passwd=s, db=n);
        return self.nc_conn

    def _redis(self):
        if not self.redis and not NetcallDB.TESTMODE:
            self.redis = redis.Redis(host=NetcallDB.REDIS_H, port=NetcallDB.REDIS_P, db=0)
        return self.redis


    def testMode(self):

        return NetcallDB.TESTMODE



    # query database for calls that *end* within dfrom/dto range.  Return dict with database
    # fields, plus a few extras we assemble here.  TODO: return cursor/iterator for UI pagers (or Java?).
    def getCallRecords(self, dfrom, dto, limit=-1):

        calls = []

        cur = self._ncc().cursor(MySQLdb.cursors.DictCursor)

# warning: many table join here will silently ignore return rows if any price table / lcr rule combo isn't set properly!!

        sql = '''SELECT C.*,I.callid,PT.mprice,A.prefix as "rtpatt", A.groupid as "rtgroup" 
                   FROM calls C, callids2calls IC, callids I,price_tables PT,dr_rules_cp_archive A
                  WHERE IC.calls_id=C.id AND IC.callid_id=I.id AND PT.ruleid=C.ruleid
                     AND PT.ptgroup=C.ptgroup AND C.ruleid=A.ruleid'''

        sql += ' AND C.t_end >= %s AND C.t_end < %s'

        if limit >= 0:
            sql += ' LIMIT %d' % (limit)

        #print sql, dfrom, dto
        #sys.exit(0)

        cur.execute(sql, (dfrom, dto))

        for c in cur.fetchall():
            calls.append(c)

        cur.close()

        return calls


    # take netcall.Call object and write all the fields into the calls table.  If the record already exists, 
    # delete and replace it.
    def writeCallRecord(self, call):

        callid = call.callid

        cid = self._getOrMakeIdFromCallId(callid)  # cid == id in netcall.callids table for the given Call-Id value.

        cdr = call.getFCdr()

        if not cdr:
            log.error('nothing to record! no fcdr.  why is that? call=%s', call)
            return

        # Note: python mysql automatically begins a new transaction when cursor is first used.
        ncc = self._ncc()
        cur = ncc.cursor(MySQLdb.cursors.DictCursor)

        try:

            # check/delete existing row for Call-Id
            cur.execute("SELECT calls_id from callids2calls WHERE callid_id='%s'" % (cid))
            h = cur.fetchone()
            if h:
                cur.execute("DELETE FROM calls WHERE id=%s", h['calls_id'])
                log.debug('netcall.calls: will clobber previous record for %s', callid)


            # create data to insert into calls table

            c_from = '?'
            c_from5 = '?'
            if cdr.c_from:
                c_from = cdr.c_from
                c_from5 = getCustomerObject(cdr.c_from).code5

            c_to5 = None
            if cdr.c_to:
                c_to5 = getTerminatorObject(cdr.c_to).code5


            # insert new row, get id

            calldata = {

                'c_from':        c_from,
                'c_from5':       c_from5,
                'c_to':          cdr.c_to,
                'c_to5':         c_to5,
                'rspcode':       cdr.last_rc,
                'fstatus':       cdr.status,
                't_start':       cdr.t_start,
                't_confirm':     cdr.t_confirm,
                't_end':         cdr.t_end,
                's_setup':       cdr.s_setup,
                's_connected':   cdr.s_connected,
                's_connected_r': cdr.s_connected_r,
                's_total':       cdr.s_total,
                'anum':          cdr.anum,
                'anum2':         cdr.anum2,
                'a_country':     cdr.a_country,
                'a_state':       cdr.a_state,
                'a_lata':        cdr.a_lata,
                'a_ocn':         cdr.a_ocn,
                'a_jtype':       cdr.a_jtype,
                'bnum':          cdr.bnum,
                'b_lrn':         cdr.b_lrn,
                'b_country':     cdr.b_country,
                'b_state':       cdr.b_state,
                'b_lata':        cdr.b_lata,
                'b_ocn':         cdr.b_ocn,
                'b_jtype':       cdr.b_jtype,
                'xstate':        cdr.xstate,
                'call_price':    cdr.call_price,
                'ruleid':        cdr.ruleid,
                'ptgroup':       cdr.ptgroup,
                'cp_nodes':      ','.join(cdr.cp_node),
            }

            cdkeys = calldata.keys()
            cdvals = calldata.values()

            sql = 'INSERT INTO calls (' + ','.join(cdkeys) + ')'
            sql += ' VALUES (' + ','.join( ['%s'] * len(cdkeys) ) + ')'

            cur.execute(sql, cdvals)

            calls_id = ncc.insert_id()

            # insert new row in callids2calls table
            cur.execute("INSERT INTO callids2calls (callid_id, calls_id) VALUES (%s,%s)", (cid, calls_id))

            ncc.commit()

        except MySQLdb.Error as e:
            log.error('problem with call %s', callid)
            log.error(e)
            ncc.rollback()
            raise e

        finally:
            if cur:
                cur.close()




    # query opensips acc table for transactions matching Call-Id values.  Ensure
    # that transactions are returned in order (sort by auto incremented primary key,
    # which is done already but I want to be explicit because it's critical).
    # TODO will eventually need to use cursors and an iterator to return instead of loading it all into ram at once
    def getTxRows(self, callids=[]):

        rdata = []

        cur = self._osc().cursor(MySQLdb.cursors.DictCursor)

        for cid in callids:

            cur.execute("SELECT * from acc WHERE callid='%s' AND dst_id=dst_id2 ORDER BY id ASC" % (cid))
            h = cur.fetchall()
            rdata.extend(h)

        cur.close()

        return rdata

    # query acc table for distinct list of Call-Ids
    # TODO will eventually need to use cursors and an iterator to return instead of loading it all into ram at once
    def getCallIds(self, dfrom, dto, src_id=None, limit=None):

        cids = []

        if not limit:
            limit = -1

        cur = self._osc().cursor(MySQLdb.cursors.DictCursor)

        sql = "SELECT distinct(callid) from acc WHERE "
        sql += " ((prtime >= '%s' AND prtime < '%s') OR (time >= '%s' AND time < '%s'))"
        if src_id:
            sql += " AND src_id='%s'" % (src_id)
        if limit >= 0:
            sql += " LIMIT %d" % (limit)

        sql = sql % (dfrom,dto,dfrom,dto)

        cur.execute(sql)
        for cid in cur.fetchall():
            cids.append(cid['callid'])

        cur.close() # needed?

        return cids



    ####


    # return primary key (int) from netcall.callids table for given Call-Id.
    def _getIdFromCallId(self, nccursor, callid):

        # TODO redis cache

        nccursor.execute("SELECT id FROM callids WHERE callid=%s", (callid))
        h = nccursor.fetchone()

        if h: return h['id']

        return None

    # @see getIdFromCallId ; creates new row in netcall.callids table as needed.
    # this creates/commits its own tx, so careful to call this before using another cursor.
    def _getOrMakeIdFromCallId(self, callid):

        # TODO lock callids table to avoid race condition

        ncc = self._ncc()
        cur = ncc.cursor(MySQLdb.cursors.DictCursor)

        try:

            cid = self._getIdFromCallId(cur, callid)

            if cid: return cid

            cur.execute("INSERT INTO callids (callid) VALUES (%s)", (callid))

            cid = ncc.insert_id()

            # TODO redis cache

            ncc.commit()

            return cid

        except MySQLdb.Error as e:
            log.error(e)
            ncc.rollback()

        finally:
            if cur:
                cur.close()



    #
    # It should be guaranteed that there will always be a valid ptgroup & corresponding price
    # to look up: opensips will only match an lcr rule based on group, and for every lcr rule in dr_rules_cp table
    # there is a fk constraint 
    def getRoutePrice(self, ptgroup, ruleid):

        if NetcallDB.TESTMODE:
            return 0.00159

        # check Redis cache first
        rck = 'pt.'+str(ptgroup)+'.'+str(ruleid)
        rp = self._redis().get(rck)

        if rp:
            if rp != 'n/a':
                return float(rp)
            else:
                return None


        cur = self._ncc().cursor(MySQLdb.cursors.DictCursor)

        cur.execute("SELECT mprice FROM price_tables WHERE ruleid=%s and ptgroup=%s",  (ruleid, ptgroup))
        h = cur.fetchone()

        cur.close()

        if h:
            rp = h['mprice']
            PTEXPIRE = 864000 # 10 days
            self._redis().setex(rck, rp, PTEXPIRE)
            return float(rp)

        else:
            rp = 'n/a'
            PTEXPIRE = 864000 # 10 days
            self._redis().setex(rck, rp, PTEXPIRE)
            return None



    # returns ts1, ts2, src_ip, pcapblob from netcall.pcaps table
    def getCaptureData(self, callid):

        ncc = self._ncc()
        cur = ncc.cursor(MySQLdb.cursors.DictCursor)

        cid = self._getIdFromCallId(cur, callid)

        if not cid:
            #print 'no cid?!? callid=',callid
            #sys.exit(0)
            return None


        cur.execute("SELECT P.ts1,P.ts2,P.src_ip,P.pcap FROM pcaps P WHERE P.callid_id=%s", (cid))
        h = cur.fetchone()

        cur.close()

        #if h: print 'get: ', ', '.join(map(str, (cid, h['ts1'], h['ts2'], h['src_ip'], len(h['pcap']))))
        #else: print 'get: ',cid,callid

        if h:
            return (h['ts1'], h['ts2'], h['src_ip'], h['pcap'])

        return None



    # store packet capture data for a call:
    # callid: Call-Id in netcall.callid
    # ts1: unix timestamp of receipt of earliest packet
    # ts2: unix timestamp of receipt of latest packet
    # src_ip: integer (4 byte, network order) source IP address of earliest packet
    # pcapblob: pcap packet (without pcap global file header)
    def writeCaptureData(self, callid, ts1, ts2, src_ip, pcapblob):
    
        cid = self._getOrMakeIdFromCallId(callid)

        cur = self._ncc().cursor(MySQLdb.cursors.DictCursor)

        cur.execute("SELECT callid_id FROM pcaps WHERE callid_id=%s", (cid))
        h = cur.fetchone()

        if h:
            cur.execute("UPDATE pcaps SET ts1=%s,ts2=%s,src_ip=%s,pcap=%s WHERE callid_id=%s", (ts1, ts2, src_ip, pcapblob, cid))

        else:
            cur.execute("INSERT INTO pcaps (callid_id,ts1,ts2,src_ip,pcap) VALUES (%s,%s,%s,%s,%s)", (cid, ts1, ts2, src_ip, pcapblob))

        self._ncc().commit()

        cur.close()

# }}}
###############################################################################



###############################################################################
# {{{ classes Carrer/Customer/Terminator

# note: could have fixed number of classes, and pass in static config data for each instance, but I think
# that there can be too many custom business rules that you'll want custom classes.... so below is a combination of both.



code3_2_customers = {}
code3_2_terminators = {}

# return singleton

def getCustomerObject(code3):
    return getCarrierObject_(code3, True)
def getTerminatorObject(code3):
    return getCarrierObject_(code3, False)

def getCarrierObject_(code3, customer):

    if not code3:
        #log.warning("null code '%s'!", code3)
        return

    elif code3 not in carrierData:
        log.warning("unknown code '%s'!", code3)

    # cached?
    if customer and code3 in code3_2_customers:
        return code3_2_customers[code3]
    if not customer and code3 in code3_2_terminators:
        return code3_2_terminators[code3]



    cd = carrierData.get(code3) # default None

    if not cd: cd = carrierData['default']

    if customer:

        c = Customer
        if 'subclass.customer' in cd:
            c = cd['subclass.customer']
        o = c(code3)
        code3_2_customers[code3] = o

    else:

        c = Terminator
        if 'subclass.terminator' in cd:
            c = cd['subclass.terminator']
        o = c(code3)
        code3_2_terminators[code3] = o
         
    return o



class Carrier(object):

    def __init__(self, code3):

        if not code3:
            raise Exception("code3 must not be empty")

        self.cdata = {}
        self.cdata.update(carrierData['default'])

        cd_ = carrierData.get(code3)
        if cd_:
            self.cdata.update(cd_) # overwrite defaults as given

        self.db = NetcallDB()


    # opportunity for custom business logic that isn't covered elsewhere
    def finalizeCdr(self, cdr): pass

    # fun python fact: careful implementing __getattr__: it will start getting called with weird keys
    # like __eq__ and friends.  seems it's not inhereting any reasonable default implementations from
    # some base class ... ah ha! ... look into old vs. new style Python classes and inheriting from object.
    # update 20131220: inherited from object, reran unit tests, seems fine, and didn't even have to override __eq__
    def __getattr__(self, key):
        return self.cdata.get(key)

    def __str__(self):
        return str(self.cdata)

        

class Terminator(Carrier): pass # can't think of what custom things we'll need yet


# each customer can end up with weird business rules; subclass this as needed
# if the customization can't be implemented with static config carrierData.
class Customer(Carrier):


    # take the number of connected seconds and apply billing_spec_r1/billing_spec_r2 .
    def _calculateRoundedBillingSeconds(self, s_connected, r1, r2):

        if not s_connected: return 0

        cr1 = False

        # first (minimum) interval
        if r1 > 0:
            if s_connected <= r1:
                return r1
            else:
                s_connected -= r1
                cr1 = True

        # subsequent intervals
        ints = s_connected/r2
        if s_connected % r2: ints += 1  # bump up to next interval

        total = ints * r2
        if cr1: total += r1

        return total

        
    # take the number of connected seconds (required arg) and apply billing_spec_r1/billing_spec_r2
    # using the default statically configured billing_spec_r1 & billing_spec_r2;
    # optional cdr argument (subclasses can use it to implement custom rules);
    # API note: look, but don't touch argument cdr
    def calculateRoundedBillingSeconds(self, s_connected, cdr=None):

        return self._calculateRoundedBillingSeconds(s_connected, self.billing_spec_r1, self.billing_spec_r2)


    # compute price for call; return (total amount, ptgroup used)
    # Explanation: the groupid field in dr_rules_cp table is now simply the route table id, and doesn't have anything
    # to do with route pricing.  Which price table to use is by default decided by static assignment in
    # netcall.customers table, or determined at run-time depending on call parameters (e.g. different price
    # tables for inter/intra state), so subclasses can look at cdr object and figure out which price table to use.
    # API note: look, but don't touch argument cdr
    def computeCallPrice(self, cdr):

        scr = cdr.s_connected_r # client assigned with previous call to calculateRoundedBillingSeconds()

        cp = 0.0

        if scr > 0:

            rt_price_minute = self.db.getRoutePrice(self.ptgroup, cdr.ruleid)

            if not rt_price_minute:
                log.error("no route price available! ptgroup=%d ruleid=%d callid=%s", self.ptgroup, cdr.ruleid, cdr.callid)
                return (0.0, self.ptgroup)

            cp = rt_price_minute * scr/60.0

        return (cp, self.ptgroup)




### custom carrier classes
###
### (create one for each carrier even if not needed, just for completeness)

class Level3Terminator(Terminator): pass

class ReynwoodCustomer(Customer): pass


class QuickcomCustomer(Customer):

    # Quickcom has a specific agreement regarding billing rounding seconds
    def calculateRoundedBillingSeconds(self, s_connected, cdr=None):

        r1 = self.billing_spec_r1
        r2 = self.billing_spec_r2

        if cdr and cdr.bnum:

            nd = PhoneNumber.num2codes(cdr.bnum)
            if nd and nd[2]=='MX':
                r1 = 1
                r2 = 1

        return self._calculateRoundedBillingSeconds(s_connected, r1, r2)

###
###


# static data we have for known carriers (definitive here, but could also be stored in db somewhere...).
# Required for each known carrier: code3, code5.  Optional: customer/terminator subclass to use.
# TODO just load this static config from customers (required values) & customers_options (optionals) tables.
carrierData = {

    'default': {
        'code3': '???',
        'code5': '?????',
        'billing_spec_r1': 6,
        'billing_spec_r2': 6,
        'ptgroup': 1,
    },

    'ryn': {
        'code3': 'ryn',
        'code5': '10112',
        'btn': '17320000000',
        'ptgroup': 10,
        'subclass.customer': ReynwoodCustomer,
    },

    'cnx': {
        'code3': 'cnx',
        'code5': '27434',
        'btn': '12120000000',
        'ptgroup': 10,
    },

    'qkc': {
        'code3': 'qkc',
        'code5': '10015',
        'btn': '8641139707285',
        'billing_spec_r1': 6,
        'billing_spec_r2': 6,
        'ptgroup': 5,
        'subclass.customer': QuickcomCustomer,
    },

    'lv3': {
        'code3': 'lv3',
        'code5': '17110',
        'subclass.terminator': Level3Terminator,
    },

    'vxr': { 'code3': 'vxr', 'code5': '20454', 'ptgroup': 9 },
    'a22': { 'code3': 'a22', 'code5': '39781', 'ptgroup': 9 },
    'vxb': { 'code3': 'vxb', 'code5': '33540', 'ptgroup': 8 },

    'wds': { 'code3': 'wds', 'code5': '11019', },
    'ctl': { 'code3': 'ctl', 'code5': '20228', },
    'erl': { 'code3': 'erl', 'code5': '24766', },
    'xox': { 'code3': 'xox', 'code5': '32003', },
    'imp': { 'code3': 'imp', 'code5': '13888', },


}


# }}}
###############################################################################



###############################################################################
## {{{ py.test tests


def setup_module(m):

    NetcallDB.TESTMODE = True

def test_sanity_check_carrierData():

    assert 'default' in carrierData

    d = carrierData['default']

    assert 'billing_spec_r1' in d
    assert d['billing_spec_r1'] >= 0

    assert 'billing_spec_r2' in d
    assert d['billing_spec_r2'] > 0

   
    dupes_c3 = set([])
    dupes_c5 = set([])
    for code3 in carrierData:
        if 'default'==code3: continue
        assert code3 not in dupes_c3
        assert len(code3) == 3
        dupes_c3.add(code3)
        d = carrierData[code3]
        assert 'code3' in d
        assert d['code3'] == code3
        assert 'code5' in d
        assert d['code5']
        assert d['code5'] not in dupes_c5
        dupes_c5.add(d['code5'])


def test_calc_bill_sec():

    code3_2_customers.clear()
    carrierData['tST'] = { 'code3': 'tST', 'code5': '99666', 'billing_spec_r1': 60, 'billing_spec_r2': 6}
    c = getCustomerObject('tST')
    assert c.calculateRoundedBillingSeconds(61) == 66
    assert c.calculateRoundedBillingSeconds(1) == 60
    assert c.calculateRoundedBillingSeconds(0) == 0

    code3_2_customers.clear()
    carrierData['tST'] = { 'code3': 'tST', 'code5': '99666', 'billing_spec_r1': 1, 'billing_spec_r2': 1}
    c = getCustomerObject('tST')
    assert c.calculateRoundedBillingSeconds(37) == 37

    code3_2_customers.clear()
    carrierData['tST'] = { 'code3': 'tST', 'code5': '99666', 'billing_spec_r1': 24, 'billing_spec_r2': 6}
    c = getCustomerObject('tST')
    assert c.calculateRoundedBillingSeconds(37) == 42

    code3_2_customers.clear()
    carrierData['tST'] = { 'code3': 'tST', 'code5': '99666', 'billing_spec_r1': 25, 'billing_spec_r2': 6}
    c = getCustomerObject('tST')
    assert c.calculateRoundedBillingSeconds(37) == 37

    code3_2_customers.clear()
    carrierData['tST'] = { 'code3': 'tST', 'code5': '99666', 'billing_spec_r1': 29, 'billing_spec_r2': 6}
    c = getCustomerObject('tST')
    assert c.calculateRoundedBillingSeconds(37) == 41

    code3_2_customers.clear()
    carrierData['tST'] = { 'code3': 'tST', 'code5': '99666', 'billing_spec_r1': 6, 'billing_spec_r2': 6}
    c = getCustomerObject('tST')
    assert c.calculateRoundedBillingSeconds(37) == 42

    code3_2_customers.clear()
    carrierData['tST'] = { 'code3': 'tST', 'code5': '99666', 'billing_spec_r1': 30, 'billing_spec_r2': 6}
    c = getCustomerObject('tST')
    assert c.calculateRoundedBillingSeconds(37) == 42

    code3_2_customers.clear()
    carrierData['tST'] = { 'code3': 'tST', 'code5': '99666', 'billing_spec_r1': 0, 'billing_spec_r2': 0}
    c = getCustomerObject('tST')
    assert c.calculateRoundedBillingSeconds(0) == 0


# test Quickcom 1/1 billing exception for Mexico numbers
def test_calc_bill_sec_qkc():

    code3_2_customers.clear()
    carrierData['qkc'] = { 'code3': 'qkc', 'code5': '10015', 'billing_spec_r1': 6, 'billing_spec_r2': 6, 'subclass.customer': QuickcomCustomer }
    c = getCustomerObject('qkc')

    cdr = nccdr.Cdr('cid12345@1.2.3.4', 'lkjsdmwerkjtag')
    cdr.bnum = '+15032223333'
    assert c.calculateRoundedBillingSeconds(37, cdr=cdr) == 42
    cdr.bnum = '+52111222333'
    assert c.calculateRoundedBillingSeconds(37, cdr=cdr) == 37
    assert c.calculateRoundedBillingSeconds(1, cdr=cdr) == 1



def erase_test_db():

    db = NetcallDB()
    assert db.testMode()

    ncc = db._ncc()
    cur = ncc.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("DELETE FROM customers_options")
    cur.execute("DELETE FROM customers")
    cur.execute("DELETE FROM price_tables")
    cur.execute("DELETE FROM price_tables_info")
    cur.execute("DELETE FROM pcaps")
    cur.execute("DELETE FROM callids2calls")
    cur.execute("DELETE FROM callids")
    cur.execute("DELETE FROM calls")
    cur.execute("DELETE FROM dr_rules_cp_archive")

    ncc.commit()



def test_callid_db_ops():

    erase_test_db()

    db = NetcallDB()
    ncc = db._ncc()
    cur = ncc.cursor(MySQLdb.cursors.DictCursor)

    callid = 'abc123zyx'

    cid = db._getIdFromCallId(cur, callid)
    assert not cid

    cid = db._getOrMakeIdFromCallId(callid)
    assert cid

    cid2 = db._getIdFromCallId(cur, callid)
    assert cid2 == cid

    cur.close()




tstPkt1 = '\xb1\xb6\x82RZ\x8d\t\x00\xa7\x05\x00\x00\xa7\x05\x00\x00E\x10\x05\xa7\x00\x00@\x00@\x11OEFf\x05\x1a\x08\x13\x92^\x13\xc4\x13\xc4\x05\x93\xe0\xabINVITE sip:18325477225@8.19.146.94 SIP/2.0\r\nRecord-Route: <sip:70.102.5.26;r2=on;lr>\r\nRecord-Route: <sip:10.0.6.100;r2=on;lr>\r\nRecord-Route: <sip:10.0.6.26;lr;ftag=3593286961-200529;did=2e3.6ae1c4a4>\r\nRecord-Route: <sip:10.0.6.100;r2=on;lr>\r\nRecord-Route: <sip:70.102.5.26;r2=on;lr>\r\nMax-Forwards: 66\r\nSession-Expires: 3600;refresher=uac\r\nSupported: timer, 100rel\r\nTo: 18325477225 <sip:18325477225@8.19.146.94>\r\nFrom: <sip:+16123513204@70.102.5.26:5060>;tag=3593286961-200529\r\nCall-ID: 435172188-3593286961-200522@LAX-MSC1S.mydomain.com\r\nCSeq: 1 INVITE\r\nAllow: INVITE, BYE, OPTIONS, CANCEL, ACK, REGISTER, NOTIFY, INFO, REFER, SUBSCRIBE, PRACK, UPDATE\r\nVia: SIP/2.0/UDP 70.102.5.26:5060;branch=z9hG4bK914c.18271474.0\r\nVia: SIP/2.0/UDP 10.0.6.26:5060;branch=z9hG4bK914c.c854af94.0\r\nVia: SIP/2.0/UDP 10.0.6.100:5060;branch=z9hG4bK914c.08271474.0\r\nVia: SIP/2.0/UDP 68.233.176.150:5060;branch=z9hG4bK6dfde233b9a2285b2281136034343e26\r\nContact: <sip:16123513204@68.233.176.150:5060>\r\nCall-Info: <sip:68.233.176.150>;method="NOTIFY;Event=telephone-event;Duration=1000"\r\nContent-Type: application/sdp\r\nContent-Length: 269\r\nUser-Agent: clogic/OpenSIPs/1.9\r\n\r\nv=0\r\no=LAX-MSC1S 1384298160 1384298160 IN IP4 68.233.176.150\r\ns=sip call\r\nc=IN IP4 68.233.176.151\r\nt=0 0\r\nm=audio 36766 RTP/AVP 0 8 96\r\na=rtpmap:0 PCMU/8000\r\na=rtpmap:8 PCMA/8000\r\na=rtpmap:96 telephone-event/8000\r\na=fmtp:96 0-15\r\na=sendrecv\r\na=silenceSupp:off - - - -\r\n'
tstPkt2 = 'L\xb6\x82R<N\x0e\x00\xdb\x03\x00\x00\xdb\x03\x00\x00E\x10\x03\xdb\x00\x00@\x00@\x11\xf6\x02Ff\x05\x1aD\xe9\xb0\x96\x13\xc4\x13\xc4\x03\xc7\xcf\xf1SIP/2.0 200 OK\r\nVia: SIP/2.0/UDP 68.233.176.150:5060;branch=z9hG4bKef4e2a66016a3beff320fa2182cbc3ce\r\nRecord-Route: <sip:sansay3003595027rdb43645@8.19.146.94:5060;lr;transport=udp>\r\nRecord-Route: <sip:70.102.5.26;r2=on;lr>\r\nRecord-Route: <sip:10.0.6.100;r2=on;lr>\r\nRecord-Route: <sip:10.0.6.26;lr;ftag=3593286849-267115;did=b22.afb61aa1>\r\nRecord-Route: <sip:10.0.6.100;r2=on;lr>\r\nRecord-Route: <sip:70.102.5.26;r2=on;lr>\r\nTo: 17136579764 <sip:17136579764@70.102.5.26>;tag=sansay3003595027rdb43645\r\nFrom: <sip:12246495568@68.233.176.150>;tag=3593286849-267115\r\nCall-ID: 435158536-3593286849-267108@LAX-MSC1S.mydomain.com\r\nCSeq: 1 INVITE\r\nContact: <sip:17136579764@8.19.146.94:5060>\r\nContent-Type: application/sdp\r\nContent-Length: 224\r\n\r\nv=0\r\no=Sansay-VSXi 188 1 IN IP4 8.19.146.94\r\ns=Session Controller\r\nc=IN IP4 8.19.146.148\r\nt=0 0\r\nm=audio 16868 RTP/AVP 0 96\r\na=rtpmap:0 PCMU/8000\r\na=rtpmap:96 telephone-event/8000\r\na=fmtp:96 0-15\r\na=sendrecv\r\na=maxptime:20\r\n'
tstPcap = tstPkt1 + tstPkt2

def test_pcaps_db_ops():

    erase_test_db()
    db = NetcallDB()

    callid1 = '435172188-3593286961-200522@LAX-MSC1S.mydomain.com'
    callid2 = '435158536-3593286849-267108@LAX-MSC1S.mydomain.com'

    p1 = db.getCaptureData(callid1)
    assert p1 is None

    db.writeCaptureData(callid1, 1000, 2000, 28777, tstPkt1)

    p1 = db.getCaptureData(callid1)
    assert p1[0] == 1000
    assert p1[1] == 2000
    assert p1[2] == 28777
    assert len(p1[3]) == len(tstPkt1)


def test_cdr_db_ops():

    erase_test_db()
    db = NetcallDB()

    # build a simple hand-crafted Call/Cdr object
    callid = 'lkjdsflknm234'
    call = nccdr.Call(callid)

    cdr = nccdr.Cdr(callid, 'tag123')

    cdr.t_start = datetime.strptime('2013-12-01 12:12:12', '%Y-%m-%d %H:%M:%S')
    cdr.t_confirm = datetime.strptime('2013-12-01 12:12:14', '%Y-%m-%d %H:%M:%S')
    cdr.t_end = datetime.strptime('2013-12-01 12:12:14', '%Y-%m-%d %H:%M:%S')
    cdr.s_setup = 2
    cdr.s_connected = 0
    cdr.s_connected_r = 0
    cdr.s_total = 2

    cdr.c_from = 'ryn'
    cdr.anum = '15032223333'
    cdr.anum2 = '15032223333'
    cdr.a_country = 'US'
    cdr.bnum = '12123443434'
    cdr.b_lrn = '12125452233'
    cdr.b_jtype = 'D'
    cdr.xstate = 'inter'

    cdr.call_price = 0.0
    cdr.ruleid = 666
    cdr.cp_node = ['g23', 'g44']


    # just for this test we need a dr_rules_cp_archive row

    ncc = db._ncc()
    cur = ncc.cursor(MySQLdb.cursors.DictCursor)
    sql = 'INSERT INTO dr_rules_cp_archive (ruleid, groupid, prefix, timerec, priority, routeid, gwlist, attrs, description) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)'
    cur.execute(sql, (666, '8', '503593', '', 0, None, '#ctl,#lv3,#c99', None, ''))

    call.f_cdr = cdr

    db.writeCallRecord(call)

    assert True


## }}}
###############################################################################




if __name__ == '__main__':

    pass
