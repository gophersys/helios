# Determinism experiment 1 — the P0→P1 pipeline under N blind readers

Date: 2026-08-26. Loop: [`.claude/rules/determinism-loop.md`](../../.claude/rules/determinism-loop.md).
Frozen input: [`products/tracker/repro/transcript.yaml`](../../products/tracker/repro/transcript.yaml)
(36 verbatim Q→A pairs, product "tracker"). Raw outputs: `products/tracker/repro/run{1,2,3}/`.
Instrument: [`tools/compare-instances.py`](../../tools/compare-instances.py) —
canonical-content comparison over a declared PROJECTION: 16 PIR
enum/set/derived features + 16 score levels + 4 record features + the
function item count. Free-text leaves (summary, users, novelty.*, success,
battery-life, timeline) are deliberately outside the projection — "PIR
agreement" is agreement on the projection, never byte-identity. Function
ITEM COUNTS spread 12–16 across instances even where the capability SET
was unanimous; the count is now measured, and item granularity remains a
named residual.
Readers: 3 fresh Opus instances per run, blind to each other, to prior runs,
and to the operator's artifacts. The operator's own extraction (instance-0)
was measured separately against run 1.

## The numbers

| Run | Contracts | Blind-3 overall | PIR | Scores | Verdict |
|---|---|---|---|---|---|
| 1 | v1 (as merged in PR #3/#5) | **34/36 = 94.4%** | 87.5% | **16/16 = 100%** | unanimous `blocked` |
| 2 | v2 (8 conventions, constraint oracle, +5 scale fixes) | **35/36 = 97.2%** | 93.8% | **16/16 = 100%** | unanimous `blocked` |
| 3 | v2 + a loosened `declared-none` generalization | **32/36 = 88.9%** | 87.5% | 93.8% | **SPLIT 2 blocked / 1 go** |
| 4 | v4 = the LANDED contracts (v3 + PR-#6-refutation harmonization) | **36/36 = 100%** on the run-1-comparable projection (36/37 = 97.3% with the widened instrument) | 94.1% | **16/16 = 100%** | unanimous `blocked` |

Contract-state provenance: run 1 measured `main` (a real commit); runs 2–3
measured then-uncommitted working states, reconstructed post-hoc at
[`products/tracker/repro/contracts/`](../../products/tracker/repro/contracts/)
(labeled reconstructions — a loop-step-6 violation caught by the PR #6
refutation); run 4 measures this branch's committed state.

Operator drift (run 1, instance-0 vs blind consensus): 5 of 7 total
disagreements were the operator deviating from his own contracts — including
the verdict. The blind instances outvoted the person who wrote the rules.

## What each run taught

1. **Run 1:** the contracts were already score-deterministic (16/16) across
   blind readers; the noise was PIR representation (2 fields) and the
   operator. All three readers independently produced near-identical
   underdetermination lists — the ambiguities are objective properties of
   the text, not reader taste.
2. **Run 2:** both run-1 divergences closed by conventions; one new,
   smaller one surfaced (`assets: []` vs `[nothing]`). The constraint
   oracle converged exactly as written (gps excluded, zephyr-rtos flagged).
3. **Run 3 — the key result:** a v2 fix (`declared-none` generalized to
   "ANY explicit statement") reopened the sell-price fork and SPLIT the
   verdict 2–1. **A fix can regress determinism, and the loop catches it
   in one run.** The v3 line closes it by definition: "explicit
   not-for-sale" means a statement about THE SALE ITSELF; statements about
   users/volume/regions never qualify; a half-answered pair is a runner
   error and the runner must ask.
4. **Run 4 — the stop state:** on the LANDED contracts, 36/36 unanimity on
   the run-1-comparable projection, scores 16/16, verdict unanimous
   `blocked` (correct for the frozen transcript, whose sell half was
   genuinely never asked — the addendum, not the extraction, is what turns
   the landed scorecard `go`). The instrument was simultaneously WIDENED
   with `fn.item_count`, which shows the one pre-named residual as a
   measured 12/13/13 spread. The next fork candidate is already flagged by
   the readers themselves: "no rush" as declared-none — same sentence
   class that split run 3, held unanimous here by the tightened wording.

## Divergence classification (loop step 4)

| Class | Count over 3 runs | Fate |
|---|---|---|
| (a) contract ambiguity | 14 distinct | every one became contract text (conventions v2/v3, scale fixes, record shapes, the evidence bar) |
| (b) input ambiguity | 3 (sell half never asked; zephyr ask-back missed; range follow-up skipped) | runner errors — now first-class PIR records; the two answers were obtained post-hoc and live in the dated addendum |
| (c) operator drift | 5 (run 1, instance-0) | landed artifacts corrected to blind consensus |
| (d) instrument bug | 1 (set compared by string rendering) | tool canonicalized; both runs re-measured |

## Accepted residuals (named, not hidden)

- Run 3's verdict SPLIT was not a stop-state (neither unanimity nor an
  accepted residual). The loop should have re-run immediately; instead
  the branch initially landed at its worst measured point — caught by the
  PR #6 refutation, answered by run 4 on the landed contracts.
- Constraint token spelling diverged in run 3 (`zephyr rtos` vs
  `zephyr-rtos`) — closed by the `canonical_tokens` convention (kebab-case
  slugs); the oracle's own example spelling was the bug.
- Function-item granularity (12–16 items for the same product) has no
  splitting rule; the capability SET is unanimous, the item COUNT is not.

- Free-text→enum mapping of garbled tokens ("akwas on schel") has no repair
  rule; all readers converged on `wakes-on-schedule`, but by judgment.
- The D1 ceiling: under a catalog whose SoC records are all D1, no
  catalog-backed capability can score green. Intended for now — declared ≠
  supported — but it means `tech.exists` green requires D2+ records.
- `metric.tech.exists` scores across all functions while `fed_by` names
  only `q.novel.magic` — scope mismatch, carried to the registry's v1.
- Verbal hedges on enum answers ("hopefully not explode lol") cannot move a
  derived score; the hazard rides in evidence to the G1 human.

## Verdict on the theory

The determinism claim held where the design said it would: derived fields
100%, scores 100% under stable contracts, verdict unanimous in three of
four runs — and failed exactly where the design admits judgment (one
under-specified sentence flipped a verdict, once by loosening a line that
had just been fixed). Run 4, on the contracts as landed, closed at
unanimity with one named, now-measured residual (item granularity).
Repeatability for hardware is achievable, but it is a property of the
CONTRACT TEXT, continuously measured, never of the readers — and the
operator is bound by the same measurement as everyone else: this report's
own landing was refuted once for drifting from the spec it defines.
