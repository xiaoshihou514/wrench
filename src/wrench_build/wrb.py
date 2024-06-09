import os
from os.path import exists
from subprocess import call, Popen, PIPE
from sys import argv

from parsy import ParseError, regex, string

from wrench_build.lib import info, read_vars_till_invalild

help_str = """
wrench-build
Build C files without checking all its dependencies
Usage:
wrb [--clean|--allclean] [target1, target2, ...]
wrb --gen-dep-graph
  --clean               Clean build files of target1, target2, ...
  --allclean            Compile all targets from scratch
  --gen-dep-graph       Generates an SVG dependency graph, requires the `dot` command
""".strip()


# whether f2 is new than f1
def newer(f1: str, f2: str) -> bool:
    if exists(f1):
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
            lambda i: (not exists("Wrenchfile") or newer(output, "Wrenchfile"))
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


# any spaces + #include + any spaces + " + name of header + .h" + any spaces
include = (
    (string("#include") << regex(r"\s+") << string('"'))
    >> regex("[^.]+")
    << string(r'.h"')
)


# recursively get the dependencies
def get_deps(file: str) -> set[str]:
    result: set[str] = get_deps_single(file)
    for dep in list(result):
        result = result.union(get_deps(dep))
    return set(filter(lambda s: not s.endswith(".h"), result))


# gets dependencies of a single module
def get_deps_single(file: str) -> set[str]:
    result: set[str] = set()
    if not exists(file):
        return result
    for line in open(file).readlines():
        try:
            # got a local include
            dep: str = include.parse(line.strip())
            result.add(dep + ".h")
            # add all dependencies in header
            # add all dependencies in implementation
            dep_impl = dep + ".c"
            # it'd better not be it self, which happens when x.c included x.h
            # and it'd better exist, since maybe x.h was a single header
            if dep_impl != file and exists(dep_impl):
                result.add(dep_impl)
        except ParseError:
            pass
    return result


def build_dir(out: str) -> str:
    return "out/" + out


def get_input(out: str) -> str:
    if out.endswith(".a"):
        # wants shared library
        return out[:-1] + "c"
        # out_striped = out[:-1] + "o"
    else:
        # wants executable
        return out + ".c"
        # out_striped = out + ".o"


def get_out_striped(out: str) -> str:
    if out.endswith(".a"):
        # wants shared library
        return out[:-1] + "o"
    else:
        # wants executable
        return out + ".o"


# Produces out, either * or *.a
def satisfy(out: str, cc: str, flags: list[str], cwd: str):
    shared_lib = out.endswith(".a")
    input = get_input(out)
    out_striped = get_out_striped(out)
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
    if not exists(build_directory):
        os.makedirs(build_directory)


def read_vars() -> dict[str, list[str]]:
    if exists("Wrenchfile"):
        return read_vars_till_invalild(open("Wrenchfile").readlines())
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
                    exists,
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
def main():
    targets_argv = argv[1:]

    cleanup = False
    exit_after_clean = False
    graph = False

    # check arguments
    if len(argv) > 1:
        opt = argv[1]
        # --help
        if opt == "--help":
            print(help_str)
            exit(0)

        # --clean / --allclean
        cleanup = opt in ["--clean", "--allclean"]
        exit_after_clean = opt == "--clean"
        if cleanup:
            targets_argv = targets_argv[1:]

        # --gen-dep-graph
        if opt == "--gen-dep-graph":
            graph = True
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

    # only generate graph
    if graph:
        handle = Popen(
            ["dot", "-Tsvg", "-o", "dependencies.svg"], stdin=PIPE, text=True
        )
        dot_file = ['digraph "dependency-graph" {']
        modules = set()
        for target in map(get_input, targets):
            modules = modules.union(get_deps(target))
            modules.add(target)
        for module in modules:
            deps = get_deps_single(module[:-2] + ".c").union(
                get_deps_single(module[:-2] + ".h")
            )
            deps = set(map(lambda s: s[:-2], deps))
            for dep in deps:
                if dep != module[:-2]:
                    dot_file.append(f'    "{module[:-2]}" -> "{dep}";')
        dot_file.append("}")
        _ = handle.communicate(input="\n".join(dot_file))
        exit(0)

    ensure_build_dir()
    build(list(targets), cc, flags)


if __name__ == "__main__":
    main()
