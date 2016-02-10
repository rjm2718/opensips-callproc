#!/usr/bin/perl -w

# mysql backup

use DBI;


# collect options
%databases = ( 
               'opensips'  => ['opensips', 'utf8'],
               'netcall' => ['netcall', 'utf8'],
             );

$big_tables_date_start = '2013-12-01 00:00:00';



$tmpd = "/tmp/restore-db-xxx/";

system("rm -rf $tmpd") && die $!;

mkdir $tmpd || die $!;
chmod 0777, $tmpd || die $!;
chdir $tmpd || die;


# 1. provide base path where bkup files can be found (e.g. /u02/mysql/backups), i.e.
#    where '200XXXXX' and 'current' directories are.
# 2. provide point-in-time (or latest available) of interest
# 3. confirm backup files with data for date are available
# 4. create new mysql databases, name with date appended, e.g. vxt1_20081010_153012



# large tables vxt1: cdr
#


# ---------------------------------------------------------------

# set sql_log_off = 'ON';  -- per-sesssion disable query log (not bin log)
# check & warn if server has binlogs enabled for a large import
# set character set 'utf8';


# getting data out of db:
#   flush tables with read lock (lock entire database ... have to stay connected)
#   flush logs
#   show master status -- note new log position
#   ... dump tables ...
#   unlock tables
#

$t2 = time;


# lock tables so they don't change until we're done; note master log positions
$dbhL = DBI->connect("DBI:mysql:", "root", "gravity88") || die;
$dbhL->do("flush tables with read lock") || die $dbhL->errstr;
$dbhL->do("flush logs") || die $dbhL->errstr;
$sthL = $dbhL->prepare("show master status");
$sthL->execute;
@trd = $sthL->fetchrow_array;
open(LIF, "> README.BINLOG.txt") || die $!;
print LIF "new master logfile = '".$trd[0]."', position=".$trd[1]."\n";
print LIF "(start binlog playback at this logfile/position)\n";
close(LIF);
print "new master logfile = '".$trd[0]."', position=".$trd[1]."\n";
print "(start binlog playback at this logfile/position)\n";
$sthL->finish;

foreach $db (keys %databases) {

    $db = lc($db);

    print "database $db\n";

    mkdir $db || die;
    chmod 0777, $db || die $!;

    $rfn = "$db.restore.sql";

    $db_cfg = $databases{$db};
    $db_new_name = $$db_cfg[0];
    $db_charset  = $$db_cfg[1];

    open(RF, "> $rfn") || die $!;
    print RF "CREATE DATABASE IF NOT EXISTS $db_new_name DEFAULT CHARACTER SET '$db_charset';\n";
    print RF "USE $db_new_name;\n";
    print RF "\n";
    close(RF);

    system("mysqldump --add-drop-database --create-options --delayed-insert --disable-keys --routines --no-data $db >> $rfn") && die;


    # query db to get list of tables
    @tables = ();
    $dbh = DBI->connect("DBI:mysql:$db", "root", "gravity88") || die;
    $sth = $dbh->prepare("SELECT table_name FROM information_schema.tables WHERE table_schema = '$db' AND table_type='BASE TABLE'");
    $sth->execute;
    while (@trd = $sth->fetchrow_array) {
        push(@tables, $trd[0]);
    }


    open(RF, ">> $rfn") || die $!;
    print RF "\n\n\n-- commands to load data from files\n\n";
    print RF "SET FOREIGN_KEY_CHECKS=0;\n";
    print RF "SET SQL_LOG_BIN=0;\n";
    print RF "SET SQL_LOG_OFF=1;\n";
    print RF "SET UNIQUE_CHECKS=0;\n";
    print RF "\n";



    foreach $table (@tables) {
        
        $table =~ s/.?$db.?\.//;
        $table =~ s/[\'\`]//g;
        #$table = lc($table);

        $of = "$tmpd/$db/$table.data";

        # limits for certain known large tables
        $where = "";
        if ($db eq 'opensips' && $table eq 'acc') {
            $where = "WHERE time >= '$big_tables_date_start'";
        }
        if ($db eq 'netcall' && $table eq 'pcaps') {
            $where = "WHERE ts1 >= 1386032554";
        }

        $sql = "SELECT * FROM $table $where INTO OUTFILE '$of'";
        print "   $db.$table  $where\n";
        $dbh->do($sql) || die $dbh->errstr;

        print RF "LOAD DATA INFILE '$of' INTO TABLE $table;\n";
    }

    close(RF);

    $dbh->disconnect() || die;
}

$dbhL->do("unlock tables") || die $dbh->errstr;
$dbhL->disconnect() || die;

$t3 = time;
$tmin = ($t3 - $t2)/60.0;

printf("\nSUCCESS. total time = %.2f min\n", $tmin);
