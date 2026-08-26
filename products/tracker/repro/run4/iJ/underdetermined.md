# Underdetermination list — instance iJ (run4)

Verbatim section (b) of the instance's return.

1. Free-text field values — whether `pir.summary`/`users`/`novelty.*`/`targets.success` record the VERBATIM answer or a normalized paraphrase. R4 puts the verbatim in `provenance`, implying the field is normalized; the skeleton shows only `summary: ...`. I recorded verbatim.
2. Function-item granularity — no splitting rule. `q.fn.senses` names position/altitude/speed/velocity/tilt; I merged speed+velocity → 4 sensing items, 12 items total. Already a named residual in `50-determinism-run-1.md` (spread 12–16 across instances).
3. `multi-affirmation` and the null option — "the runner must present every value" does not say whether `none` counts as a value owed. I named both `drops` and `none` as unpresented in `re.1`.
4. Asked-but-unanswered adaptive = runner error? `runner_errors[]` is scoped by its parenthetical to "multi-affirmation violations and missed ask-backs", but `50-determinism-run-1.md` class (b) lists "range follow-up skipped" as a runner error. I ruled it NOT a runner error (it was asked) — only an UNKNOWN.
5. `q.time.proto` = "no rush we are just testing out the system" — `declared-none` names "no deadline / no threshold" literally; "no rush" is a paraphrase of the same subject. I read it as `none-declared`. Verdict-adjacent: it decides `metric.risk.schedule` green-vs-unknown and `metric.feasibility.head-start` amber-vs-red.
6. Rate on an unspawned sense — `rate-attachment` describes attachment when a rate exists; nothing says what an item without a spawn carries. I wrote `rate: ABSENT`; omitting the key is equally defensible.
7. Does `q.fn.offline` emit a function item, and under which word? `feeds` names `pir.functions`; the coverage table maps it to `compute`. I emitted a compute item; a reader could emit none.
8. `q.fn.stores` item count — retention and store-and-forward backfill are two behaviours in one answer. I emitted one storage item.
9. DIRECT CONFLICT: `carry-placement` says the concealment detail "goes to notes", but `pir_fields` declares no notes field and the contract forbids loose notes ("an answer that fits no field forces a versioned schema change"). I put it in a `note:` key inside the provenance entry.
10. `metric.platform.compute-demand` — the derivation keys on "stated rate period >= 1 s"; "if an alert it must be as quick as possible" states a LATENCY, not a period. Green vs amber is unclosed. I scored green and named the hedge.
11. `metric.feasibility.power-risk` derivation — "the floor when declared, else the delight target" never says whether a `none-declared` floor counts as "declared". Only the parenthetical ("never makes green vacuous") resolves it, by inference. I fell through to the delight target (1 month+) → amber.
12. `metric.tech.exists` scope — `fed_by` names only `q.novel.magic` ("not really" → nothing unproven → green), while the catalog seam demands scoring across ALL functions (→ amber). The docs admit this as a residual "carried to the registry's v1". I scored across functions.
13. The evidence bar's "searched" — "red requires that the scorer searched and can name nothing" defines no corpus, no tool, and no way to record the search. I named upstream Zephyr implementations (`drivers/gnss`, `zephyr,modem-cellular`, BMI270/LIS2DH) from model knowledge and explicitly flagged them as NOT verified against the pinned SHA.
14. No record slot for research tasks — the metrics doc requires "the gap becomes a named research task" but the scorecard spec has no field. I added `research_tasks:` on the score.
15. No slot for a tested-but-false `absent_when` — I added `absent_when_holds: false` on the two metrics that declare one.
16. No slot for which derivation a derived score applied — record-keeping mirrors only `scored_by`/`verdict_weight`/`consumer`. I added `derivation_applied`.
17. Does the G0 blocker also belong in `recommendation.blockers`? Rule 2 populates blockers with core unknowns; the contract puts the G0 state in `reasons[0]` but never says the two are exclusive. I kept `blockers` to the core unknown only and cross-referenced.
18. `unknowns[].blocks` for adaptive-fed fields — `q.constraint.strength` and `q.followup.range` feed no metric id, so `blocks: []`. `gate: G0` covers the constraint case; nothing in the shape covers a scoring-tier UNKNOWN that blocks nothing (`pir.environment.limits`).
19. Timestamp granularity — date-only is legal, but nothing says whether entries share one date or take per-question ordinals. All carry `2026-08-26`.
20. `pir.targets.unit_cost` typing — `q.scale.cost` is `pair-number`, yet the answer carries a currency, a bound ("no more than") and a qualifying quantity ("at 10 unit qty"). No slot for any of the three; I recorded a string.
21. `pir.targets.battery_life` typing — `pair-number-unit` has no slot for the open-ended "+" in "1 month +".
22. `source:` shape — "(transcript ref)" only. I used a path.
23. `consistency[]` shape — "per-rule result" with no key set. I used `{id, result, note}`.
24. `runner_errors[]` shape — no key set declared. I used `{id, kind, question, detail, effect}`.
25. Evidence on an unreachable scale limb — F3 demands evidence, but `metric.viability.economics` has BOTH limbs unreachable. I recorded the BOM-class judgment explicitly marked non-scoring rather than suppressing it.
26. `pir.ref` path form — "the exact PIR scored" with no path convention; this PIR lives outside the repo.
