# SFD process — phases, gates, axes

Status: SKELETON v0, depth D0. Every phase here gets its own doc in a later
round. This file fixes the shape: what the phases are, what each one emits,
and what its gate refuses.

## 1. Cross-cutting axes

These apply to every phase. They are dimensions, not steps.

| Axis | Values | Rule |
|---|---|---|
| DEPTH | D0 sketch → D1 sourced → D2 derived → D3 proven | see `README.md`. No fact rises without evidence. |
| POWER CLASS | PC0 primary battery or harvest (cannot recharge) · PC1 rechargeable · PC2 mains | set in P0 (derived from `q.power.source`, mapping in `30-p0-graph.yaml`), binds harder as PC decreases |
| OWNER | EDEN (agent) · HUMAN · PAIR | every artifact names its owner |
| PROVENANCE | claim + source path @ SHA + proof | applies to every fact in every artifact |

## 2. The phases

```
P0 INTAKE ─▸ P1 FEASIBILITY ─▸ P2 PLATFORM CLASS ─▸ P3 SW ARCHITECTURE
                                                        │
             P6 CO-VERIFICATION ◂─ P5 HW ARCHITECTURE ◂─ P4 PART SELECTION
```

### P0 — INTAKE

- Method: a fixed question graph plus adaptive chat interrogation. Eden runs
  it when a new project declares (or hints at) a physical product. The graph,
  its rules and the full PIR field list live in
  [`30-p0-interrogation.md`](30-p0-interrogation.md) +
  [`30-p0-graph.yaml`](30-p0-graph.yaml).
- Output: **PIR** — Product Intent Record (spec: `sfd.pir/v0` in the P0
  contract).
- Gate **G0**: every reachable required question answered; UNKNOWNs recorded
  with the metrics they block, never silently defaulted; consistency rules
  green.

### P1 — FEASIBILITY

- Method: score the PIR against the metric registry
  ([`40-p1-metrics.md`](40-p1-metrics.md) +
  [`40-p1-registry.yaml`](40-p1-registry.yaml)): viability, tech-exists,
  feasibility, risk — plus platform metrics consumed by P2. "Needs
  hardware?" and "needs firmware?" are DERIVED FLAGS computed from the
  PIR's functions, not question-fed metrics.
- Output: scorecard; the system recommends go / pivot / kill with reasons.
- Gate **G1**: the HUMAN decides, recorded with their words. A safety human
  gate blocks any recommendation until cleared.

### P2 — PLATFORM CLASS

- Decision: none · analog-only · MCU + Zephyr · MPU + embedded Linux · hybrid.
- Scope now: the Zephyr lane only. The Linux lane is a named hole.
- Output: **PCR** — Platform Class Record, with the why.
- Gate **G2**: class fixed. Judgment-heavy → independent architecture review
  slot (reviewer intentionally unnamed here).

### P3 — SOFTWARE ARCHITECTURE (Zephyr is the source of truth)

- Method: the Zephyr-truth compiler — six typed stages. See
  [`10-p3-pipeline.md`](10-p3-pipeline.md).
- Output: **SDHR** — Software-Derived Hardware Requirements — plus the
  virtual-board devicetree and a Kconfig fragment.
- Gate **G3**: every SDHR line traces back to a PIR function AND forward to a
  devicetree node. Two-way traceability, or red.

### P4 — PART SELECTION + CONNECTION DERIVATION

- Method: match the SDHR demand table against the capability index; pick the
  SoC from the supported set; pick externals by binding coverage.
- Output: candidate BOM + pin/bus map + the frozen virtual-board devicetree.
- Gate **G4**: the devicetree compiles · zero pin conflicts · `west build` of
  the application skeleton is green.

### P5 — HARDWARE ARCHITECTURE (fills what software cannot see)

- Method: a hardware architect (human, later agent-assisted) works against the
  SDHR and fills the declared holes: power tree, decoupling, clock sourcing,
  boot straps, external boot flash, debug port, RF front-end and antenna, EMC,
  thermal, connectors, mechanical.
- Output: handoff package → the ECAD lane (`research-hardware`). The boundary
  stays clean: this repo never designs a schematic.
- Gate **G5**: every devicetree node has a schematic owner · the architect
  signs against the SDHR.

### P6 — CO-VERIFICATION

- Method: the firmware builds against the REAL board devicetree; a twister
  smoke runs; measured power is compared against the P3 power budget.
- Gate **G6**: red→green evidence is recorded, never asserted.

## 3. The supported-SoC set v0 — two lanes

Power class picks the lane. One flat list would hide the conflict between
"low power" and a 600 MHz crossover part.

| Lane | Part | Why it is here | Depth |
|---|---|---|---|
| A — performance | NXP `MIMXRT1052CVL5B` | crossover M7; HMI/DSP-heavy products; **no internal flash** — external boot flash is mandatory hardware | D1 — `catalog/socs/mimxrt1052.yaml` |
| B — low-power wireless | Espressif `ESP32-C6` | Wi-Fi 6 (2.4 GHz) + BLE + 802.15.4; HP core + LP core | D1 — `catalog/socs/esp32c6.yaml` |
| B — low-power wireless | other Espressif BLE/Wi-Fi parts | family breadth; exact parts enter via the capability index only | D0 |

A part is "supported" only when its capability-index record exists at D1+.
The list above is intent, not support.

## 4. Method — how research is done in this repo

1. Mine upstream Zephyr at a pinned SHA. Never a datasheet first; the
   datasheet fills holes the tree cannot answer.
2. Verify by build, not by docs: `native_sim`/qemu first, hardware after.
3. Every doc passes an independent adversarial refutation before it lands.
4. Architecture reviews sit at G2 and G5 — the two judgment-heavy gates.
