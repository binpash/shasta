#!/bin/sh
x=$(echo hi)
(exit 47)
sleep 3 &
kill $!
echo hi | tr a-z A-Z
