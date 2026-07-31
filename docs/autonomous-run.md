# Autonomous run: de-legacy → factory → composer migration

> Protocol for the unattended completion of tasks #7, #5, #6. Every stage:
> PLAN (inline, consult this doc + PROGRESS.md) → EXECUTE (Workflow
> fan-out, worktree isolation for parallel file mutation) → REVIEW
> (adversarial verify workflow; fix confirmed findings) → GATE (all tests
> green + ruff) → COMMIT (conventional, one branch+PR per stage).
> Oracles decide, never vibes. When all three stages are merged-ready,
> STOP and hand off for ultrareview.

## Stage 1 — De-legacy (branch feat/de-legacy, base feat/layout-engine)
Delete, each deletion proven covered by an ecad-path test first:
1. `_generate_symbol_legacy` + `_generate_lib_symbol_sexp_legacy` → replace
   parity tests with golden-file snapshots of the CURRENT (fixed) output.
2. `chip_library` hand-coded chips: keep as **data** (they seed the factory
   until generated parts exist) but move behind the registry; delete
   `generate_lib_symbol_sexp` legacy path once schematic_gen callers use
   SymbolModel directly.
3. `datasheet_parser` hardcoded fallbacks: delete AFTER Stage 2 produces
   generated ESP32 parts (ordering constraint — do not break e2e first).
4. Legacy single-unit inline path (`to_inline_sexp`/`flatten` legacy format)
   once no caller remains.
KEEP: corpus parser, manufacturing exports, validate.py (production).
Gate: full suite green minus the known corpus-data failures (list them in
the PR body verbatim).

## Stage 2 — Phase D factory (branch feat/ingest-factory)
Foundations (already validated, on disk): `data/zephyr/VALIDATION.md`
(LTS v3.7.2 pinned; esp32h2 → v4.4.1 fallback; REAL macro formats quoted),
`data/datasheets/SECTIONS.md` (running-page-header section finder; zh
editions primary — fetch en editions from espressif.com when reachable,
zh fallback).
Build order (parallel worktree workflow for 1-4, contracts from the
approved plan in ~/.claude/plans/crispy-conjuring-lampson.md):
1. `ingest/zephyr.py` — parse pinctrl (shared ESP32_PINMUX macro,
   line-continued defines, ESP_NOSIG sentinel, sigmap companion), dtsi
   (ngpios dual banks), HAL io_mux (FUNC_*, dedupe _0 aliases).
2. `ingest/datasheet.py` — pdftotext section slicing per SECTIONS.md
   regexes + Claude CLI extraction of ONLY those pages; JSON-schema gate.
3. `ingest/crossverify.py` + `ingest/state.py` — evidence ledger,
   stage machine (discovered→…→approved), gates per plan table.
4. `ingest/codegen.py` — Component class + sidecar + .kicad_sym +
   per-part markdown doc; clobber-safe via sha256; `_overrides.py` hook.
5. `ingest/factory.py` CLI (status | step <id>) + COMPONENTS.md projection.
Acceptance: ESP32-S3-WROOM-1 through ALL stages, 0 evidence conflicts,
generated class importable with 41 accessors, footprint resolved w/ STEP.
Then a pipeline() workflow over the remaining 14 seed parts (modules
first; module peripherals fall through to chip PDFs — SoCs before the
five slim modules that lack peripheral sections).
Review: adversarial workflow over the generated parts (pin-level spot
checks vs official symbols + Zephyr).

## Stage 3 — Phase E composer migration (branch feat/composer-migration)
Composer builds a typed Design (registry parts, no Custom: stubs, real
footprints) → layout() per sheet → emit(); delete all hardcoded
coordinates; hierarchical: root sheet + per-sheet engine output (extend
engine for hier labels per plan). e2e: GPS tracker spec → ERC 0 →
netlist == intended → manufacturing exports run → SVG rendered.
Update tests that encoded old behavior in the same commit; document each.

## Invariants for every agent
- kicad-cli via PATH (/Applications/KiCad.app/Contents/MacOS locally,
  KICAD_SHARE honored); venv .venv/bin/python; ruff clean before commit.
- pipeline→ecad import direction only. Deterministic everything.
- Never commit data/ (gitignored) except COMPONENTS.md at root.
- If blocked >2 attempts on one gate: record blocker in PROGRESS.md,
  move to next independent unit, surface at handoff.

## Handoff (when done)
Update PROGRESS.md + this doc's status line; ensure branches pushed with
PRs stacked; write a summary of what shipped + known gaps; instruct the
user to run `/code-review ultra` from ~/code/hardware on the top branch.

STATUS: stage 1 starting.
