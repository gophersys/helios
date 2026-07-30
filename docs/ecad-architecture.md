# src/ecad — Architecture

One sentence: **`src/ecad` is the typed world; `src/pipeline` is the
corpus/legacy world; pipeline imports ecad, never the reverse.**

## Layers (bottom-up)

| Module | Responsibility | Depends on |
|---|---|---|
| `model.py` | Frozen value types: `PinSpec`, `UnitDef`, `FootprintRef`, `SourcingInfo`, enums | — |
| `net.py`, `component.py`, `design.py` | Runtime design graph: `Component` (typed pin accessors), `Net.connect`, `Design.check()` lint + `intended_netlist()` ground truth | model |
| `symbol.py` | `SymbolModel` — the ONLY symbol-geometry source. Styles: `legacy` (parity) / `readable` (4-side). Emitters: `.kicad_sym`, inline multi-unit, inline flattened | component |
| `emit.py` | Pure .kicad_sch S-expression primitives: deterministic UUIDs, symbol instances (explicit pin numbers), labels/wires/junctions/no-connects, generated `power:*` symbols | — |
| `footprints.py` | Installed-KiCad footprint index + descriptor resolution (never guesses) + validation gates | model |
| `ingest/` | Component factory stages (Phase D): official-symbol parse today; datasheet/Zephyr/crossverify/codegen next | model, footprints |
| `layout/` | The layout engine: `graph_build → rank → order → place → route → engine.emit`, with `lints.py` hard gates | symbol, emit |

## Oracles (what "correct" means)

1. `Design.check()` — definition-time lint, before any file exists.
2. `layout/lints.py` — geometric: orthogonal, on-grid, no overlaps, junction sanity.
3. `kicad-cli sch erc` — **errors must be 0**.
4. `kicad-cli sch export netlist` — must equal `Design.intended_netlist()` exactly.
5. Determinism — same Design → byte-identical file.

All five run in `tests/ecad/test_layout_engine.py` on every fixture.

## Key invariants

- Emitted lib_symbols child names use the bare part name (`NEO-6M_0_1`),
  never lib-prefixed — KiCad refuses to load otherwise.
- Power nets are never routed edges: pins get power-symbol taps; a passive
  with zero signal edges is a satellite cap placed beside its owner IC.
- A rail with a real `power_out` driver never gets a `PWR_FLAG`.
- `sanitize_pin_name` collisions across distinct pin names are refused at
  attribute access (`pin()` always works) — never silently merged.
