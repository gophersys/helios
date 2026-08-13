# dense-ui

Research, tooling, `.claude` instrumentation and demos for building **dense,
fixed-size, decision-heavy UIs** — instrument panels, engineering consoles,
telemetry dashboards — with a **blind layout engine**: an LLM that cannot see,
so layout is computed from mathematics and proved by geometry checks, never
judged from pixels.

## The idea in one paragraph

A dense panel is one parameter tree rendered twice: once as pixels, once as
traffic on a wire. The framework walks three gated stages — **REASON** (a
parameter census before any layout), **LAYERS** (layout committed in six
layers), **CONTRACT** (every control bound to one address behind one adapter
seam) — and the geometry of stage 2 is emitted by a **solver** from font
metrics and measured anchors, then proved by a battery: glyph-ink overlap,
crowding floors, the gap law, containment, alignment, edge breathing, and a
widest-string content sweep. What a sighted reviewer calls "looks off"
decomposes into a failed predicate with two names and a number.

## Layout

| Path | What |
|---|---|
| `framework/` | `DENSE-UI.md` (the method), `LAYOUT-MATH.md` (the calculus), lens drafts, `research/` (verified sources behind every constant) |
| `tools/densui/` | the calculus as a Python package: font metrics, geometry predicates (uv project; `uv run --extra dev pytest`) |
| `demos/operator/` | worked example: a playable Web Audio replica of Ableton Operator, solver-laid-out, gate-proven (needs local fonts — see its README) |
| `.claude/` | repo instrumentation for Claude sessions working here |
| `PLAN.md` / `LOOP.md` / `LOG.md` | the autonomous work loop: plan, protocol, journal |

## Provenance

(Canary line: exercising the on-pr review lane; this PR merges trivially.)

Extracted from a working session that built the Operator replica and, forced by
each failure, the framework itself. The corrections log in
`demos/operator/spec/ratios.md` records what eyeballing got wrong and what
measuring fixed — the repository exists so that never has to be relearned.
