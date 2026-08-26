# P3 — the Zephyr-truth compiler

Status: v0, depth D0–D1. This is the system that turns a Product Intent
Record into hardware requirements, with Zephyr as the single source of truth.
Chip-agnostic: the supported SoCs are rows in the capability index, never
branches in the pipeline.

```
PIR ─▸ S1 FUNCTION MAP ─▸ S2 SUBSYSTEM BIND ─▸ S3 PERIPHERAL DEMAND
                                                      │
        S6 CONTRACT ◂─ S5 EXTERNALS ◂─ S4 SOC SATISFY ◂┘
```

Each stage is a pure transform with one input artifact and one output
artifact. A stage never reaches around its neighbor.

## S1 — FUNCTION MAP

- Transform: product functions (PIR) → capability vocabulary.
- Artifact: **capability manifest**.
- Vocabulary v0 (CLOSED): `connectivity` · `sensing` · `actuation` ·
  `storage` · `compute` · `hmi` · `power` · `security` · `time`.
- Rule: a function that fits no word forces a versioned vocabulary change —
  an explicit event, never a silent add. The closed set is what makes S2
  mechanical.

## S2 — SUBSYSTEM BIND

- Transform: capability → Zephyr subsystem + API + Kconfig root.
- Artifact: **subsystem map**. Example row:
  `connectivity.wifi → subsys/net + wifi_mgmt API → CONFIG_WIFI`.
- Source: the `subsys/` tree and `include/zephyr/` API headers @ pinned SHA.
- The map is finite and versioned per Zephyr release. Building it IS the
  research; each row carries its source path.

## S3 — PERIPHERAL DEMAND

- Transform: subsystem set → device classes the firmware will demand
  (radio, I2C/SPI/UART controllers, timers, flash controller, ADC, …).
- Artifact: **demand table** — class, count, and the constraint that created
  it (throughput, timing, wake capability).
- Source: the driver model — `drivers/<class>/` + `dts/bindings/<class>/`.
  A binding's `on-bus:` and required properties are machine-readable
  statements of what a device class needs from the hardware.

## S4 — SOC SATISFY

- Transform: demand table × capability index → fit matrix.
- Artifact: **fit matrix** per lane (A performance · B low-power wireless).
- Rule: the pipeline reads ONLY the capability index
  ([`capability-index.schema.yaml`](capability-index.schema.yaml)) — never a
  datasheet, never memory. If the index lacks a field, the index is extended
  by extraction; the pipeline is not special-cased.

## S5 — EXTERNALS

- Transform: demands the SoC does not satisfy → external part candidates
  (sensors, memories, PMICs, transceivers).
- Filter — ONE test: does an upstream binding + driver exist for the part?
  - yes → candidate, carrying its `compatible` and binding path.
  - no → flagged as **driver-work**, with a cost estimate. Never hidden,
    never auto-accepted.
- Artifact: **candidate list** with per-candidate provenance.

## S6 — CONTRACT

- Transform: everything above → the deliverables.
- Artifacts:
  1. **SDHR** — Software-Derived Hardware Requirements. Every line cites its
     S1–S5 lineage.
  2. **virtual-board devicetree** — the contract file itself.
  3. **Kconfig fragment** — the software half of the same contract.
- Gate **G3**: two-way traceability. Backward: SDHR line → PIR function.
  Forward: SDHR line → devicetree node. A line that cannot do both is red.

## The power model — "low-power" as data, not vibe

Zephyr encodes power as devicetree data. Per SoC, with implementation
status stated (a table in the present tense that is not implemented is a
lie — refuted 2026-08-26):

| Source | What it yields | Status |
|---|---|---|
| `zephyr,power-state` nodes (binding: `dts/bindings/power/`) | states, `min-residency-us`, `exit-latency-us` | **EXTRACTED v0** — every such node in the include closure; `cpu-power-states` phandles are NOT followed yet, so states are not attributed to a CPU cluster |
| `wakeup-source` property on device nodes | what can wake the SoC from which state | PLANNED |
| `CONFIG_PM` / `CONFIG_PM_DEVICE` / `CONFIG_PM_DEVICE_RUNTIME` coverage in drivers | which drivers can power-manage their device, which cannot | PLANNED |

The SDHR then carries a **power-state budget**: for each product mode
(active / idle / sleep / ship) → the required SoC state, the wake sources,
and the expected time-in-state. P5 inherits it as rail and power-domain
requirements. The power class (PC0/PC1/PC2) sets how hard the budget binds:
PC0 makes it the primary constraint; PC2 makes it a note.

## What P3 can never see — declared holes

P3 stops where the devicetree stops. These belong to P5, by name:

power tree · decoupling · crystal and clock sourcing · boot straps ·
external boot flash selection · debug port · RF front-end and antenna ·
EMC · thermal · connectors · mechanical.

Rule: the S6 handoff lists these as HOLES with owners. Absence is explicit —
a hole that is not named is a defect in this pipeline, not in P5.

## Extraction spec — where truth lives in the Zephyr tree

The capability index is EXTRACTED, never hand-written. Sources, per SoC,
with implementation status. Path notes are measured at v4.2.0
(413b789deb39), not idealized: 13 of 102 `soc.yml` sit at vendor level
(`soc/espressif/soc.yml` declares esp32c6), and SoC dtsi locations vary
(`dts/riscv/espressif/esp32c6/…`, but mimxrt1052's file is
`dts/arm/nxp/nxp_rt1050.dtsi` — vendor-prefixed, but not SoC-named).
Discovery therefore never trusts one path pattern: it matches dtsi
basenames at separator boundaries AND follows the `.dts` includes of
boards that declare the SoC, then resolves the full dtsi include closure.

| Zephyr source | Yields | Status → record field |
|---|---|---|
| `soc/**/soc.yml` | identity, family, series | **EXTRACTED v0** → `name`, `family`, `series`, `soc_yml` |
| SoC dtsi include closure | declared peripheral inventory (compatibles), power states | **EXTRACTED v0** → `dtsi_files`, `compatibles`, `power_states` |
| `dts/bindings/**/*.yaml` | per-component binding paths, class, bus (through `include:` chains) | **EXTRACTED v0** → `bindings`, `class`, `buses` |
| `drivers/**` (`DT_DRV_COMPAT`) | driver existence | **EXTRACTED v0** → `drivers`, `depth` D1→D2 |
| `boards/**/board.yml` | boards declaring the SoC | **EXTRACTED v0** → `boards` |
| `samples/`, `tests/`, `boards/` dts sources | exercise evidence (exact quoted-compatible match) | **EXTRACTED v0** → `exercised_by` |
| `Kconfig.soc` (cores, FPU), memory map, pinctrl | compute + memory + pin detail | PLANNED |
| west blob metadata (`hal_espressif` etc.) | binary-blob dependency | PLANNED |

Two rules:

1. **Declared ≠ supported.** A peripheral that appears in a `.dtsi` enters at
   D1. It reaches D2 with a matching in-tree driver, D3 only with build/run
   proof. Per-field depth is the v1 goal; v0 depth is per record.
2. **The SHA moves atomically.** Re-extract at each Zephyr release bump; the
   diff is reviewed; every record in the index cites the same SHA, and
   `sfd verify` re-extracts and diffs every record against the tree.
