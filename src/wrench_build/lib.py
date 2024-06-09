from typing import override
from parsy import ParseError, seq, string, regex


# prints out lovely bold green text
def info(msg: str):
    print(f"\033[92m\033[1m{msg}\033[0m")


# not so lovely bold red text
def error(msg: str):
    print(f"\033[91m\033[1m{msg}\033[0m")


class Var:
    name: str

    def __init__(self, name: str):
        self.name = name

    @override
    def __repr__(self):
        return f"var({self.name})"


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
        try:
            key_val = var_parser.parse(line.strip())  # type: ignore[reportAny]
            lookup[key_val["name"]] = key_val["val"]
        except ParseError:
            break
    resolve(lookup)
    return lookup  # type: ignore[reportReturnType]
