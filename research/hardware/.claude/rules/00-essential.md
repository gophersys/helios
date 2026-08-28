# Essential Rules — hardware

## Project Purpose

AI-instrumented hardware design pipeline. Parses open-source KiCad projects,
extracts circuit design patterns, and enables AI-driven hardware design from
intent to manufacturing files.

## Code Style

- **Python**: ruff formatted, type hints on signatures, pathlib, f-strings
- **Shell**: `set -euo pipefail`, quote all vars, use `$(...)` not backticks

## Key Decisions

- **KiCad 10 toolchain, KiCad 9 emission format** — kicad-cli 10 is the validation
  toolchain (resolve from PATH via `src/pipeline/kicad_cli.py`, never a hardcoded
  path); the parser accepts KiCad 3–10 files (KiCad 10 boards drop the numbered net
  table — kiutils Fix 7); generated files emit the KiCad 9 version token (20250114),
  which KiCad 10 accepts. Old files can be normalized headlessly via
  `kicad-cli sch|pcb upgrade` (new in 10)
- **kiutils** is the primary parsing library (sch + pcb, typed objects, KiCad 9/10 tested)
- **sexpdata** is the fallback for raw S-expression access
- **kicad-cli** for validation (ERC, DRC, netlist export) — runs headless
- **File-level parsing**, not KiCad IPC API — works without running KiCad instance

## Directory Structure

```
hardware/
├── docs/                  # Research, specs, thesis
│   ├── thesis.md          # Master research document
│   └── ci.md              # CI: runners, image, pinned corpus
├── src/ecad/              # Typed design model (Component/Pin/Net/Design)
├── src/pipeline/          # Corpus parsing, generation, validation
├── ci/Dockerfile          # KiCad 10 CI image
├── scripts/               # Acquisition, triage, validation scripts
├── tests/                 # Test suite
├── data/                  # (gitignored) Raw + parsed + pattern data
└── .devcontainer/         # Dev environment with KiCad 10 CLI
```

Dependency direction is **`src/pipeline` → `src/ecad`, never the reverse.**

## Running things

This repo uses a virtualenv at `.venv/`. The system `python3` does **not** have
pytest or ruff installed — always use the venv binaries:

```bash
.venv/bin/pytest tests/ -q          # NOT python3 -m pytest
.venv/bin/ruff check src/ tests/    # must pass before committing
```

Working directory is `~/code/research-hardware`.

## Tests and KiCad

Tests that drive `kicad-cli` **skip** when KiCad is not installed — they do not
fail. If you see a large number of skips locally, that is expected without KiCad;
CI runs them for real. See [10-ci.md](10-ci.md).

Tests use REAL KiCad files from `data/raw/` — no mocks. That corpus is gitignored
and pinned by commit; `bash scripts/clone_pilots.sh` populates it.

## Workplan Reference

See `docs/thesis.md` Section 8 for the full task list (TASK-001 through TASK-029).

## Git Workflow

Branches + PRs, never commit to main directly.

```bash
git checkout -b <type>/<description>   # feat, fix, docs, chore, test, ci
git commit -m "<type>(<scope>): <msg>" # max 72 chars, imperative
```
