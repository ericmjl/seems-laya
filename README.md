# Seems, judged by Laya

Seems is a programming language with judgment built in. It is Python plus a few words: a
condition can be plain English, and the decision model answers it.

This repository is a variant of [kavehmz/seems-lang](https://github.com/kavehmz/seems-lang)
with one thing changed: the judgments come from
[Laya](https://github.com/NandhaKishorM/laya) (Convai Innovations, Apache 2.0) instead of
TypeSafe's hosted [Jev](https://typesafe.ai) API. All credit for the language, the
translator, the runtime and the playground goes to the upstream project; this fork exists
to ask one question: **what does the language feel like when the judge is open-weight,
local, and free?**

```python
if order.total > 500 and ticket.text asks for a refund:
    send_to_manager(ticket)
unsure:
    send_to_human(ticket)
```

- `order.total > 500` is **exact**. Python answers it.
- `ticket.text asks for a refund` is a **judgment**. Laya answers it with a probability.
- A judgment is **yes, no or unsure**. `unsure:` is a real branch of `if`.

## What changed from upstream

| | upstream (kavehmz/seems-lang) | this repo |
| --- | --- | --- |
| Decision model | TypeSafe Jev, hosted API | Laya, open weights (ModernBERT/mmBERT) |
| Where it runs | TypeSafe's cloud | your machine: in-process (`pip install laya`) or `tools/laya_server.py` |
| API key | `TYPESAFE_API_KEY`, per-token billing | none; compute is yours |
| Question types | Noul, Choice, Score | the same `noul` / `choice` / `score` contract |
| The language, translator, runtime, playground | — | unchanged apart from names |

The seam is one method: `client.ask(state, questions, model)`. The translator never sees a
model, and the runtime only wants an envelope of `{model, answers, usage}` back. Laya
happens to speak almost the same envelope Jev does, so `seems/client.py` is where the
whole swap lives.

- **Language guide:** see `LANGUAGE.md` (also served at `/guide` inside the playground).
- **The brief the project started from:** `BRIEF.md` (upstream's; kept for history).
- **Upstream's measured results with Jev:** [VERIFICATION.md in kavehmz/seems-lang](https://github.com/kavehmz/seems-lang/blob/main/VERIFICATION.md).

## Install

The language is a normal pip package. In any Python 3.10+ environment:

```sh
pip install seems-laya            # the language; stdlib only, talks to LAYA_URL if set
pip install "seems-laya[laya]"    # + the open-weight judge, in-process
```

Then write a program:

```python
# triage.seems
import seems

if ticket.amount > 500 and ticket.text asks for a refund:
    queue = "manager"
else:
    queue = "support"
unsure:
    queue = "human review"
```

and run or import it like any Python:

```sh
seems run triage.seems            # or: python -m seems run triage.seems
seems translate triage.seems      # the Python it becomes, for editors and linters
seems check triage.seems
seems preload                     # download the checkpoint before the first judgment
seems serve --host 0.0.0.0        # the LAYA_URL endpoint, e.g. on a GPU box
```

```python
import seems; seems.install()     # then .seems files import like modules:
import triage                     # triage.seems
```

The first judgment loads the checkpoint (~1.7 GB into `~/.cache/huggingface`, once);
after that everything is local. Without the `[laya]` extra, set `LAYA_URL` to a `seems
serve` endpoint (this machine or elsewhere) and the language stays stdlib-only.

## Run the playground (Docker)

Everything runs in containers. Nothing is installed on the host. You need Docker (or
Podman with `docker compose`); there is no API key, because Laya runs next to the app.

```sh
cp .env.example .env
docker compose up --build -d
docker compose run --rm laya python -m seems preload   # download the checkpoint once (~1.7 GB)
```

Open localhost:3004. The first `up` builds an image with PyTorch in it; the `preload`
pulls the Laya checkpoint into a shared volume, so restarts are cheap. After that, every
judgment is a local forward pass: no network egress, no bill.

```sh
docker compose run --rm app pytest                        # 72 tests, no model needed
docker compose run --rm app python tools/live_check.py    # every example against real Laya
docker compose run --rm -T app python tools/build_guide.py > docs/index.html
docker compose run --rm app python -m seems run --stats examples/02_support_triage.seems
docker compose down
```

Two ways to reach the model, picked by `LAYA_URL`:

- `LAYA_URL` **set** (the compose default, `http://laya:8000`): the app talks to
  `tools/laya_server.py`, a small standard-library HTTP wrapper around a Laya `Router`.
  The app container keeps the upstream promise that the language itself needs only the
  Python standard library.
- `LAYA_URL` **unset**: the `laya` package is imported in-process. Simplest for scripts
  and notebooks: `pip install laya`, then just run your `.seems` file.

`LAYA_MODEL` picks the checkpoint: `english` (default, `convaiinnovations/laya`),
`multilingual`, `typed-decisions`, `router` (auto-route per request), or any Hugging Face
id, such as a checkpoint you fine-tuned on your own domain.

## What to look at

**Playground** (localhost:3004)

- Six examples, from the core idea to pip libraries. Edit them or write your own.
- The editor colours the judgment verb and the English that goes to Laya.
- **Judgments** tab: every judgment with its probability, the exact question and state
  Laya got, and how long the batch took. Cost is now your own compute, so it reads $0.
- **Translated Python** tab: the Python your program became. Same line numbers.
- The `sure at` slider moves the bar between yes, unsure and no. Try 0.95 on example 1.

**Support desk app** (localhost:3004/desk)

- A real small web service: Flask routes, a SQLite table, JSON API.
- It is written in Seems: `app/desk.seems`. The server loads it with a plain `import desk`.
- Send the sample tickets. The rule `amount > 500` runs in code. Laya reads the text.
  With the model local, a ticket's judgment is a forward pass, not a round trip.

## How it works

```
program.seems ──► translator ──► plain Python ──► Python runs it
                  (no AI, fixed rules)               │
                                                     ▼
                                   runtime: lazy judgments, 3-valued logic,
                                   batching, cache, trace ──► Laya (local)
```

1. **A superset of Python.** Every Python file is already valid Seems, so classes,
   exceptions, async, pytest and every pip library work from day one. The test suite feeds
   120 standard library files through the translator and they come out byte for byte the
   same.
2. **A strict grammar.** The translator uses Python's own tokenizer and fixed rules. No
   model reads the source. In valid Python two plain words never stand next to each other
   (`text seems angry`), so the new syntax cannot clash with real code.
3. **Line numbers never move.** Each source line becomes exactly one Python line.
4. **Three Laya question types, three language features.**

 | Laya | Seems | Example |
 | --- | --- | --- |
 | noul | judgment verbs, `judgment` block | `if reply contradicts policy:` |
 | choice | `kind` block | `team(text) == team.billing` |
 | score | `scale` block | `anger(text) >= anger.annoyed` |

5. **Unsure is part of the language.** Below 0.25 is no, above 0.75 is yes, between is
   unsure. `and`, `or`, `not` follow three-valued logic. Without an `unsure:` branch, an
   unsure judgment raises `Unsure`, so a program cannot act on a guess by accident.
6. **Fast without effort.** Decision models are cheapest when independent questions about
   the same state travel together. The language does that for you: judgments are lazy,
   `if / elif` asks all its branches in one batch, and an exact "no" skips Laya completely.
   With Laya behind the runtime, a batch of questions is one forward pass (~33 ms on a
   modest GPU, hundreds of milliseconds on CPU), so the batching matters less for latency
   here than it does against a hosted API, and more for keeping the questions sharp.
7. **Repeatable.** Every answer is cached by model, state and question, so a second run is
   instant and identical. A local model is also deterministic: same input, same forward
   pass, same answer, where the hosted API wobbled by up to 0.05 between identical
   requests.

## Measured

Upstream measured Jev in the source repository (link above). The equivalent Laya runs are
in [VERIFICATION.md](VERIFICATION.md), recorded 2026-09-24 on Apple Silicon, laya 0.3.20:

- Five of six examples pass with the base `english` checkpoint; example 06 raises `Unsure`
  on an intent judgment where Jev was confident enough, which is the language's safety
  behavior doing its job on a weaker judge.
- Warm, the examples finish in 0.2-0.9 seconds (upstream: 1-4 seconds over the network),
  and cost $0.00.
- Laya 0.3.20 is not thread-safe on macOS; the runtime's parallel requests are serialized
  at the client (see VERIFICATION.md, finding 1).

To reproduce:

```sh
docker compose run --rm app python tools/live_check.py
```

## Limits

- The tests prove the language mechanics. They do not prove that Laya judges well in your
  domain, and Laya's accuracy is more checkpoint-dependent than Jev's: the published
  zero-shot base checkpoint is much weaker than its fine-tuned siblings.
- The English checkpoint reads at most 512 tokens per question (state included). Long
  tickets get truncated; `multilingual` reads more.
- Fewer than ~20 options per `choice` is the publisher's recommendation; Jev accepted up
  to 255.
- Laya reads literally. `text seems angry` is a loose question. For anything that matters,
  declare a `judgment` with yes and no criteria.
- Math, counting, dates and exact lookups belong in Python.
- Editors and linters do not know Seems. `python -m seems translate file.seems` gives them
  Python.
- Judgments block the thread while they wait. There is no `await` form yet.
- The playground runs any code you type, inside the container. It only accepts requests
  from a local page. Do not expose the port.

## Files

| Path | What |
| --- | --- |
| `seems/translator.py` | Seems to Python. Tokens in, same lines out. |
| `seems/runtime.py` | Lazy judgments, three-valued logic, batching, cache, trace. |
| `seems/client.py` | The call to Laya: HTTP to `LAYA_URL`, or in-process. Standard library only. |
| `seems/importer.py` | `import` hook for `.seems` files, and `run_path`. |
| `seems/__main__.py` | `python -m seems run / translate / check / preload`. |
| `app/desk.seems` | The support desk service, written in Seems. |
| `app/server.py`, `app/static/` | Playground API and pages. |
| `examples/` | Six programs and their data. |
| `docs/index.html` | The language guide page, built from `tools/guide_source.html`. |
| `seems/serve.py` | `seems serve`: small HTTP wrapper around a local Laya Router (the `LAYA_URL` endpoint). |
| `tools/laya_server.py` | Compat wrapper: `python tools/laya_server.py` == `python -m seems serve`. |
| `tests/` | 72 tests with a fake Laya. `tools/live_check.py` uses the real one. |

## Acknowledgements

- [kavehmz/seems-lang](https://github.com/kavehmz/seems-lang) is the source of this
  project: the language design, translator, runtime, playground and docs are upstream's
  work, imported at commit `e47728b` and modified in plain sight (see the git history;
  commit 1 is the untouched tree).
- [Laya](https://github.com/NandhaKishorM/laya) by Convai Innovations provides the
  decision model, under Apache 2.0.
- Seems was built for [TypeSafe Jev](https://typesafe.ai); this variant is an
  experiment, not a criticism of that design.
