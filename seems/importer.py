"""Run Seems files and let ``import`` find them.

After ``seems.install()`` a plain ``import desk`` loads ``desk.seems`` from
anywhere on ``sys.path``, next to ordinary ``.py`` modules.

After ``seems.install_py()`` (done automatically at interpreter start when the
distribution's .pth hook is installed, see ``seems/autoload.py``) plain ``.py``
files may contain judgment syntax too: any module whose source the translator
can rewrite is translated before it compiles. Files without judgment syntax
pass through byte for byte, so everything already on ``sys.path`` behaves
exactly as before.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import linecache
import os
import sys

try:
    from importlib._bootstrap import _call_with_frames_removed
except ImportError:  # pragma: no cover
    def _call_with_frames_removed(f, *args, **kwargs):
        return f(*args, **kwargs)

from . import runtime
from .translator import DESCRIBING, RELATING, compile_seems

SUFFIX = ".seems"
PY_SUFFIX = ".py"

_HOOK_STATE = {"seems": False, "py": False, "hook": None}

# Cheap pre-filter: the translator is byte-identical on plain Python, so a false
# positive only costs one tokenize pass. Real judgment syntax always contains a
# judgment verb (or the unsure branch keyword) somewhere in the file.
JUDGMENT_MARKS = tuple(sorted({*DESCRIBING, *RELATING, "unsure"}))


def module_globals(extra=None):
    """Names every Seems module gets for free."""
    names = {"__seems__": runtime, "Unsure": runtime.Unsure}
    names.update(extra or {})
    return names


class SeemsLoader(importlib.machinery.SourceFileLoader):
    def path_stats(self, path):
        # No bytecode cache: the translator decides what the code means.
        raise OSError("seems modules are not cached")

    def source_to_code(self, data, path, *, _optimize=-1):
        source = importlib.util.decode_source(data) if isinstance(data, bytes) else data
        return compile_seems(source, path)

    def exec_module(self, module):
        module.__dict__.update(module_globals())
        super().exec_module(module)


class PySeemsLoader(importlib.machinery.SourceFileLoader):
    """A .py loader that speaks judgment syntax.

    Same file, same line numbers, same bytecode caching as ordinary Python: the
    translator rewrites only the judgment lines and leaves every other byte in
    place, so a module without judgments is indistinguishable from stock
    (the test suite feeds 120 standard library files through it).

    Every module whose code references ``__seems__`` (i.e. every module the
    translator actually rewrote) also gets the runtime names, like .seems
    modules do. The check is on the compiled code, not on this process having
    done the translation: a warm bytecode cache skips source_to_code entirely.
    Unrelated modules are left byte-identical and name-clean, because third
    parties do introspect module namespaces.
    """

    def source_to_code(self, data, path, *, _optimize=-1):
        source = importlib.util.decode_source(data) if isinstance(data, bytes) else data
        if any(mark in source for mark in JUDGMENT_MARKS):
            return compile_seems(source, path)
        return super().source_to_code(data, path, _optimize=_optimize)

    def source_to_code(self, data, path, *, _optimize=-1):
        source = importlib.util.decode_source(data) if isinstance(data, bytes) else data
        self._translated = any(mark in source for mark in JUDGMENT_MARKS)
        if self._translated:
            return compile_seems(source, path)
        return super().source_to_code(data, path, _optimize=_optimize)

    def _cache_bytecode(self, *args, **kwargs):
        # Never cache translated code: the .pyc would validate against the
        # untouched source on disk, so a warm cache would keep running judgment
        # syntax even with the hook off (SEEMS_PY=off, or after uninstall).
        # Plain modules cache exactly as before, so the environment keeps its
        # normal startup speed.
        if getattr(self, "_translated", False):
            return
        return super()._cache_bytecode(*args, **kwargs)

    def get_code(self, fullname):
        code = super().get_code(fullname)
        self._needs_globals = code is not None and _references_seems(code)
        return code

    def exec_module(self, module):
        code = self.get_code(module.__name__)  # sets the flag; warms the bytecode cache
        if code is None:
            raise ImportError(f"cannot load module {module.__name__!r}")
        if getattr(self, "_needs_globals", False):
            module.__dict__.update(module_globals())
        _call_with_frames_removed(exec, code, module.__dict__)


def _references_seems(code):
    """True if this code object (or anything nested in it) uses __seems__.

    Judgment syntax compiles into thunks and lambdas, so the reference lives in
    a nested code object, not in the module-level one.
    """
    stack = [code]
    while stack:
        current = stack.pop()
        if "__seems__" in current.co_names:
            return True
        stack.extend(k for k in current.co_consts if hasattr(k, "co_consts"))
    return False


def install():
    """Teach ``import`` to load .seems files. Safe to call more than once."""
    _HOOK_STATE["seems"] = True
    _ensure_hook()


def install_py():
    """Teach ``import`` to run judgment syntax inside plain .py files.

    Opt out for the process with SEEMS_PY=off. Safe to call more than once.
    """
    if os.environ.get("SEEMS_PY", "").strip().lower() in ("off", "0", "false", "no"):
        return
    _HOOK_STATE["py"] = True
    _ensure_hook()


def _ensure_hook():
    """(Re)build the single path hook that serves both suffixes.

    One hook, not two: importlib keeps one FileFinder per directory in
    path_importer_cache, so the first hook that claims a directory owns every
    suffix in it. Separate hooks would make .seems and .py modules mutually
    invisible depending on installation order.
    """
    current = _HOOK_STATE.get("hook")
    if current is not None and getattr(current, "_seems_py", False) == _HOOK_STATE["py"]:
        return
    if current is not None:
        sys.path_hooks.remove(current)
    details = [
        (SeemsLoader, [SUFFIX]),
        ((PySeemsLoader, [PY_SUFFIX]) if _HOOK_STATE["py"]
         else (importlib.machinery.SourceFileLoader, importlib.machinery.SOURCE_SUFFIXES)),
        (importlib.machinery.ExtensionFileLoader, importlib.machinery.EXTENSION_SUFFIXES),
        (importlib.machinery.SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES),
    ]
    maker = importlib.machinery.FileFinder.path_hook(*details)

    def seems_hook(path):
        return maker(path)

    seems_hook._seems = True
    seems_hook._seems_py = _HOOK_STATE["py"]
    sys.path_hooks.insert(0, seems_hook)
    _HOOK_STATE["hook"] = seems_hook
    sys.path_importer_cache.clear()


def run_source(source: str, filename: str = "<seems>", argv=None, name="__main__"):
    """Translate and run a program. Returns its globals."""
    install()
    linecache.cache[filename] = (len(source), None, source.splitlines(keepends=True), filename)
    code = compile_seems(source, filename)
    scope = module_globals({"__name__": name, "__file__": filename, "__builtins__": __builtins__})
    if argv is not None:
        sys.argv = list(argv)
    exec(code, scope)
    runtime.flush()
    return scope


def run_path(path: str, argv=None):
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    folder = os.path.dirname(os.path.abspath(path))
    if folder not in sys.path:
        sys.path.insert(0, folder)
    return run_source(source, path, argv=argv)
