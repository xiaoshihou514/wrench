# prints out lovely bold green text
def info(msg: str):
    print(f"\033[92m\033[1m{msg}\033[0m")


# not so lovely bold red text
def error(msg: str):
    print(f"\033[91m\033[1m{msg}\033[0m")
