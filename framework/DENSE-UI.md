# DENSE-UI — a framework for fixed-size, decision-heavy panels

One screen that must hold many parameters without overwhelming: a synth device,
a hardware bring-up bench, a firmware telemetry console, a multi-discipline
engineering tool. The framework makes the layout decisions FOR the user, records
each one, and binds every control to a backend through one seam.

**The spine — three stages, in order, each ending at a hard gate:**

```
REASON (census)  →  LAYERS (layout, committed L0→L5)  →  CONTRACT (behavior + binding)
```

You may not draw in stage 1, bind in stage 2, or re-zone in stage 3.

**The one-sentence model:** a dense panel is one parameter tree rendered twice —
once as pixels, once as traffic on a wire. Widgets call the tree; the tree calls
an adapter; the adapter owns the transport. No widget ever imports the backend.

Synthesized from three lens drafts (`draft-cognition.md`, `draft-systems.md`,
`draft-craft.md`, beside this file) and verified against a working replica of
Ableton Operator — census/layers/contract in `example-operator/`, beside this
file. Read the drafts for the full arguments.

The procedures that execute this framework are three skills:
`~/.claude/skills/ui-reason/SKILL.md` (stage 1),
`~/.claude/skills/ui-layout/SKILL.md` (stage 2),
`~/.claude/skills/ui-bind/SKILL.md` (stage 3).

---

## The budgets (constants every stage is measured against)

| Budget | Value | Consequence |
|---|---|---|
| Working memory | ~4 chunks | every "remember where you were" spends a slot the task needs |
| Pre-attentive glance | <200 ms | only position, color, size, motion survive; text does not |
| Causality window | ~100 ms | slower feedback reads as a broken tool, not a slow one |
| Chromatic roles | ≤3 per panel | selection, active/hot, semantic alarm; structure stays achromatic |
| Chunk size | ≤5 controls, ≤5 chunks/zone, ≤4 zones | above five, a chunk becomes a list to search |

**Why density wins:** hidden controls cost recall ("which tab was it under?"),
which decays; visible controls cost recognition, which does not. And Fitts: a
dense panel with small targets close together operates faster than a sparse one
with big targets far apart. Density is a memory argument and a speed argument,
not an aesthetic one.

## The craft axioms

- **A1 — Crowding is axis proliferation, not control count.** Fix a crowded
  panel by merging alignment axes, never by deleting parameters. Target:
  controls ÷ distinct axes ≥ ~3. Executable, not advisory:
  `densui.audit.axis_census` counts the axes a rendered panel actually draws
  (and Bonsiepe's Ω, psycho-math R6.3) and `densui.audit.check_axis_budget`
  spends them; a panel that earns a lower floor declares it in `[rules]` with a
  written `axis_budget_reason`.
- **A2 — Contrast rises as area falls.** Ground flattest, plates next, labels,
  values, then state marks strongest. Nothing large may be loud.
- **A3 — Delete edges before content.** Plates are a 2–4 % luminance step and a
  gap, not a stroke. Perceived density tracks edge count, not object count.
- **A4 — Color is a state channel; decoration gets none.**
- **A5 — The value is the control.** Drag the number itself; no slider + spinner
  + readout triples.
- **A6 — One inverted ground, and it means "contextual".** Exactly one dark
  region, and its content follows selection.
- **A7 — A fixed instrument is measured in pixels.** No reflow, no breakpoints,
  no user layout. Scale uniformly if needed.
- **A8 — Motion belongs to the backend.** Meters animate; a dragged control
  answers in the same frame with zero easing.

---

## STAGE 1 — REASON (the census)

Count the world before drawing anything. One table, every row complete.

1. **List every parameter**: name, kind (continuous / int / bool / enum /
   trigger / read-only stream), min, max, taper, unit, default, and its value in
   the reference or a typical session.
2. **Assign each a candidate address now** — dotted, lowercase, stable:
   `osc.b.level`, `bench.rail.3v3.setpoint`. An address you cannot write down is
   a parameter you do not yet understand. The address will outlive the layout.
3. **Classify direction**: `set` (UI writes), `read` (stream: meters, link
   state, temperatures — census them even though they have no knob), `derived`
   (computed; gets NO address of its own), `ui.` (local, never transmitted).
4. **Write the display string and the widest string** per parameter
   (`-5.9 dB` and `-inf dB`; `468 Hz` and `8.61 kHz`). Precision and unit are
   census facts; the widest string sizes columns in stage 2.
5. **Assign a read tier**, exactly one: `GLANCE` (<200 ms, encoded in
   position/color/size only), `SCAN` (point from memory, confirm by label),
   `READ` (exact number, foveal stop). Two tiers on one parameter = a bug.
6. **Score frequency** (constant / per-task / per-setup / rare — decides
   position) and **consequence** (free / visible / costly / destructive —
   decides error treatment; the only thing allowed to lower density).
7. **Write the glance questions** — ≤5, in the user's words ("Is it on?",
   "What am I editing?", "Is anything clipping?"). Each maps to ≥1 GLANCE
   parameter; each GLANCE parameter serves ≥1 question.
8. **Open the mode ledger**: every control whose meaning changes with another
   (Operator: `Fixed` relabels Coarse→Freq, Fine→Multi in place). Record
   trigger, scope, indicator, relabel.
9. **Open the decision ledger**: every choice taken away from the user, with the
   rejected alternative and the reason.
10. **Find repeated templates and the canonical order.** Repeated prefixes in
    the tree (`osc.{a..d}.*`) predict repeated plates; shared suffix sets
    (`*.env.*`) predict a shared editor. Order by the domain's learned order
    (ADSR, signal flow, boot sequence) — never alphabetical.
11. **Count and publish**: total parameters, per-chunk counts, N settable /
    streams / derived / ui-only. "63 parameters in 1500×260 px" is a design fact.

**GATE 1 — do not draw until:** every row complete (address, direction, tier,
frequency, consequence, format, widest string, default) · glance questions
mapped both ways · mode + decision ledgers open · templates and canonical order
named · counts published · zero layout words in the census · every mark in the
reference attributed (no orphan ink) · no parameter marked "we'll hide it".

---

## STAGE 2 — LAYERS (layout committed L0→L5)

Six layers, committed in order. The order is simultaneously the paint order, the
contrast order (A2), and the commit order. Render and look after each layer.
Each layer also carries a binding obligation — a layout that cannot satisfy it
is wrong regardless of how it looks.

**L0 — Frame.** Fix the size in px; set a base unit (4 px) and snap everything
to it. Choose the ground tone (largest area → flattest). Declare the frame
non-responsive and versioned: after ship, moving a control is a breaking change.
Binding: fixed frame ⇒ static widget count ⇒ the whole binding table is known at
build time. *Test: the empty frame looks deliberate.*

**L1 — Zoning.** Cut into ≤4 zones along the domain's flow; zone boundaries
follow address prefixes (a zone is a subtree). Assign the one inverted ground
(A6) to the contextual zone. Spend all gutters here, once. **Choose the shared
editor now — one detail region, many owners** — the single decision that makes
a large census fit. It is legitimate only if: the owner stays visible and live
(a row that still works is a selector; a tab is pure overhead), the detail
always appears in the same place, and switching costs one click and zero memory.
Exactly one owner is selected at all times — no null state. No tabs over objects
of one kind, no accordions, no modals, no popovers.
*Test: squint — the zones survive, the contextual zone is the focus.*

**L2 — Group plates.** Repeated templates get identical geometry on a strict
stack or grid; plates are luminance + gap, no strokes (A3); ≤5 controls per
plate. One plate subscribes to one prefix (atomic repaint — no half-old rows on
preset load). Exactly one plate carries the selected treatment, always.
*Test: greyscale — hierarchy readable, every border justified.*

**L3 — Control placement.** Shared axes: knobs on one centerline, labels on one
baseline, values on one baseline (A1). One label rule panel-wide. Column widths
come from the census's widest string — never from the live value (a column that
resizes mid-drag makes the panel shimmy). Tabular figures mandatory for changing
values; the unit lives inside the value's text node (`8.61 kHz`) — no legends,
no tooltips, no hover-only labels. Geometry derives from the descriptor, never
from a value. **Every dimension comes from a measured ratio table** (built in
stage 1 by pixel-measuring the reference, never by eye); widget-library defaults
are how a panel starts looking machine-generated, and the text:control height
ratio is the identity-carrying one (Operator: ~0.8 — text nearly knob-height).
*Test: draw the axes, count them; controls ÷ axes ≥ ~3.*

**L4 — State and annunciators.** Apply the color budget (A4); write the channel
table (which hue means what, per zone) and allow no channel two meanings in one
zone. Selection announces at both ends: the source plate lights AND the shared
editor names its owner. Mode switches annunciate in two channels, one
non-textual (relabel + mark). Disabled sections dim (~40 %) but keep geometry
and stay interactive. Every annunciator names a source address AND a staleness
deadline — **unknown must not look like zero**: a dead sensor renders `—`/dim,
never a plausible `0.00`. Telemetry lives on edges/strips, never interleaved
with editable controls. *Test: screenshot every state; no coordinate moves.*

**L5 — Interaction affordances.** One gesture vocabulary, stated once, outside
the chrome: drag = change, shift = fine, double-click = default, wheel = step,
click = select. The whole plate is the selection target. The cursor states the
role (`ns-resize`, `pointer`) — the cheapest affordance there is. Graphs are
editable (one handle moves two parameters) or they are wasted area. Gestures
emit intents (`addr, delta, modifiers`); the tree converts and clamps — this is
what makes interaction replayable in tests and rate-limitable at the seam.
Error prevention is cheap reversal, never confirmation dialogs; destructive and
continuous controls never share a chunk. User-driven response is instantaneous;
only backend-driven values animate (A8).

**GATE 2 — do not bind until:** counts hold (≤4 zones, ≤5 chunks/zone, ≤5
controls/chunk) · every census parameter has a home; none hidden · region→prefix
map has zero orphans both ways · channel table written, no collisions ·
worst-case string test passes (no column moves) · squint + greyscale pass ·
**point test** (a stranger with the census points at 10 named parameters, each
<2 s) · **glance test** (1 s flash answers all glance questions) · a static
render from defaults alone exists, with no backend attached · decision ledger
updated with every layout call.

---

## STAGE 3 — CONTRACT (behavior + binding)

Every control names one address; both sides talk to the tree, never to each
other.

1. **One descriptor shape, no exceptions**: `{ addr, label, kind, min, max,
   taper, default, enum?, fmt(v), parse(s), step, dragScale, direction,
   authority, persist }`. One shape → one renderer → a hundred controls that
   stay identical. `dragScale` defaults to 200 px = full range through the taper.
2. **`fmt` is pure, total, and owns units + precision.** It must render every
   state: normal, floor (`-inf dB`), over-range (`over`), stale (`—`), unread
   (`?`). A formatter that cannot say "no data" will print a plausible number
   when the link is down. Column widths are measured from `fmt` at build time.
3. **Store engineering units; derive normalized [0,1] on demand.** Taper lives
   in the value model, and `denorm(norm(v)) == v` is a test, not a hope.
4. **The tree API is the only mutation path**: `get(addr)` · `set(addr, value,
   source)` · `subscribe(prefix, cb)` · `stream(addr, cb)`. `set` clamps,
   quantizes, notifies UI, then the adapter. `source ∈ {user, device, preset,
   automation, test}` — this one field buys undo (record only `user`), echo
   handling, and automation at once. Unknown address **throws**; a control bound
   to nothing must fail loudly, never render a default.
5. **The adapter is the only replaceable part**: `apply(addr, value)` ·
   `readAll()` · `subscribeStreams(cb)` · `health()` · `capabilities()`.
   Transports (in-process, OSC, WebSocket, serial) differ in exactly ordering,
   coalescing, latency, back-pressure — handled here, invisible to widgets.
   Coalesce last-write-wins per address per frame; decimate for slow links at
   the seam, never in the widget.
6. **Latency classes, per address**: <100 ms → render optimistically (in-process
   engines); 100 ms–1 s → show local value + an *unconfirmed* badge until echo
   (OSC, WebSocket, serial); >1 s or unreliable → the control is a *request*
   with pending/failed states (firmware writes). The ~100 ms causality window is
   why these classes exist.
7. **Sync state is three values per address**: `local` (optimistic),
   `confirmed` (last device ack), `pendingSince`. Render `local`; badge when
   pending exceeds the deadline. **Suppress echoes by generation token, never by
   value comparison** (devices quantize: send 8610, get 8608, a value-comparing
   UI loops). If a readback disagrees with no pending token, adopt the device
   value and repaint — hiding a disagreement hides a range bug.
8. **Never move a value under the cursor**: while a control is engaged, device
   pushes to that address queue, and apply on release.
9. **Modes rebind, they never duplicate.** The same widget switches address
   under the governing flag, exactly as the mode ledger recorded. Hidden
   duplicate widgets drift.
10. **Streams are a separate namespace**: read-only, sampled at a stated rate,
    staleness deadline, never persisted, never undoable; `set` on a stream
    throws.
11. **Persistence is address → engineering value + schema version.** Unknown
    address on load reports loudly and names it — a silently dropped address is
    a preset that quietly changed sound.
12. **Degraded mode is written before shipping**: on disconnect, values keep
    last-known + stale mark, streams render `—`, writes queue or refuse (state
    which), link state is a first-class annunciator.

**GATE 3 — done when:** binding coverage is bijective (zero orphan widgets,
zero unreachable addresses, tested in both directions) · formatter/parser table
test passes incl. floor/over/stale/unknown · taper round-trip test passes · the
whole panel runs headless against a **fake backend** · echo/coercion drill run,
not asserted · disconnect drill run mid-drag · rate test: 120 Hz of drags into a
slow transport, bounded queue, correct final value · a second adapter has driven
the same panel unchanged · **cold-read test**: a stranger names the selected
section, enabled sections, and current mode within 10 s, with no legend.

---

## Decisions the tool makes FOR the user

A preference is not a kindness: the user must make it, remember it, re-make it
on the next machine — and it dissolves the shared spatial map that lets one
person's expertise transfer to another's screen. Decide, record, never ask.

| Decided | Rejected | Reason |
|---|---|---|
| Fixed size, uniform scale only | Responsive reflow | spatial constancy is the substrate of expertise |
| One shared detail editor | Tabs / popovers / accordions | owner stays live; zero navigation depth; one address for "detail" |
| Selection = click anywhere in a plate | Explicit edit buttons | the chunk is already the target |
| Unit inside the value text | Legends, tooltips | no working-memory carry per read |
| Color reserved for state | Decorative color | ≤3 chromatic roles is a hard budget |
| Canonical domain order | Alphabetical / space-optimal | reuses an order already in long-term memory |
| Uniform repeated templates | Per-instance optimization | N instances, one learning event |
| No user-configurable layout | Customizable panels | preserves the shared map |
| Cheap reversal everywhere | Confirmation dialogs | a dialog amputates the context you judge against |

## The tests, in one place

| Test | Catches | When |
|---|---|---|
| Squint | zoning/focus errors, shouting decoration | after L1, L2 |
| Greyscale | color carrying the only copy of a state | after L4 |
| Worst-case string | live-value jitter, unreserved failure strings | after L3, gate 3 |
| Ratio audit (headless render vs measured table, ±5%) | library-default geometry, wrong text:control ratio | gate 2 |
| Point (stranger, census, 10 targets, <2 s each) | wrong positions | gate 2 |
| Glance (1 s flash) | missing annunciators | gate 2 |
| Cold read (10 s, no legend) | missing selection/mode annunciation | gate 3 |
| Fake-backend headless run | binding gaps, hidden UI state | gate 3 |
| Disconnect + echo drills | fabricated readings, echo loops | gate 3 |

A panel that passes is calm. Calm is not a style — it is the absence of axes,
edges, and hues that were never earned, and the presence of an honest seam.

## The layout calculus

Stage 2's geometry is COMPUTED, never judged — the engine laying it out cannot
see. `LAYOUT-MATH.md` (same directory) is the calculus: sizes only from font
metrics or declared tokens; no coordinate a function of any text width; the
baseline as the only vertical text anchor; glyph-ink collision with declared
exceptions; the gap law (equal ±3% or ≥1.45×, similarity-gated); integer
edges; and the proof battery that replaces eyes. `research/` holds the
verified sources behind every constant.
