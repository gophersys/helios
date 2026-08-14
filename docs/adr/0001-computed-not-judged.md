# ADR-0001: Computed, Not Judged

- **Status:** Accepted
- **Date:** 2026-08-14
- **Deciders:** Mateo

## Context

The builder of these panels cannot see them. Every generation of the Operator replica that
relied on visual judgement — estimated knob diameters, eyeballed ratios, "looks right" spacing —
was wrong, three times in a row, and each wrongness read as machine-generated to a human in
under a second. Meanwhile every number that came from measurement (pixel scans, TTF metrics,
glyph-ink probes) survived. A verdict produced by looking is a check that cannot fail in the
hands of something that cannot look.

## Decision

Geometry and verdicts are computed, never judged. Concretely:

- Every size derives from TTF metrics or a declared token (LAYOUT-MATH A-1); no coordinate is
  a function of rendered text width (A-2). Layout is solved, then audited by the proof battery.
- Renders, screenshots and composites may generate a FAIL — decomposed into a predicate with
  two part names and a number — and may never generate a PASS (`docs/eyes.md`).
- A gate's result is its bare exit code. Piping a gate through grep/tail in the command that
  decides success is banned (LOOP.md; three real masking incidents).
- A check that cannot run is a FAIL, never a skip: missing Chrome, missing font, missing file
  all raise (`probe.py`, `fontmetrics.py`, `audit.py` are fail-loud throughout).
- Local runs develop; the fleet certifies. Fleet-relevant claims read the CI run's per-job
  conclusions, not a local green (the Arial-vs-DejaVu divergence cost four rounds).

## Consequences

Easier: blind agents produce panels that pass their own batteries on first render (telemetry,
bench); disagreements resolve by re-running a measurement instead of re-arguing a taste.
Harder: every new visual property needs a predicate and a probe before it can be enforced —
"it looks cramped" must become a gap number against G-1 before it counts. Invalid: any PASS
whose provenance is a look, including a human's. Alternative rejected: screenshot-diff
approval (judgement at one remove — it moves the eyeball into a threshold nobody can defend,
and it cannot name which part is wrong).
