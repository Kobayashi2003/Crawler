"""Interactive prompt: command completion + persistent history.

Uses ``prompt_toolkit`` when available (Tab completion, arrow-key history,
fuzzy substring matching). If it is not installed, everything degrades to
plain ``input()`` so the program still runs with only ``requests``.
"""

import sys
from typing import Callable, List, Optional

try:
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import History
    from prompt_toolkit.shortcuts import PromptSession as _PTSession
    HAS_PROMPT_TOOLKIT = True
except Exception:  # pragma: no cover - optional dependency
    HAS_PROMPT_TOOLKIT = False
    Completer = object  # type: ignore
    History = object    # type: ignore


if HAS_PROMPT_TOOLKIT:

    class _JSONHistory(History):
        """Seed prompt history from the stored command history."""

        def __init__(self, storage):
            super().__init__()
            self.storage = storage

        def load_history_strings(self) -> List[str]:
            try:
                # Newest-first is what prompt_toolkit expects.
                return [r.command for r in self.storage.get_history(limit=1000)]
            except Exception:
                return []

        def store_string(self, string: str) -> None:
            # Persisted separately by the command loop; nothing to do here.
            pass

    class _CommandCompleter(Completer):
        """Substring-match completion over the (hot-reloaded) command names."""

        def __init__(self, get_commands: Callable[[], dict]):
            self.get_commands = get_commands

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if ':' in text:  # typing params, not a command name
                return
            low = text.lower()
            for cmd in sorted(self.get_commands().keys()):
                if not low or low in cmd:
                    yield Completion(cmd, start_position=-len(text), display=cmd)

    class _ArtistCompleter(Completer):
        """Fuzzy completion over artists by index, id, name and alias."""

        def __init__(self, artists):
            # (search keys, display, value-to-insert)
            self.entries = []
            for i, a in enumerate(artists, 1):
                keys = [str(i), a.name.lower(), a.id.lower()]
                if a.alias:
                    keys.append(a.alias.lower())
                label = f"{i}. {a.display_name()} [{a.id}]"
                self.entries.append((keys, label, a.id))

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor.lower()
            seen = set()
            for keys, label, value in self.entries:
                if (not text or any(text in k for k in keys)) and label not in seen:
                    seen.add(label)
                    yield Completion(value, start_position=-len(document.text_before_cursor),
                                     display=label)


class CLIPromptSession:
    """Main ``> `` prompt with history and command completion."""

    def __init__(self, storage, get_commands: Callable[[], dict]):
        # prompt_toolkit needs an interactive terminal; with piped/redirected
        # stdin it can't run, so fall back to plain input() there.
        self._plain = not HAS_PROMPT_TOOLKIT or not _is_interactive()
        if self._plain:
            self._session = None
        else:
            self._session = _PTSession(
                history=_JSONHistory(storage),
                completer=_CommandCompleter(get_commands),
                complete_while_typing=False,
            )

    def prompt(self, message: str = "> ") -> str:
        if self._plain:
            return input(message).strip()
        try:
            return self._session.prompt(message).strip()
        except (EOFError, KeyboardInterrupt):
            raise
        except Exception:
            self._plain = True  # terminal misbehaving; stay on plain input
            return input(message).strip()


def _is_interactive() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def prompt_artist(message: str, artists) -> str:
    """Prompt for an artist selection, with completion when available."""
    if not HAS_PROMPT_TOOLKIT or not _is_interactive():
        return input(message).strip()
    try:
        from prompt_toolkit import prompt as _prompt
        return _prompt(message, completer=_ArtistCompleter(artists)).strip()
    except (EOFError, KeyboardInterrupt):
        raise
    except Exception:
        return input(message).strip()
