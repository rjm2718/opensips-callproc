#!/bin/sh 

echo "Enabling slow_query_log=1, long_query_time=0, log_output='TABLE'"

echo "set global slow_query_log = 1;" | mysql mysql
echo "set global long_query_time = 0;" | mysql mysql
echo "set global log_output = 'TABLE';" | mysql mysql


echo " try 'TRUNCATE mysql.slow_log;'"
