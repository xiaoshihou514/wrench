# :wrench: wrench

[![Rye](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/rye/main/artwork/badge.json)](https://rye.astral.sh)

A simple build utility for your C project.

```bash
rye install wrench-build
# or if you don't mind polluting the environment
pip install wrench-build
```

## Why and how

Consider a simple project:

```
decode.h decode.c
emulate.c
execute.c execute.h
fetch.c fetch.h
instr.h
register.c register.h
utils.c utils.h
```

The dependency graph looks like this:

![dependencies](https://github.com/xiaoshihou514/wrench/assets/108414369/7f282e97-adb7-4940-ba95-18df1fafc4a8)

To build it manually, you have to run:

```bash
gcc -c execute.c -o out/execute.o
gcc -c fetch.c -o out/fetch.o
gcc -c register.c -o out/register.o
gcc -c utils.c -o out/utils.o
gcc -c decode.c -o out/decode.o
gcc -c emulate.c -o out/emulate.o
gcc out/execute.o out/fetch.o out/register.o out/utils.o out/decode.o out/emulate.o -o emulate
```

That's very error prone and also gets really boring after a while, you may want to write a make file (or maybe tell chatgpt to write it).

```make
CC      = gcc
all:    emulate
decode.o:       decode.c decode.h instr.h register.h utils.h
emulate:        emulate.o decode.o execute.o fetch.o register.o utils.o
emulate.o:      emulate.c decode.h execute.h fetch.h instr.h register.h utils.h
execute.o:      execute.c execute.h instr.h register.h utils.h
fetch.o:        fetch.c fetch.h register.h utils.h
register.o:     register.c register.h
utils.o:        utils.c register.h utils.h
```

Let's be honest, this is very hard to read and very cumbersome to write. Since C compiling follows simple rules, we can automate this. To do the same thing with wrench-build, just run `wrb emulate` to tell it what you want it to generate.

```
CC=gcc
CFLAGS=
Trying to build out/execute.o
gcc -c execute.c -o out/execute.o
Trying to build out/utils.o
gcc -c utils.c -o out/utils.o
Trying to build out/decode.o
gcc -c decode.c -o out/decode.o
Trying to build out/register.o
gcc -c register.c -o out/register.o
Trying to build out/fetch.o
gcc -c fetch.c -o out/fetch.o
Trying to build out/emulate.o
gcc -c emulate.c -o out/emulate.o
Trying to build emulate
gcc out/execute.o out/utils.o out/decode.o out/register.o out/fetch.o out/emulate.o -o emulate
```

Now `wrb` will read all your files and sort out the includes and give you the output. :tada:

OK, now that we can compile stuff easily we may wish to run something, maybe `valgrind` or a linter, or just some tests.

You can write a `Wrenchfile`, the full supported fields are listed below:

```
CC = clang
MY_VAR = -Iheaders
CFLAGS = -Wall -Werror -g $(MY_VAR)
BUILD = target1 target2
LIBDIRS = lib1 lib2 $(ERROR)
LIB= map set hash
ERROR =lib3

SHELL= fish

main(nvim -l -): task1, task2
  vim.print({hello = "world"})

task1(): task2
  set foo ${CFLAGS}
  echo $foo

task3(bash):
 if [ ${SHELL} == "lib3" ]; then
     echo ${SHELL}
 fi

task2():
  echo "fish"
```

## Credits

Wrench-build is a python rewrite of `cb` written by Duncan White (originally version was in Perl).
