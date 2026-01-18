#!/usr/bin/env bash

dv="dv"
VAR=${VAR:-$dv}
if [ "$VAR" = "$dv" ]; then
  echo "Hello!"
else
  echo "Goodbye!"
fi

VAR="not_dv"
if [ "$VAR" = "$dv" ]; then
  echo "Hello!"
else
  echo "Goodbye!"
fi

iterations=$(seq 3)
for i in $iterations; do
  echo "Number: $i"
done
