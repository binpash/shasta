#!/bin/sh

if [ ! -d libdash_tests/ ]; then
  git clone https://github.com/binpash/libdash.git
  mv libdash/test libdash_tests
  rm -rf libdash
fi

pip install .. libdash
