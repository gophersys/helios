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
- [x] `densui.audit`: the full proof battery (overlap w/ declared exceptions,
      crowding floors, gap law via `gap_law_violations`, containment,
      breathing, alignment spreads) as reusable functions consuming probe
      output; the operator scripts become thin wrappers. Chrome discovery
      cross-platform (mac path, `google-chrome`, `chromium`), FAIL if absent.
- [x] `densui.solve`: generalise `solve_layout.py` — inputs (anchors, floors,
      units, font path, tuck/breathing constants) come from a spec file, not
      constants in code; deterministic shuffled re-solve stays mandatory.
- [x] `densui.measure`: the reference-forensics toolkit (luminance scans,
      gridline crops, colour sampling, 8x anatomy zooms) from the session's
      ad-hoc scripts; Pillow as optional extra `[measure]`.
- [x] `densui compare`: ref-vs-built composite generator (the A/B strips).
- [x] CLI entry point: `uv run densui <solve|audit|sweep|measure|compare>`.

## P2 — The panel spec (make a new panel a data file, not a code fork)

- [x] Define `panel.toml` schema covering census -> tracks ->
      anchors -> widgets -> declared legal overlaps -> gate tolerances; write
      `docs/spec.md`.
- [x] Rewrite the Operator demo's solver inputs as `demos/operator/panel.toml`;
      byte-identical solved CSS proves the migration.
- [x] Schema validation with named errors (a spec typo must fail loudly).

## P3 — Gates in CI (all six proofs on every push)

- [x] Font-parametric demo build: `assemble.py --font <ttf>` — no font
      committed; the runner's DejaVu drives CI, the solver re-solves per font.
- [x] Chrome headless on the arc-org fleet runs ratio + overlap + sweep gates
      (`ctl.sh build --font <runner ttf>`); extend ctl.sh with a `geometry`
      target; if the fleet image lacks Chrome/fonts, coordinate with
      eden/infrastructure (BLOCKED.md) rather than pinning ubuntu-latest.
- [x] Adopt the cictl review standard (`ctl.sh test-review`, cictl review/)
      for this repo's PRs; all jobs hard-fail on arc-org.

## P4 — New demos, none of them Ableton (the real generality test)

- [x] `demos/telemetry/`: a firmware telemetry console (streams, staleness,
      alarms right/below per psycho-math) designed BLIND — no reference image;
      census -> spec -> solver -> gates only.
- [x] `demos/bench/`: a hardware bring-up bench panel (rails, probes, links)
      exercising the CONTRACT stage against a fake serial backend.
- [x] Each demo: census.md, panel spec, gates green, honest NOTES on what the
      framework could not decide.

## P5 — Eyes as a supplement, proofs as the authority

- [x] Integrate a CDP interaction loop for gesture-level
      verification (drags, menus, wheel), replacing ad-hoc CDP scripts.
- [x] `docs/eyes.md`: when screenshots may be consulted (anatomy discovery)
      and when they may not (never to pass a gate).

## P6 — Research continuation

- [x] Verify or discard the four unverified constants flagged in
      `framework/research/psycho-math.md` §9; update LAYOUT-MATH.
- [x] Empirically probe the forbidden-zone thresholds (1.03/1.45) on generated
      panels; record method + result.
- [x] Extend typo-math with the fonts actually used here (per-face cap tables).
- [x] dgrid tracks from font advances (grid_rows solver model; pulled forward on 3rd recurrence) — the display
      grid is the last hand-sized text geometry; DejaVu round 4 proved it
      (clabel ink gaps 1.4/1.8px), current fix is gap arithmetic only.

## P7 — Instrumentation

- [x] Repo `.claude/skills/`: repo-scoped ui-reason / ui-layout / ui-bind that
      cite THIS repo's framework files; keep the personal `~/.claude` copies as
      pointers (single canonical source: this repo). Update
      `~/.claude/CLAUDE.md` instrumentation list accordingly.
- (standing watch, not a box) `~/code/.claude/`: checked every run by the
      loop protocol; still absent. If it appears: re-read precedence, record
      conflicts in LOG.md, never override it.
- [x] An `ui-verifier` agent definition: runs only the proof battery and
      refuses to pass on assertion.

- [ ] Rebase dense-ui-ci as a gophersys/base CHILD image (house convention:
      base -> domain children; browser via google-chrome-stable apt repo, not
      snap/playwright-CDN). BLOCKED on the GHCR_PULL_TOKEN grant — see
      BLOCKED.md 2026-08-14; devcontainer keeps building FROM dense-ui-ci.

## P8 — Repository hygiene

- [x] ADR system (`docs/adr/`): ADR-0001 computed-not-judged;
      ADR-0002 licensed-assets policy.
- [ ] README polish with one A/B strip and one gate-failure example.
