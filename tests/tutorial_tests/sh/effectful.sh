#!/bin/sh

f() {
    echo "i am effectful, because I am a function definition"
}

x="i am effectful because i am a bare assignment"
y="i am effectful because i am an assignment on a special built-in" set -- 1
z="i am effectful because... our definition of effectful is conservative" echo "lol"
echo "${w=i am effectful because I am a defaulting assignment}"
echo $(( q += 1)) "i am effectful because i update q"
echo $(( q + 1 )) "i am effectful because arithmetic is dynamically parsed, so we're conservative"
echo "I am not effectful"