"""Minimal dynamic plugin loader with hot reload.

Every call re-reads the target file from disk, so edits take effect immediately
without restarting the program. Used for two things:

  * hot-reloadable commands  -- ``dynamic_get('COMMAND_MAP', 'src/cli.py')``
  * optional format plugins  -- see ``formatter.py`` and ``plugins/format_plugin.py``

Unlike a bare importlib reload, a missing plugin file is tolerated: the
decorator helpers fall back to a no-op so the app still runs without any
``plugins/`` files present.
"""

from __future__ import annotations

import importlib.util
import pathlib
import types
from typing import Any

# Project root (parent of src/).
_BASE_DIR = pathlib.Path(__file__).resolve().parent.parent


def _load_module(module_filename: str) -> types.ModuleType:
    path = _BASE_DIR / module_filename
    if not path.exists():
        raise FileNotFoundError(f"Plugin file not found: {path}")

    module_path = pathlib.Path(module_filename)
    module_name = module_path.stem

    # Files under src/ are loaded as part of the 'src' package so their relative
    # imports (from .models import ...) resolve.
    if 'src' in module_path.parts:
        full_name, package = 'src.' + module_name, 'src'
    else:
        full_name, package = module_name, None

    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {module_filename}")

    module = importlib.util.module_from_spec(spec)
    if package:
        module.__package__ = package
    spec.loader.exec_module(module)
    return module


def dynamic_get(var_name: str, module_filename: str, default=None) -> Any:
    """Read a module-level variable from a file, reloading it each call."""
    if not module_filename:
        raise ValueError("module_filename must be provided")
    module = _load_module(module_filename)
    value = getattr(module, var_name, None)
    if value is None:
        if default is None:
            raise AttributeError(f"Variable '{var_name}' not found in {module_filename}")
        return default
    return value


def dynamic_call(func_name: str, module_filename: str, *args: Any, default=None, **kwargs: Any) -> Any:
    """Call a function from a file, reloading it each call.

    With no positional/keyword args, returns the resolved function itself so it
    can be used as a decorator (see ``formatter.py``). If the plugin file is
    missing or the function is absent, ``default`` is used.
    """
    if not module_filename:
        raise ValueError("module_filename must be provided")
    try:
        module = _load_module(module_filename)
        func = getattr(module, func_name, None)
    except FileNotFoundError:
        func = None
    if func is None:
        func = default
    if not callable(func):
        raise AttributeError(f"Function '{func_name}' not found or not callable in {module_filename}")
    if not args and not kwargs:
        return func  # decorator / late-binding use
    return func(*args, **kwargs)


def plugin_hook(func_name: str, module_filename: str):
    """Decorator factory that applies an optional plugin wrapper at call time.

    Given ``@plugin_hook('format_post_plugin', 'plugins/format_plugin.py')`` on
    ``f``, each call resolves the plugin's ``format_post_plugin(inner)`` (a
    decorator) and runs it around ``f``. If no plugin is present, ``f`` runs
    unchanged. Resolving per-call is what makes edits hot-reload.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            plugin = dynamic_call(func_name, module_filename, default=lambda inner: inner)
            return plugin(func)(*args, **kwargs)
        wrapper.__name__ = getattr(func, '__name__', func_name)
        return wrapper
    return decorator


__all__ = ["dynamic_get", "dynamic_call", "plugin_hook"]
