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

## A/B: judged vs measured

The framework exists because judging failed three times in a row on the same
knob. From the Operator replica's corrections log
(`demos/operator/spec/ratios.md`):

| Dimension | A: judged (read as AI-generated) | B: measured (passes) |
|---|---|---|
| Knob diameter | Ø34 px — invented, round 1 | Ø27 px — scanned through the measured center |
| Knob diameter | Ø20 px — a **chord** scan, round 2 | (a chord under-reads the ring by 35%) |
| Label size | 11 px — invented | 16 px, from measured glyph heights |
| Graph:grid split | 63:37 — misread | 151:160 |

Every "A" column entry survived a look; none survived a pixel scan. Hence
ADR-0001: sizes come from metrics or declared tokens, and renders may FAIL a
build but may never PASS one (`docs/eyes.md`).

## What a gate failure looks like

The solver refuses rather than renders a violation. A 240px plate asked to
hold two dials whose widest value string does not fit
(`docs/examples/crowded.toml`, committed; a test pins this refusal so the
example cannot rot — output verbatim, ink decimals vary by face):

```
$ densui solve crowded.toml
densui: solve failed: row/coarse: widest value ink ends 103.4, crowds next dial at 64.0 (needs +43px > anchor_tolerance 2)
$ echo $?
2
```

Both part names, the two coordinates in conflict, the shortfall in px, and the
bound that stopped the solver from silently absorbing it. The fix is a design
decision — wider plate, shorter format, larger tolerance — made in the spec,
never by the renderer.

## Layout

| Path | What |
|---|---|
| `framework/` | `DENSE-UI.md` (the method), `LAYOUT-MATH.md` (the calculus), lens drafts, `research/` (verified sources behind every constant) |
| `tools/densui/` | the calculus as a Python package: font metrics, solver, geometry predicates, glyph-ink probe, CDP gesture driver, tree/seam contract reference (uv project; `uv run --extra dev pytest`) |
| `demos/operator/` | worked example: a playable Web Audio replica of Ableton Operator, solver-laid-out, gate-proven (needs local fonts — see its README) |
| `demos/telemetry/` | first fully-blind panel: designed and built with no reference image, passing its own battery |
| `demos/bench/` | the CONTRACT demo: rendered from a live parameter tree after a scripted drill session — the pixels are evidence of contract states |
| `corpus/` | one minimal page per measured defect class, seeded with exactly one deliberate defect its predicate must catch (`./ctl.sh score`) |
| `docs/` | `eyes.md` (what looking may and may not decide), `spec.md`, `scorecard.md`, `adr/` (ADR-0001 computed-not-judged, ADR-0002 licensed assets) |
| `ci/` | the `dense-ui-ci` image (Chromium + fonts + uv); CI runs the same gates as `ctl.sh` |
| `loop/` | the autonomous 5-minute work loop (launchd; armed manually) |
| `.claude/` | repo instrumentation: rules, `ui-reason`/`ui-layout`/`ui-bind` skills, the `ui-verifier` agent |
| `PLAN.md` / `LOOP.md` / `LOG.md` | the autonomous work loop: plan, protocol, journal |

## Provenance

Extracted from a working session that built the Operator replica and, forced by
each failure, the framework itself. The corrections log in
`demos/operator/spec/ratios.md` records what eyeballing got wrong and what
measuring fixed — the repository exists so that never has to be relearned.
