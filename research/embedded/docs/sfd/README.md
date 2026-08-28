# SFD — the software-first design process

Status: SKELETON v0 (2026-08-26). This is the system, not an example.
Owner: Mateo. Carrier target: Eden project intake.

The thesis in one sentence: **the devicetree is the contract between firmware
and hardware — firmware derives it first, hardware must then satisfy it.**

| Doc | Content | Depth |
|---|---|---|
| [`00-process.md`](00-process.md) | The full process: phases P0–P6, gates G0–G6, cross-cutting axes | D0 |
| [`10-p3-pipeline.md`](10-p3-pipeline.md) | P3 in depth: the Zephyr-truth compiler, six stages | D0–D1 |
| [`20-component-process.md`](20-component-process.md) | How anything enters the system; part numbers bind LAST | D1 |
| [`30-p0-interrogation.md`](30-p0-interrogation.md) | P0: rules R1–R5, tiers, constraints channel, G0, PIR v0 | D1 |
| [`30-p0-graph.yaml`](30-p0-graph.yaml) | The interrogation graph Eden runs — 30 typed questions + 3 adaptive, derivations, consistency rules | D1 |
| [`40-p1-metrics.md`](40-p1-metrics.md) | P1: scorecard frame F1–F5, verdict rules, catalog seam | D1 |
| [`40-p1-registry.yaml`](40-p1-registry.yaml) | The metric registry — 16 metrics + 2 flags; closes R2's two-way trace | D1 |
| [`50-determinism-run-1.md`](50-determinism-run-1.md) | The determinism experiment: 4 runs × 3 blind readers, numbers + residuals | D3 — measured |
| [`60-p2-platform.md`](60-p2-platform.md) | P2: the platform-class derivation table, lane rules, PCR record | D1 |
| [`capability-index.schema.yaml`](capability-index.schema.yaml) | The catalog record shapes (doc copy; truth is `tools/sfd/record.go`) | D1 |

The machine behind the docs:

| Piece | Where | What |
|---|---|---|
| `sfd` tool | [`tools/sfd/`](../../tools/sfd/) | Go library + CLI: Zephyr tree in, typed records out. The Eden seam. |
| catalog | [`catalog/`](../../catalog/) | extracted records — versioned, reviewed, cited by SHA |
| workspace | `ws/` (git-ignored) + [`manifest/west.yml`](../../manifest/west.yml) | the pinned Zephyr the records cite |
| devcontainer | [`.devcontainer/`](../../.devcontainer/) | rides `ghcr.io/gophersys/embedded` by digest; consume-only |
| gate | [`gate.sh`](../../gate.sh) | the whole safety net (repo has zero CI): vet + tests + `sfd verify`, devcontainer-only, FAIL-NOT-SKIP |

Numbering leaves room: `50-` P4 part selection, `60-` P5 hardware
handoff — each lands in a later round.

## Depth scale (used everywhere)

| Depth | Meaning | Evidence bar |
|---|---|---|
| D0 | sketch | none — a shape to react to |
| D1 | sourced | cites a path @ SHA or a document |
| D2 | derived | machine-derived from a D1+ source |
| D3 | proven | a build or a run produced the evidence |

A fact never rises a level without its evidence. A doc states its depth.
