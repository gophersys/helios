# LAYERS — layout plan for the Operator replica

Stage-2 output of the Dense-UI framework. The layout is decided in six layers,
each committed before the next. No control appears before its layer.

## L0 — Frame
Fixed canvas, 1253 × 333 CSS px (the reference's native scale, ratios.md), non-responsive by design (density UIs are
fixed instruments, not fluid pages). Page centers the device on a neutral ground
and never scrolls horizontally. A separate help strip below the device (not part
of the replica chrome) documents keys; it may use page styling, the device may not.

## L1 — Zoning (the density budget is spent here)
```
+-—+------------------+----------------------------+------------------+—+-+
|g | LEFT RACK 361px  |  CENTER DISPLAY (dark) 478 |  RIGHT RACK 376  |m| |
|r | 4 osc rows       |  contextual detail editor  |  4 fixed rows    |e| |
|i | ~30% width       |  ~38% width                |  ~28% width      |t| |
|p |                  |                            |                  |e| |
+-—+------------------+----------------------------+------------------+—+-+
title bar above all three zones, full width
```
Rule applied: **one detail editor, many owners.** Eight sections (osc A–D, LFO,
Filter, Pitch, Global) share one center editor. This is the single decision that
makes ~63 parameters fit; it is made for the user, not offered as preference.

## L2 — Group plates
- Left rack: 4 identical row plates, stacked, 1 px gaps, order D,C,B,A.
- Right rack: 4 row plates: LFO, Filter, Pitch, Global.
- Center: one dark plate split: graph (top ~55%), parameter grid (bottom ~45%)
  in two labeled columns (Envelope | Oscillator — headers change per owner).
- Selected plate renders lighter; exactly one plate is selected at all times.

## L3 — Control placement (inside each plate)
- Osc row: [Coarse knob][Fine knob][Fixed checkbox][Level knob][letter badge].
  Labels above knobs, values below-right of each knob. Badge right-aligned.
- LFO row: [checkbox+label][wave dd][dest dd][R][Rate knob][Amount knob].
- Filter row: [checkbox+label][type dd][12|24][circuit dd][Freq knob][Res knob].
- Pitch row: [glyph+checkbox][Pitch Env knob][Spread knob][Transpose knob].
- Global row: [4 LED squares][Time knob][Tone knob][Volume knob].
- Center grid: 4 columns × 3 rows (Envelope) + 2 columns (Oscillator), label
  above value, values are drag targets themselves (no extra widgets).
- Knobs align on a shared horizontal axis per row; labels on a shared axis.

## L4 — State & annunciators
- Selection: plate background + blue arcs/checkbox on the selected row only.
- Activity: checkbox filled blue = section on; hollow = off. Osc on/off = the four
  colored LEDs in Global (yellow/green/orange/red = A/B/C/D).
- Value heat: amber text for oscillator-group values and 24/R/Q chips.
- Mode: Fixed=on relabels Coarse/Fine → Freq/Multi with corner ticks.
- Output: right-edge meter, green segments, driven by the engine.

## L5 — Interaction affordances
- Whole plate is the selection hit target (not just the badge).
- Knobs/values: vertical drag, shift=fine, double-click=default, wheel=step.
- Envelope handles: square, 8 px, grab cursor; constrained drag (time on x,
  level on y); graph redraws live and the engine hears the change immediately.
- Cursor communicates role: ns-resize on draggables, pointer on plates/toggles.

## Decisions made FOR the user (recorded, not asked)
1. Fixed size, no responsiveness — an instrument, not a page.
2. One shared detail editor — no per-section popovers, no tabs, no accordion.
3. Selection follows any click in a plate — no explicit "edit" button.
4. Values live inside the control (unit-bearing text) — no tooltips required.
5. Color is reserved for state — decoration gets none.

## Channel table (L4 — added after the verify pass found it missing)

| channel | zone | meaning | source |
|---|---|---|---|
| blue #7cccf6 | racks + display | selected plate's controls; enabled section; curves/handles | ui.selected, *.on |
| amber #f7a827/#e98c29 | display + chips + LED | hot value, engaged chip (R/Q/24), selected algorithm, activator | osc.*.feedback etc. |
| identity set (yellow/green/orange/red + badge green + meter green) | global row, badges, meter | WHICH oscillator / output present | osc.*.on, meter stream |

Three roles. The four LED hues are one channel (identity) with four coded
values, exactly as Live ships it — recorded as a fidelity-over-budget decision.
