# Dense-UI — a design framework for fixed-size, decision-heavy panels
### Draft: the VISUAL CRAFT lens

Scope: one screen holding many parameters at once — a synth device (Ableton
Operator), a hardware bring-up bench, a firmware telemetry console, an EE/SW
status wall. The backend may be an audio engine, OSC, a serial link, or a
WebSocket bus; the craft does not change, because the eye cannot see transports.

The spine is fixed: **REASON (census) → LAYERS (layout committed layer by layer)
→ CONTRACT (behavior + address).** You may not draw in stage 1, bind in stage 2,
or re-zone in stage 3. Each stage ends at a hard gate.

## Craft axioms

The rules of thumb the three stages enforce, each with its reason — a rule
without its reason gets misapplied at the first exception.

**A1 — Crowding is axis proliferation, not control count.**
A panel feels crowded when the eye has too many distinct start-lines to track.
Operator holds ~63 reachable parameters and still reads calmly, because they
resolve to roughly a dozen x-positions and eight y-positions. Measure **axis
economy** = controls ÷ distinct alignment axes. Below ~3 a panel feels noisy
however few controls it has; above ~4 it reads as a machine. Fix crowding by
merging axes, not by deleting parameters.

**A2 — Contrast rises as area falls (inverse-area contrast law).**
Largest region, flattest tone; smallest mark, strongest. Ground → plate → label
→ value → state mark. Anything with both large area and strong contrast (a
bright background, a heavy border grid, a saturated header) steals the
pre-attentive budget from the marks that actually change.

**A3 — Delete edges before deleting content.**
Perceived density tracks *edge count per unit area*, not object count. A plate
defined by a 2–4 % luminance step costs zero edges; the same plate with a 1 px
stroke costs four. Operator separates eight rows with luminance and a 1 px gap
and draws no boxes at all. Borders are the first cut when a panel feels tight,
and cutting them costs no information.

**A4 — Color is a state channel. Decoration gets none.**
Hue is the only channel that survives peripheral vision in a crowded field, so
spend it on what changes. Budget: **at most three chromatic roles** — SELECTION,
ACTIVE/HOT, SEMANTIC ALARM (reserved, normally absent). Everything structural is
achromatic. Operator: blue = selected/enabled, amber = hot value or engaged chip,
green/yellow/orange/red = per-source LEDs. Nothing is colored because it looked
nice.

**A5 — The value is the control.**
One parameter = one visual object that both displays and edits. A slider plus a
spinner plus a text field is three affordances and one fact; it triples the cost
per parameter and buys nothing. Drag the number itself. Chrome you did not draw
cannot crowd the panel, and those pixels are what let the census fit.

**A6 — One inverted ground, and it means "contextual".**
Reserve a single dark (or otherwise inverted) region for the area whose *content
changes with selection*. The user learns the ground, not a legend: light = always
here, dark = belongs to whatever is selected. A second inverted region breaks the
rule and the panel becomes a collage.

**A7 — A fixed instrument is measured in pixels.**
Density UIs do not reflow. Target constancy makes a panel learnable — muscle
memory addresses a screen position, and a control that moves between sessions
cannot be learned. Scale the whole frame uniformly if you must; never rewrap,
never breakpoints, never user-chosen layout. A decision made FOR the user.

**A8 — Motion belongs to the backend, never to the user's own hand.**
Meters, plots, and telemetry may animate. A control answering a drag moves in
the same frame with zero easing: an eased knob reads as a slow machine and then
as an inaccurate one. Latency in a value is indistinguishable from error.

## STAGE 1 — REASON (census)

No layout, no sketch, no component names. You are counting the world.

1.1 **State the frame facts first.** Fixed size in px, aspect, whether it scrolls
(it does not), what surrounds it. Everything downstream is a budget against it.

1.2 **List every parameter** with name, type (continuous / int / bool / enum /
trigger / read-only telemetry), range, unit, default, and its reference value.

1.3 **Write the display string for each parameter, now** — `-inf dB`,
`8.61 kHz`, `15.7 ms`, `0 %`, `+3 st`. Precision and unit are census facts, not
styling; they decide column widths in stage 2, so finding them later means
re-doing the layout.

1.4 **Record the widest possible string per parameter**, not the current one.
`-inf dB` beats `-5.9 dB`; `8.61 kHz` beats `468 Hz`. This is the number stage 2
reserves space for.

1.5 **List every non-parameter mark**: labels, headers, badges, LEDs, meters,
glyphs, chrome. If ink exists it is on this list; ink with no owner is
decoration and gets deleted at the gate.

1.6 **List the states each control can annunciate**: selected, enabled/disabled,
modal relabel, out-of-range, stale/no-data, editing. States are what color will
be spent on, so an unlisted state cannot be shown.

1.7 **Name the mode switches** — any control whose *meaning* changes with
another. Operator: `Fixed` on relabels Coarse→Freq and Fine→Multi in the same two
knob positions. Mode switching is a density mechanism and the easiest thing to
render invisibly, so it is flagged here.

1.8 **Count the density and name the mechanisms that pay for it**: contextual
editor shared by many owners; repeated row templates; modal relabeling;
unit-bearing values instead of separate readouts; color reserved for state. If
the count does not fit the frame, add a mechanism — never shrink the type.

### Gate 1 — do not proceed until

- [ ] Every parameter has type, range, unit, default, format, and widest string.
- [ ] Every mark is attributed to a parameter, label, state, or the frame.
      **No orphan ink.**
- [ ] Every state and every mode switch is written down.
- [ ] The density count and the mechanisms that pay for it are on the page.
- [ ] Not one layout word has been written. If the census says "left panel", you
      skipped a stage — delete it and keep counting.

## STAGE 2 — LAYERS

Layout is committed in six layers, back to front. The order is not arbitrary: it
is at once the **paint order**, the **contrast order** (A2), and the **commit
order**. Each layer spends only the space and contrast the layer under it left
behind, and once committed it is frozen — later layers adapt to it. That is what
stops one late control from quietly re-flowing a whole panel. Render after each
layer and look at it; a layer you cannot look at is a layer you did not commit.

### L0 — Frame
- Fix the canvas in px. Set the base unit (4 px is a good default) and snap every
  later coordinate to it: sub-pixel offsets read as blur, blur reads as noise.
- Choose the ground tone. Largest area, so flattest (A2).
- Record non-responsiveness as a decision made for the user (A7).
- *Commit test:* an empty frame at final size looks like a deliberate object.

### L1 — Zoning (the density budget is spent here, once)
- Divide the frame into 3–5 zones with proportions, not contents. Operator:
  left rack ~30 %, contextual dark display ~38 %, right rack ~28 %, plus grip
  and meter edges, with a full-width title bar above.
- Assign the **one inverted ground** (A6) to the contextual zone.
- Set the gutters here and nowhere else. Whitespace in a fixed panel is spent
  once at zone level; inside plates, padding is a small constant. Spend it per
  control and you run out, then start shrinking type instead.
- Decide the sharing rule: **one detail editor, many owners.** Eight Operator
  sections share one center editor — the single decision that makes ~63
  parameters fit. No popovers, tabs, or accordions: they trade density for
  clicks and hide state.
- *Commit test:* squint until text disappears. You should still see the zones,
  and the contextual zone should be the obvious focus.

### L2 — Group plates
- Repeated plates go on a strict stack or grid; identical roles get identical
  geometry. A repeated template is the cheapest density mechanism there is — the
  eye learns it once and then reads by position.
- Define plates by luminance step and gap, not by stroke (A3).
- Split the contextual zone into fixed sub-regions (Operator: graph ~55 % top,
  parameter grid ~45 % bottom, in two labeled columns).
- Exactly one plate carries the selected treatment, always — never zero.
- *Commit test:* in greyscale the plate hierarchy reads, and no border exists
  that you cannot justify.

### L3 — Control placement (grids and shared axes)
- Inside each plate, place controls on **shared alignment axes**: knobs in a row
  on one centerline, labels on one baseline, values on one baseline. Alignment
  is what makes a repeated template invisible.
- Columns get a fixed width from census 1.4 — widest formatted string plus the
  base unit. Never size a value column to its current content: a column that
  resizes mid-drag makes the panel shimmy, and shimmer reads as instability.
- Label position is one rule per panel, applied everywhere (e.g. label above,
  value below-right). Mixed conventions cost a lookup on every glance.
- **Label economy:** if a label repeats three or more times along one axis, it
  moves to a column or plate header. The unit already lives in the value, so the
  label carries meaning only.
- Typography: one small sans in two sizes (label ~11 px, value ~12 px) plus a
  tabular-figure or monospaced face for anything numeric. **Tabular figures are
  mandatory** for values that change: proportional digits change width with the
  digits, so a live value visibly jitters. Units live in the same text node as
  the number (`8.61 kHz`) — no separate readout to align, crowd, or lose. Align
  on the numeral/unit boundary, never centered: a centered column of numbers has
  no readable edge.
- *Commit test:* draw the axis lines over a screenshot. Count them. If controls
  ÷ axes is under ~3, merge axes before continuing (A1).

### L4 — State and annunciation
- Apply the color budget (A4). Selection hue, active hue, semantic hue. Nothing
  else is chromatic.
- **Selection is announced at both ends of the wire:** the source plate carries
  the lighter ground and the accent, and the contextual editor names its owner in
  its header. The commonest dense-UI defect is a shared editor that never says
  whose values it shows.
- **Mode switches annunciate in two channels, one non-textual.** Operator
  relabels Coarse→Freq *and* adds corner ticks. A text-only change is invisible
  to an eye that is on the knob; a mark-only change is unreadable.
- Disabled sections dim (~40 % opacity) but keep geometry and stay interactive
  where the backend allows. Hiding a disabled control moves the layout and
  destroys target constancy (A7).
- Telemetry and read-only state (meters, link status, temperatures) live on an
  edge or a dedicated strip, never interleaved with editable controls: the user
  must see at a glance what they can change.
- Distinguish **no data** from **zero**. A stale channel renders as a dash or a
  dimmed field, never `0.00`. A console showing a plausible zero for a dead
  sensor is worse than one showing nothing.
- *Commit test:* screenshot the panel in every state (all selections, all modes,
  enabled and disabled, alarm present). No coordinate may move between shots.

### L5 — Interaction affordances
- The whole plate is the selection hit target, not a small badge — a large
  target costs no pixels, because it is area you already drew.
- One gesture vocabulary for the whole panel: vertical drag = change, shift =
  fine, double-click = default, wheel = step. Documented once in a help strip
  outside the instrument chrome — never as tooltips inside it.
- The cursor is the affordance: `ns-resize` on draggables, `pointer` on plates
  and toggles. Cheaper than any visual hint, and it never crowds.
- Where a graph exists, drag its breakpoints, one handle moving two parameters
  at once. A graph you can only read is wasted area.
- No hover-only information: hover reveals hide state from exactly the
  peripheral vision a dense panel exists to serve.
- Never re-order or re-sort controls in response to data. Sorting is for lists;
  an instrument's positions are the addresses the hand has memorized (A7).
- User-driven response is instantaneous; only backend-driven values animate (A8).
- *Commit test:* every interactive object has a cursor, a hit area ≥ its visual
  size, and a keyboard or pointer path to its default.

### Gate 2 — do not proceed until

- [ ] All six layers committed in order, each rendered and looked at.
- [ ] **Squint test:** zones and focus survive; nothing unintended shouts.
- [ ] **Greyscale test:** fully usable with hue removed — hue reinforces state,
      it never carries the only copy of it.
- [ ] **Worst-case string test:** every value at its widest string, no column
      moves.
- [ ] **Axis count** recorded; controls ÷ axes ≥ ~3.
- [ ] Every chromatic mark maps to a census state; the color budget holds.
- [ ] Decisions made FOR the user are listed (fixed size, one shared editor,
      selection follows any click in a plate, values are the controls, color
      reserved for state). Anything on this list is never exposed as a preference.

## STAGE 3 — CONTRACT

One parameter tree is the single source of truth: the UI and the backend never
talk to each other, only to the tree. That seam is what makes the same panel work
over Web Audio today and a serial link tomorrow.

3.1 **One address per control** (`osc.b.env.attack`, `bench.rail.3v3.setpoint`,
`link.uart0.baud`). One address, one control, no duplicates, no aliases.

3.2 **One descriptor shape for every parameter**: `addr, label, kind, min, max,
taper, default, enum?, fmt(value) → string-with-unit, dragScale`. One shape means
one renderer, and one renderer is why a hundred controls stay visually identical.

3.3 **`fmt` owns units and precision, and it is the census's own function.**
Formatting must not live in the widget: two widgets formatting the same kind will
eventually disagree, and disagreeing units in a dense panel are a correctness bug
wearing a typography costume.

3.4 **Reserve each value column from `fmt`, not from live values** — measure the
widest output over the range at build time (step 1.4). This is the craft rule
that keeps a live panel still.

3.5 **A control renders only from `get(addr)`**; local state is limited to an
in-flight drag delta. Any other copy drifts, and a drifted readout in an
engineering console is a wrong measurement.

3.6 **Bind the state channels, not just the values.** Selection, enable, mode,
staleness, and alarm are addresses too; a visual state with no address gets faked
by the widget and desynchronizes.

3.7 **Mode switches rebind, they do not duplicate.** The same widgets change
address when the mode flips (Coarse↔Freq). Hidden duplicate widgets drift and
double the layout you must verify.

3.8 **Every mutation goes through `set(addr, value)`** — clamp, taper, notify UI,
notify backend — and an unknown address throws. A control bound to nothing must
fail loudly, never render a plausible default.

3.9 **State timing and staleness per address**: applied live or at the next event
(note-on, next scan, next frame), and how a disconnected value renders — dash,
dim, link annunciator, never a last-known value that looks live. A user who
cannot tell whether a change took effect will make it twice.

### Gate 3 — do not proceed until

- [ ] Census parameter ↔ address ↔ control is one-to-one, checked both ways.
- [ ] Every address has `fmt` and a reserved column width.
- [ ] Every state from census 1.6 has an address and a rendering.
- [ ] Every mode switch rebinds the same widgets and annunciates in two channels.
- [ ] Unknown address throws; no silent default anywhere.
- [ ] Timing and stale behavior stated per address.
- [ ] **Cold-read test:** a stranger with no legend names the selected section,
      the enabled sections, and the current mode within ten seconds. If not, the
      defect is in L4 — go back, do not go forward into a tooltip.

## The four tests, in one place

| Test | What it catches | When |
|---|---|---|
| Squint | Zoning and focus errors; a shouting decoration | after L1, L2 |
| Greyscale | Color carrying information it should only reinforce | after L4 |
| Worst-case string | Layout jitter during live values | after L3, L4, gate 3 |
| Cold read | Missing selection/mode annunciation | gate 3 |

A panel that passes all four is calm. Calm is not a style — it is the absence of
axes, edges, and hues that were never earned.
