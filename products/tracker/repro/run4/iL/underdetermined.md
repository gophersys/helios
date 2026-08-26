# Underdetermination list — instance iL (run4)

Verbatim section (b) of the instance's return.

1. Function-item granularity. No splitting rule for a multi-noun answer ("positon… altitude, speed, velocity, tilt"). I made 4 sensing items (velocity folded into speed) and split q.fn.stores into 2. Named residual in 50-determinism-run-1.md, still unfixed.
2. `notes` has no home. `conventions.carry-placement` routes the concealment detail "to notes", but `pir_fields` declares no notes field and the contract says an answer that fits no field forces a versioned schema change. I invented `physical.notes`.
3. "no rush" as declared-none. `declared-none-general` exemplifies "no deadline" but never says whether an attitude statement ("no rush… correctness over speed") explicitly declares the asked date not-binding. I recorded `timeline.proto: none-declared`.
4. Verbatim vs normalized for text fields. Nothing says whether `pir.summary`/`pir.users` carry the user's words or a normalized statement. I kept summary verbatim, normalized users.
5. "tight pick" is undefined for q.phys.size. The graph spawns `q.followup.range` on "tight picks" without naming which enum values qualify. I judged `phone` not tight → `physical.dims: ABSENT`. The other branch would give a runner error + UNKNOWN dims.
6. "extreme pick" is undefined for q.env.conditions — I inherited the spawn from the transcript rather than deriving which of water/dust/heat/cold/vibration/washing are extreme.
7. viability.outcome green vs amber. The answer names three checkable conditions but no threshold (accuracy, uptime, latency). No rule says whether functional acceptance conditions are "a measurable outcome".
8. viability.novelty amber vs red. "an existing product already is this" is arguably true (the founder concedes others exist); no test says when a stated-but-unverified difference stops counting. I took amber.
9. platform.edge-autonomy green vs amber. Losing alerts — the product's own stated success condition — offline is either "fine offline" or "degrades acceptably"; the text supports both. I took amber.
10. power-risk binding target. "the floor when declared, else the delight" plus "a none-declared floor never makes green vacuous" only implies that none-declared ≠ declared. I fell through to the 1-month delight target. Nothing quantifies "comfortably plausible" vs "requires aggressive sleep design" for PC1.
11. tech.exists scope. The registry itself names the mismatch (scored across all functions, `fed_by` only `q.novel.magic`) without resolving it. I scored the whole capability set.
12. Catalog-seam aggregation over mixed depths. Green@D2+, amber@D1, red@no-coverage-no-example, but no rule for a product whose capabilities span D2 (bme280), D1 (esp32c6) and zero coverage (GNSS, modem, IMU). I applied a weakest-limb (min) rule.
13. "Known example" evidence standard. The bar accepts "a shipped product class or an upstream Zephyr-supported implementation the scorer can NAME", but no Zephyr tree exists here (`ws/` holds only `west.yml`) and the repo forbids unsourced facts. I named commercial product classes and demoted every upstream claim to a research task rather than cite an unverifiable path @ SHA.
14. risk.privacy amber vs red. Red is "health/identity data without a compliance plan"; there is no compliance plan here either, and nothing says whether a missing plan aggravates the location case. I let the enum literal decide → amber.
15. `runner_errors[]` key set is unspecified (only its purpose is). I invented `{question, kind, detail, effect}`.
16. `consistency[]` key set and level vocabulary are unspecified ("per-rule result"). I used `{id, result: green, note}` for a rule that did not fire — "green" vs "not-fired" is my choice.
17. `g0` extras. `{status, blockers[]}` is declared; I added a `passed[]` list, neither required nor forbidden.
18. UNKNOWN placement for a missing pair half. `unknown-addressing` gives the leaf path for `unknowns[]`, but does not say whether the value slot also carries the literal `UNKNOWN`. I wrote both.
19. `blocks: []` legality. `q.followup.range` feeds no metric, so an unanswered scoring question yields an UNKNOWN that blocks nothing; R5 assumes a non-empty list. I left it empty and noted that env-risk stays scoreable.
20. Excluded volunteered tokens have no record. The oracle defines exclusion but the PIR has no field for a rejected token. I used YAML comments rather than invent a field.
21. Provenance shape for derived fields. The spec example is `{question, quote, at}`; `derived-items` gives `{source, rule}` for function items only. For `pir.power_class` / `pir.compliance.certifications` I merged both.
22. Timestamp source. Date-only is legal, but nothing says the transcript header date (2026-08-26) is the answer time. I assumed it for every `at`.
23. risk.schedule "no dates declared" does not say whether BOTH dates or EITHER must be none-declared; the metric is `scored_by: derived` yet carries no `derivation` key. I required both.
24. Garbled-token repair has no rule ("akwas on schel"→`wakes-on-schedule`, "requiemrnt"→`hard`, "1 button and 1 led"→`one-button`). Named residual; done by judgment.
25. Scorecard mirroring vs registry lint. The contract says `scores[]` mirror `scored_by`/`verdict_weight`/`consumer`, but the registry forbids `verdict_weight` on P2-class metrics. I omitted it there. I also added `derivation_applied` (power-risk, compute-demand) and `human_gate: false` (safety), which the record spec neither names nor forbids.
26. Empty `decision`. The spec shows a populated map; empty map vs null vs omitted keys is unstated. I used `{}`.
