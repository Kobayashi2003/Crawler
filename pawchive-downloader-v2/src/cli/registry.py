"""Declarative command registry: one parse/validate/dispatch path for the shell.

Each command is registered with its parameter specs, so input parsing, type
validation, completion and `help` all read a single source of truth. Handlers
stay plain functions ``handler(ctx, **typed_params)``.

This module is imported normally (not hot-reloaded), so `Command` instances
stay type-stable across reloads of the commands module.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple


class CommandError(Exception):
    """A user-input problem. Printed as a message, never as a traceback."""


class ExitShell(Exception):
    """Raised by the `exit` command to leave the prompt loop."""


@dataclass(frozen=True)
class Param:
    name: str
    kind: str = 'str'          # str | bool | int | date
    default: Any = ''
    help: str = ''
    choices: Tuple[str, ...] = ()   # allowed values, if a fixed set

    def values(self) -> str:
        """Short hint of accepted values, for help output."""
        if self.choices:
            return '|'.join(self.choices)
        return {'bool': 'true|false', 'date': 'YYYY-MM-DD', 'int': 'N'}.get(self.kind, '')


@dataclass(frozen=True)
class Command:
    name: str
    handler: Callable
    group: str
    summary: str
    params: Tuple[Param, ...] = ()
    aliases: Tuple[str, ...] = ()

    def signature(self) -> str:
        """`name:key=,key=` hint for help and error messages."""
        if not self.params:
            return self.name
        return f"{self.name}:" + ",".join(f"{p.name}=" for p in self.params)


def build_map(commands: List[Command]) -> Dict[str, Command]:
    """Name and alias -> Command. Registration order is preserved for help."""
    out: Dict[str, Command] = {}
    for cmd in commands:
        for key in (cmd.name, *cmd.aliases):
            if key in out:
                raise ValueError(f"duplicate command name: {key}")
            out[key] = cmd
    return out


# ==================== Input parsing ====================

def parse_input(text: str) -> Tuple[str, str, Dict[str, Optional[str]]]:
    """Split one input line into `(name, positional, key=value pairs)`.

    Canonical form is ``command:key=value,key=value``; a bare remainder after a
    space (``help sync``) is returned as `positional` and mapped to the
    command's first parameter. A bare ``key`` with no ``=`` maps to ``None`` --
    a flag whose meaning depends on the param type (True for a bool).
    """
    text = text.strip()
    head, colon, rest = text.partition(':')
    if not colon:
        name, _, positional = text.partition(' ')
        return name.strip(), positional.strip(), {}

    pairs: Dict[str, Optional[str]] = {}
    for part in rest.split(','):
        part = part.strip()
        if not part:
            continue
        key, eq, value = part.partition('=')
        key = key.strip()
        if not key:
            raise CommandError(f"Bad parameter '{part}': use key=value.")
        pairs[key] = value.strip() if eq else None
    return head.strip(), '', pairs


def resolve(command_map: Dict[str, Command], name: str) -> Command:
    """Exact name or alias, else a unique prefix; anything else is an error
    with suggestions."""
    if name in command_map:
        return command_map[name]

    prefixed = {cmd.name: cmd for key, cmd in command_map.items()
                if key.startswith(name)}
    if len(prefixed) == 1:
        return next(iter(prefixed.values()))

    if prefixed:
        options = ', '.join(sorted(prefixed))
        raise CommandError(f"'{name}' is ambiguous: {options}")
    close = difflib.get_close_matches(name, command_map.keys(), n=3, cutoff=0.6)
    hint = f" Did you mean: {', '.join(close)}?" if close else " Type 'help'."
    raise CommandError(f"Unknown command '{name}'.{hint}")


# ==================== Validation ====================

_TRUE, _FALSE = {'true', '1', 'yes', 'y', 'on'}, {'false', '0', 'no', 'n', 'off'}


def _coerce(param: Param, raw: Optional[str]) -> Any:
    if raw is None:
        # Bare flag (`:deep`): only a bool takes no value, and means true.
        if param.kind == 'bool':
            return True
        raise CommandError(f"'{param.name}' needs a value, e.g. {param.name}=...")
    if param.kind == 'bool':
        low = raw.lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise CommandError(f"'{param.name}' must be true or false, got '{raw}'.")
    if param.kind == 'int':
        try:
            return int(raw)
        except ValueError:
            raise CommandError(f"'{param.name}' must be a number, got '{raw}'.")
    if param.kind == 'date':
        try:
            datetime.fromisoformat(raw)
        except ValueError:
            raise CommandError(
                f"'{param.name}' must be a date (YYYY-MM-DD or ISO), got '{raw}'.")
        return raw
    if param.choices and raw not in param.choices:
        raise CommandError(
            f"'{param.name}' must be one of {param.values()}, got '{raw}'.")
    return raw


def build_kwargs(cmd: Command, positional: str, pairs: Dict[str, str]) -> Dict[str, Any]:
    """Validate raw input against the command's params; returns typed kwargs."""
    if positional and not cmd.params:
        raise CommandError(f"'{cmd.name}' takes no parameters.")
    if pairs and not cmd.params:
        raise CommandError(f"'{cmd.name}' takes no parameters.")

    kwargs: Dict[str, Any] = {}
    if positional:
        first = cmd.params[0]
        kwargs[first.name] = _coerce(first, positional)

    by_name = {p.name: p for p in cmd.params}
    for key, raw in pairs.items():
        param = by_name.get(key)
        if param is None:
            raise CommandError(
                f"Unknown parameter '{key}' for '{cmd.name}'. Usage: {cmd.signature()}")
        if key in kwargs:
            raise CommandError(f"Parameter '{key}' given twice.")
        kwargs[key] = _coerce(param, raw)
    return kwargs
