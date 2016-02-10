#!/bin/sh 

echo "Disabling slow_query_log"

echo "set global slow_query_log = 0;" | mysql mysql
echo "set global long_query_time = 10;" | mysql mysql

