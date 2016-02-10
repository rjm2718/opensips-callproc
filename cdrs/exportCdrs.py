#!/usr/bin/python

# output module for netcall.calls Cdr data


import sys, time, os, getopt
from datetime import datetime
from datetime import timedelta
import logging as log

import netcall



# formatting helper functions
def df1(d):
    if d: return d.strftime("%Y-%m-%d %H:%M:%S")
    else: return '        '

def n2s(n):
    if n: return str(n)
    else: return '0'

def qstr(o):
    if not o:
        return ''
    else:
        return "'"+str(o)+"'"

def f4str(f): # fmt 4 dec places
    if not f: return ''
    else: return '%.4f' % (f)

def Y():  # marker to use field and apply formatting function from 'all' column
    pass

def n():  # skip this field marker
    pass


# table of fields, and mapping functions for each output module
# (field: name of key in dict returned by getCdrs() methods...)

fmap = [
    # description         |  field         |    all     |   RDSG  |   customer 
    ['Call-Id',              'callid',          qstr,       Y,        Y     ],
    ['start timestamp',      't_start',         df1,        Y,        Y     ],
    ['conn timestamp',       't_confirm',       df1,        Y,        Y     ],
    ['end timestamp',        't_end',           df1,        Y,        Y     ],
    ['setup seconds',        's_setup',         n2s,        Y,        Y     ],
    ['conn seconds',         's_connected',     n2s,        Y,        Y     ],
    ['conn seconds (r)',     's_connected_r',   n2s,        Y,        Y     ],
    ['total seconds',        's_total',         n2s,        Y,        Y     ],
    ['from',                 'c_from',          qstr,       n,        n     ],
    ['from code',            'c_from5',         qstr,       Y,        n     ],
    ['to',                   'c_to',            qstr,       n,        n     ],
    ['to code',              'c_to5',           qstr,       Y,        n     ],
    ['final response code',  'rspcode',         n2s,        n,        n     ],
    ['final status',         'fstatus',         qstr,       Y,        Y     ],
    ['anum caller-id',       'anum',            qstr,       Y,        Y     ],
    ['anum caller-id 2',     'anum2',           qstr,       Y,        Y     ],
    ['origination type',     'a_jtype',         qstr,       Y,        Y     ],
    ['anum country',         'a_country',       qstr,       n,        n     ],
    ['anum state',           'a_state',         qstr,       Y,        Y     ],
    ['anum LATA',            'a_lata',          qstr,       Y,        Y     ],
    ['anum OCN',             'a_ocn',           qstr,       Y,        Y     ],
    ['bnum called num',      'bnum',            qstr,       Y,        Y     ],
    ['bnum LRN',             'b_lrn',           qstr,       Y,        Y     ],
    ['destination type',     'b_jtype',         qstr,       n,        n     ],
    ['bnum country',         'b_country',       qstr,       Y,        n     ],
    ['bnum state',           'b_state',         qstr,       Y,        Y     ],
    ['bnum LATA',            'b_lata',          qstr,       Y,        Y     ],
    ['bnum OCN',             'b_ocn',           qstr,       Y,        Y     ],
    ['jurisdiction',         'xstate',          qstr,       Y,        Y     ],
    ['lcr rule id',          'ruleid',          n2s,        Y,        n     ],
    ['lcr pattern',          'rtpatt',          qstr,       n,        n     ],
    ['route table',          'rtgroup',         n2s,        Y,        n     ],
    ['price table',          'ptgroup',         n2s,        Y,        n     ],
    ['route minute price',   'mprice',          f4str,      Y,        Y     ],
    ['call price',           'call_price',      f4str,      Y,        Y     ],
    ['cp nodes',             'cp_nodes',        qstr,       n,        n     ],
]


# internal output -- all fields
# RDSG (billing system) output
# customer output


#################################################################################

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
    print ' --csv     use csv formatted output'
    print ' --ftp     make multiple output files for clients (implies --csv)'
    print " --dfrom   query acc table for calls that start from date"
    print " --dto     query acc table for calls that start earlier than date"
    print " --src_id  limit calls processed to this source (inbound customer) id"
    print " --limit   limit calls processed"
    sys.exit(-1)

if __name__ == '__main__':

    csv = False
    ftp = False

    p_dfrom = None
    p_dto   = None
    p_src_id = None   # 'vxb'
    p_limit = -1
    

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h', ['csv', 'ftp', 'dfrom=', 'dto=', 'limit=', 'src_id=', 'help'])

    except getopt.GetoptError as e:
        cmdHelp(e)

    try:

        for opt, arg in opts:
            if opt=='--csv':
                csv = True
            if opt=='--ftp':
                ftp = True
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

    except Exception as e:
        cmdHelp(e)



    if not p_dto:
        p_dto = datetime.now()
    if not p_dfrom:
        p_dfrom = p_dto - timedelta(hours=1)



    db = netcall.NetcallDB()

    calls = db.getCallRecords(p_dfrom, p_dto, p_limit)

    # sort by t_end
    calls.sort(key=lambda call: call['t_end']

#    for c in calls:
#        print c['callid'], c['call_price']



    # RDSG for start

    colname = []
    cfields = []
    cffuncs = []

    for f in fmap:

        if f[3] != Y:
            continue

        colname.append(f[0])
        cfields.append(f[1])
        cffuncs.append(f[2])

    print ','.join(colname)

    for c in calls:

        d = []
        for nf in zip(cfields, cffuncs):
            v = c[nf[0]] # field value
            m = nf[1] # map function
            d.append( m(v) )

        print ','.join(d)
