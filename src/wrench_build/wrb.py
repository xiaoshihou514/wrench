import os

from sys import argv
from subprocess import call
from typing import override
from parsy import regex, string, ParseError, seq
from .lib import info, error

help_str = """
wrench-build
Build C files without checking all its dependencies
Usage: wrb [--clean|--allclean] [target1, target2, ...]
  --clean               Clean build files of target1, target2, ...
  --allclean            Compile all targets from scratch
""".strip()


# whether f2 is new than f1
def newer(f1: str, f2: str) -> bool:
    if os.path.exists(f1):
        return os.path.getmtime(f2) < os.path.getmtime(f1)
    else:
        return False


# run the compiler and wait for it to finish
def compile(compiler: str, flags: list[str], input: list[str], output: str):
    cmd = [compiler] + flags + input + ["-o"] + [output]
    info(f"Trying to build {output}")
    # the output is newer than all of its input, no need to rebuild
    # we force a rebuild if the Wrenchfile was updated
    if all(
        map(
            lambda i: (not os.path.exists("Wrenchfile") or newer(output, "Wrenchfile"))
            and newer(output, i),
            input,
        )
    ):
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


spaces = regex(r"\s*")
# any spaces + #include + any spaces + " + name of header + .h" + any spaces
include = (
    (string("#include") << regex(r"\s+") << string('"'))
    >> regex("[^.]+")
    << string(r'.h"')
)


# recursively get the dependencies
def get_deps(file: str) -> set[str]:
    result: set[str] = set()
    for line in open(file).readlines():
        try:
            # got a local include
            dep: str = include.parse(line.strip())
            dep_header = dep + ".h"
            # add all dependencies in header
            result = result.union(get_deps(dep_header))
            # add all dependencies in implementation
            dep_impl = dep + ".c"
            # it'd better not be it self, which happens when x.c included x.h
            # and it'd better exist, since maybe x.h was a single header
            if dep_impl != file and os.path.exists(dep_impl):
                result.add(dep_impl)
                result = result.union(get_deps(dep_impl))
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


class Var:
    name: str

    def __init__(self, name: str):
        self.name = name

    @override
    def __repr__(self):
        return f"var({self.name})"


def resolve_single(name: str, table: dict[str, list[str | Var]]):
    val = table[name]
    result: list[str] = []
    for str_or_var in val:
        if isinstance(str_or_var, str):
            result.append(str_or_var)
        else:
            var = str_or_var.name
            var_val = table.get(var)
            if var_val is None:
                error("{var} used but not declared")
                exit(-1)
            else:
                resolve_single(var, table)
                result += table[var]  # type: ignore[reportAttributeAccessIssue]
    table[name] = result  # type: ignore[reportAttributeAccessIssue]


def resolve(table: dict[str, list[str | Var]]):
    for name in table:
        if all(map(lambda sv: sv is str, table[name])):
            pass
        else:
            resolve_single(name, table)


var_parser = seq(
    name=regex(r"[^=\s]+") << spaces << string("="),
    val=(spaces >> regex(".+")).map(
        lambda args: list(
            map(
                lambda arg: Var(arg[2:-1])
                if arg.startswith("$(") and arg.endswith(")")
                else arg,
                args.split(),
            )
        )
    ),
)


def read_vars() -> dict[str, list[str]]:
    if os.path.exists("Wrenchfile"):
        lookup: dict[str, list[str | Var]] = {}
        for line in open("Wrenchfile").readlines():
            try:
                key_val = var_parser.parse(line.strip())  # type: ignore[reportAny]
                lookup[key_val["name"]] = key_val["val"]
            except ParseError:
                pass
        resolve(lookup)
        return lookup  # type: ignore[reportReturnType]
    else:
        return {"CC": ["gcc"], "CFLAGS": []}


def rm(files: list[str]):
    cmd = ["rm"] + files
    if len(cmd) > 1:
        print(" ".join(cmd))
        if call(cmd) != 0:
            exit(-1)


# api functions
def build(reqs: list[str], cc: str, flags: list[str]):
    for requirement in reqs:
        satisfy(requirement, cc, flags, os.getcwd())


def clean(targets: list[str]):
    for target in targets:
        info(f"Trying to clean build output of {target}")
        target_impl: str
        shared_lib = target.endswith(".a")
        if shared_lib:
            # wants shared library
            target_impl = target[:-1] + "c"
        else:
            # wants executable
            target_impl = target + ".c"
        rm(
            list(
                filter(
                    os.path.exists,
                    list(
                        map(
                            lambda s: build_dir(s[:-1] + "o"),
                            list(get_deps(target_impl).union({target_impl})),
                        )
                    )
                    + [target],
                )
            )
        )


# Main
if __name__ == "__main__":
    targets_argv = argv[1:]

    cleanup = False
    exit_after_clean = False
    # check arguments
    if len(argv) > 1:
        opt = argv[1]
        # give the user some help
        if opt == "--help":
            print(help_str)
            exit(0)

        # whether we are asked to clean up
        cleanup = opt in ["--clean", "--allclean"]
        exit_after_clean = opt == "--clean"
        if cleanup:
            targets_argv = targets_argv[1:]

    # read flags from Wrenchfile
    vars = read_vars()
    for k, v in vars.items():
        print(f"{k}={' '.join(v)}")
    cc = "gcc" if vars.get("CC") is None else vars["CC"][0]
    # flags is CFLAGS + L(LIBDIRS) + l(LIBS)
    flags = vars.get("CFLAGS", [])
    flags += list(map(lambda s: "-L" + s, vars.get("LIBDIRS", [])))
    flags += list(map(lambda s: "-l" + s, vars.get("LIBS", [])))
    targets = set(vars.get("BUILD", [])).union(set(targets_argv))

    # cleanup logic
    if cleanup:
        clean(list(targets))
        if exit_after_clean:
            exit(0)

    ensure_build_dir()
    build(list(targets), cc, flags)
