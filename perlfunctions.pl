# Perl functions to be loaded into OpenSips
# Ryan Mitchell <rjm@tcl.net>
#
#
# TODO
# Redis connection timeout (async event libs?), use slave as needed for reads
# Redis connection peristence between requests
# Mysql connection timeout
# Mysql connection persistence between requests

use IO::Socket::INET;
use Time::HiRes qw( gettimeofday tv_interval );

use OpenSIPS qw (log);
use OpenSIPS::Constants;
use Redis::hiredis;

use NanpaDB;


######################################################

sub getRedisConnection {
    my $readOnly = shift || 0;

    my $redis = Redis::hiredis->new();
    $redis->connect('10.0.6.26', 6379);

    return $redis;
}

sub redis_get {
    my $key = shift || "";
    my $redis = getRedisConnection(1);
    my $k1 = $redis->command("get", $key);
    $redis->quit();
    return $k1;
}

sub redis_set {
    my ($key, $value) = @_;
    my $redis = getRedisConnection(0);
    my $timeout = 43200;
    if ($value =~ /error/i) { $timeout = 300; } # hack!
    my $k1 = $redis->command("set", $key, $value, "EX", $timeout); # 12h cache
    $redis->quit();
}

sub redis_rpush {
    my ($list, $value) = @_;
    my $redis = getRedisConnection(0);
    my $k1 = $redis->command("rpush", $list, $value);
    $redis->quit();
}




######################################################



# XML Port: 25201 (UDP)
# Primary: 184.173.103.52
# Secondary: 208.43.96.25
#
# <LRN>15038289199</LRN>


$custid = "f55c5f6e-9050-4104-9b39-e5131d34bef1";
$svc_ip = "184.173.103.52";
#$svc_ip = "84.173.103.52";
$svc_port = 25201;

$lrn_dip_timeout_seconds = 2;

sub lrnDip {

    my $m = shift; # message

    eval {

        my $dt;
        my $t0 = [gettimeofday];

        # weird, but this is how it's done
        my $rU = $m->pseudoVar("\$rU");
        my $fU = $m->pseudoVar("\$fU");


        my $err = "";
        my $lrn = "";

        my $lrn_c = redis_get($rU);
        #log(L_NOTICE, "* lrnDip: redis cache for $rU => $lrn_c");

        if (! $lrn_c) {

            my ($sock, $req, $resp);

            $req = "<CustomerID>$custid</CustomerID> <QueryNumber>$rU</QueryNumber>\r\n";

            $sock = new IO::Socket::INET( PeerAddr => "$svc_ip:$svc_port", Proto => 'udp' ) || die "failed to create socket";

            $sock->sockopt(SO_RCVTIMEO, pack("L!L!", $lrn_dip_timeout_seconds, 0));

            $sock->send($req);
            $sock->recv($resp, 1024, 0);


            if ($resp) {

                $resp =~ s/\s+//gs;

                if (length($resp) < 20 && $resp =~ /error/i) {
                    $err = "error:1";
                }

                if ($resp =~ /<LRN>(.+?)<\/LRN>/i) {
                    $lrn = $1;
                    $err = "error:rsp1" if (length($lrn) < 10);
                }
            }
            else { $err = "error:nrsp1"; }

            $sock->close();

            my $t1 = [gettimeofday];
            $dt = tv_interval($t0, $t1);

            if (! $err) {
                $lrn_c = $lrn;
            }
            else {
                $lrn_c = $err; # cache negative/error result too ... though we should look at the type of error and possibly try again
            }

            redis_set($rU, $lrn_c);
        }
        else {

            if ($lrn_c =~ /error/i) {
                $err = $lrn_c;
            } else {
                $lrn = $lrn_c;
            }
        }



        my $rU0 = $rU;

        if ($dt && ($dt > ($lrn_dip_timeout_seconds * 0.8) && !$lrn && !$err)) {

            $err="timeout";
            OpenSIPS::AVP::add("lrn_error", $err);

        }
        elsif ($err) {
            OpenSIPS::AVP::add("lrn_error", $err);
        }
        else {

            OpenSIPS::AVP::add("lrn", $lrn);
            $rU = $lrn;
        }


        # $rU == lrn or original $rU if lrn dip failed
        # either way now do table lookup for number info
        my $ndf = NanpaDB::getNumberInfo($fU);
        my $ndt = NanpaDB::getNumberInfo($rU);

        # inter or intra-state? set avp(drgrpid) to 1 or 2 corresponing to dr_rules_cp.groupid
        my $drgrpid = ($$ndf{'state'} eq $$ndt{'state'}) ? "2" : "1";
        OpenSIPS::AVP::add("drgrpid", $drgrpid);

        # data we know about destination number
        OpenSIPS::AVP::add("ru_state", $$ndt{'state'});
        OpenSIPS::AVP::add("ru_lata",  $$ndt{'lata'});
        OpenSIPS::AVP::add("ru_ocn",   $$ndt{'ocn'});

        #log(L_NOTICE, "* lrnDip: fU=$fU rU=$rU (rU0=$rU0) state=$$ndt{'state'} ocn=$$ndt{'ocn'} drgrpid=$drgrpid | dt=$dt err=$err");
    };

    if ($@) {
        log(L_CRIT, "lrnDip failure: $@") if $@; # ...
        OpenSIPS::AVP::add("lrn_error", "error:$@");
        OpenSIPS::AVP::add("lrn", "");
        OpenSIPS::AVP::add("drgrpid", "1");
        return 0;
    }


    return 1;
}




# queue new call-id event ... so cdr processor will know about it
sub postNewCallId {

    my $m = shift; # message

    eval {
        my $callid = $m->pseudoVar("\$ci");
        #log(L_NOTICE, "- callid = $callid");
        redis_rpush("cdr:callids", $callid);
    };

    if ($@) {
        log(L_CRIT, "noteNewCallId failure: $@") if $@; # ...
        return 0;
    }

    return 1;
}
