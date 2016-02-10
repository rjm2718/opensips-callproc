# CP node
#  - this is principally an LCR exercise; you should be able to do nearly everything with
#    the drouting module you're already familiar with; could then use Perl or some other
#    way to deal with complex cases and performance/caching improvements.
#
# bind only to pvt address 
# TODO
#  - topology hiding (for security and to reduce size of SIP packets full of route/via headers)
#  - refresh DB connection in a timer route, else there will be frequent delays as haproxy doesn't allow persistent connections


####### Global Parameters #########

debug=2
log_stderror=no
log_facility=LOG_LOCAL7

fork=yes
children=20


# TODO prevent *all* DNS lookups
#disable_dns_blacklist=no
rev_dns=no

# CP node listens only on pvt interface
listen=udp:eth0:5060

auto_aliases=no

# any CP can be an alias for any other CP node
alias=10.0.6.23
alias=10.0.6.26
alias=10.0.6.27

mhomed=0

disable_tcp=yes
#disable_tls=yes


user_agent_header="User-Agent: clogic/OpenSIPs/1.9"




####### Modules Section ########

#set module path
mpath="/usr/lib/opensips/modules/"

loadmodule "db_mysql.so"
loadmodule "signaling.so"
loadmodule "sl.so"
loadmodule "tm.so"
loadmodule "rr.so"
loadmodule "maxfwd.so"
loadmodule "textops.so"
loadmodule "sipmsgops.so"
loadmodule "mi_fifo.so"
loadmodule "uri.so"
loadmodule "acc.so"
loadmodule "dialog.so"
loadmodule "uac_auth.so"
loadmodule "uac.so"
loadmodule "drouting.so"
loadmodule "perl.so"


modparam("dialog|acc|drouting", "db_url", "mysql://opensips:barf@10.0.6.100/opensips")


# I wonder if the pings are done in a separate timer thread ... if not you need
# to figure out if there's a performance penalty (i.e. some blocking op) for too
# low an interval.
modparam("db_mysql", "ping_interval", 10)
modparam("db_mysql", "timeout_interval", 2)


modparam("mi_fifo", "fifo_name", "/tmp/opensips_fifo")
modparam("mi_fifo", "fifo_mode", 0666)


modparam("drouting", "drr_table", "dr_rules_cp") # separate LCR table different from LB node
modparam("drouting", "use_domain", 0)
modparam("drouting", "probing_interval", 0) # disabled ***
modparam("drouting", "probing_from", "sip:hello@70.102.5.26")
modparam("drouting", "probing_method", "OPTIONS")
modparam("drouting", "probing_reply_codes", "501, 403, 404, 405")
modparam("drouting", "ruri_avp", '$avp(dr_ruri)') # the next failover (not the current) route
modparam("drouting", "gw_id_avp", '$avp(dr_gw_id)')
modparam("drouting", "gw_attrs_avp", '$avp(dr_gw_attrs)')
modparam("drouting", "carrier_id_avp", '$avp(dr_carrier_id)')
modparam("drouting", "rule_attrs_avp", '$avp(rule_attrs)')  # use this field to read in our route price from attrs field in dr_rules table
modparam("drouting", "rule_id_avp", '$avp(rule_id)')


modparam("uri", "use_uri_table", 0)


#### dialog module
modparam("dialog", "dlg_match_mode", 1)
modparam("dialog", "db_mode", 0)  # only write dialog data to db on shutdown (can also use cachedb_url for better frequent cluster synchronization)
#modparam("dialog", "db_update_period", 10) # for db_mode=2
modparam("dialog", "default_timeout", 14400)  # for cachedb only?
#modparam("dialog", "profiles_no_value", "a22;c99;cnt;erl;icp;ilb;lv3;rjm;vxb;vxr;wds")
modparam("dialog", "profiles_with_value", "inbound; outbound")




#### ACCounting module
modparam("acc", "early_media", 1)
modparam("acc", "report_cancels", 1)
modparam("acc", "detect_direction", 0)
modparam("acc", "db_table_missed_calls", "acc")  # use same table to record failed transactions as is used for all other acc logs
modparam("acc", "db_flag", "LOG_FLAG")
#modparam("acc", "cdr_flag", "CDR_FLAG") # dont want this: want tx to written to acc immediately (don't wait for end of call to add up times)
modparam("acc", "db_missed_flag", "LOG_MISSED_FLAG")
modparam("acc", "failed_transaction_flag", "FAILED_TRANSACTION_FLAG")
# make sure to add these extra fields to 'acc' table
modparam("acc", "db_extra", "drgrpid=$avp(a_drgrpid);caller_id=$avp(a_caller);callee_id=$avp(a_callee);src_id=$avp(a_src_id);dst_id=$avp(a_dst_id);cp_node=$avp(a_cp);prtime=$avp(a_Tf);callee_lrn=$avp(a_lrn);ruleid=$avp(a_ruleid);t_branch_idx=$avp(t_branch_idx)")
#modparam("acc", "multi_leg_info", "dst_id2=$avp(a_dst_id);t_branch_idx=$avp(t_branch_idx);fc2=$avp(a_fc2)")
modparam("acc", "multi_leg_info", "dst_id2=$avp(a_dst_id)")


#### Record Route Module
modparam("rr", "append_fromtag", 1) # need append_fromtag for uac_replace_from function

#### uac module
modparam("uac","restore_mode","auto")
modparam("uac","restore_passwd","barf")
#modparam("uac","rr_to_store_param","bT")
#modparam("uac","rr_from_store_param","bF")

modparam("perl","filename","/etc/opensips/perlfunctions.pl")
modparam("perl","modpath", "/usr/lib/opensips/perl/")


# note: not good enough, can't init script vars here
#startup_route {
#
#}

####### Routing Logic ########

# main request routing logic

route {

    $var(m_outbound_proxy_public) = "70.102.5.26:5060";
    $var(m_outbound_proxy) = "10.0.6.100:5060";
    $var(m_this_node) = 'g07'; # gwid of this CP in dr_gateways table
    
    route(REQINIT);

    if (has_totag()) route(WITHINDLG);




    ##
    #---- initial requests (no To tag) section ----#
    ##


    # CANCEL processing
    if (is_method("CANCEL"))
    {
        # XXX knows where to send it? this is for the case where invite is cancelled, before we
        # have dialog state and full route set!
        if (t_check_trans()) t_relay();

        exit();
    }


    #---- catch retransmissions ----#
    t_check_trans();

    xlog("new request from carrier: CL-src3=$(hdr(X-CL-src3)[0])  rU=$rU");

    # preloaded route checking
    if (loose_route()) { # true== req contains Route header
        xlog("L_ERR", "Attempt to route with preloaded Route's [$fu/$tu/$ru/$ci]");
        if (!is_method("ACK"))
            sl_send_reply("403","Preload Route denied");
        exit;
    }

    # record routing
    if (!is_method("REGISTER|MESSAGE")) record_route();

    # account only INVITEs
    if (is_method("INVITE")) {
        
        setflag(LOG_FLAG); # do accounting
        #setflag(CDR_FLAG); # do accounting
        setflag(FAILED_TRANSACTION_FLAG);
        setflag(LOG_MISSED_FLAG);
        create_dialog();
        $avp(src_id_tmp) = $(hdr(X-CL-src3)[0]);  # name/id of source of this call
        set_dlg_profile("inbound", "$avp(src_id_tmp)"); # 3 letter carrier code, set by LB node
        #set_dlg_profile("c3");
    }

    




    ##
    ## number mangling (TODO: use dialog.topology_hiding)
    ##
    ## note: we require e164 format from our customers, but drouting rules prefixes can only be numeric
    ##       so strip '+' and assume for all route processing the number is in FULL (ie e.164 without the '+')
    ##       and then the '+' or whatever other prefix/strip gets applied as needed per entry in dr_gateways table.
    ##       Strategy: regardless of source, try to put From/To/Contact into a standard format and then
    ##       transform once the destination is known.
    ## 


    # request URI mangling section


    # VxR test
    if ($(hdr(X-CL-src3)[0])=='vxr') {
        xlog("adding '1' for VxR inbound call");
        prefix('1');
    }

    ## Voxbone test    # dtmf/echo test +14086474636
    #if (uri=~"sip:15032060203@") {
    #    rewriteuser("14086474636");
    #}

    # Voxbone -> 5037053463
    if (uri=~"sip:15032060203@") {
        rewriteuser("15037053463");
    }
    # a22 -> Voxbone
    if (uri=~"sip:15036665555@") {
        #rewriteuser("15032060203");
        rewriteuser("15037053463");
    }



    ## for some customers, choice of routing table is explicit from prefix or predefined
    ## based on carrier.  If so, set drgrpid0 avp, and this will override any choice made
    ## based on lrn inter/intra lookup
    $avp(drgrpid0) = "";
    if ($(hdr(X-CL-src3)[0])=='qkc') {

        if (uri =~ "sip:9920.+") $avp(drgrpid0) = "4"; # 0.004 table
        if (uri =~ "sip:9921.+") $avp(drgrpid0) = "5"; # 0.005 table
        if (uri =~ "sip:9922.+") $avp(drgrpid0) = "6"; # 0.0068 table

        xlog("setting drgrpid0 8");
        $avp(drgrpid0) = "8";
        if ($avp(drgrpid0)) strip(4);
    }
    else if ($(hdr(X-CL-src3)[0])=='ryn' || $(hdr(X-CL-src3)[0])=='a22' || $(hdr(X-CL-src3)[0])=='vxr') {

        xlog("setting drgrpid0 8");
        $avp(drgrpid0) = "8";
    }



    if (uri =~ "sip:\+1.+") {

        strip(1);  # uri number now in FULL format

    } else if (uri =~ "sip:1[0-9]{10}") {
        # we can let it slide, it's obvious it's a 1+10 domestic number

    } else {
        xlog("*warning* bad inbound number $ru");
        send_reply("400", "Invalid Number Format");
        exit;
    }


    # oU0 = original number dialed, post ruri mangling (oU0 will be the number, in standard full format, used
    # for LCR prefix lookup and stored in CDR values)
    $avp(oU0) = $rU; 



    ##
    ## LCR route processing
    ##

    sl_send_reply("100", "trying");


    # announce to the world that there is a new Call-Id
    perl_exec("postNewCallId");

    # drouting LCR table allows multiple route sets based on group:
    #   group 1 == domestic interstate,  group 2 == domestic intrastate,  group 3 == international

    # Perl function does LRN dip + inter/intra state calculation and sets the following AVPs:
    #  lrn       - result of LRN dip (if available)
    #  lrn_error - error doing LRN dip (could be client (eg num format) or server error)
    #  drgrpid   - which groupid to use in dr_rules_cp table (1==interstate 2==intrastate)
    #
    # If lrn_error is set, lrn will be empty and drgrpid will default to interstate.
    #
    perl_exec("lrnDip");
    #xlog("ok! drgrpid=$avp(drgrpid) lrn=$avp(lrn) lata=$avp(ru_lata)/state=$avp(ru_state) ocn=$avp(ru_ocn) error=$avp(lrn_error)");

    if (! $avp(lrn_error)) $rU = $avp(lrn);
    else xlog("warning: keeping original rU on lrn error $avp(lrn_error)");

    if ($avp(drgrpid0)) $avp(drgrpid) = $avp(drgrpid0);  # override drgrpid set by lrn script

    xlog(" +1> oU0=$avp(oU0) rU=$rU  drgrpid=$avp(drgrpid)");


    # do_routing can't take a variable argument (wtf, really?)
    #$avp(dr_carrier_id) = "";  # wtf: assigning an avp once here prevents do_routing from overwriting value
    switch ($avp(drgrpid)) {
        case "1":
            do_routing("1");
            break;
        case "2":
            do_routing("2");
            break;
        case "4":
            do_routing("4");
            break;
        case "5":
            do_routing("5");
            break;
        case "6":
            do_routing("6");
            break;
        case "7":
            do_routing("7");
            break;
        case "8":
            do_routing("8");
            break;
        case "9":
            do_routing("9");
            break;
    }


    if (! $avp(dr_carrier_id) || $avp(dr_carrier_id) == 'c99') {
        xlog("*warning* do_routing found no matching rule for number $rU");
        send_reply("480", "no routes available");
        $avp(a_src_id) = $(hdr(X-CL-src3)[0]);  # name/id of source of this call
        if ($fU) $avp(a_caller) = $fU;
        else $avp(a_caller) = "";
        $avp(a_drgrpid) = $avp(drgrpid);
        $avp(a_callee) = $avp(oU0); # $rU; # keep original dialed number for cdr record
        $avp(a_cp) = $var(m_this_node);
        $avp(a_Tf) = $time(%Y-%m-%d %H:%M:%S);
        if ($avp(ru_lata)) $avp(a_lata) = $avp(ru_lata);
        if ($avp(ru_ocn))  $avp(a_ocn) = $avp(ru_ocn);
        if ($avp(lrn))     $avp(a_lrn) = $avp(lrn);
        else if ($avp(lrn_error)) $avp(a_lrn) = 'error';
        acc_db_request("480 no routes available", "acc");
        exit;
    }


    # now restore original ruri and recall drouting function
    $rU = $avp(oU0);
    #if ($(hdr(X-CL-src3)[0])=='vxr') {
    #    xlog("adding '1' for VxR inbound call");
    #    prefix('1');
    #}
    route_to_gw("$avp(dr_gw_id)");
    xlog(" +3> oU0=$avp(oU0) ru=$ru");
    xlog(" routing to gw: dr_gw_id=$avp(dr_gw_id) dr_carrier_id=$avp(dr_carrier_id) rule_id=$avp(rule_id)  [next]dr_ruri=$avp(dr_ruri)");

    t_on_failure("gw_failure");
    t_on_branch("br1");

    $var(use_outbound_proxy) = 1;
    route(generic_relay);

}


#------------------------------------------------------------------------------

# mangle From/To fields according to target carriers's requirements.
# uses uac_replace_from() and uac_replace_to() methods
route[SET_TFU1] {

    # look at $fU and $tU and write into $var(fu1) and $var(tu1) in
    # normalized FULL number format.

    if ($fU =~ '^\+') {
        # in e.164 format
        $var(fu1) = $(fU{s.substr,1,0});

    } else if ($fU =~ '^1[2-9][0-9]{9}') {
        # great, already in FULL format (domestic US)
        $var(fu1) = $fU;

    } else if ($fU =~ '^[2-9][0-9]{9}') {
        $var(fu1) = "1" + $fU;

    } else if ($fU =~ '^011[2-9][0-9]+') {
        $var(fu1) = $(fU{s.substr,3,0});
    }
    else {
        if ($fU) {
            $var(fu1) = $fU;
        } else {
            $var(fu1) = ""; # TODO is this what you want?
        }
        xlog("warning: couldn't grok fU $fU");
    }
    


    #perl_exec("checkValidCallerId"); # sets avp

    if ($(hdr(X-CL-src3)[0])=='qkc') {
    #if ($(hdr(X-CL-src3)[0])=='a22') {

        # Cambodia: 8553083453012 (855+2digits+6or7digits == 11 or 12 digits (up to 13 digits for mobile))
        if ($var(fu1) =~ '^855[0-9]+') {
            if ($var(fu1) =~ '^855[0-9]{12,13}') { # valid Cambodia
            } else { $var(fu1) = '8641139707285'; }

        # HK: some conflicting info, but all HK numbers are 8 digits after 852
        } else if ($var(fu1) =~ '^852[0-9]+') {
            if ($var(fu1) =~ '^852[0-9]{11}') { # valid HK
            } else { $var(fu1) = '8641139707285'; }

        } else if ($var(fu1) =~ '^1[0-9]+') {
            if ($var(fu1) =~ '^1[0-9]{10}') { # valid US
            } else { $var(fu1) = '8641139707285'; }
        }

        else if ($var(fu1) =~ '^[1-9]+' && $(var(fu1){s.len}) > 9) {
            # maybe valid somewhere ...
        }

        else {
            # definitely not valid
            $var(fu1) = '8641139707285';
        }

        xlog("p6: $var(fu1)");
    }



    if ($tU =~ '^\+') {
        # in e.164 format
        $var(tu1) = $(tU{s.substr,1,0});

    } else if ($tU =~ '^1[2-9][0-9]{9}') {
        # great, already in FULL format (domestic US)
        $var(tu1) = $tU;

    } else if ($tU =~ '^[2-9][0-9]{9}') {
        $var(tu1) = "1" + $tU;

    } else if ($tU =~ '^011[2-9][0-9]+') {
        $var(tu1) = $(tU{s.substr,3,0});
    }
    else {
        $var(tu1) = $tU;
        xlog("warning: couldn't grok tU $tU");
    }



    # custom rules for each trunk
    if ($avp(dr_carrier_id) != "cnt") { # century link: 10 or 1+10 (no '+' allowed)
        $var(fu1) = "+" + $var(fu1);
        $var(tu1) = "+" + $var(tu1);
    }


    $var(f_1) = "sip:" + $var(fu1) +"@"+ $var(m_outbound_proxy_public);
    #$var(t_1) = "sip:" + $var(tu1) +"@"+ $var(m_current_target_gw);
    $var(t_1) = "sip:" + $rU +"@" + $rd;


    # calling uac_replace more than once screws up the way the header is written to the packet,
    # though the restore seems to still work properly.  So still call uac_replace as needed but
    # manually set user/domain in request.

    uac_replace_from("$var(f_1)");
    uac_replace_to("$var(t_1)");

    return;
}
#------------------------------------------------------------------------------


# most REQINIT sanity checks is already covered by the LB node
route[REQINIT] {

    remove_hf("User-Agent");

    # OPTIONS should be used to query actual user's capabilites?
    if (is_method("OPTIONS")) {
        sl_send_reply("200", "OK");
        exit();
    }


    #xlog(">>> msg from $si:$sp: $rm $ru / From $fu");
    #xlog("$mb\n\n");

    return;
}

route[WITHINDLG] {

    #---- Sequential requests section ----#

    #xlog(">>> within dialog >>> msg from $si:$sp: $rm $ru\n");

    # sequential request withing a dialog should
    # take the path determined by record-routing
    # shouldn't there be some authentication before relaying/routing any request ??? 
    #
    # see http://www.mail-archive.com/sr-users@lists.sip-router.org/msg08973.html for problem
    # with some BYE/ACK/re-INVITE requests missing Route headers
    #

    #if (validate_dialog()) xlog("---> DLG_status=$DLG_status validate_dialog==true\n");
    #else                   xlog("---> DLG_status=$DLG_status validate_dialog==false\n");

    if (loose_route()) {
        #xlog("    loose_route()==true");
        #if (uri==myself) xlog("    uri==myself");
        #else             xlog("    uri!=myself");

        # XXX if this transaction fails, we are not recording in acc properly
        if (is_method("BYE")) {
            setflag(LOG_FLAG); # do accounting
            #setflag(CDR_FLAG); # do accounting
            #setflag(FAILED_TRANSACTION_FLAG);
            #setflag(LOG_MISSED_FLAG);
            $avp(a_src_id) = $(hdr(X-CL-src3)[0]);  # name/id of source of this call
            if ($fU) {
                $avp(a_caller) = $fU;
            } else {
                $avp(a_caller) = "";
            }
            $avp(a_cp) = $var(m_this_node);
        } else if (is_method("INVITE")) {
            record_route();
        }

        route(generic_relay);

    } else {

        #xlog("    loose_route()==false");
        #if (uri==myself) xlog("    uri==myself");
        #else             xlog("    uri!=myself");


        if ( is_method("ACK") ) {
            if ( t_check_trans() ) {
                t_relay();
                exit;
            } else {
                exit;
            }
        }

#            # hack to deal with bad subsequent requests that lack Route header
#            #if ($DLG_status != NULL && !validate_dialog()) {
#            if ($fU == "ryan1" && !validate_dialog()) {
#                xlog("* DLG_status=$DLG_status for $fU\n");
#                fix_route_dialog();
#                xlog("* fix_route_dialog() called for $fU\n");
#                route(generic_relay);
#            }

        else send_reply("404","Not here");
    }

    exit;
}




route[generic_relay] {
    

    if ($var(use_outbound_proxy)) {

        $du = "sip:" + $var(m_outbound_proxy);
        $var(use_outbound_proxy) = 0;
    }

    #xlog("route[generic_relay] du=$du ru=$ru ");

    if (!t_relay()) {
        send_reply("500","Internal Error");
    };

    exit;
}



#onreply_route {
#
#    #xlog("OpenSIPS received a reply from $si: $rs - $rr\n");
#}



failure_route[gw_failure] {

    $var(m_outbound_proxy_public) = "70.102.5.26:5060";
    $var(m_outbound_proxy) = "10.0.6.100:5060";
    $var(m_this_node) = 'g07'; # gwid of this CP in dr_gateways table

    $avp(t_rc) = $T_reply_code;  # triggers duplicate of acc row
    $avp(t_es) = $avp(dr_carrier_id) +"-"+ $avp(t_rc);
    if ($avp(aerr)) $avp(aerr) = $avp(aerr) +";"+ $avp(t_es);
    else $avp(aerr) = $avp(t_es);

    if (t_local_replied("all")) {
        xlog (" - no reply received\n");
    }

    if (t_was_cancelled()) {
        xlog("cancelled");
        exit;
    }

    xlog("failure_route called: rs=$rs T_reply_code=$T_reply_code");

    # uncomment the following lines if you want to block client 
    # redirect based on 3xx replies.
    ##if (t_check_status("3[0-9][0-9]")) {
    ##t_reply("404","Not found");
    ##  exit;
    ##}

    # use next LCR route if possible
    if (t_check_status("(408|403|480)|([56][0-9][0-9])")) {  # TODO response when we hit a carriers sim calls limit

        # disable gw with dr_disable() here ... ?
        xlog(" )))))))---- failed on $avp(dr_carrier_id)");
        if ($avp(dr_carrier_id)) {
            unset_dlg_profile("outbound", "$avp(dr_carrier_id)");
        }

        if (! use_next_gw()) {
            xlog("*warning* use_next_gw no more routes to try!");
            t_reply("480", "no routes available");
        }
        else if ($avp(dr_carrier_id) == 'c99') {
            xlog("*warning* use_next_gw no more routes to try! ; dr_carrier_id=$avp(dr_carrier_id) ");
            t_reply("480", "no routes available");
        }
        else {

            #xlog(" use_next_gw:  dr_gw_id=$avp(dr_gw_id) dr_carrier_id=$avp(dr_carrier_id) rule_id=$avp(rule_id)  [next]dr_ruri=$avp(dr_ruri)");
            # now restore original ruri and recall drouting function
            #xlog(" +4> oU0=$avp(oU0) rU=$rU");
            $rU = $avp(oU0);
            #if ($(hdr(X-CL-src3)[0])=='vxr') {
            #    xlog("adding '1' for VxR inbound call");
            #    prefix('1');
            #}
            route_to_gw("$avp(dr_gw_id)");
            xlog(" +5> oU0=$avp(oU0) ru=$ru");

            t_on_failure("gw_failure");  # necessary to re-arm?
            t_on_branch("br1"); # necessary to re-arm?
            $var(use_outbound_proxy) = 1;
            route(generic_relay);
        }
    }

    # TODO want to record final response from final route tried (otherwise acc table show 404 sent back to caller)
    
    exit;
}

branch_route[br1] {

    xlog("~ branch_route: T_branch_idx = $T_branch_idx / aerr= $avp(aerr)");

    setflag(LOG_FLAG); # do accounting
    #setflag(CDR_FLAG); # do accounting
    setflag(FAILED_TRANSACTION_FLAG);
    setflag(LOG_MISSED_FLAG);

    # for accounting
    #$avp(a_fc2) = '';
    $avp(t_branch_idx) = $T_branch_idx;
    $avp(a_dst_id) = $avp(dr_carrier_id);
    $avp(a_src_id) = $(hdr(X-CL-src3)[0]);  # name/id of source of this call
    if ($fU) $avp(a_caller) = $fU;
    else $avp(a_caller) = "";
    $avp(a_drgrpid) = $avp(drgrpid);
    $avp(a_callee) = $avp(oU0); # $rU; # keep original dialed number for cdr record
    $avp(a_cp) = $var(m_this_node);
    $avp(a_Tf) = $time(%Y-%m-%d %H:%M:%S);
    $avp(a_ruleid) = $avp(rule_id);
    if ($avp(ru_lata)) $avp(a_lata) = $avp(ru_lata);
    if ($avp(ru_ocn))  $avp(a_ocn) = $avp(ru_ocn);
    if ($avp(lrn))     $avp(a_lrn) = $avp(lrn);
    else if ($avp(lrn_error)) $avp(a_lrn) = 'error';

    set_dlg_profile("outbound", "$avp(dr_carrier_id)");

    # number mangling continued: From/To mangling (now that we know target gateway ... don't forget to call this again
    # in failure route if a new gateway is tried)
    route(SET_TFU1);

    #if (remove_hf("User-Agent")) {
    #    append_hf("User-Agent: clogic/OpenSIPs/1.8\r\n");
    #}

    remove_hf("User-Agent");
    append_hf("User-Agent: clogic/OpenSIPs/1.9\r\n");

}



# if you want to OPTIONS probe from this CP node, forward to LB
#local_route {
#
#    $var(m_outbound_proxy_public) = "70.102.5.26:5060";
#    $var(m_outbound_proxy) = "10.0.6.100:5060";
#
#    if ( is_method("OPTIONS") ) {
#        $du = "sip:" + $var(m_outbound_proxy);
#    }
#
#    xlog("local_route: $rm - $ru");
#
#}



#timer_route[gw_update, 10] {
#    avp_db_query("select gwlist where ruleid==1",$avp(i:100));
#    $shv(i:100) =$avp(i:100);
#}
