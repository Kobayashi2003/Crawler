"""Inline-param parsing: bool flag shorthand (`:deep` == `:deep=true`)."""
import sys, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.cli.registry import (Command, CommandError, Param, build_kwargs,
                              parse_input)

fails = []


def check(name, cond):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        fails.append(name)


# A command with one bool and one str param.
cmd = Command("sync", lambda ctx: None, "SYNC", "x",
              params=(Param("artist", "str"), Param("deep", "bool", False)))


def kwargs(text):
    _name, positional, pairs = parse_input(text)
    return build_kwargs(cmd, positional, pairs)


# parse_input records a bare key as None, a key= as '', a key=v as 'v'.
check("bare key parses to None", parse_input("sync:deep")[2] == {"deep": None})
check("key= parses to ''", parse_input("sync:deep=")[2] == {"deep": ""})
check("key=v parses to 'v'", parse_input("sync:deep=false")[2] == {"deep": "false"})

# The requirement: `:deep` == `:deep=true`.
check("bare bool flag is True", kwargs("sync:deep") == {"deep": True})
check("explicit true matches", kwargs("sync:deep=true") == {"deep": True})
check("explicit false still works", kwargs("sync:deep=false") == {"deep": False})

# Mixed with another param.
check("flag among other params", kwargs("sync:artist=hane,deep") == {"artist": "hane", "deep": True})
check("flag before other params", kwargs("sync:deep,artist=hane") == {"artist": "hane", "deep": True})

# A bare non-bool param is an error (a value is required).
try:
    kwargs("sync:artist")
    check("bare non-bool needs a value", False)
except CommandError:
    check("bare non-bool needs a value", True)

# An empty explicit value for a bool is NOT the flag shorthand -> still invalid.
try:
    kwargs("sync:deep=")
    check("deep= (empty) is rejected, not treated as flag", False)
except CommandError:
    check("deep= (empty) is rejected, not treated as flag", True)

print("\n" + ("ALL PASS" if not fails else f"FAILURES: {fails}"))
sys.exit(1 if fails else 0)
