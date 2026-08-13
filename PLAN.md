# PLAN — the Dense-UI programme

The single source of truth for what to build. The 10-minute loop (`LOOP.md`)
executes this top-to-bottom: first unchecked box in the lowest unfinished
phase. Every box = code + tests + gates green + docs + LOG entry + pushed
commit. Mark in-progress boxes with `⏳ <ISO-time>` and stuck ones with `⚠`.

## P0 — Bootstrap ✅

- [x] Repo, package (`densui.geometry`, `densui.fontmetrics`), tests, CI, demo
      import, framework + research corpus, loop + cron.

## P1 — Generalise the toolchain (de-Ableton everything outside the demo)

- [x] `densui.probe`: the DOM-measurement JS (ink rects via Range +
      `measureText`) as a library asset with a Python driver
      (`densui.probe.collect(page, selectors) -> parts`), extracted from
      `demos/operator/build/overlap_audit.py`.
- [ ] ⏳ 2026-08-13T21:08Z `densui.audit`: the full proof battery (overlap w/ declared exceptions,
      crowding floors, gap law via `gap_law_violations`, containment,
      breathing, alignment spreads) as reusable functions consuming probe
      output; the operator scripts become thin wrappers. Chrome discovery
      cross-platform (mac path, `google-chrome`, `chromium`), FAIL if absent.
- [ ] `densui.solve`: generalise `solve_layout.py` — inputs (anchors, floors,
      units, font path, tuck/breathing constants) come from a spec file, not
      constants in code; deterministic shuffled re-solve stays mandatory.
- [ ] `densui.measure`: the reference-forensics toolkit (luminance scans,
      gridline crops, colour sampling, 8x anatomy zooms) from the session's
      ad-hoc scripts; Pillow as optional extra `[measure]`.
- [ ] `densui compare`: ref-vs-built composite generator (the A/B strips).
- [ ] CLI entry point: `uv run densui <solve|audit|sweep|measure|compare>`.

## P2 — The panel spec (make a new panel a data file, not a code fork)

- [ ] Define `panel.toml` (or yaml) schema covering census -> tracks ->
      anchors -> widgets -> declared legal overlaps -> gate tolerances; write
      `docs/spec.md`.
- [ ] Rewrite the Operator demo's solver inputs as `demos/operator/panel.toml`;
      byte-identical solved CSS proves the migration.
- [ ] Schema validation with named errors (a spec typo must fail loudly).

## P3 — Gates in CI (all six proofs on every push)

- [ ] Font-parametric demo build: `assemble.py --font <ttf>` with a freely
      licensed committed font (check OFL redistribution properly; include the
      licence file) or the runner's DejaVu; solver re-solves for that font.
- [ ] Chrome headless in GitHub Actions runs ratio + overlap + sweep gates.
- [ ] CI job matrix: tools (pytest+ruff), demo-static (node --check +
      params self-test), demo-geometry (the proofs). All hard-fail.

## P4 — New demos, none of them Ableton (the real generality test)

- [ ] `demos/telemetry/`: a firmware telemetry console (streams, staleness,
      alarms right/below per psycho-math) designed BLIND — no reference image;
      census -> spec -> solver -> gates only.
- [ ] `demos/bench/`: a hardware bring-up bench panel (rails, probes, links)
      exercising the CONTRACT stage against a fake serial backend.
- [ ] Each demo: census.md, panel spec, gates green, honest NOTES on what the
      framework could not decide.

## P5 — Eyes as a supplement, proofs as the authority

- [ ] Integrate a Playwright-MCP (or CDP) interaction loop for gesture-level
      verification (drags, menus, wheel), replacing ad-hoc CDP scripts.
- [ ] `docs/eyes.md`: when screenshots may be consulted (anatomy discovery)
      and when they may not (never to pass a gate).

## P6 — Research continuation

- [ ] Verify or discard the four unverified constants flagged in
      `framework/research/psycho-math.md` §9; update LAYOUT-MATH.
- [ ] Empirically probe the forbidden-zone thresholds (1.03/1.45) on generated
      panels; record method + result.
- [ ] Extend typo-math with the fonts actually used here (per-face cap tables).

## P7 — Instrumentation

- [ ] Repo `.claude/skills/`: repo-scoped ui-reason / ui-layout / ui-bind that
      cite THIS repo's framework files; keep the personal `~/.claude` copies as
      pointers (single canonical source: this repo). Update
      `~/.claude/CLAUDE.md` instrumentation list accordingly.
- [ ] `~/code/.claude/`: still absent; if the loop ever finds it created,
      re-read precedence and record any conflicts in LOG.md instead of
      overriding it.
- [ ] An `ui-verifier` agent definition: runs only the proof battery and
      refuses to pass on assertion.

## P8 — Repository hygiene

- [ ] ADR system (`docs/adr/`) in the house style; ADR-0001: computed-not-
      judged; ADR-0002: licensed-assets policy.
- [ ] README polish with one A/B strip and one gate-failure example.
