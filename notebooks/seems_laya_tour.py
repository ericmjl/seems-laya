import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import importlib.util
    import subprocess
    import sys
    from pathlib import Path

    import seems
    from seems import translate
    from seems.client import mode

    mo.md(
        f"""
        # Seems, judged by Laya

        **Seems is Python with typed decisions built into the language.**
        A condition can be plain English; an open-weight decision model (Laya) answers it
        with a probability; `unsure:` is a real branch of `if`.

        This notebook shows the language running in a **regular Python environment**:
        a normal venv, a normal `python`, no Docker, no API key, no bill.

        Setup: seems `{seems.__version__}` (pip-installed), judge backend `{mode()}`
        (in-process Laya on this machine), interpreter startup hook active.
        """
    )
    return Path, mo, seems, subprocess, sys, translate


@app.cell
def _(mo):
    source = """import seems

    tickets = [
        {"amount": 950, "text": "Charged twice for March, I want my money back today."},
        {"amount": 40,  "text": "The app crashes whenever I open settings."},
    ]

    for t in tickets:
        if t["amount"] > 500 and t["text"] asks for a refund:
            queue = "manager"
        else:
            queue = "support"
        unsure:
            queue = "human review"
        print(f"${t['amount']:>4}  ->  {queue}")
    """

    mo.md(
        f"""
    ## 1. The language

    A superset of Python: a deterministic translator rewrites only the judgment lines,
    using Python's own tokenizer, keeping line numbers exactly where you wrote them.

    ```python
    {source}
    ```
        """
    )
    return (source,)


@app.cell
def _(mo, source, translate):
    result = translate(source, "triage.seems")

    mo.vstack([
        mo.md("**The Python that actually runs** (same line numbers; a traceback points at your file):"),
        mo.ui.code_editor(result.python, language="python"),
    ])
    return


@app.cell
def _(Path, mo, subprocess, sys):
    demo = Path("notebooks/examples/triage.py")
    file_text = demo.read_text()

    out = subprocess.run([sys.executable, demo], capture_output=True, text=True, timeout=300)

    mo.vstack([
        mo.md(
            """
            ## 2. It is just a `.py` file

            No marker, no special extension, no launcher. It runs under a plain `python`
            because the environment has Seems installed and the startup hook active.
            Live output:
            """
        ),
        mo.ui.code_editor(file_text, language="python"),
        mo.md(f"""
        ```
        {out.stdout.strip()}
        ```
        The `$40` ticket landed in `human review`: the model was not sure enough to act,
        so the `unsure:` branch caught it. That is the language's whole deal.
        """),
    ])
    return


@app.cell
def _(mo, sys):
    sys.path.insert(0, "notebooks/examples")
    import triage  # a plain import: goes through the startup hook, becomes judgment-aware

    mo.md(
        f"""
        ## 3. And it imports like any module

        A plain `import triage` (no launcher, no extension trick) loaded the file above
        through the hook, ran it, and the module's globals are live here:
        `len(triage.tickets)` = {len(triage.tickets)}.

        Anything that imports your package gets judgments: Flask apps
        (`gunicorn app:app`), workers, pytest files, notebooks.
        """
    )
    return


@app.cell
def _(mo):
    ticket_box = mo.ui.text_area(
        value="Charged twice for March, I want my money back or I cancel the plan.",
        label="Ticket text", full_width=True,
    )
    amount_box = mo.ui.number(start=0, stop=5000, value=950, label="Amount ($)")
    sure_bar = mo.ui.slider(start=0.50, stop=0.99, value=0.75, step=0.01, label="sure at")
    mo.vstack([ticket_box, amount_box, sure_bar])
    return amount_box, sure_bar, ticket_box


@app.cell
def _(amount_box, furious, mo, seems, sure_bar, ticket_box):
    seems.configure(sure=sure_bar.value)

    ticket = ticket_box.value
    amount = amount_box.value

    if amount > 500 and ticket asks for a refund:
        call = "manager"
    elif ticket sounds furious:
        call = "manager"
    else:
        call = "support"
    unsure:
        call = "human review"

    refund = seems.ask("Does the customer ask for a refund?", ticket)
    angry = seems.ask("Does the ticket sound furious or alarming?", ticket)

    badge = {"manager": "\U0001F3C1", "support": "\U0001F6E0", "human review": "\U0001F64B"}[call]
    mo.md(
        f"""
        ### {badge} `{call}`

        This cell contains **judgment syntax directly** -- no `run_source`, no launcher.
        marimo compiled it through the patched compiler; the `unsure:` branch is a real
        branch of the cell.

        | judgment | probability | at bar `{sure_bar.value:.2f}` |
        | --- | --- | --- |
        | asks for a refund | `{refund.p:.3f}` | {refund.verdict()} |
        | sounds furious | `{angry.p:.3f}` | {angry.verdict()} |

        Deterministic: same question, same probability, every run. Cost: **$0.00**,
        it ran on this machine.
        """
    )
    return


@app.cell
def _(mo, seems):
    trace_program = """import seems
    ticket = "Your outage ate our launch, this is unacceptable and I want a refund"
    ticket sounds furious
    ticket asks for a refund
    """

    with seems.trace() as events:
        seems.run_source(trace_program, "<trace-demo>")

    rows = [
        {
            "line": e.get("line"), "judgment": e.get("source"), "question": e.get("question"),
            "p": e.get("p"), "verdict": e.get("verdict"),
        }
        for e in events if e["type"] == "judgment"
    ]
    mo.vstack([
        mo.md("## 4. Every judgment, inspected"),
        mo.ui.table(rows, selection=None),
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ## What the integration buys you

    | surface | judgment syntax? | how |
    | --- | --- | --- |
    | any imported module (apps, workers, pytest) | yes, automatic | the startup hook translates on import |
    | marimo cells | yes, in-cell | run marimo through `seems-marimo` (this notebook) |
    | `python script.py` as `__main__` | use the launcher | `seems run script.py` (CPython compiles `__main__` below the import system) |
    | any other host | opt in | `from seems._marimo_patch import install; install()` |

    The judge is **local and open-weight**: deterministic answers, $0 marginal cost,
    data never leaves the machine. Swap checkpoints with `LAYA_MODEL`
    (`english`, `multilingual`, `typed-decisions`, or your own fine-tune), or serve one
    GPU box with `seems serve` and point `LAYA_URL` at it.

    Next rungs: capture `unsure` judgments, fine-tune your own checkpoint, hot-swap it
    with `LAYA_MODEL=<your-hub-id>`. The language is the loop.
    """)
    return


if __name__ == "__main__":
    app.run()
