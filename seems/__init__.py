"""Seems: Python plus judgments.

Created by kavehmz (https://github.com/kavehmz/seems-lang); this distribution
answers the judgments with Laya instead of TypeSafe Jev.

    if ticket.text asks for a refund and ticket.amount > 500:
        ...
    unsure:
        ...

Use ``python -m seems run program.seems`` or ``seems.install()`` followed by a
normal ``import`` of a ``.seems`` file.
"""
from .client import LayaClient, LayaError
from .importer import install, install_py, run_path, run_source
from .runtime import (NO, UNSURE, YES, JudgmentDef, Kind, Level, Member, Pick, Rating, Scale,
                      Truth, Unsure, ask, certainty, clear_cache, configure, each, flush,
                      stats, sure_level, trace)
from .translator import SeemsSyntaxError, compile_seems, translate

def autoload():
    """Judgment syntax in plain .py files, for this process.

    Installed automatically at interpreter start when the distribution's .pth
    hook is in site-packages; call this to turn it on by hand.
    """
    install()
    install_py()


__version__ = "0.1.0"

__all__ = [
    "LayaClient", "LayaError", "autoload", "install", "install_py", "run_path", "run_source", "NO", "UNSURE", "YES",
    "JudgmentDef", "Kind", "Level", "Member", "Pick", "Rating", "Scale", "Truth", "Unsure",
    "ask", "certainty", "clear_cache", "configure", "each", "flush", "stats", "sure_level",
    "trace", "SeemsSyntaxError", "compile_seems", "translate",
]
