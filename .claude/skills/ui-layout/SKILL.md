---
name: ui-layout
description: Stage 2 of the Dense-UI framework — commit the layout of a dense fixed-size panel in six layers L0 to L5, in order. Use after a parameter census exists and Gate 1 has passed, when deciding zones, plates, alignment axes, colour channels and gestures for an instrument panel, engineering console or telemetry dashboard, or when a panel already feels crowded and needs its axes merged. Produces layers.md and ends at Gate 2; no binding until it passes.
---

# Stage 2 — LAYERS (layout committed L0→L5)

Six layers, committed in order. The output is one file, `layers.md`, in the
project you are working in.

**You may not bind in this stage** — no addresses wired to widgets, no transport,
no backend. And you may not start without a census: if `census.md` does not exist
and pass Gate 1, stop and run `~/.claude/skills/ui-reason/SKILL.md` first. A
layout drawn before a count is a picture you will defend instead of a panel you
can measure.

The layer order is simultaneously the **paint order**, the **contrast order**
(A2) and the **commit order**. Each layer spends only the space and contrast the
layer under it left behind, and once committed it is frozen — later layers adapt
to it. That is what stops one late control from re-flowing the whole panel.

**Render and look after each layer.** A layer you cannot look at is a layer you
did not commit.

## Read first

- `framework/DENSE-UI.md` (this repo) — the framework in one page.
- `demos/operator/spec/layers.md` (this repo) — the worked layout:
  Operator's ~63 parameters resolved into 3 zones, 8 plates and one shared dark
  editor. Read it beside its own `census.md` in the same directory, so you can
  see which census fact forced which layout call.
- In `framework/drafts/` (this repo): `draft-craft.md` for the
  full argument behind each axiom, `draft-cognition.md` for the chunking and Fitts
  arithmetic, `draft-systems.md` for the binding obligation each layer carries.

## The craft axioms — every layer is checked against these

- **A1 — Crowding is axis proliferation, not control count.** Fix a crowded
  panel by merging alignment axes, never by deleting parameters. Target:
  controls ÷ distinct axes ≥ ~3.
- **A2 — Contrast rises as area falls.** Ground flattest, then plates, labels,
  values, state marks strongest. Nothing large may be loud.
- **A3 — Delete edges before content.** Perceived density tracks edge count, not
  object count. A plate is a 2–4 % luminance step and a gap; the same plate with
  a 1 px stroke costs four edges and carries no more information.
- **A4 — Colour is a state channel; decoration gets none.** At most three
  chromatic roles: selection, active/hot, semantic alarm.
- **A5 — The value is the control.** Drag the number itself. A slider plus a
  spinner plus a readout is three affordances and one fact.
- **A6 — One inverted ground, and it means "contextual".** Exactly one dark
  region, and its content follows selection. A second one makes a collage.
- **A7 — A fixed instrument is measured in pixels.** No reflow, no breakpoints,
  no user layout. Scale the whole frame uniformly if you must.
- **A8 — Motion belongs to the backend.** Meters animate. A dragged control
  answers in the same frame with zero easing — latency in a value is
  indistinguishable from error.

## The budgets — count them, do not estimate them

| Budget | Value |
|---|---|
| Zones | ≤4 |
| Chunks per zone | ≤5 |
| Controls per chunk | ≤5 |
| Chromatic roles | ≤3 per panel |
| Base unit | 4 px, everything snapped |

Above five, a chunk stops being one unit and becomes a list to be searched.

## L0 — Frame

1. Fix the canvas in px. Set the base unit (4 px) and snap every later
   coordinate to it — sub-pixel offsets read as blur, blur reads as noise.
2. Choose the ground tone: largest area, therefore flattest (A2).
3. Declare the frame non-responsive and **versioned**. After ship, moving a
   control is a breaking change; deprecate a position, never silently relocate
   it. Record this in the decision ledger (A7).
4. Binding obligation: a fixed frame means a static widget count, so the whole
   binding table is known at build time. Refuse virtualization, lazy mounting
   and responsive reflow — they make binding dynamic and untestable for no user
   benefit on a panel that never scrolls.

*Commit test:* the empty frame at final size looks like a deliberate object.

## L1 — Zoning (the density budget is spent here, once)

5. Cut the frame into **≤4 zones** along the domain's flow, stated as
   proportions, not contents. Sources → the thing being edited → shaping and
   output. A bench: target → probe → log. Telemetry: fleet → device → stream.
6. **A zone is a subtree.** Zone boundaries follow address prefixes. If a zone
   must mix prefixes, declare and name an explicit view model for it — an
   undeclared mix is where state duplication starts.
7. Assign the one inverted ground (A6) to the contextual zone.
8. **Spend all gutters here, once.** Whitespace in a fixed panel is a zone-level
   budget; inside plates, padding is a small constant. Spend it per control and
   you run out, then start shrinking type instead. A separating gap needs only
   ~1.5× the internal gap to read as a boundary.
9. **Choose the shared editor now — one detail region, many owners.** This is
   the single decision that makes a large census fit.

### The shared-editor legitimacy test

All three must hold, or it is not a shared editor, it is a tab:

- **The owner stays visible and live.** An Operator row is a selector *and* four
  working knobs. A tab is only a selector — it does no work when it is not
  selected, so it is pure overhead.
- **The detail always appears in the same place.** The eye learns one address for
  "which" and one for "the detail".
- **Switching costs one click and zero memory.** No back, no depth, no "where
  was I".

Exactly one owner is selected at all times — **no null state**, therefore no
empty detail panel to explain.

Forbidden, with no exception: tabs over objects of one kind, accordions, modals,
popovers. Tabs may divide tasks, never objects of the same kind. An accordion
re-flows the panel and invalidates the pointing map on every open. A modal
amputates the context you are judging the change against.

10. Write the rebind rule for every shared region now, in this layer, not
    improvised in code later: on owner change — unsubscribe old prefix, **clear
    transient drag state**, resubscribe, repaint. Skipping "clear drag state" is
    how a drag started on oscillator B lands on oscillator C.

*Commit test:* squint until text disappears. The zones survive, and the
contextual zone is the obvious focus.

## L2 — Group plates

11. Repeated templates get **identical geometry** on a strict stack or grid.
    Identical roles, identical geometry — the eye learns it once and then reads
    by position.
12. Define plates by luminance step and gap, not by stroke (A3).
13. ≤5 controls per plate. Never mix chunk grammars inside one zone: four
    identical rows, or four bespoke groups — not three and one.
14. Delimit each chunk with **one** mechanism — a plate, or a gap, or a rule.
    Never all three. Borders and fills are pre-attentive channels; spending them
    on decoration means they are unavailable for state.
15. Split the contextual zone into fixed sub-regions (Operator: graph ~55 % top,
    parameter grid ~45 % bottom, two labelled columns).
16. **One plate, one subscription root.** A plate subscribes to its prefix, not
    each control to its own address: one prefix subscription repaints a row
    atomically, while per-control subscriptions let a row render half-old and
    half-new during a preset load.
17. Exactly one plate carries the selected treatment, always — never zero.

*Commit test:* in greyscale the plate hierarchy reads, and no border exists that
you cannot justify.

## L3 — Control placement

18. Place by **frequency first, then canonical order**. Constant-use controls
    land on the dominant scan path.
19. **Shared axes:** knobs on one centreline per row, labels on one baseline,
    values on one baseline (A1). Aligned rows let one saccade sample a whole row;
    ragged rows force one saccade per item.
20. One label rule for the whole panel (e.g. label above, value below-right),
    applied everywhere. Mixed conventions cost a lookup on every glance.
21. **Label economy:** a label repeating three or more times along one axis moves
    to a column or plate header. The unit already lives in the value, so the
    label carries meaning only.
22. **Column widths come from the census's widest string** (step 5 of stage 1),
    plus the base unit — never from the live value. A column that resizes
    mid-drag makes the panel shimmy, and shimmer reads as instability. Reserve
    for `—`, `stale`, `over`, `-inf dB`: the degraded state is the one that will
    shift everything if you did not measure it.
23. **Tabular figures are mandatory** for any value that changes. Proportional
    digits change width with the digits, so a live value visibly jitters. Align
    on the numeral/unit boundary, never centred — a centred column of numbers has
    no readable edge.
24. The unit lives **inside the value's text node** (`8.61 kHz`). No legends, no
    tooltips, no hover-only labels. Hover-only turns a parallel visual search
    into a serial one — n hovers instead of one sweep — and is the commonest way
    a dense panel becomes unlearnable.
25. **Confusability check:** two parameters sharing a name stem, a unit and a
    widget must not be adjacent without a distinguisher.
26. Geometry derives from the descriptor — `kind`, `range`, widest formatted
    string — never from a value.
26b. **Every dimension comes from the measured ratio table** (census 5b):
    control Ø, row height, text sizes, alignment offsets, zone splits. Widget
    library defaults are how a panel starts looking machine-generated. Guard the
    **text:control height ratio** above all — Operator measures ~0.8 (text
    nearly knob-height); an estimated build inverted it and the panel stopped
    looking like an instrument.

*Commit test:* draw the axis lines over a render and count them. If
controls ÷ axes is under ~3, merge axes before continuing (A1).

## L4 — State and annunciators

27. Apply the colour budget (A4) and **write the channel table**: which hue means
    what, per zone. No channel carries two meanings in one zone — if colour means
    both "selected" and "warning" in one zone, neither reads at a glance.

    ```markdown
    | channel | zone | meaning | source address |
    |---|---|---|---|
    | blue | racks | selected / enabled | ui.selected, *.on |
    | amber | dark display | hot value, engaged chip | osc.*.feedback, *.retrig |
    ```

28. **Selection announces at both ends:** the source plate lights AND the shared
    editor names its owner in its header. The commonest dense-UI defect is a
    shared editor that never says whose values it is showing.
29. **Mode switches annunciate in two channels, one non-textual** — relabel plus
    a mark (Operator: Coarse→Freq *and* corner ticks). A text-only change is
    invisible to an eye that is on the knob; a mark-only change is unreadable.
    Mode indicators live inside the chunk they modify: a remote mode indicator is
    the classic mode-error generator.
30. Disabled sections dim (~40 %) but **keep geometry and stay interactive**.
    Hiding a disabled control moves the layout exactly when the user is trying to
    fix something (A7).
31. Every annunciator names a **source address AND a staleness deadline**, and a
    defined degraded appearance. **Unknown must not look like zero**: a dead
    sensor renders `—` or dimmed, never a plausible `0.00`. A synth never teaches
    this because an in-process engine cannot go silent; a serial bench goes
    silent constantly, and a meter that decays to a confident 0.0 is a fabricated
    reading.
32. Telemetry lives on an edge or a dedicated strip, never interleaved with
    editable controls — the user must see at a glance what they can change.

*Commit test:* screenshot every state — every selection, every mode, enabled and
disabled, alarm present. **No coordinate moves between shots.**

## L5 — Interaction affordances

33. One gesture vocabulary for the whole panel, stated once in a help strip
    **outside** the instrument chrome: drag = change, shift = fine,
    double-click = default, wheel = step, click = select.
34. The whole plate is the selection hit target, not a small badge. It is area
    you already drew, so a large ballistic target costs no pixels.
35. The cursor states the role — `ns-resize` on draggables, `pointer` on plates
    and toggles. The cheapest affordance there is: zero pixels of the density
    budget.
36. Graphs are editable — one handle moving two parameters at once — or they are
    wasted area.
37. **Gestures emit intents, not writes:** `intent(addr, pixelDelta, modifiers)`;
    the tree converts through the taper and clamps. This is what makes
    interaction replayable in tests, recordable as automation, and rate-limitable
    at the seam without touching a widget.
38. Error prevention is **cheap reversal, never confirmation**. Every continuous
    change is reversible in one gesture; no dialog. A dialog costs >1 s and
    steals the context you were judging against, and it taxes the frequent case
    to guard the rare one.
39. **Destructive and continuous never share a chunk.** Irreversible commits get
    a larger target, a different widget class, and a position outside the drag
    field.
40. Never re-order or re-sort controls in response to data. Sorting is for lists;
    an instrument's positions are addresses the hand has memorised.
41. User-driven response is instantaneous; only backend-driven values animate (A8).

*Commit test:* every interactive object has a cursor, a hit area ≥ its visual
size, and a one-gesture path to its default.

## GATE 2 — do not bind until every line is true

- [ ] All six layers committed in order, each rendered and looked at.
- [ ] Counts hold, **counted not estimated**: ≤4 zones, ≤5 chunks per zone, ≤5
      controls per chunk.
- [ ] Every census parameter has a home. None is "to be hidden".
- [ ] Region→prefix map exists with zero orphan regions and zero orphan prefixes,
      checked in both directions.
- [ ] Disclosure is a shared contextual editor passing all three legitimacy
      tests, or there is none. No tabs over objects, no accordions, no modals,
      no popovers.
- [ ] Rebind procedure written for every shared region, including clearing
      transient drag state.
- [ ] Channel table written; no channel carries two meanings in one zone.
- [ ] Every annunciator lists source address, mapping, staleness deadline and
      degraded appearance.
- [ ] Axis count recorded; controls ÷ axes ≥ ~3, both sides counted over the
      CONTROLS. **Counted by `densui.audit.axis_census` on the rendered panel
      and spent by `densui.audit.check_axis_budget`** — drawing the axes by eye
      is the estimate this replaces. A lower floor is legitimate only as a
      `[rules]` `axis_budget_floor` with a written `axis_budget_reason`. A floor
      at or below 1.0 is refused at load — controls per control-axis never falls
      below 1.00 — so a panel that can state no budget declares
      `axis_budget_exempt` with its `axis_budget_reason` instead.
- [ ] **Hit pitch measured**: `densui.audit.check_hit_pitch` — 24 px circles on
      the target centres do not intersect (WCAG 2.2 SC 2.5.8). The edge gap is
      the wrong reading and passes layouts that mis-click.
- [ ] **Integer edges proved**: `densui.audit.check_integer_edges` on the solved
      output and on the probe rects at scale 1, over the population
      `densui.audit.snappable` declares (`[rules]` `snap_kinds`, default the
      token-sized `dial` and `checkbox`). Glyph ink and any box sized by its own
      content carry no integer claim; narrowing further costs a written
      `snap_kinds_reason`.
- [ ] **Squint test** passed: zones and focus survive, nothing unintended shouts.
- [ ] **Greyscale test** passed: fully usable with hue removed. Hue reinforces
      state, it never carries the only copy of it.
- [ ] **Worst-case string test** passed: every value at its widest string,
      including failure strings — no column moves.
- [ ] **Ratio audit run, not asserted**: render headless, dump
      `getBoundingClientRect()` per object class, compare against the measured
      ratio table at ±5% — including the text:control height ratio. A build that
      was never measured against its reference will drift toward library
      defaults, and library defaults read as generated.
- [ ] **Composite test** (when a reference exists): stack reference and build
      crops of each region at 2×, look at them side by side, and fix what
      differs. The audit catches geometry drift; only the composite catches
      wrong component anatomy, wrong two-line row structure, wrong value
      placement, and the wrong typeface.
- [ ] **The proof battery run** (`framework/LAYOUT-MATH.md` (this repo)
      — the blind layout calculus; a worked validator is
      `example-operator/overlap_audit.py`): glyph-ink overlap with declared
      exceptions only; crowding floors (3 px ink gap, 2 px hairline); the
      **gap law** — same-neighbourhood gaps equal ±3% or ≥1.45×, compared
      between adjacent SAME-KIND control units with no third control
      interposed; containment; alignment spreads ≤1 px; content sweep at
      widest strings. The engine cannot see, so layout is never a coordinate
      guessed and eyeballed: sizes come only from font metrics or declared
      tokens, no coordinate is a function of a text width (fixed tracks, not
      flex packing), text renders INTO reserved boxes, and every "looks off"
      must decompose into a failed predicate with two names and a number.
      Positions are EMITTED BY A SOLVER, never hand-written: anchors + TTF
      advances in, verified CSS out, with rhythm equalised by construction and
      determinism proven by a shuffled re-solve
      (worked example: `example-operator/solve_layout.py`, injected at build).
- [ ] **Point test** run: someone who did not draw the panel, holding only the
      census, points at 10 named parameters in <2 s each. Failures name the
      parameters to move.
- [ ] **Glance test** run: cover 1 s, uncover 1 s, cover — all glance questions
      answered from the flash. Failures name the missing annunciators.
- [ ] A static render from defaults alone exists, with **no backend attached**.
- [ ] Decision ledger updated with every layout call, each with its rejected
      alternative and its reason.

The point test and the glance test must be run against a person who did not draw
the panel, and each failure must produce a named change. Run against yourself
they always pass, and **a gate that always passes is decoration**. If no second
person is available, say so and record both tests as UNRUN — never as passed.

When Gate 2 passes, go to `.claude/skills/ui-bind/SKILL.md`.
