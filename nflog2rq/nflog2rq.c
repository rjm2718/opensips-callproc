/* Read SIP packets from Netlink NFLOG setup, create a pcap formatted encapsulation, and
 * shove into the Redis 'sipcap:input' queue.  (Other programs will drain the queue of
 * packets for processing and filing).  This program does only very basic filtering: insert
 * into Redis queue only if the packet roughly looks like a SIP packet and we can find
 * a Call-Id value (skip OPTIONS, REGISTER, and other uninteresting non- call related requests).
 *
 * This approach was chosen so we get the packets after iptables has had a chance to filter
 * out whatever firehouse of crap we'd otherwise see using tcpdump, etc.
 *
 * Use the equivalent rules in iptables:
 *
 *  -A OUTPUT -m udp -p udp --sport 5060 -j NFLOG --nflog-group 10
 *  -A OUTPUT -m tcp -p tcp --sport 5060 -j NFLOG --nflog-group 10
 *  -A TFW -m udp -p udp --dport 5060 -j NFLOG --nflog-group 10
 *  -A TFW -m tcp -p tcp --dport 5060 -j NFLOG --nflog-group 10
 *
 * Compiling:
 *  Was a bitch with incompatible(?) shared libs on different versions of Ubuntu, so I got the sources
 *  for and compiled libnfnetlink-1.0.1 and nflog-bindings-0.2, and used the reultant object
 *  files to link directly with this program:
 *   `gcc -O2 nflog2rq.c -I/usr/local/include -lhiredis libnfnetlink.o libnetfilter_log.o -o nflog2rq`
 *
 * TODO
 *  - what happens to Netlink packets when this program isn't running or is blocked?  where do we
 *    see Linux queue stats?
 *  - Redis HA
 *  - finish investigation into fragmented packet reassembly; supposedly if the conntrack module is in use
 *    packets should be reassembled before they reach iptables INPUT chain ... but I'm not entirely sure.
 *  - ipv6?
 *  - would it be better to have implemented this as a OpenSips module?
 *
 * (c) 2013 Telecom Logic, LLC. <rjm@tcl.net>
 * $Id:$
 *
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <signal.h>
#include <ctype.h>
#include <netinet/in.h>
#include <sys/time.h>

#include <libnetfilter_log/libnetfilter_log.h>
#include <hiredis/hiredis.h>


#define MIN(a,b) (((a)<(b))?(a):(b))
#define MAX(a,b) (((a)>(b))?(a):(b))



#define NFLOG_GROUP 10

#define redis_server "a26"

static char* exclude_sip_methods[] = {"REGISTER", "OPTIONS", "NOTIFY", "SUBSCRIBE"};


static unsigned char pkbuf[8192]; // buffer for nflog received packet
static size_t pkbuf_len;

//static unsigned char *sippacket; // pointer within pkbuf to start of sip packet (or whatever garbage in app layer of protocol)
//static size_t sippacket_len;

static int fdx; // file desc for netlink socket

static redisContext *rctx;
static int redis_errs = 0; // connect and query error count

static int pcount = 0; // packets received
static int scount = 0; // interesting sip packets received
static int rcount = 0; // packets successfully injecting into redis queue

static int keepRunning = 1;



// {{{ pcap functions


// not used here, the global/file header for writing pcap format
struct pcap_file_header {
	u_int32_t magic;
	u_short version_major;
	u_short version_minor;
	int32_t thiszone;       /* GMT to local correction */
	u_int32_t sigfigs;      /* accuracy of timestamps */
	u_int32_t snaplen;      /* max length of captured packets, in octets */
	u_int32_t network;      /* data link type (LINKTYPE_*) */
};

// header for each packet
struct pcap_frame {
	int32_t ts_sec;
	int32_t ts_usec;
	u_int32_t incl_len;     /* number of octets of packet saved in file */
	u_int32_t orig_len;    /* actual length of packet */
};

// extract nflog packet and copy into pkbuf with proper pcap header; return total length including all headers
void make_pcap_pkt(struct nflog_data *ldata)
{
	char *payload;
	int payload_len = nflog_get_payload(ldata, &payload);

    struct timeval tv;
    // nflog_get_timestamp(ldata, &tv); // not updated for every packet ?!?
    gettimeofday(&tv, NULL);

    struct pcap_frame *pf = (struct pcap_frame *)pkbuf;
    pf->ts_sec = tv.tv_sec;
    pf->ts_usec = tv.tv_usec;
    pf->incl_len = payload_len;
    pf->orig_len = payload_len;

    unsigned char *pp = pkbuf + sizeof(struct pcap_frame);

    memcpy(pp, payload, payload_len);

	pkbuf_len = sizeof(struct pcap_frame) + payload_len;
}


// when using nflog as we are, what we get is a raw ip packet, with no other layers encapsuated,
// so we must specify raw ip type 101.
int write_pcap_global_header()
{
    struct pcap_file_header h;

    h.magic = 0xa1b2c3d4;
    h.version_major = 2;
    h.version_minor = 4;
    h.thiszone =0;
    h.sigfigs = 0;
    h.snaplen = 65535;
    h.network = 101;   // 1==ethernet, 101==raw ip ... ?

    //if (write(pcfd, &h, sizeof(h)) != sizeof(h)) return -1;

    return 0;
}

// }}}


// {{{ sip parsing/filting functions


// uninteresting if no Call-ID value or CSeq method is REGISTER/NOTIFY/OPTIONS (note because ACK
// is its own pseudo transaction, we'll have to accept ACKs having to do with some uninteresting
// requests...).  Beware of SIP compact headers use: Call-ID > i
int sip_packet_is_interesting() {

    int i,n;

    size_t pcap_frame_size = sizeof(struct pcap_frame);

    // brain-dead parsing: just go through entire packet buffer looking for strings, don't try to
    // grokk the ip, transport, or sip packet.  per sip spec lines break on crlf 0d0a

    unsigned char* pp = pkbuf + pcap_frame_size;
    unsigned char* px = pp + pkbuf_len - 2; // stop parsing before here

    int has_cid = 0;
    int has_interesting_method = 1;

    int state = 0; // 0=? 1=cr, 2=crlf
    int state_n = 0;
    while (pp < px) {
        state_n = state;
        switch (state) {

            case 0:
                if (*pp==0x0D) state_n=1;
                break;

            case 1:
                if (*pp==0x0A) state_n=2;
                else state_n=0;
                break;

            case 2: // we're at begining of line in sip packet (probably)
                state_n = 0;
                if (strncasecmp(pp, "Call-ID: ", MIN(9, (px-pp)))==0 ||
                    strncasecmp(pp, "i:", MIN(2, (px-pp)))==0) {
                    has_cid = 1;
                    break;
                }
                if (strncasecmp(pp, "CSeq: ", MIN(6, (px-pp)))==0) {
                    pp += 6;
                    if (pp >= px) break;
                    unsigned char* cr = strchr(pp, 0x0D);
                    if (cr) { // true if this line has a crlf (as opposed to eof or other unexpected garbage)
                        while ((cr-pp) > 0 && !isalpha(*pp)) pp++; // advance pp to next alpha char
                        size_t l2 = cr - pp;
                        if (l2 > 0 && l2 < 64 && isalpha(*pp)) {
                            char method[64];
                            strncpy(method, pp, l2);
                            method[l2] = 0;
                            for (i=0; i<strlen(method); i++) { // this deals with any training spaces or garbage after method string
                                if (!isalpha(method[i])) {
                                    method[i] = 0;
                                    break;
                                }
                            }
                            //printf("method=[%s]\n", method);
                            n = sizeof(exclude_sip_methods)/sizeof(exclude_sip_methods[0]);
                            for (i=0; i<n; i++) {
                                if (strncasecmp(method, exclude_sip_methods[i], l2)==0) has_interesting_method = 0;
                            }
                        }
                    }
                }
                break;

        }
        state = state_n;
        pp++;
    }

    return has_interesting_method && has_cid;
}

// }}}


// {{{ redis connect/disconnect functions

void redis_connect()
{
    struct timeval timeout = { 1, 900000 }; // 1.9 seconds
    rctx = redisConnectWithTimeout(redis_server, 6379, timeout);

    if (! rctx) printf("\nRedis connection error: no memory?\n");

    else if (rctx->err) {
        printf("\nRedis connection error: %s\n", rctx->errstr);
        redisFree(rctx);
        rctx = NULL;
    }

    printf("connected to Redis on host %s\n", redis_server);
}

void redis_disconnect()
{
    if (rctx) {
        redisFree(rctx);
        rctx = NULL;
    }
}

int redis_is_pingable()
{
    if (! rctx) return 0;

    redisReply *r = redisCommand(rctx, "PING");
    if (! r) return 0;

    //printf("ping => %s\n", r->str);
    
    int sc = strncasecmp(r->str, "PONG", 4);

    freeReplyObject(r);

    if (sc==0) return 1;

    else return 0;
}


// will wait forever for a good redis connection
void redis_reconnect_and_check()
{
    redis_disconnect();

    int cerrs=0;
    int ssec=2;

    while (keepRunning) {

        redis_connect();

        if (redis_is_pingable()) break;
        else cerrs++;
        
        redis_disconnect();

        ssec = (int)((cerrs + redis_errs)/2.0);
        if (ssec > 6) ssec = 6;
        if (ssec < 1) ssec = 1;

        sleep(ssec);
    }
}

// }}}


void redis_queue_pkbuf()
{
    redisReply *r = redisCommand(rctx, "RPUSH sipcap:input %b", pkbuf, pkbuf_len);

    if (r) {
        rcount++;
        freeReplyObject(r);
        char cr = 0x0d;
        printf("%d%c", rcount, cr);
        fflush(stdout);
    }

    else {
        printf("\nredisCommand error: %s\n", rctx->errstr);
        redis_errs++;
        // "Once an error is returned the context cannot be reused and you should set up a new connection."
        redis_reconnect_and_check();
    }
}


int cb(struct nflog_g_handle *gh, struct nfgenmsg *nfmsg, struct nflog_data *nfa, void *data)
{
    pcount++;

    make_pcap_pkt(nfa);

    if (sip_packet_is_interesting()) {
        scount++;
        redis_queue_pkbuf();
    }

	return 0;
}


void intHandler(int n) {
    printf("\nshutting down...\n");
    keepRunning = 0;
    close(fdx);
}

int main(int argc, char **argv)
{
	struct nflog_handle *h;
	struct nflog_g_handle *qh;
	struct nflog_g_handle *qh100;
	int rv;
	char buf[4096];

    //pcfd = open("nx.pcap", O_CREAT|O_WRONLY|O_TRUNC, 0644);
    //if (write_pcap_global_header()) {
    //    printf("failed pcap write\n");
    //    exit(-1);
    //}

    signal(SIGINT, intHandler);
    //struct sigaction sa;
    //sa.sa_handler = intHandler;
    //sigemptyset(&sa.sa_mask);
    //sa.sa_flags = SA_RESTART; /* Restart functions if interrupted by handler */
    //if (sigaction(SIGINT, &sa, NULL) == -1) return EXIT_FAILURE;


    redis_reconnect_and_check();

    if (! keepRunning) return EXIT_SUCCESS;

	h = nflog_open();
	if (!h) {
		fprintf(stderr, "error during nflog_open()\n");
		exit(1);
	}

	if (nflog_unbind_pf(h, AF_INET) < 0) {
		fprintf(stderr, "error nflog_unbind_pf()\n");
		exit(1);
	}

	if (nflog_bind_pf(h, AF_INET) < 0) {
		fprintf(stderr, "error during nflog_bind_pf()\n");
		exit(1);
	}


	qh = nflog_bind_group(h, NFLOG_GROUP);
	if (!qh) {
		fprintf(stderr, "no handle for group %d\n", NFLOG_GROUP);
		exit(1);
	}

	if (nflog_set_mode(qh, NFULNL_COPY_PACKET, 0xffff) < 0) {
		fprintf(stderr, "can't set packet copy mode\n");
		exit(1);
	}

	fdx = nflog_fd(h);

	nflog_callback_register(qh, &cb, NULL);

	printf("registering callback for group %d; entering main loop\n", NFLOG_GROUP);
	while (keepRunning && (rv = recv(fdx, buf, sizeof(buf), 0)) && rv >= 0) {
		/* handle messages in just-received packet */
		nflog_handle_packet(h, buf, rv);
	}

	nflog_unbind_group(qh);

	nflog_close(h);

    //close(pcfd);

    printf("%d packets from nflog, %d of those interesting sip packets, %d of those sent to Redis queue\n", pcount, scount, rcount);

	return EXIT_SUCCESS;
}
