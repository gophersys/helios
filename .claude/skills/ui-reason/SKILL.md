---
name: ui-reason
description: Stage 1 of the Dense-UI framework — take the parameter census before any layout exists. Use when starting a dense, fixed-size panel (instrument, bring-up bench, telemetry console, engineering dashboard), when replicating a hardware or software device from a screenshot, or when an existing panel has too many controls and nobody can say how many. Produces census.md and ends at Gate 1; no layout word may be written until it passes.
---

# Stage 1 — REASON (the census)

Count the world before drawing anything. The output is one file, `census.md`,
in the project you are working in.

**You may not draw in this stage.** No zones, no columns, no "left panel", no
component names, no pixel positions. If a sentence in the census could be a
layout instruction, delete it and keep counting. A census contaminated by layout
stops being a count of the world and becomes a defence of a picture somebody
already had in mind.

## Read first

- `framework/DENSE-UI.md` (this repo) — the framework. Budgets, axioms,
  all three gates in one page.
- `demos/operator/spec/census.md` (this repo; audits in `demos/operator/build/`) — a complete worked
  census: Ableton Live 12's Operator, ~63 parameters in 1500×260 px, taken from
  a screenshot. Read it before writing your own. It is what "done" looks like.
- Deeper arguments, when a rule here is being resisted — all three in
  `framework/drafts/` (this repo): `draft-cognition.md` (why density is a memory
  argument), `draft-systems.md` (why the census is the schema's first draft),
  `draft-craft.md` (why unattributed ink is deleted).

## The budgets that bind this stage

| Budget | Value |
|---|---|
| Working memory | ~4 chunks |
| Pre-attentive glance | <200 ms — position, colour, size, motion only; text does not survive |
| Chunk size | ≤5 controls per chunk, ≤5 chunks per zone, ≤4 zones |

You are not laying out yet, but every parameter you census is spent against
these. A census of 300 parameters with no density mechanism named is a census
that has already failed.

## Steps

### 1. State the frame facts

Fixed size in px, aspect, what surrounds it, and the explicit statement that it
does not scroll and does not reflow. Everything downstream is a budget against
this number.

### 2. List every parameter

One row each: name, kind (`continuous | int | bool | enum | trigger | stream`),
min, max, taper (`lin | log`), unit, default, and its value in the reference or
in a typical session.

**A parameter with no default is not censused.** Double-click reset, preset
load, and disconnect fallback all need it; finding three defaults during
implementation means three guesses.

Enum members are listed in full, in wire order, with the wire encoding (index or
token) stated.

### 3. Assign the address now — not in stage 3

Dotted, lowercase, stable, machine-first: `osc.b.level`, `bench.rail.3v3.setpoint`,
`link.uart0.baud`. Arrays keyed by stable ids (`osc.a`, never `osc.0` if the
order can change).

An address you cannot write down is a parameter you do not yet understand. The
address is the UI key, the preset key, the log key and the wire key — one string,
four jobs — and it will outlive the layout, which is the thing most likely to be
redone.

### 4. Classify direction and authority

- `set` — the UI writes it.
- `read` — a stream; the device emits it and the UI can never write it.
- `derived` — computed from other addresses. **Gets no address of its own.**
  Two addresses for one truth is the state-duplication bug dense panels hide best.
- `ui.` — local, never transmitted.

Then name the authority: who owns truth when they disagree — UI, host/preset, or
device (a value you can request but the device may coerce).

### 5. Write the display string AND the widest string

`-5.9 dB` and `-inf dB`. `468 Hz` and `8.61 kHz`. `0 %`. `+3 st`.

Precision and unit are census facts, not styling. The **widest** string is the
one stage 2 reserves column width from — and it is usually a failure string
(`—`, `over`, `stale`, `-inf dB`), which is exactly the string you must render
when the link dies and have no slack left to render it in.

### 5b. Measure the reference — never estimate it

When a reference exists (a screenshot, a hardware photo, an incumbent tool),
build the **ratio table programmatically** — pixel scans, luminance transitions,
colour sampling — never by eye. Record: frame dimensions, zone widths, plate/row
heights and gaps, control outer sizes, text sizes derived from measured glyph
heights, label/value alignment offsets, and every state colour, sampled.

Record the **text:control height ratio** explicitly. It is the single most
identity-carrying ratio in a dense panel, and it is exactly the one eyeballing
gets wrong: Operator measures **~0.8** — the text is nearly as tall as the knob —
while an estimated build produced 0.32 (big knobs, small text) and read as
machine-generated. A widget library's default sizes are not a source of
geometry; if a dimension is not in the table, it is not yet decided.

Then measure the **component anatomy** at 8× zoom, per widget class: the layer
stack (is the knob a disc, or a flat arc + needle?), stroke weights, fills,
state colors — all sampled, none assumed. A widget library's own anatomy is not
evidence; recreating "a knob" instead of THIS knob is how replicas read as
generated. Two traps proven by the worked example: scan a diameter through the
measured center, never a chord (a chord scan under-read the knob by 35%); and
verify the finished build with **reference-vs-built composites** per region —
the ratio audit catches drift, only the composite catches wrong anatomy.

Worked example: `demos/operator/spec/ratios.md` (this repo)
(including its corrections log — eyeballing failed twice before measuring won).

### 6. Assign exactly one read tier

- `GLANCE` — answerable in <200 ms with no fixation. Encoded in position, colour,
  size or motion only.
- `SCAN` — the user points from memory, then confirms by label.
- `READ` — an exact number with a unit, worth a foveal stop.

**Two tiers on one parameter is a bug**: it will be encoded twice and both
encodings will be weaker.

### 7. Score frequency and consequence

- Frequency: `constant | per-task | per-setup | rare`. Decides **position**, not
  size.
- Consequence of a wrong value: `free | visible | costly | destructive`. Decides
  **error treatment** at L5, and is the only thing allowed to lower density.

### 8. Census the streams

Meters, scopes, link state, temperatures, last-fault, sample counters, latency.
These are real panel content with no knob, and they compete for the same
attention budget as controls.

**A census that lists only knobs guarantees a stage-3 surprise.** A panel with
zero streams is a panel whose telemetry was forgotten, not a panel without
telemetry — say which it is, explicitly.

Streams get their own namespace: read-only, a stated sample rate, a staleness
deadline, never persisted.

### 9. Attribute every mark — no orphan ink

List every non-parameter mark: labels, headers, badges, LEDs, glyphs, meters,
chrome. If ink exists it is on this list, owned by a parameter, a label, a state
or the frame. Ink with no owner is decoration and is deleted at the gate.

When working from a screenshot, this is the step that catches what you did not
notice you were copying.

### 10. List the states each control can annunciate

Selected, enabled/disabled, modal relabel, out-of-range, stale/no-data, editing,
pending. Colour is spent on these in stage 2, so **an unlisted state cannot be
shown**.

### 11. Write the glance questions

At most five, in the user's own words: "Is it on?", "What am I editing?", "Is
anything clipping?", "Is the link alive?"

Map both ways:

- Each question maps to ≥1 `GLANCE` parameter. An unanswered question is a
  missing annunciator.
- Each `GLANCE` parameter serves ≥1 question. An unclaimed one is demoted to
  `SCAN`, and gives the colour channel back.

### 12. Open the mode ledger

Every control whose *meaning* changes with another. Operator has exactly one:
`osc.x.fixed` on relabels Coarse→Freq and Fine→Multi **in the same two knob
positions**.

Record per mode: trigger address, scope, indicator, and the relabel. Write slots
as `addr = f(governing addr)`. Mode switching is a density mechanism and the
easiest thing to render invisibly, so it is flagged here or it is lost.

### 13. Open the decision ledger

Every choice you take away from the user, with the rejected alternative and the
reason. It stays open through stages 2 and 3 and closes at Gate 3.

A preference is not a kindness: the user must make it, remember it, re-make it
on the next machine — and it dissolves the shared spatial map that lets one
person's expertise transfer to another's screen.

### 14. Find the repeated templates and the canonical order

- Repeated address prefixes (`osc.{a..d}.*`) predict repeated plates. N
  identical chunks cost **one** learning event; N bespoke chunks cost N.
- A shared suffix set (`*.env.*`) predicts a **shared editor**. This is the
  density decision, and it is readable directly off the tree's shape.
- Order every ordered set by the domain's learned order — ADSR, signal flow,
  boot sequence, the order printed on the board. Never alphabetical, never
  space-optimal: both destroy an order already sitting in long-term memory.

Write the prefix counts down.

### 15. Count and publish

Total parameters, per-prospective-chunk counts, and N settable / N streams /
N derived / N ui-only, summing to the total. Then name the mechanisms that pay
for the density: shared contextual editor, repeated templates, mode relabelling,
unit-bearing values, colour reserved for state.

"~63 reachable parameters in 1500×260 px" is a design fact, not a boast. If the
count does not fit the frame, **add a mechanism — never shrink the type**.

## The census table

```markdown
| addr | name | kind | min | max | taper | unit | default | ref | dir | auth | fmt | widest | tier | freq | consq |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| osc.b.level | Level | continuous | -inf | 0 | log | dB | -inf | -5.9 dB | set | preset | `-5.9 dB` | `-inf dB` | SCAN | per-task | free |
```

Then, as separate sections: frame facts · streams · marks · states · glance
questions · mode ledger · decision ledger · templates and canonical order ·
counts.

## GATE 1 — do not draw until every line is true

- [ ] Every row complete: address, kind, range, taper, unit, default, reference
      value, direction, authority, format, widest string, tier, frequency,
      consequence. **No blanks.**
- [ ] Enum members listed in full, in wire order, with the encoding stated.
- [ ] Every displayed number or light that is not a control appears as a stream,
      with a sample rate and a staleness deadline.
- [ ] Slots marked as `addr = f(governing addr)`.
- [ ] ≤5 glance questions, mapped in both directions, with zero orphan `GLANCE`
      parameters.
- [ ] Mode ledger complete; every mode has a planned in-chunk indicator.
- [ ] Decision ledger open, with at least the decisions already forced by the
      frame.
- [ ] Repeated templates named, canonical order recorded for every ordered set.
- [ ] Counts published and summing to the total.
- [ ] Every mark attributed. **No orphan ink.**
- [ ] If a reference exists: the ratio table is **measured, not estimated** —
      built by pixel measurement, with the text:control ratio recorded.
- [ ] No parameter marked "we'll hide this one". Hiding is not a stage-1 move.
- [ ] **Zero layout words in the census.** If it says "left panel", you skipped a
      stage: delete the sentence and keep counting.

A gate is not a summary. Walk the list and answer each line against the file you
wrote, out loud, naming the line in `census.md` that satisfies it. A gate you
declare passed without checking is a check that cannot fail, which is worse than
no check because it is believed.

When Gate 1 passes, go to `.claude/skills/ui-layout/SKILL.md`.
