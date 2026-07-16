"""Parameter system: binding, defaults, bool flags, choices, completion,
and the registration-time signature check."""
import sys, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.cli.registry import (Command, CommandError, Param, build_map,
                              param_suggestions, parse_input)

fails = []


def check(name, cond):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        fails.append(name)


# A command with a str, a bool, and an enum param.
cmd = Command("sync", lambda ctx: None, "SYNC", "x",
              params=(Param("artist", "str", ""),
                      Param("deep", "bool", False),
                      Param("sort", "str", "name", choices=("name", "recent"))))


def bind(text):
    _name, positional, pairs = parse_input(text)
    return cmd.bind(positional, pairs)


# --- parse_input records a bare key as None, key= as '', key=v as 'v'.
check("bare key -> None", parse_input("sync:deep")[2] == {"deep": None})
check("key= -> ''", parse_input("sync:deep=")[2] == {"deep": ""})
check("key=v -> 'v'", parse_input("sync:deep=false")[2] == {"deep": "false"})

# --- bind returns EVERY param, defaults applied (single source of truth).
check("defaults applied for all params",
      bind("sync:artist=a") == {"artist": "a", "deep": False, "sort": "name"})

# --- bool flag shorthand: `:deep` == `:deep=true`.
check("bare bool flag is True", bind("sync:deep")["deep"] is True)
check("explicit true", bind("sync:deep=true")["deep"] is True)
check("explicit false", bind("sync:deep=false")["deep"] is False)
check("positional binds to first param", bind("sync hane")["artist"] == "hane")

# --- typed coercion + choices.
try:
    bind("sync:sort=bogus"); check("bad choice raises", False)
except CommandError:
    check("bad choice raises", True)
try:
    bind("sync:artist"); check("bare non-bool needs a value", False)
except CommandError:
    check("bare non-bool needs a value", True)
try:
    bind("sync:deep="); check("empty value for bool is rejected", False)
except CommandError:
    check("empty value for bool is rejected", True)
try:
    bind("sync:nope=1"); check("unknown param rejected", False)
except CommandError:
    check("unknown param rejected", True)

# --- kind is validated at construction.
try:
    Param("x", "bogus"); check("unknown kind rejected", False)
except ValueError:
    check("unknown kind rejected", True)

# --- values() hints drive help and completion.
check("choices hint", Param("s", "str", choices=("a", "b")).values() == "a|b")
check("bool hint", Param("b", "bool").values() == "true|false")
check("date hint", Param("d", "date").values() == "YYYY-MM-DD")
check("str hint is empty", Param("s", "str").values() == "")

# --- completion suggests param names, then a param's values.
names = [insert for insert, _s, _d in param_suggestions(cmd, "")]
check("suggests all param names", set(names) == {"artist", "deep", "sort"})
check("filters by prefix", [i for i, _s, _d in param_suggestions(cmd, "de")] == ["deep"])
used = [i for i, _s, _d in param_suggestions(cmd, "deep=true,")]
check("drops already-used params", "deep" not in used and "artist" in used)
vals = [i for i, _s, _d in param_suggestions(cmd, "sort=")]
check("suggests choice values", vals == ["name", "recent"])
check("suggests bool values", [i for i, _s, _d in param_suggestions(cmd, "deep=")] == ["true", "false"])
_ins, start, _disp = param_suggestions(cmd, "sort=re")[0]
check("value completion replaces the partial", (_ins, start) == ("recent", -2))

# --- registration rejects a handler whose args disagree with declared params.
good = Command("g", lambda ctx, a: None, "G", "x", params=(Param("a"),))
build_map([good])
check("matching signature accepted", True)
bad = Command("b", lambda ctx, a: None, "B", "x", params=(Param("other"),))
try:
    build_map([bad]); check("mismatched signature rejected", False)
except ValueError:
    check("mismatched signature rejected", True)

print("\n" + ("ALL PASS" if not fails else f"FAILURES: {fails}"))
sys.exit(1 if fails else 0)
