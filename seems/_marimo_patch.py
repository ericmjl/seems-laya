"""Teach the in-process compiler judgment syntax.

For hosts that compile code themselves -- marimo compiles notebook cells with
builtin ``compile`` -- the import hook never sees the source. This module
patches ``builtins.compile`` instead: string sources that mention a judgment
verb are translated first, everything else passes through byte for byte.

It also binds ``__seems__`` and ``Unsure`` as builtins, so translated code
resolves its runtime names without any import or prelude, and cell source
stays exactly as the programmer wrote it (line numbers included).

Opt in per process: ``python -m seems.marimo edit notebook.py`` (or the
``seems-marimo`` console script). Never installed automatically.
"""
from __future__ import annotations

import builtins
import sys

from . import runtime
from .translator import DESCRIBING, RELATING, translate

JUDGMENT_MARKS = tuple(sorted({*DESCRIBING, *RELATING, "unsure"}))

_original_compile = None
_original_exec = None
_cache: dict[int, str] = {}


def _translate_source(source: str, args, kwargs) -> str:
    key = hash(source)
    translated = _cache.get(key)
    if translated is None:
        filename = kwargs.get("filename")
        if filename is None and len(args) > 1 and isinstance(args[1], str):
            filename = args[1]
        translated = translate(source, filename or "<seems>").python
        _cache[key] = translated
    return translated


def _patched_compile(source, /, *args, **kwargs):
    if isinstance(source, str) and any(mark in source for mark in JUDGMENT_MARKS):
        try:
            source = _translate_source(source, args, kwargs)
        except Exception:  # let the real compiler surface real syntax errors
            pass
    return _original_compile(source, *args, **kwargs)


def _patched_exec(source, globals=None, locals=None, /, **kwargs):
    # exec(str) compiles inside C and never sees the patched compile builtin,
    # so hosts that exec cell strings need this shim too.
    translated = False
    if isinstance(source, str) and any(mark in source for mark in JUDGMENT_MARKS):
        try:
            source = _patched_compile(source, "<seems>", "exec")
            translated = True
        except Exception:  # let the real exec raise the real syntax error
            pass
    if translated and globals is None:
        # Bare exec(code) inside this wrapper would bind assignments to the
        # wrapper frame's locals while thunks read module globals. Give the
        # cell the caller's globals as one namespace instead.
        return _original_exec(source, sys._getframe(1).f_globals)
    return _original_exec(source, globals, locals, **kwargs)


def install() -> None:
    """Turn judgment syntax on for every string compiled in this process."""
    global _original_compile, _original_exec
    if _original_compile is None:
        _original_compile = builtins.compile
        builtins.compile = _patched_compile
    if _original_exec is None:
        _original_exec = builtins.exec
        builtins.exec = _patched_exec
    builtins.__seems__ = runtime
    builtins.Unsure = runtime.Unsure
