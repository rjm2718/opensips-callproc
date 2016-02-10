#!/usr/bin/python

## NOTE: this program superseded by nccdr.py

# 2013-06-15 Ryan Mitchell <rjm@tcl.net>
#
# This script will be run automatically from cron; uses the nccdr/netcall modules to process cdrs
# for a given date range and records cdrs into netcall.calls table (other scripts can then query
# that table and create FTP files, etc).

# > read cmd line args, process acc table, etc.

# * final answer on date range: given a date range, we are interested in calls that have terminated with the
#    range.  great, because we can do an easier query and not miss any long duration (or long setup) calls; the
#    only thing you do is if you find an incomplete call, go back to an earlier time to search for the starting
#    transactions.  Forget about Redis new Call-Id queue ... nice idea but it's adding unecessary complexity.


import sys, time, os, getopt, re
from datetime import datetime
from datetime import timedelta
from collections import Counter


import netcall, nccdr


# default parameters overrid by command line
p_dfrom = None
p_dto   = None
p_src_id = None   # 'vxb'
p_limit = -1





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
    print " --dfrom   query acc table for calls that start from date"
    print " --dto     query acc table for calls that start earlier than date"
    print " --src_id  limit calls processed to this source (inbound customer) id"
    print " --limit   limit calls processed"
    print " --summary print only statistics summary of calls (mutex with csv option)"
    sys.exit(-1)



if __name__ == '__main__':

    csv = False
    summ = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h', ['csv', 'dfrom=', 'dto=', 'limit=', 'src_id=', 'help', 'summary'])

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
            if opt=='--summary':
                summ=True
            if opt=='--help' or opt=='-h':
                cmdHelp()

    except Exception as e:
        cmdHelp(e)


    if ftp:
        csv = True

    if summ:
        csv = False
        ftp = False



    if not p_dto:
        p_dto = datetime.now()
    if not p_dfrom:
        p_dfrom = p_dto - timedelta(hours=1)

    print 'date range ['+str(p_dfrom)+","+str(p_dto)+"]"

    callids_ = load_callids(dfrom=p_dfrom, dto=p_dto, src_id=p_src_id, limit=p_limit)
    if not callids_:
        print >> sys.stderr, 'no call-id values found in database, nothing to do...'
        sys.exit(0)


    # pass in dfrom to catch corner case: call-id found within date range, but actual start of call lies outside
    (calls, incompletes) = process_cdrs(callids=callids_, dfrom=p_dfrom)




    print len(calls),'complete'
    print len(incompletes),'incomplete (possibly active current calls)'

        
    cdrs_r = []  # to record
    cdrs_e = []  # failed branches
    for call in calls:
        cdrs_r.append(call.getFCdr())
        cdrs_e.extend(call.getErrCdrs())

    cdrs_r.sort(key=lambda cdr: cdr.t_start)
    cdrs_e.sort(key=lambda cdr: cdr.t_start)


    incs_r = []  # to record
    incs_e = []  # failed branches
    for call in incompletes:
        fcdr1 = call.getFCdr()
        if fcdr1: incs_r.append(fcdr1)
        incs_e.extend(call.getErrCdrs())

    incs_r.sort(key=lambda cdr: cdr.t_start)
    incs_e.sort(key=lambda cdr: cdr.t_start)
    print 'incs_r.len=',len(incs_r)
    print 'incs_e.len=',len(incs_e)

    if csv:

        headerI = csvHeaders(Cdr.reportFieldsInternal)
        headerC = csvHeaders(Cdr.reportFieldsCustomer)

        # ftp plan: create multiple output files,
        #  1. csv output for each customer (src_id), copy to customer's ftp directory
        #  2. csv output for internal use: all calls with routing & pricing info
        #  3. csv output for internal use: failed routes
        #  4. for internal use: asr,ccr report
        if ftp:

            now = datetime.now() # make a reasonable prefix please
            fpfx = 'cdrs'+now.strftime('%Y.%m.%d.%H.%M.%S')

            # 3
            if len(cdrs_e) > 0:
                fn = fpfx+'.failed.csv'
                f = open(fn, 'w')
                f.write(headerI+'\n')
                for cdr in cdrs_e:
                    f.write(cdr.csvExport(Cdr.reportFieldsInternal)+'\n')
                f.close()
                ftpul(fn, '.')

            # 2
            fn = fpfx+'.csv'
            f = open(fn, 'w')
            f.write(headerI+'\n')
            for cdr in cdrs_r:
                f.write(cdr.csvExport(Cdr.reportFieldsInternal)+'\n')
            f.close()
            ftpul(fn, '.')

            # 1
            srcs = {}
            for cdr in cdrs_r:
                if cdr.c_from not in srcs:
                    srcs[cdr.c_from] = 1
            for src in srcs.keys():
                print 'writing cdrs for', src
                fn = fpfx+'.'+src+'.csv'
                f = open(fn, 'w')
                f.write(headerC+'\n')
                for cdr in cdrs_r:
                    if cdr.c_from == src:
                        f.write(cdr.csvExport(Cdr.reportFieldsCustomer)+'\n')
                f.close()
                ftpul(fn, 'customers/'+src)


        else:

            print headerI
            for cdr in cdrs_r:
                print cdr.csvExport(Cdr.reportFieldsInternal)

    else: # if not csv

        if not summ:

            print '\ncdrs to record:'
            for cdr in cdrs_r:
                print '',cdr

            print '\nfailed routes (part of complete Call):'
            for cdr in cdrs_e:
                print '',cdr

            print '\nINC cdrs to record:'
            for cdr in incs_r:
                print '',cdr

            print '\nINC failed routes:'
            for cdr in incs_e:
                print '',cdr

        else: # summary

            ncalls_conn = 0

            csecT = 0.0
            for cdr in cdrs_r:
                if cdr.s_connected > 0:
                    csecT += cdr.s_connected
                    ncalls_conn += 1

            print 'total connected minutes = %.1f' % (csecT/60.0)
            print '%d connected calls out of %d (%.1f%%)' % (ncalls_conn, len(calls), 100.0*float(ncalls_conn)/len(calls))

            #print 'completes:'
            #csecT2 = 0.0
            #for icall in calls:
            #    csecT2 += icall.get_current_duration_seconds()
            #print 'csecT2=%.1f' % (csecT2/60.0)

            print '\nincompletes (cid, duration minutes) longer than 30 min:'
            for icall in incompletes:
                if icall.get_current_duration_seconds() > 1800:
                    ds = '%.1f' % (icall.get_current_duration_seconds()/60.0)
                    print '',icall.cid,',',ds

