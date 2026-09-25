"""Judgment syntax inside plain .py files (the interpreter-startup hook)."""
import importlib.util
import subprocess
import sys
import textwrap

from seems.importer import PySeemsLoader, _references_seems, install_py

PROGRAM = '''\
import seems

ticket = "Please refund my order, charged twice"

if ticket asks for a refund:
    queue = "manager"
else:
    queue = "support"
unsure:
    queue = "human review"

print(queue)
'''

PLAIN = "value = 1 + 1\n"


def loader_for(tmp_path, source, name="m"):
    path = tmp_path / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    return PySeemsLoader(name, str(path))


def test_translated_code_references_the_runtime(tmp_path):
    code = loader_for(tmp_path, PROGRAM).source_to_code(PROGRAM.encode(), "m.py")
    assert _references_seems(code)


def test_plain_python_compiles_untouched(tmp_path):
    loader = loader_for(tmp_path, PLAIN)
    code = loader.source_to_code(PLAIN.encode(), "m.py")
    assert not _references_seems(code)
    assert not getattr(loader, "_translated", True)


def test_translated_code_is_never_bytecode_cached(tmp_path):
    loader = loader_for(tmp_path, PROGRAM)
    loader.source_to_code(PROGRAM.encode(), "m.py")
    assert loader._cache_bytecode(PROGRAM.encode(), "m.py", None, "m") is None  # no-op, no error


def test_end_to_end_import(tmp_path):
    (tmp_path / "rules.py").write_text(textwrap.dedent(PROGRAM), encoding="utf-8")
    code = (
        "import seems, sys\n"
        "from seems.testing import FakeLaya, noul\n"
        "seems.configure(client=FakeLaya(lambda state, question: noul(0.9)), cache=False)\n"
        "seems.autoload()\n"
        f"sys.path.insert(0, {str(tmp_path)!r})\n"
        "import rules\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        env={"SEEMS_AUTOLOAD": "1", "PATH": "/usr/bin:/bin"},
    )
    assert out.returncode == 0, out.stderr
    assert "manager" in out.stdout


def test_opt_out(tmp_path):
    (tmp_path / "rules.py").write_text(textwrap.dedent(PROGRAM), encoding="utf-8")
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(tmp_path)!r})\n"
        "import rules\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        env={"SEEMS_AUTOLOAD": "off", "PATH": "/usr/bin:/bin"},
    )
    assert out.returncode != 0 and "SyntaxError" in out.stderr


def test_install_py_is_idempotent():
    hooks = len([h for h in __import__("sys").path_hooks if getattr(h, "_seems_py", False)])
    install_py()
    install_py()
    again = len([h for h in __import__("sys").path_hooks if getattr(h, "_seems_py", False)])
    assert again in (hooks, hooks + 1)
