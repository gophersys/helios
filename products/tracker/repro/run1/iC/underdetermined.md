# Underdetermination list — instance iC (run1)

Verbatim section (b) of the instance's return.

1. No timestamps in the transcript. R4 mandates a timestamp per value; the frozen input carries only a file-header date. I used date-granular `at: '2026-08-26'` everywhere rather than fabricate a time.
2. `q.fn.talks` is a single-select `enum`, answered with two values (`far-away-anywhere` + `phone-nearby`). No coercion rule exists. I kept both as separate connectivity function items.
3. `q.power.duty` is a single-select `enum`, answered with three values. `pir.modes` is a list, so I kept all three. This also decided `derivations.capability.time` (fires on set membership of `wakes-on-schedule`) — the derivation is written for a scalar.
4. `q.phys.size` named two values (`phone`, `deck-of-cards`). I took `phone` on the ask's "at most" wording.
5. No encoding for "answered: nothing". `q.fn.acts` = "does not do anything". I kept a function item with `detail: none` so the feed is not dead; dropping it would orphan a required question's feed.
6. Which capability word `q.fn.offline` feeds. It feeds `pir.functions` but the answer is a behaviour, not a capability. I filed it under `compute` (edge autonomy).
7. No encoding for "answered: no date exists" on a `date`-typed field. `q.time.proto`/`q.time.prod` were answered "no rush"/"no deadline" — not UNKNOWN (the founder is not missing information) and not ABSENT (no `conditional_fields` entry). I used a `none-declared` sentinel and scored `metric.risk.schedule` green. Calling it UNKNOWN instead would flip that score.
8. `q.scale.cost` half-answered. Build stated, sell never stated. R5 forces UNKNOWN; inferring "not for sale" from `q.intent.who`/`volume`/`moat` would be a derivation the graph does not authorise. This single call produces the `blocked` verdict.
9. The tier/weight contradiction this exposes. `q.scale.cost` is tier `scoring` (UNKNOWN passes G0 by design) yet feeds a core metric that blocks P1. Rule 2's parenthetical says "G0 should have prevented this" — G0 structurally cannot. Reported in `recommendation.reasons`.
10. Shape of `pair-number-unit` / `pair-number` values is unspecified. I typed them `{value, unit, bound}` and `{value, currency, bound, at_quantity}`.
11. `floor` = "no lowest threshold" — a declared non-floor, distinct from UNKNOWN and from ABSENT. Encoded `bound: none-declared`; it makes `power-risk` red mechanically unreachable.
12. R5's `blocks` for a field fed by a metric-less question. `q.followup.range` feeds no metric, so `pir.environment.limits` UNKNOWN mechanically blocks nothing (`blocks: []`) despite degrading `env-risk`. I recorded `[]` and named the degradation in the metric's evidence instead.
13. Unspawned adaptive vs UNKNOWN. `q.followup.range` never spawned for `q.phys.size` → `dims: {}` (N/A). The graph's "unspawned adaptive is N/A" is stated only for G0, not for the PIR record.
14. What counts as "volunteered technology". No token list exists. I classified `gps` and `zephyr-rtos` as volunteered-and-unclassified (→ G0 red); I did *not* classify `led`, `pcb`, `assembly` — LED is covered by the `a-light` enum value.
15. `q.env.conditions`: the runner offered 6 of 7 values; `drops` was never presented, and "yes all the ones suggested" affirms only what was shown. Recorded the 6, no partial-unknown mechanism exists to record the 7th.
16. `metric.feasibility.head-start` has no level for "nothing exists AND no timeline". Red is a conjunction whose second half is false; green is unreachable. Chose amber by the global scale.
17. `metric.viability.economics` cannot be `absent` — the registry declares no `absent_when` on it, so a not-for-sale product has no defined state. Named as the fix in `blockers[].clear_by`.
18. Catalog-seam wording "no coverage AND no known example → red". GNSS/cellular have zero catalog coverage but obvious shipped examples; the doc gives no evidence bar for "known example". I scored both amber and named research tasks.
19. `metric.risk.safety`: answer `none`, but qualified "hopefully not explode lol" on a PC1 pack in vibration/heat/water. `scored_by: derived` forbids judgment, so green stands; carried into `reasons` with the note that the fix is re-answering `q.comp.safety`, not overriding the score.
20. `metric.platform.compute-demand` is fed only by rates (all ≥1 s → green), which cannot see three concurrent protocol stacks. Scored green mechanically, flagged as a P2 carry-forward.
21. Scorecard record extensions. The spec's example shows only `id/score/evidence/blocked_by`; I added `consumer`, `verdict_weight`, `scored_by`, a `precedence_trace`, `derived_evidence`, and a `catalog` header block. PIR extensions: `product`, `source`, `g0`, per-item `rate`, `volunteered_in`/`classified_by` split on constraints, and `part`/`why` on unknowns.
