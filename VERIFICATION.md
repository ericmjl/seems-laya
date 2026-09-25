# Verification

The numbers in the upstream repository ([kavehmz/seems-lang](https://github.com/kavehmz/seems-lang),
`VERIFICATION.md`, recorded 2026-09-19 against `jev-1.13.0`) describe the same language and
test suite answered by TypeSafe's hosted Jev. This fork answers with Laya, so its numbers
live here. Same six examples, byte-identical to upstream, different judge.

## Tests without network

```
python -m pytest        ->  72 passed
```

These prove the language mechanics only. They run against `seems.testing.FakeLaya`, so they
need neither the model nor a network.

## Live check: in-process, Apple Silicon (MPS), laya 0.3.20, `LAYA_MODEL=english` (2026-09-24)

```sh
python tools/live_check.py
```

| example | exit | judgments | unsure | requests | tokens | seconds |
| --- | --- | --- | --- | --- | --- | --- |
| 01 is vs seems | 0 | 10 | 2 | 4 | 422 | 2.3 |
| 02 support triage | 0 | 32 | 2 | 8 | 2,240 | 0.7 |
| 03 handling unsure | 0 | 6 | 4 | 6 | 255 | 0.2 |
| 04 comparing two values | 0 | 9 | 0 | 9 | 618 | 0.3 |
| 05 with pip libraries | 0 | 30 | 1 | 20 | 1,905 | 0.9 |
| 06 more python | 1 | 10 | 0 | 5 | 635 | 0.3 |

Seconds are wall clock per whole example. Each example runs in a fresh process, so the
first request pays the checkpoint load (~2 s); steady-state, a batched request answers in
tens of milliseconds (example 03: six requests in 111 ms of model time). Upstream's Jev
table, measured on other hardware over the network, had 3.1 / 1.0 / 4.4 / 3.9 / 2.4 / 1.0
seconds for the same programs. Cost is $0.00 everywhere: the tokens column counts what a
hosted API would have billed for.

## Same run, `LAYA_MODEL=typed-decisions`

| example | exit | unsure | seconds |
| --- | --- | --- | --- |
| 01 | 0 | 3 | 3.7 |
| 02 | 0 | 7 | 4.5 |
| 03 | 0 | 4 | 2.6 |
| 04 | 0 | 1 | 2.9 |
| 05 | 0 | 2 | 4.7 |
| 06 | 1 | 0 | 4.0 |

The checkpoint fine-tuned on customer-service workflows is *more* unsure on these review
and intent tasks than the base English checkpoint, not less. Checkpoint choice is a real
decision, not a formality.

## Findings

1. **Laya 0.3.20 is not thread-safe on macOS.** The runtime sends independent requests side
   by side; concurrent `Router.predict()` calls abort the whole process with an MPS
   command-buffer assertion (`_status < MTLCommandBufferStatusCommitted`). Both
   `seems/client.py` and `tools/laya_server.py` therefore serialize model access with a
   lock. The cost is small: the runtime already batches same-state questions, and a local
   forward pass is milliseconds, so cross-request parallelism buys little locally. The
   same code path parallelizes happily against a Laya server on a GPU box.
2. **Example 06 hits `Unsure` where Jev did not.** `intent is one of leave, complain` came
   back 0.64 (base) / 0.67 (typed-decisions) against the 0.75 bar, and the example has no
   `unsure:` branch there. This is the language's designed safety behavior doing its job on
   a weaker judge: programs written against Jev's calibration can need explicit `unsure:`
   branches under Laya. We left the example byte-identical to upstream on purpose; the
   traceback is the result.
3. **The base English checkpoint distributes probability more diffusely than Jev.** Unsure
   counts moved per example: 2/10 vs upstream's 2, 2/32 vs 3, 4/6 vs 3, 0/9 vs 1, 1/30 vs 5
   on the pass side, but the failures concentrate on mixed-sentiment and multi-intent
   judgments. The model card's warning (soft calibration trails argmax accuracy) is
   visible here: sharper thresholds need criteria, a fine-tuned checkpoint, or a lower
   `sure at` bar.
4. **Determinism is a real upgrade.** Upstream measured Jev wobbling up to 0.05 between
   identical requests. Laya re-answers identically, and the cache makes repeat runs free
   twice over.
5. **Latency moved from network-shaped to load-shaped.** Against Jev, time followed round
   trips. Against a local Laya, time follows checkpoint loads: warm, the same programs
   that took 1-4 seconds upstream finish in 0.2-0.9 seconds.

The comparison is indicative, not a controlled benchmark: different machine, different
network, upstream's numbers recorded inside their container on 2026-09-19.
