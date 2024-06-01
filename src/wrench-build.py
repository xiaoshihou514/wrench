import os
from sys import argv
from subprocess import call
from parsy import regex, string, ParseError


# parses #include "foo.h" -> foo
include = (
    (regex("[ \t]*") << string('#include "')) >> regex(".*?\\.h") << regex('".*\n')
)


# run the compiler and wait for it to finish
def compile(compiler: str, flags: list[str], input: list[str], output: str | None):
    cmd: list[str]
    if output is not None:
        cmd = [compiler] + flags + input + ["-o"] + [output]
    else:
        cmd = [compiler] + flags + input
    print(" ".join(cmd))
    if call(cmd, cwd=cwd) != 0:
        exit(-1)


# recursively get the dependencies
def get_deps(file: str) -> set[str]:
    result: set[str] = set()
    lines = open(file).readlines()
    for line in lines:
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


# Produces out, either * or *.a
def satisfy(out: str, cc: str, flags: list[str], cwd: str):
    out_striped: str
    input: str
    if out.endswith(".a"):
        # wants shared library
        input = out[:-1] + "c"
        out_striped = out[:-1] + "o"
    else:
        # wants executable
        input = out + ".c"
        out_striped = out + ".o"
    # the object files that we need
    deps: list[str] = list(get_deps(input))
    deps_out: list[str] = list(map(lambda s: s[:-1] + "o", deps))
    for dep, dep_out in zip(deps, deps_out):
        compile(cc, flags + ["-c"], [dep], dep_out)
    # finally we compile itself
    compile(cc, flags + ["-c"], [input], out_striped)
    # and link all the stuff together
    compile(cc, flags, deps_out + [out_striped], out)


# Main
cc: str = "gcc"
flags: list[str] = []
cwd = os.getcwd()

# stuff we need to build
reqs = argv[1:]
for requirement in reqs:
    satisfy(requirement, cc, flags, cwd)
