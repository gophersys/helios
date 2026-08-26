# P2 — the platform class

Status: v0, depth D1 (designed with Mateo, 2026-08-26). P2 decides the
compute substrate class from artifacts that already exist — the PIR, the
P1 scorecard's platform metrics, and the constraints channel. It asks the
founder nothing new, and it is the most DERIVED phase in the chain: a
decision table, not a judgment, with conflicts stopped and surfaced,
never silently resolved.

## Authority (decided: derived-binding, conflicts to human)

A clean derivation — every rule fires unambiguously, `conflicts` empty —
FIXES the class mechanically. The human is notified, not consulted; G1
already carried the human gate for the product as a whole. A CONFLICT
(two rules demanding different classes) stops the machine: the PCR
carries the conflict and the human decides, recorded verbatim (the same
F4 pattern as G1).

## Inputs

| Source | Fields |
|---|---|
| PIR | `power_class`, `constraints[]` (hard OS/tech), `functions` |
| P1 scorecard | `derived.needs_hardware`, `derived.needs_firmware`, the three P2-class metrics: `metric.platform.hmi-class`, `metric.platform.compute-demand`, `metric.platform.edge-autonomy` |

## The derivation table (first match wins; conflicts stop the machine)

| # | Condition | Class |
|---|---|---|
| 1 | `needs_hardware = false` | `none` |
| 2 | `needs_firmware = false` (passive/analog hardware) | `analog-only` |
| 3 | a hard OS constraint (e.g. `zephyr-rtos`) | that OS's class — UNLESS rule 4's OR rule 6's condition also holds, which is a **CONFLICT** (a hard OS constraint on an MPU-demanding or hybrid-shaped product), surfaced to the human. A hybrid under a hard-Zephyr constraint is DELIBERATELY a human call, never auto-derived. |
| 6 | rule 4's condition AND the hybrid discriminator (below) | `hybrid` (MPU + companion MCU) |
| 4 | `hmi-class` red OR `compute-demand` red | `mpu-linux` |
| 5 | otherwise | `mcu-zephyr` |

Evaluation order is the row order shown: 1, 2, 3, 6, 4, 5.

**The hybrid discriminator (derived, not judged):** a product is
hybrid-shaped when rule 4's condition holds AND `pir.modes` includes
`wakes-on-event` or `wakes-on-schedule` AND `power_class` ∈ [PC0, PC1] AND
at least one `sensing` function item exists — an MPU-demanding product
that must also sense on a battery while asleep.

`edge-autonomy` never selects the class; it colors the P3 architecture
(where logic lives) and rides into the PCR's `context` field.

**ABSENT inputs (the registry declares both platform metrics can be):**
an ABSENT `compute-demand` or `hmi-class` counts as the ABSENCE OF DEMAND
— it satisfies no red condition and satisfies the lane-B condition (a
product that demands nothing cannot demand a performance lane). This is
stated here so the fifth absent-vs-value gap in this repository is closed
in the doc that would otherwise host the sixth.

## Lane (decided: derived, in the PCR)

Inside `mcu-zephyr`, the lane narrows P4's fit matrix early:

| Condition | Lane |
|---|---|
| `hmi-class` green AND `compute-demand` green AND `power_class` ∈ [PC0, PC1] | **B** — low-power wireless |
| `hmi-class` amber (small-readout) OR `compute-demand` amber OR `power_class` = PC2 | **A** — performance |

P4 may overturn the lane with evidence; the overturn is recorded in the
fit matrix with its reason — never silent.

## The PCR record

```yaml
schema: sfd.pcr/v0
product: <slug>
class: none | analog-only | mcu-zephyr | mpu-linux | hybrid
lane: A | B          # mcu-zephyr only; absent otherwise
derived: true        # false only when a conflict forced a human decision
rules_fired: []      # table row numbers, in firing order
derived_from: []     # the exact metric/constraint/field ids consumed
conflicts: []        # empty on a clean derivation
context: {}          # non-selecting inputs carried forward (edge-autonomy)
decision: {}         # populated ONLY on conflict — verdict/by/quote/at
provenance:
  pir: {ref: ..., hash: ...}
  scorecard: {ref: ..., hash: ...}
```

## Gate G2

1. The class is fixed — by derivation (clean) or by recorded human
   decision (conflict).
2. Every `rules_fired` entry names a table row; every `derived_from` entry
   names an existing field or metric id.
3. The independent architecture review slot (00-process.md) applies to
   CONFLICT cases and to any PCR whose class is `hybrid` — the two
   judgment-bearing outcomes.

## Enforcement status (stated exactly)

| Piece | Status |
|---|---|
| the derivation table + lane rules + PCR spec | **AUTHORED v0** — this file |
| `sfd pcr <product>` (mechanical derivation from PIR + scorecard) | PLANNED |
| PCR verification (recompute + diff, the catalog-verify pattern) | PLANNED |
