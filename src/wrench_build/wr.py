import re
from itertools import takewhile
from subprocess import Popen, PIPE
from sys import argv
from os.path import exists
from typing import override
from parsy import ParseError, seq, string, regex

from wrench_build.lib import info

# from .lib import error, read_vars_till_invalild

help_str = """
wrench
Run tasks defined in Wrenchfile
Usage:
    wr [task1, task2, ...]
""".strip()


######################################################
def error(msg: str):
    print(f"\033[91m\033[1m{msg}\033[0m")


spaces = regex(r"\s*")

var_parser = seq(
    name=regex(r"[^=\s]+") << spaces << string("="),
    val=(spaces >> regex(".+")).map(
        lambda args: list(
            map(
                lambda arg: (
                    Var(arg[2:-1])
                    if arg.startswith("$(") and arg.endswith(")")
                    else arg
                ),
                args.split(),
            )
        )
    ),
)


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


def read_vars_till_invalild(lines: list[str]) -> dict[str, list[str]]:
    lookup: dict[str, list[str | Var]] = {}
    while True:
        line = lines.pop(0).strip()
        if not line:
            continue
        try:
            key_val = var_parser.parse(line.strip())  # type: ignore[reportAny]
            lookup[key_val["name"]] = key_val["val"]
        except ParseError:
            lines.insert(0, line)
            break
    resolve(lookup)
    return lookup  # type: ignore[reportReturnType]


decl_parser = seq(
    name=regex((r"[^(\s]+")) << spaces,
    shell=(string("(") >> regex(r"[^)]*") << string(")")).map(
        lambda s: re.split(r"\s+", s)
    ),
    dependencies=(spaces >> string(":") >> spaces >> regex("[^\n]*")).map(
        lambda s: filter(lambda dep: dep, re.split(r"\s*,\s*", s))
    ),
)

pattern = re.compile(r"\$\{(\w+)\}")


def str_interpolate(line: str, lookup: dict[str, str]):
    return pattern.sub(
        lambda match: lookup.get(match.group(1), f"${{{match.group(1)}}}"), line
    )


######################################################


class Task:
    shell: list[str]
    dependencies: list[str]
    body: str

    def __init__(self, shell: list[str], dependencies: list[str], body: str):
        self.shell = shell
        self.dependencies = dependencies
        self.body = body

    @override
    def __repr__(self):
        return f"Task: {self.shell} | {' '.join(self.dependencies)} | {self.body}"

    def run(self, lookup: dict[str, "Task"]):
        if self.dependencies:
            for dep in self.dependencies:
                maybe_task = lookup.get(dep)
                if maybe_task is None:
                    error(f"{dep} is declared as a dependency but not defined")
                    exit(-1)
                else:
                    info(f"running dependency {dep}")
                    maybe_task.run(lookup)
        handle = Popen(self.shell, stdin=PIPE, text=True)
        _ = handle.communicate(input=self.body)


def read_tasks(lines: list[str], vars: dict[str, list[str]]) -> dict[str, Task]:
    result = {}
    lookup = {k: " ".join(v) for k, v in vars.items()}
    while True:
        if not lines:
            break

        line = lines.pop(0).strip()
        if not line:
            continue

        # parse a single task
        decl_line = line
        try:
            decl = decl_parser.parse(decl_line)  # type: ignore[reportAttributeAccessIssue]
            if decl["shell"] == [""]:
                decl["shell"] = vars["SHELL"]
        except ParseError:
            error(f"Cannot parse \n{decl_line}\nas task declaration")
            exit(-1)

        # we use the indent of the first line as the indent for the block
        body_start = lines.pop(0)
        indent = len(list(takewhile(lambda x: x == " ", body_start)))
        # don't forget to replace the ${VAR}
        body = [str_interpolate(body_start[indent:], lookup)]
        while True:
            if not lines:
                break
            maybe_body = lines.pop(0)[indent:-1]
            if not maybe_body:
                break
            body.append(str_interpolate(maybe_body, lookup))

        task = Task(decl["shell"], decl["dependencies"], "\n".join(body))  # type: ignore[reportAttributeAccessIssue]
        result[decl["name"]] = task
    return result


# Main
def main():
    tasks: list[str] = ["main"]
    # Check arguments
    if len(argv) > 1:
        if argv[1] == "--help":
            print(help_str)
            exit(0)
        tasks = argv[1:]

    if not exists("Wrenchfile"):
        print("Wrenchfile not found")
        exit(-1)
    lines = open("Wrenchfile").readlines()

    vars = read_vars_till_invalild(lines)
    all_tasks = read_tasks(lines, vars)

    for task in tasks:
        maybe_task = all_tasks.get(task)
        if maybe_task is None:
            error(f"{task} was asked to run but is not defined")
            exit(-1)
        else:
            info(f"running {task}")
            maybe_task.run(all_tasks)


if __name__ == "__main__":
    main()
