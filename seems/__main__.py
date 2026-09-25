"""Command line:  python -m seems run|translate|check FILE"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback

from . import runtime
from .importer import run_path
from .translator import translate

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))


def _print_error(err):
    """A traceback without the frames of the Seems runtime itself."""
    tb = traceback.TracebackException.from_exception(err)
    for item in (tb, *_chain(tb)):
        item.stack = traceback.StackSummary.from_list(
            [f for f in item.stack if not f.filename.startswith(_PKG_DIR) and "<frozen" not in f.filename])
    sys.stderr.write("".join(tb.format()))


def _chain(tb):
    seen = []
    for link in (tb.__cause__, tb.__context__):
        if link is not None:
            seen.append(link)
            seen.extend(_chain(link))
    return seen


def main(argv=None):
    parser = argparse.ArgumentParser(prog="seems", description="Seems: Python plus judgments")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a .seems program")
    run.add_argument("--trace", help="write every request and judgment to this file as JSON lines")
    run.add_argument("--no-cache", action="store_true", help="ask Laya again even for known answers")
    run.add_argument("--sure", type=float, help="certainty level, default 0.75")
    run.add_argument("--stats", action="store_true", help="print totals at the end")
    run.add_argument("file")
    run.add_argument("args", nargs=argparse.REMAINDER)
    tr = sub.add_parser("translate", help="print the Python that a .seems file becomes")
    tr.add_argument("--standalone", action="store_true", help="add the runtime import line")
    tr.add_argument("file")
    check = sub.add_parser("check", help="check syntax only")
    check.add_argument("file")
    sub.add_parser("preload", help="load the Laya checkpoint now (it downloads on first use)")
    serve = sub.add_parser("serve", help="serve Laya over HTTP, the LAYA_URL endpoint (needs the laya package)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--model", default=None, help="default checkpoint: english | multilingual | typed-decisions")
    serve.add_argument("--device", default=None, help="torch device, for example mps or cuda")
    options = parser.parse_args(argv)

    if options.command == "serve":
        from .serve import main as serve_main
        extra = []
        if options.model:
            extra += ["--model", options.model]
        if options.device:
            extra += ["--device", options.device]
        return serve_main(["--host", options.host, "--port", str(options.port), *extra])

    if options.command == "preload":
        from .client import LayaClient
        started = time.perf_counter()
        try:
            answer = LayaClient().ask("preload", {
                "q0": {"type": "noul", "instructions": "Does this sentence contain a word?"}},
                runtime.settings.model)
        except Exception as err:
            sys.stderr.write(f"[seems] could not reach Laya: {err}\n")
            return 1
        sys.stdout.write(f"[seems] ready: model {answer.get('model')} answered in "
                         f"{time.perf_counter() - started:.1f}s\n")
        return 0

    if options.command == "run":
        if options.trace:
            os.environ["SEEMS_TRACE"] = options.trace
        if options.no_cache:
            runtime.configure(cache=False)
        if options.sure:
            runtime.configure(sure=options.sure)
        try:
            run_path(options.file, argv=[options.file, *options.args])
        except SystemExit:
            raise
        except KeyboardInterrupt:
            return 130
        except BaseException as err:
            _print_error(err)
            return 1
        finally:
            sys.stdout.flush()
            if options.stats:
                totals = runtime.stats()
                sys.stderr.write(
                    f"[seems] {totals['judgments']} judgments, {totals['cached']} from cache, "
                    f"{totals['requests']} requests, {totals['input_tokens']} tokens, "
                    f"${totals['cost_usd']:.6f}\n")
        return 0

    with open(options.file, encoding="utf-8") as handle:
        source = handle.read()
    try:
        result = translate(source, options.file, standalone=getattr(options, "standalone", False))
        compile(result.python, options.file, "exec")
    except SyntaxError as err:
        _print_error(err)
        return 1
    if options.command == "translate":
        sys.stdout.write(result.python)
    else:
        print(f"{options.file}: ok ({len(result.changed)} lines use Seems syntax)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
