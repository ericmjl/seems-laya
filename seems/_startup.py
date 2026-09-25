"""Interpreter-startup hook, executed by the seems-laya.pth file in site-packages.

Makes judgment syntax work in plain .py files under a plain ``python``: any
module the translator can rewrite is translated before it compiles, every other
file passes through untouched. The language core is standard-library only, so
the startup cost is one small import.

Opt out for a process with SEEMS_AUTOLOAD=off (or SEEMS_PY=off for just the
.py hook).
"""
import os

if os.environ.get("SEEMS_AUTOLOAD", "1").strip().lower() not in ("0", "off", "false", "no"):
    try:
        from . import importer

        importer.install()
        importer.install_py()
    except Exception:  # never break the interpreter that hosts us
        pass

# Opt-in compiler patch for hosts that compile code themselves (marimo kernels
# are multiprocessing-spawned children; they inherit this env var from the
# seems-marimo wrapper and patch here, before marimo compiles any cell).
if os.environ.get("SEEMS_COMPILE_PATCH", "") == "1":
    try:
        from ._marimo_patch import install as _install_compile_patch

        _install_compile_patch()
    except Exception:  # never break the interpreter that hosts us
        pass
