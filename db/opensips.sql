-- customizations:
--  acc added custom fields
--  separate dr_rules_lb and dr_rules_cp tables


-- 2013/11/26: removed rt_cost from acc table, created separate customer pricing table netcall.price_tables

-- ----------------------------------------------------------------------------------------





-- MySQL dump 10.13  Distrib 5.5.31, for Linux (x86_64)
--
-- Host: localhost    Database: opensips
-- ------------------------------------------------------
-- Server version	5.5.31-30.3-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `acc`
--

DROP TABLE IF EXISTS `acc`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `acc` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `method` char(16) NOT NULL DEFAULT '',
  `from_tag` char(64) NOT NULL DEFAULT '',
  `to_tag` char(64) NOT NULL DEFAULT '',
  `callid` char(64) NOT NULL DEFAULT '',
  `sip_code` char(3) NOT NULL DEFAULT '',
  `sip_reason` char(32) NOT NULL DEFAULT '',
  `time` datetime NOT NULL,
  `duration` int(11) unsigned NOT NULL DEFAULT '0',
  `setuptime` int(11) unsigned NOT NULL DEFAULT '0',
  `created` datetime DEFAULT NULL,
  `caller_id` varchar(256) DEFAULT NULL,
  `callee_id` varchar(256) DEFAULT NULL,
  `src_id` varchar(64) DEFAULT NULL,
  `dst_id` varchar(64) DEFAULT NULL,
  `cp_node` varchar(16) NOT NULL DEFAULT 'g00',
  `prtime` datetime DEFAULT NULL,
  `callee_lrn` varchar(32) DEFAULT NULL,
  `ruleid` int(10) unsigned NOT NULL DEFAULT '0',
  `dst_id2` varchar(64) DEFAULT NULL,
  `t_branch_idx` char(4) DEFAULT NULL,
  `drgrpid` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `callid_idx` (`callid`),
  KEY `acc_idx_time` (`time`),
  KEY `acc_idx_prtime` (`prtime`)
) ENGINE=InnoDB AUTO_INCREMENT=8814754 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Temporary table structure for view `accv`
--

DROP TABLE IF EXISTS `accv`;
/*!50001 DROP VIEW IF EXISTS `accv`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `accv` (
  `id` tinyint NOT NULL,
  `method` tinyint NOT NULL,
  `from_tag` tinyint NOT NULL,
  `to_tag` tinyint NOT NULL,
  `sip_code` tinyint NOT NULL,
  `sip_reason` tinyint NOT NULL,
  `time` tinyint NOT NULL,
  `prtime` tinyint NOT NULL,
  `callee_id` tinyint NOT NULL,
  `dst_id` tinyint NOT NULL,
  `t_branch_idx` tinyint NOT NULL,
  `callid` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `address`
--

DROP TABLE IF EXISTS `address`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `address` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `grp` smallint(5) unsigned NOT NULL DEFAULT '0',
  `ip` char(50) NOT NULL,
  `mask` tinyint(4) NOT NULL DEFAULT '32',
  `port` smallint(5) unsigned NOT NULL DEFAULT '0',
  `proto` char(4) NOT NULL DEFAULT 'any',
  `pattern` char(64) DEFAULT NULL,
  `context_info` char(32) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `aliases`
--

DROP TABLE IF EXISTS `aliases`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `aliases` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `username` char(64) NOT NULL DEFAULT '',
  `domain` char(64) DEFAULT NULL,
  `contact` char(255) NOT NULL DEFAULT '',
  `received` char(128) DEFAULT NULL,
  `path` char(128) DEFAULT NULL,
  `expires` datetime NOT NULL DEFAULT '2020-05-28 21:32:15',
  `q` float(10,2) NOT NULL DEFAULT '1.00',
  `callid` char(255) NOT NULL DEFAULT 'Default-Call-ID',
  `cseq` int(11) NOT NULL DEFAULT '13',
  `last_modified` datetime NOT NULL DEFAULT '1900-01-01 00:00:01',
  `flags` int(11) NOT NULL DEFAULT '0',
  `cflags` int(11) NOT NULL DEFAULT '0',
  `user_agent` char(255) NOT NULL DEFAULT '',
  `socket` char(64) DEFAULT NULL,
  `methods` int(11) DEFAULT NULL,
  `sip_instance` char(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `alias_idx` (`username`,`domain`,`contact`,`callid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dbaliases`
--

DROP TABLE IF EXISTS `dbaliases`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `dbaliases` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `alias_username` char(64) NOT NULL DEFAULT '',
  `alias_domain` char(64) NOT NULL DEFAULT '',
  `username` char(64) NOT NULL DEFAULT '',
  `domain` char(64) NOT NULL DEFAULT '',
  PRIMARY KEY (`id`),
  UNIQUE KEY `alias_idx` (`alias_username`,`alias_domain`),
  KEY `target_idx` (`username`,`domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dialog`
--

DROP TABLE IF EXISTS `dialog`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `dialog` (
  `dlg_id` bigint(10) unsigned NOT NULL,
  `callid` char(255) NOT NULL,
  `from_uri` char(128) NOT NULL,
  `from_tag` char(64) NOT NULL,
  `to_uri` char(128) NOT NULL,
  `to_tag` char(64) NOT NULL,
  `mangled_from_uri` char(64) DEFAULT NULL,
  `mangled_to_uri` char(64) DEFAULT NULL,
  `caller_cseq` char(11) NOT NULL,
  `callee_cseq` char(11) NOT NULL,
  `caller_ping_cseq` int(11) unsigned NOT NULL,
  `callee_ping_cseq` int(11) unsigned NOT NULL,
  `caller_route_set` text,
  `callee_route_set` text,
  `caller_contact` char(128) NOT NULL,
  `callee_contact` char(128) NOT NULL,
  `caller_sock` char(64) NOT NULL,
  `callee_sock` char(64) NOT NULL,
  `state` int(10) unsigned NOT NULL,
  `start_time` int(10) unsigned NOT NULL,
  `timeout` int(10) unsigned NOT NULL,
  `vars` text,
  `profiles` text,
  `script_flags` int(10) unsigned NOT NULL DEFAULT '0',
  `flags` int(10) unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (`dlg_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dialplan`
--

DROP TABLE IF EXISTS `dialplan`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `dialplan` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `dpid` int(11) NOT NULL,
  `pr` int(11) NOT NULL,
  `match_op` int(11) NOT NULL,
  `match_exp` char(64) NOT NULL,
  `match_flags` int(11) NOT NULL,
  `subst_exp` char(64) NOT NULL,
  `repl_exp` char(32) NOT NULL,
  `disabled` int(11) NOT NULL DEFAULT '0',
  `attrs` char(32) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dispatcher`
--

DROP TABLE IF EXISTS `dispatcher`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `dispatcher` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `setid` int(11) NOT NULL DEFAULT '0',
  `destination` char(192) NOT NULL DEFAULT '',
  `socket` char(128) DEFAULT NULL,
  `flags` int(11) NOT NULL DEFAULT '0',
  `weight` int(11) NOT NULL DEFAULT '1',
  `attrs` char(128) NOT NULL DEFAULT '',
  `description` char(64) NOT NULL DEFAULT '',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `domain`
--

DROP TABLE IF EXISTS `domain`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `domain` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `domain` char(64) NOT NULL DEFAULT '',
  `last_modified` datetime NOT NULL DEFAULT '1900-01-01 00:00:01',
  PRIMARY KEY (`id`),
  UNIQUE KEY `domain_idx` (`domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dr_carriers`
--

DROP TABLE IF EXISTS `dr_carriers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `dr_carriers` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `carrierid` char(64) NOT NULL,
  `gwlist` char(255) NOT NULL,
  `flags` int(11) unsigned NOT NULL DEFAULT '0',
  `attrs` char(255) DEFAULT '',
  `description` char(128) NOT NULL DEFAULT '',
  `limit_in` int(11) DEFAULT NULL,
  `limit_out` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dr_carrier_idx` (`carrierid`)
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dr_gateways`
--

DROP TABLE IF EXISTS `dr_gateways`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `dr_gateways` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `gwid` char(64) NOT NULL,
  `type` int(11) unsigned NOT NULL DEFAULT '0',
  `address` char(128) NOT NULL,
  `strip` int(11) unsigned NOT NULL DEFAULT '0',
  `pri_prefix` char(16) DEFAULT NULL,
  `attrs` char(255) DEFAULT NULL,
  `probe_mode` int(11) unsigned NOT NULL DEFAULT '0',
  `description` char(128) NOT NULL DEFAULT '',
  PRIMARY KEY (`id`),
  UNIQUE KEY `dr_gw_idx` (`gwid`)
) ENGINE=InnoDB AUTO_INCREMENT=69 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dr_groups`
--

DROP TABLE IF EXISTS `dr_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `dr_groups` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `username` char(64) NOT NULL,
  `domain` char(128) NOT NULL DEFAULT '',
  `groupid` int(11) unsigned NOT NULL DEFAULT '0',
  `description` char(128) NOT NULL DEFAULT '',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dr_rules_cp`
--

DROP TABLE IF EXISTS `dr_rules_cp`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `dr_rules_cp` (
  `ruleid` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `groupid` char(255) NOT NULL,
  `prefix` char(64) NOT NULL,
  `timerec` char(255) NOT NULL,
  `priority` int(11) NOT NULL DEFAULT '0',
  `routeid` char(255) DEFAULT NULL,
  `gwlist` char(255) NOT NULL,
  `attrs` char(255) DEFAULT NULL,
  `description` char(128) NOT NULL DEFAULT '',
  PRIMARY KEY (`ruleid`),
  KEY `drcp_prefix_idx` (`prefix`)
) ENGINE=InnoDB AUTO_INCREMENT=3023166 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dr_rules_lb`
--

DROP TABLE IF EXISTS `dr_rules_lb`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `dr_rules_lb` (
  `ruleid` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `groupid` char(255) NOT NULL,
  `prefix` char(64) NOT NULL,
  `timerec` char(255) NOT NULL,
  `priority` int(11) NOT NULL DEFAULT '0',
  `routeid` char(255) DEFAULT NULL,
  `gwlist` char(255) NOT NULL,
  `attrs` char(255) DEFAULT NULL,
  `description` char(128) NOT NULL DEFAULT '',
  PRIMARY KEY (`ruleid`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ft`
--

DROP TABLE IF EXISTS `ft`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ft` (
  `order_id` int(11) DEFAULT NULL,
  `ordered` int(11) DEFAULT NULL,
  `checkin` int(11) DEFAULT NULL,
  `collected` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `grp`
--

DROP TABLE IF EXISTS `grp`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `grp` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `username` char(64) NOT NULL DEFAULT '',
  `domain` char(64) NOT NULL DEFAULT '',
  `grp` char(64) NOT NULL DEFAULT '',
  `last_modified` datetime NOT NULL DEFAULT '1900-01-01 00:00:01',
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_group_idx` (`username`,`domain`,`grp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `load_balancer`
--

DROP TABLE IF EXISTS `load_balancer`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `load_balancer` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `group_id` int(11) unsigned NOT NULL DEFAULT '0',
  `dst_uri` char(128) NOT NULL,
  `resources` char(255) NOT NULL,
  `probe_mode` int(11) unsigned NOT NULL DEFAULT '0',
  `description` char(128) NOT NULL DEFAULT '',
  PRIMARY KEY (`id`),
  KEY `dsturi_idx` (`dst_uri`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `location`
--

DROP TABLE IF EXISTS `location`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `location` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `username` char(64) NOT NULL DEFAULT '',
  `domain` char(64) NOT NULL DEFAULT '',
  `contact` char(255) NOT NULL DEFAULT '',
  `received` char(128) DEFAULT NULL,
  `path` char(255) DEFAULT NULL,
  `expires` datetime NOT NULL DEFAULT '2020-05-28 21:32:15',
  `q` float(10,2) NOT NULL DEFAULT '1.00',
  `callid` char(255) NOT NULL DEFAULT 'Default-Call-ID',
  `cseq` int(11) NOT NULL DEFAULT '13',
  `last_modified` datetime NOT NULL DEFAULT '1900-01-01 00:00:01',
  `flags` int(11) NOT NULL DEFAULT '0',
  `cflags` int(11) NOT NULL DEFAULT '0',
  `user_agent` char(255) NOT NULL DEFAULT '',
  `socket` char(64) DEFAULT NULL,
  `methods` int(11) DEFAULT NULL,
  `sip_instance` char(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_contact_idx` (`username`,`domain`,`contact`,`callid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `pdt`
--

DROP TABLE IF EXISTS `pdt`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pdt` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `sdomain` char(128) NOT NULL,
  `prefix` char(32) NOT NULL,
  `domain` char(128) NOT NULL DEFAULT '',
  PRIMARY KEY (`id`),
  UNIQUE KEY `sdomain_prefix_idx` (`sdomain`,`prefix`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `re_grp`
--

DROP TABLE IF EXISTS `re_grp`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `re_grp` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `reg_exp` char(128) NOT NULL DEFAULT '',
  `group_id` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `group_idx` (`group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `rtpproxy_sockets`
--

DROP TABLE IF EXISTS `rtpproxy_sockets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `rtpproxy_sockets` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `rtpproxy_sock` text NOT NULL,
  `set_id` int(10) unsigned NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `silo`
--

DROP TABLE IF EXISTS `silo`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `silo` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `src_addr` char(128) NOT NULL DEFAULT '',
  `dst_addr` char(128) NOT NULL DEFAULT '',
  `username` char(64) NOT NULL DEFAULT '',
  `domain` char(64) NOT NULL DEFAULT '',
  `inc_time` int(11) NOT NULL DEFAULT '0',
  `exp_time` int(11) NOT NULL DEFAULT '0',
  `snd_time` int(11) NOT NULL DEFAULT '0',
  `ctype` char(32) NOT NULL DEFAULT 'text/plain',
  `body` blob NOT NULL,
  PRIMARY KEY (`id`),
  KEY `account_idx` (`username`,`domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `speed_dial`
--

DROP TABLE IF EXISTS `speed_dial`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `speed_dial` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `username` char(64) NOT NULL DEFAULT '',
  `domain` char(64) NOT NULL DEFAULT '',
  `sd_username` char(64) NOT NULL DEFAULT '',
  `sd_domain` char(64) NOT NULL DEFAULT '',
  `new_uri` char(128) NOT NULL DEFAULT '',
  `fname` char(64) NOT NULL DEFAULT '',
  `lname` char(64) NOT NULL DEFAULT '',
  `description` char(64) NOT NULL DEFAULT '',
  PRIMARY KEY (`id`),
  UNIQUE KEY `speed_dial_idx` (`username`,`domain`,`sd_domain`,`sd_username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `subscriber`
--

DROP TABLE IF EXISTS `subscriber`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `subscriber` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `username` char(64) NOT NULL DEFAULT '',
  `domain` char(64) NOT NULL DEFAULT '',
  `password` char(25) NOT NULL DEFAULT '',
  `email_address` char(64) NOT NULL DEFAULT '',
  `ha1` char(64) NOT NULL DEFAULT '',
  `ha1b` char(64) NOT NULL DEFAULT '',
  `rpid` char(64) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_idx` (`username`,`domain`),
  KEY `username_idx` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `uri`
--

DROP TABLE IF EXISTS `uri`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `uri` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `username` char(64) NOT NULL DEFAULT '',
  `domain` char(64) NOT NULL DEFAULT '',
  `uri_user` char(64) NOT NULL DEFAULT '',
  `last_modified` datetime NOT NULL DEFAULT '1900-01-01 00:00:01',
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_idx` (`username`,`domain`,`uri_user`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `usr_preferences`
--

DROP TABLE IF EXISTS `usr_preferences`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `usr_preferences` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(64) NOT NULL DEFAULT '',
  `username` char(128) NOT NULL DEFAULT '0',
  `domain` char(64) NOT NULL DEFAULT '',
  `attribute` char(32) NOT NULL DEFAULT '',
  `type` int(11) NOT NULL DEFAULT '0',
  `value` char(128) NOT NULL DEFAULT '',
  `last_modified` datetime NOT NULL DEFAULT '1900-01-01 00:00:01',
  PRIMARY KEY (`id`),
  KEY `ua_idx` (`uuid`,`attribute`),
  KEY `uda_idx` (`username`,`domain`,`attribute`),
  KEY `value_idx` (`value`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `version`
--

DROP TABLE IF EXISTS `version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `version` (
  `table_name` char(32) NOT NULL,
  `table_version` int(10) unsigned NOT NULL DEFAULT '0',
  UNIQUE KEY `t_name_idx` (`table_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Final view structure for view `accv`
--

/*!50001 DROP TABLE IF EXISTS `accv`*/;
/*!50001 DROP VIEW IF EXISTS `accv`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8 */;
/*!50001 SET character_set_results     = utf8 */;
/*!50001 SET collation_connection      = utf8_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `accv` AS select `acc`.`id` AS `id`,`acc`.`method` AS `method`,`acc`.`from_tag` AS `from_tag`,`acc`.`to_tag` AS `to_tag`,`acc`.`sip_code` AS `sip_code`,`acc`.`sip_reason` AS `sip_reason`,`acc`.`time` AS `time`,`acc`.`prtime` AS `prtime`,`acc`.`callee_id` AS `callee_id`,`acc`.`dst_id` AS `dst_id`,`acc`.`t_branch_idx` AS `t_branch_idx`,`acc`.`callid` AS `callid` from `acc` where (`acc`.`dst_id` = `acc`.`dst_id2`) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2013-11-26 14:15:18
