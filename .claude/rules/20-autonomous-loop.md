# Autonomous Work Loop

When invoked via `/loop`, follow this protocol.

## On Every Invocation

1. **Read PROGRESS.md** — this is the single source of truth
2. **Run tests** — from `~/code/research-hardware`:
   ```bash
   .venv/bin/pytest tests/ -q
   ```
   Use the venv binary: the system `python3` has no pytest installed.
3. **Assess state:**
   - Tests failing → fix the failing tests/code first
   - Tests passing → find the next unchecked `[ ]` task in PROGRESS.md
   - Phase complete → move to the next phase
4. **Do the work** — implement, test, fix
5. **Update PROGRESS.md** — mark completed tasks with `[x]`
6. **Commit** on a branch (never main): `git commit -m "<type>(<scope>): <msg>"`
7. **Push** and open/update a PR

## Reading the test result correctly

Skips are not passes. Without KiCad installed, roughly 58 tests skip — every one of
them covering ERC, DRC, Gerber or netlist export, i.e. the pipeline's validation
loop. Do not report "all tests pass" on a run with that skip count; say which
capability was missing. CI runs them for real (see [10-ci.md](10-ci.md)).

If the suite errors rather than skips on a missing tool, that is a bug in the
capability detection — fix it there, not by marking the test.

## Quality Standards

- All code must have tests (TDD — write test first, then implementation)
- Tests use REAL KiCad files from `data/raw/` — NO mocks
- Python: type hints, docstrings on public functions, pathlib for paths
- `.venv/bin/ruff check src/ tests/` must pass before committing

## Key Context

- Vendored kiutils is in `tools/kiutils/` — this is OUR copy to fix and extend
- Parser architecture spec is in `docs/parser-architecture.md`
- Full research is in `docs/thesis.md`
- Pilot projects (12 real KiCad designs) are in `data/raw/`, pinned by commit
- Pipeline code goes in `src/pipeline/`; the typed model lives in `src/ecad/`
