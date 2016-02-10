DROP TABLE IF EXISTS customers_options;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS price_tables;
DROP TABLE IF EXISTS price_tables_info;
DROP TABLE IF EXISTS pcaps;
DROP TABLE IF EXISTS callids2calls;
DROP TABLE IF EXISTS callids;
DROP TABLE IF EXISTS calls;
DROP TABLE IF EXISTS dr_rules_cp_archive;





-- calls/cdrs ref a dr_rules_cp ruleid, but opensips.dr_rules_cp changes regularly, so always keep the original copy
-- here so the id is always valid (and never reset the auto increment ruleid in opensips.dr_rules_cp).  insert the
-- copy here the moment a new row is added to dr_rules_cp.
CREATE TABLE dr_rules_cp_archive (
   ruleid      int(10)   unsigned not null,
   groupid     char(255) not null, -- route group id (no relation to pricing tables)
   prefix      char(64)  not null,
   timerec     char(255) not null,
   priority    int(11)   not null default '0',
   routeid     char(255) default null,
   gwlist      char(255) not null,
   attrs       char(255) default null,
   description char(128) not null default '',
  PRIMARY KEY (ruleid)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=4 DEFAULT CHARSET=utf8;



-- a call, from the viewpoint of a single line-item customer cdr, is a complicated thing !
CREATE TABLE calls (

    id  int(10) primary key auto_increment,

    c_from  char(3) not null,  -- # from Customer: 3 letter carrier code
    c_from5 char(5) not null,  -- # from Customer: 5 letter carrier code
    c_to    char(3),           -- # to Terminator: 3 letter carrier code
    c_to5   char(5),           -- # to Terminator: 5 letter carrier code

    rspcode int, -- last response code
    fstatus varchar(100), -- final status string

    t_start   datetime default null, -- # time of first invite 
    t_confirm datetime default null, -- # time of final reply for that invite (confirmation or end of dialog)
    t_end     datetime default null, -- # time of dialog end (bye message or same as t_confirm if dialog was never confirmed)
                                     
    s_setup       int, -- computed   # seconds spent in call setup (calculated as t_confirm - t_start)
    s_connected   int, -- computed   # seconds spent in confirmed dialog state (calculated as t_end - t_confirmed)
    s_connected_r int, -- computed   # rounded s_connected per business rules (6/6, 60/6, etc)
    s_total       int, -- computed   # total seconds (calculated as t_end - t_start)

    anum      varchar(100),  -- # user part of caller-id field
    anum2     varchar(100),  -- # modified anum as needed (e.g. btn subst.)
    a_country varchar(100),  -- computed # from lookup table on anum2
    a_state   varchar(100),  -- computed # from lookup table on anum2
    a_lata    varchar(100),  -- computed # from lookup table on anum2
    a_ocn     varchar(100),  -- computed # from lookup table on anum2
    a_jtype   varchar(100),  -- computed # anum2 jurisdiction type ('I', 'D', 'U')

    bnum      varchar(100),  -- # original dialed number
    b_lrn     varchar(100),  -- mapped from bnum
    b_country varchar(100),  -- computed # from lookup table on bnum (b_lrn)
    b_state   varchar(100),  -- computed # from lookup table on bnum (b_lrn)
    b_lata    varchar(100),  -- computed # from lookup table on bnum (b_lrn)
    b_ocn     varchar(100),  -- computed # from lookup table on bnum (b_lrn)
    b_jtype   varchar(100),  -- computed # bnum jurisdiction type ('I', 'D', 'U')

    xstate  varchar(100), -- computed state jurisdiction: 'intra' if a_state==b_state else 'inter' (if international, set to inter but otherwise ignore this field)
    call_price float, -- computed total billing amount for each call

    ruleid  int(10) unsigned, -- fk to dr_rules_cp_archive
    ptgroup int unsigned, -- fk to price_tables_info

    cp_nodes varchar(255), -- comma-separated list of cp nodes used

  FOREIGN KEY (ruleid) REFERENCES dr_rules_cp_archive(ruleid)

) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE INDEX calls_ite ON calls(t_end);

-- simple list of callids for calls and pcaps
CREATE TABLE callids (
    id     int(10) primary key auto_increment,
    callid varchar(250) not null,
   UNIQUE KEY (callid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


-- many-to-many: cdrs for b2bua or 3way or ??? calls will have multiple call-id values
CREATE TABLE callids2calls (
    callid_id int(10) not null,
    calls_id int(10) not null,
  FOREIGN KEY (callid_id) REFERENCES callids(id) ON DELETE CASCADE,
  FOREIGN KEY (calls_id) REFERENCES calls(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- use mysql (5.5 or higher) compressed table format.  Innodb file format
-- *must* be Barracuda (innodb_file_format = Barracuda).
-- Note: KEY_BLOCK_SIZE=2 was determined to
-- be optimal (about 7x disk savings, at cost of about 2x cpu for various
-- access patterns).
CREATE TABLE pcaps (

    callid_id int(10) primary key,

    ts1 int not null default 0, -- unix timestamp of earliest packet
    ts2 int not null default 0, -- unix timestamp of latest packet
    src_ip int unsigned not null default 0, -- source ip address of earliest packet

    pcap  mediumblob, -- pcap format linked list of packets

  FOREIGN KEY (callid_id) REFERENCES callids(id) ON DELETE CASCADE

) ENGINE=InnoDB ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=2 DEFAULT CHARSET=utf8;




CREATE TABLE price_tables_info (
    ptgroup  int unsigned primary key,
    name     varchar(255) not null,
    notes    varchar(1024) not null
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


-- allow for different customers to use different price tables. every dr_rules_cp_archive row needs at least one row here.
-- multiple rows can point to the same ruleid if they are in different ptgroup (price table group id).  This table will
-- accumulate new entries for every new dr_rules_cp row added.  The idea is to never delete a row here so given a call
-- record and ruleid, we can always look up which price row was used.
--
-- note: so a UI will clearly show that a price table corresponds (is assigned to) a specific lcr table
CREATE TABLE price_tables (
   ruleid    int  unsigned not null, -- fk to dr_rules_cp_archive
   ptgroup   int  unsigned not null, -- price table id (no relation to dr_rules_cp.groupid)
   mprice    float default null,
  FOREIGN KEY (ruleid) REFERENCES dr_rules_cp_archive(ruleid),
  FOREIGN KEY (ptgroup) REFERENCES price_tables_info(ptgroup)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=4 DEFAULT CHARSET=utf8;


CREATE TABLE customers (
    id     int         primary key auto_increment,
    name   varchar(64) not null,
    code3  char(3)     not null,
    code5  char(5)     not null,
    ptgroup int unsigned default null, -- fk to route_prices.ptgroup: current assigned price table to use (note: opensips could change the group used at runtime)
   FOREIGN KEY (ptgroup) REFERENCES price_tables_info(ptgroup),
   UNIQUE KEY (name),
   UNIQUE KEY (code3),
   UNIQUE KEY (code5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE customers_options (
    customer_id  int  not null,
    name   varchar(64) not null,
    value  varchar(64) not null,
   FOREIGN KEY (customer_id) REFERENCES customers(id),
   UNIQUE KEY (customer_id, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

