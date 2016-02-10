#!/usr/bin/python

# redis/pcap functions...
#
# 2013-11-10 Ryan Mitchell <rjm@tcl.net>
#
# take packets from sipcap:input queue and append them to the pcap file
# blob for the cdr with matching Call-Id in the netcall.cdrs table.
#
# TODO
#
# - skip pcap file header, save a little space in db
# - store date range of packets in pcaps table
# - ip address stored as int(4) of source of earliest packet
# - when updating, sort packets by timestamp
#

import sys, time, os, getopt, re, struct
from datetime import datetime
from datetime import timedelta
from collections import Counter

import redis
import netcall


REDISHOST = 'a26'
REDISCQI = 'sipcap:input' # 'sipcap:input'
REDISCQP = 'sipcap:processing' # 'sipcap:processing'



p_limit = None
qproc=False


db = None
def getDB():

    global db

    if not db:
        db = netcall.NetcallDB()
    
    return db

redSrv = None
def getRDS():

    global redSrv

    if not redSrv:
        redSrv = redis.Redis(host=REDISHOST, port=6379, db=0)

    return redSrv


def redis_get_iqsize():

    return getRDS().llen(REDISCQI)

def redis_get_pcap_packet():

    return getRDS().rpoplpush(REDISCQI, REDISCQP)

def redis_commit_pcap_write(pkt):

    c = getRDS().lrem(REDISCQP, pkt, 0)

    if c > 1:
        print >> sys.stderr, ' - warn: pkt lrem found duplicates; c=', c
    if c == 0:
        print >> sys.stderr, ' - error: pkt lrem failed, pkt not found; c=', c




def make_pcap_file_header():

    # struct pcap_file_header
    return struct.pack('IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 101)


# converts integer (4 bytes in network order) to ipv4 string
def ip2str(ip):

    return '%d.%d.%d.%d' % (ip>>24 & 0xff, ip>>16 & 0xff, ip>>8 & 0xff, ip & 0xff)

# returns (timestamp, num bytes of packet, lenth of header + packet, src_ip, dst_ip)
def decode_pcap_and_ip_packet_header(pkt):

    if pkt and len(pkt) >= 36:

        (ts_sec, ts_usec, incl_len, orig_len) = struct.unpack('iiII', pkt[0:16])

        iphfs = struct.unpack('!IIIII', pkt[16:36]) # network byte order
        src_ip = iphfs[3]
        dst_ip = iphfs[4]

        return (ts_sec + ts_usec/1.0e6, incl_len, incl_len + 16, src_ip, dst_ip)

    return None



def pcaplist2blob(pkts):

    if not pkts or len(pkts)==0:
        return '';

    blob = ''
    for p in pkts:
        blob += p

    return blob


def pcaps2list(pcap_data):

    pkts = []

    if not pcap_data or len(pcap_data)==0:
        return pkts

    # 1st packet
    pkt = pcap_data

    while pkt:
        i = decode_pcap_and_ip_packet_header(pkt)
        if i and i[1] > 0:
            pkts.append(pkt[0 : i[2]])
            pkt = pkt[ i[2] : ]
        else:
            pkt = None

    return pkts



# parse pcap binary data and count number of packets found
def count_pcap_packets(pcap_data):

    return len(pcaps2list(pcap_data))





re_cid = re.compile(b'^Call-ID: (.+?)\r\n', re.DOTALL|re.MULTILINE|re.IGNORECASE)

def parse_callid(pkt):

    if not pkt:
        return None

    m = re_cid.search(pkt)

    if m:
        return m.group(1)

    return None



def write_new_pcap_file(callid, outfile):

    r = getDB().getCaptureData(callid)

    if not r:

        print "no pcap found for Call-Id", callid
        return

    pcap_blob = r[3]

    of = open(outfile, 'w')
    of.write(make_pcap_file_header() + pcap_blob)
    of.close()

    print 'wrote pcap file', outfile, 'with',count_pcap_packets(pcap_blob),'packets'


############################################################################

## {{{ py.test code

tstPkt1 = '\xb1\xb6\x82RZ\x8d\t\x00\xa7\x05\x00\x00\xa7\x05\x00\x00E\x10\x05\xa7\x00\x00@\x00@\x11OEFf\x05\x1a\x08\x13\x92^\x13\xc4\x13\xc4\x05\x93\xe0\xabINVITE sip:18325477225@8.19.146.94 SIP/2.0\r\nRecord-Route: <sip:70.102.5.26;r2=on;lr>\r\nRecord-Route: <sip:10.0.6.100;r2=on;lr>\r\nRecord-Route: <sip:10.0.6.26;lr;ftag=3593286961-200529;did=2e3.6ae1c4a4>\r\nRecord-Route: <sip:10.0.6.100;r2=on;lr>\r\nRecord-Route: <sip:70.102.5.26;r2=on;lr>\r\nMax-Forwards: 66\r\nSession-Expires: 3600;refresher=uac\r\nSupported: timer, 100rel\r\nTo: 18325477225 <sip:18325477225@8.19.146.94>\r\nFrom: <sip:+16123513204@70.102.5.26:5060>;tag=3593286961-200529\r\nCall-ID: 435172188-3593286961-200522@LAX-MSC1S.mydomain.com\r\nCSeq: 1 INVITE\r\nAllow: INVITE, BYE, OPTIONS, CANCEL, ACK, REGISTER, NOTIFY, INFO, REFER, SUBSCRIBE, PRACK, UPDATE\r\nVia: SIP/2.0/UDP 70.102.5.26:5060;branch=z9hG4bK914c.18271474.0\r\nVia: SIP/2.0/UDP 10.0.6.26:5060;branch=z9hG4bK914c.c854af94.0\r\nVia: SIP/2.0/UDP 10.0.6.100:5060;branch=z9hG4bK914c.08271474.0\r\nVia: SIP/2.0/UDP 68.233.176.150:5060;branch=z9hG4bK6dfde233b9a2285b2281136034343e26\r\nContact: <sip:16123513204@68.233.176.150:5060>\r\nCall-Info: <sip:68.233.176.150>;method="NOTIFY;Event=telephone-event;Duration=1000"\r\nContent-Type: application/sdp\r\nContent-Length: 269\r\nUser-Agent: clogic/OpenSIPs/1.9\r\n\r\nv=0\r\no=LAX-MSC1S 1384298160 1384298160 IN IP4 68.233.176.150\r\ns=sip call\r\nc=IN IP4 68.233.176.151\r\nt=0 0\r\nm=audio 36766 RTP/AVP 0 8 96\r\na=rtpmap:0 PCMU/8000\r\na=rtpmap:8 PCMA/8000\r\na=rtpmap:96 telephone-event/8000\r\na=fmtp:96 0-15\r\na=sendrecv\r\na=silenceSupp:off - - - -\r\n'
tstPkt2 = 'L\xb6\x82R<N\x0e\x00\xdb\x03\x00\x00\xdb\x03\x00\x00E\x10\x03\xdb\x00\x00@\x00@\x11\xf6\x02Ff\x05\x1aD\xe9\xb0\x96\x13\xc4\x13\xc4\x03\xc7\xcf\xf1SIP/2.0 200 OK\r\nVia: SIP/2.0/UDP 68.233.176.150:5060;branch=z9hG4bKef4e2a66016a3beff320fa2182cbc3ce\r\nRecord-Route: <sip:sansay3003595027rdb43645@8.19.146.94:5060;lr;transport=udp>\r\nRecord-Route: <sip:70.102.5.26;r2=on;lr>\r\nRecord-Route: <sip:10.0.6.100;r2=on;lr>\r\nRecord-Route: <sip:10.0.6.26;lr;ftag=3593286849-267115;did=b22.afb61aa1>\r\nRecord-Route: <sip:10.0.6.100;r2=on;lr>\r\nRecord-Route: <sip:70.102.5.26;r2=on;lr>\r\nTo: 17136579764 <sip:17136579764@70.102.5.26>;tag=sansay3003595027rdb43645\r\nFrom: <sip:12246495568@68.233.176.150>;tag=3593286849-267115\r\nCall-ID: 435158536-3593286849-267108@LAX-MSC1S.mydomain.com\r\nCSeq: 1 INVITE\r\nContact: <sip:17136579764@8.19.146.94:5060>\r\nContent-Type: application/sdp\r\nContent-Length: 224\r\n\r\nv=0\r\no=Sansay-VSXi 188 1 IN IP4 8.19.146.94\r\ns=Session Controller\r\nc=IN IP4 8.19.146.148\r\nt=0 0\r\nm=audio 16868 RTP/AVP 0 96\r\na=rtpmap:0 PCMU/8000\r\na=rtpmap:96 telephone-event/8000\r\na=fmtp:96 0-15\r\na=sendrecv\r\na=maxptime:20\r\n'
tstPcap = tstPkt1 + tstPkt2

def test_run_test1():

    assert(count_pcap_packets(None)==0)
    assert(count_pcap_packets(tstPkt1)==1)
    assert(count_pcap_packets(tstPcap)==2)

def test_run_test2():

    assert(parse_callid(None)==None)
    assert(parse_callid('')==None)
    assert(parse_callid('lkjsdf')==None)

    callid = parse_callid(tstPkt1)
    assert(callid=='435172188-3593286961-200522@LAX-MSC1S.mydomain.com')
    callid = parse_callid(tstPkt2)
    assert(callid=='435158536-3593286849-267108@LAX-MSC1S.mydomain.com')

def test_run_test3():

    (ts, plen, pcplen, src_ip, dst_ip) = decode_pcap_and_ip_packet_header(tstPkt1)

    assert(ip2str(src_ip)=='70.102.5.26')
    assert(ip2str(dst_ip)=='8.19.146.94')


def test_list_unlist():

    blob = tstPcap

    pkts = pcaps2list(blob)
    assert len(pkts)==2

    blob2 = pcaplist2blob(pkts)
    assert blob == blob2

## }}}


## main #######################################################################

def cmdHelp(e=None):
    if e:
        print '***'
        print ' error=',e
        print '***'

    print ''
    print 'usage:'
    print ''
    print ' ',sys.argv[0],'[options]'
    print ''
    print '   -h | --help'
    print "   --qproc   get packets from sipcap:input, put into netcall.pcaps table"
    print "   --limit   limit packets taken from queue"
    print ''
    print ' ',sys.argv[0],'call-id outputfile'
    print ''
    print '   Creates a new pcap file from database for the given call-id, if found'
    print ''
    sys.exit(-1)


if __name__ == '__main__':

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h', ['qproc', 'limit=', 'help'])

    except getopt.GetoptError as e:
        cmdHelp(e)

    if len(opts)==0 and len(args)==0:
        print '\nwhat do you want me to do?'
        cmdHelp()

    try:

        for opt, arg in opts:
            if len(args) > 0: # if any options given, then no further args allowed
                cmdHelp("conflicting options (none allowed if further arguments given)")
            if opt=='--limit':
                p_limit = int(arg)
            if opt=='--qproc':
                qproc=True
            if opt=='--help' or opt=='-h':
                cmdHelp()

    except Exception as e:
        cmdHelp(e)


    
    if len(args) > 0:

        if len(args) != 2:
            cmdHelp("wrong number of arguments!")

        else: 
            write_new_pcap_file(args[0], args[1])
            sys.exit(0)


    pcount = 0

    t0 = time.time()

    while True:

        if p_limit is not None:
            if p_limit <= 0:
                break
            else:
                p_limit -= 1


        if not pcount%1000:
            iqs = redis_get_iqsize()
            print pcount ,',', iqs

        pkt = redis_get_pcap_packet()

        pkt0 = pkt  # need unmodified pkt for commit later

        if not pkt:
            print 'no packets (queue empty)'
            break

        callid = parse_callid(pkt)

        if not callid:
            print 'severe: no call-id value found in packet (will leave in processing queue)'
            continue


        r = getDB().getCaptureData(callid)

        pcap_blob = None
        if r:
            pcap_blob = r[3]
        else:
            pcap_blob = '' # new call-id, 1st packet


        pcap_blob += pkt

        # sort, update extracted fields as needed
        pkts = pcaps2list(pcap_blob)

        # sort by timestamp
        pkts.sort(key=lambda pkt: decode_pcap_and_ip_packet_header(pkt)[0])


        (ts1, plen1, pcplen1, src_ip1, dst_ip1) = decode_pcap_and_ip_packet_header(pkts[0]) # earliest packet

        ts2 = ts1
        if len(pkts) > 1:
            (ts2, plen2, pcplen2, src_ip2, dst_ip2) = decode_pcap_and_ip_packet_header(pkts[-1]) # latest packet


        pcap_blob = pcaplist2blob(pkts) # blob is now in timestamp sorted order

        getDB().writeCaptureData(callid, ts1, ts2, src_ip1, pcap_blob)

        #print ':  ',','.join(map(str, (ts1, ts2, plen1, pcplen1, src_ip1, dst_ip1)))
        #print 'saved pcap with',count_pcap_packets(pcap_blob),'packets for callid', callid

        redis_commit_pcap_write(pkt0)

        pcount += 1


    t1 = time.time()

    print '\nprocessed %d packets in %.1f seconds' % (pcount, t1-t0)
