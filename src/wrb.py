import os
from sys import argv
from subprocess import call
from parsy import regex, string, ParseError


# prints out lovely bold green text
def info(msg: str):
    print(f"\033[92m\033[1m{msg}\033[0m")


# whether f2 is new than f1
def newer(f1: str, f2: str) -> bool:
    if os.path.exists(f2):
        return os.path.getmtime(f1) < os.path.getmtime(f2)
    else:
        return False


# run the compiler and wait for it to finish
def compile(compiler: str, flags: list[str], input: list[str], output: str):
    cmd = [compiler] + flags + input + ["-o"] + [output]
    info(f"Trying to build {output}")
    # the output is newer than all of its input, no need to rebuild
    if all(map(lambda i: newer(i, output), input)):
        return
    print(" ".join(cmd))
    if call(cmd, cwd=os.getcwd()) != 0:
        exit(-1)


# creates shared lib from object file
def ar(input: list[str], output: str):
    info(f"Trying to build {output}")
    cmd = ["ar", "rcs"] + [output] + input
    print(" ".join(cmd))
    if call(cmd) != 0:
        exit(-1)


# parses #include "foo.h" -> foo
include = (
    (regex("[ \t]*") << string('#include "')) >> regex(".*?\\.h") << regex('".*\n')
)


# recursively get the dependencies
def get_deps(file: str) -> set[str]:
    result: set[str] = set()
    for line in open(file).readlines():
        try:
            # got a local include
            dep_header = include.parse(line)
            # add all dependencies in header
            result = result.union(get_deps(dep_header))
            # add all dependencies in implementation
            dep = dep_header[:-1] + "c"
            # it'd better not be it self, which happens when x.c included x.h
            # and it'd better exist, since maybe x.h was a single header
            if dep != file and os.path.exists(dep):
                result.add(dep)
                result = result.union(get_deps(dep))
        except ParseError:
            pass
    return result


def build_dir(out: str) -> str:
    return "out/" + out


# Produces out, either * or *.a
def satisfy(out: str, cc: str, flags: list[str], cwd: str):
    out_striped: str
    input: str
    shared_lib = out.endswith(".a")
    if shared_lib:
        # wants shared library
        input = out[:-1] + "c"
        out_striped = out[:-1] + "o"
    else:
        # wants executable
        input = out + ".c"
        out_striped = out + ".o"
    # compile the object files that we need
    deps: list[str] = list(get_deps(input))
    deps_out: list[str] = list(map(lambda s: s[:-1] + "o", deps))
    for dep, dep_out in zip(deps, deps_out):
        compile(cc, flags + ["-c"], [dep], build_dir(dep_out))
    # finally we compile itself
    compile(cc, flags + ["-c"], [input], build_dir(out_striped))
    # and link all the stuff together
    final_input = list(map(build_dir, deps_out + [out_striped]))
    if shared_lib:
        ar(final_input, out)
    else:
        compile(cc, flags, final_input, out)


def ensure_build_dir():
    build_directory: str = os.getcwd() + "/out"
    if not os.path.exists(build_directory):
        os.makedirs(build_directory)


# api for wr.py
def build(reqs: list[str], cc: str, flags: list[str]):
    for requirement in reqs:
        satisfy(requirement, cc, flags, os.getcwd())


# Main
if __name__ == "__main__":
    cc: str = "gcc"
    flags: list[str] = []

    # read flags from Wrenchfile
    if os.path.exists("Wrenchfile"):
        for line in open("Wrenchfile").readline():
            pass

    ensure_build_dir()
    build(argv[1:], cc, flags)
