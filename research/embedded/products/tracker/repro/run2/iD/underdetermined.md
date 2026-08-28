# Underdetermination list — instance iD (run2)

Verbatim section (b) of the instance's return.

1. Where a runner error is recorded. `conventions.multi-affirmation` says a partial presentation "is a runner error recorded in the PIR", but `pir_fields` has no such field and R4/adaptive forbids loose notes. → invented top-level `runner_errors`.
2. What happens to an unpresented multi value. `drops` was never offered. Answered-not-selected vs unasked-UNKNOWN is undefined. → left the field answered with the 6 presented values; recorded the omission as a runner error, not an UNKNOWN.
3. How to record ABSENT outside `conditional_fields`. `pir.physical.dims` is fed only by an adaptive that never spawned. `conditional_fields` declares only `battery_life` and `unit_cost.sell`. → wrote `dims: ABSENT` and invented a top-level `absent:` list.
4. The `unknowns[]` item shape. Spec is `{field, blocks}`. A required-tier UNKNOWN that blocks zero metrics (zephyr-rtos strength) would lose its G0 significance entirely. → added `tier`, `gate`, `detail`.
5. Which capability word `q.fn.offline` takes. It feeds `pir.functions` but the answer names no capability in S1's closed set. → chose `compute` (edge autonomy); `storage` was equally arguable.
6. How `q.fn.rate` lands in `pir.functions`. The item shape has no rate slot, the type is `number-unit` (singular), and the position answer states two conditional periods plus "configurable". → invented a typed `rate:` sub-object with per-condition periods.
7. The constraint item's single `quote` slot. Two verbatim utterances exist per constraint — the volunteering and the `q.constraint.strength` classification — and the register section says "both are recorded with the verbatim quote". → `quote` = volunteering, plus `source_question` + `strength_provenance`.
8. Whether "no rush ... correctness over speed" is `declared-none`. `q.time.prod` ("no deadline") is explicit; `q.time.proto` is inferred. → treated both as `none-declared`. If proto is instead UNKNOWN, `metric.risk.schedule` and `metric.feasibility.head-start` both move.
9. `q.phys.carry` names two enum values. "mounted with an adapter" AND "just hidden and tucked somewhere" (= `sits`); it is an enum, not a multi, and `conventions.bound-asks` does not apply (no bound requested). → chose `mounted`.
10. `q.comp.safety` = "no, just hopefully not explode lol". Whether the aside escalates `none` → `minor`. The stated answer is "no". → recorded `none`; surfaced the Li-ion hazard as a caveat in the scorecard and named the rule-1 override if the human reclassifies.
11. Actuation vs the alarm. "alamr" appears in `q.intent.exists` and notifications in `q.intent.win`, but `q.fn.acts` answers "it does not do anything to the bike". → followed `q.fn.acts`; no actuation item (negative-function convention).
12. Whether P1 may run on a PIR that fails G0. Nothing says the scorecard is refused. → produced as instructed, with the G0 red as `reasons[0]` rather than hidden.
13. `metric.risk.schedule` with both dates `none-declared`. The registry writes no level for "no dates asserted". → green (vacuous unbounded slack), stated explicitly in the evidence as "no schedule risk asserted", not "checked and sound".
14. `metric.platform.compute-demand` and "as quick as possible". The derivation reads *stated* rate periods; "within seconds" is ≥1 s and "as quick as possible" states no period. → green, with the amber reading named in the evidence.
15. The catalog seam contradicts the `metric.tech.exists` scale. The seam says "no coverage and no known example scores red"; the scale's red is "no known working example". GNSS/cellular/IMU have zero catalog coverage but well-known upstream examples. → resolved for the registry scale (F1: the registry is the contract) → amber + three named research tasks.
16. The verdict-deciding call: is "its just for me" / "2, maybe 10 for my freinds" an explicit not-for-sale? `conditional_fields` demands an *explicit* not-for-sale for ABSENT and says silence is UNKNOWN. → UNKNOWN. This single reading is what makes the verdict `blocked` rather than a scoreable economics metric.
17. `scores[]` item keys. Spec shows `{id, score, evidence, blocked_by}`. → mirrored `consumer`, `verdict_weight`, `scored_by` (and `human_gate` on risk.safety) from the registry for auditability.
18. `derived:` flags carry no evidence slot although F3 demands evidence for every judgment. → added a sibling `derived_evidence` block.
19. `recommendation` records no rule identity. Precedence matters and stopping point is load-bearing. → added `rule_applied`.
20. Provenance for an asked-but-unanswered adaptive. R4 requires a quote; there is none. → entry with empty `quote` + `status: asked-unanswered` + the ask text.
21. No product/slug field in the PIR spec. → added `product: tracker` (per instruction) and `extracted`.
22. No place for the consistency-rule result. G0 condition 3 evaluates them; the record has no slot. → added a `consistency:` block recording `c.app-needs-link` green with its reason.
23. Timestamp granularity/uniformity. Transcript has no clock; `conventions.timestamps` permits date-only. → `"2026-08-26"` uniformly, which makes every item's `at` identical and therefore useless for ordering.
