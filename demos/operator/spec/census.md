# CENSUS — Ableton Live 12 "Operator" device panel

Stage-1 output of the Dense-UI framework: a full parameter census taken from the
reference screenshot, before any layout decision. Every control is listed with
its type, value model, displayed value in the reference, and visual state.

## 0. Frame facts

- One fixed-size device panel. No scrolling, no resizing, no responsive reflow.
- Aspect: very wide, short. Live devices are ~170 px tall at 100% zoom; Operator is
  one of the widest stock devices. Replica target: ~1500 × 260 CSS px (≈1.55× Live scale).
- Three vertical zones on a light-grey face, plus a dark contextual display in the middle:
  - LEFT rack: 4 oscillator rows (D, C, B, A top→bottom).
  - CENTER: dark display — envelope graph + parameter grid for the SELECTED section.
  - RIGHT rack: 4 rows — LFO, Filter, Pitch, Global.
- Chrome: title bar (activator LED, preview triangle, "Operator" title; hot-swap +
  save icons at right). Left edge: vertical grip dots. Right edge: segmented level meter.

## 1. Interaction vocabulary (whole device)

| Gesture | Meaning |
|---|---|
| Vertical drag on knob/number | Change value (≈200 px = full range) |
| Shift + drag | Fine (×0.1) |
| Double-click | Reset to default |
| Scroll wheel over control | Step value |
| Click on a rack row | SELECT it → center display shows its detail |
| Click checkbox/toggle | Boolean flip |
| Click dropdown | Enum menu |
| Drag square handle in graph | Edit envelope breakpoint (time + level at once) |

## 2. LEFT rack — oscillator rows

Four identical rows. Top→bottom: **D, C, B, A**. Each row:

| Control | Type | Range / model | Reference values (D/C/B/A) |
|---|---|---|---|
| Coarse | knob | int 0–48 (harmonic ratio) | 1 / 3 / (hidden) / 1 |
| Fine | knob | int 0–1000 | 0 / 0 / (hidden) / 0 |
| Fixed | checkbox | bool | off / off / **ON** / off |
| Level | knob | −inf…0 dB | −inf dB / −14 dB / −5.9 dB / −5.4 dB |
| Letter badge | selection tag | A–D | B badge is **green-filled**; others grey outline |

**Mode switch (key density decision):** when `Fixed` is ON the row RELABELS —
`Coarse`→`Freq` (Hz, 0.1–1000 Hz shown "468 Hz") and `Fine`→`Multi` (×0.1–×1000,
shown "0.1"). Same two knob positions, different parameters. The labels carry small
corner tick marks in this mode.

**Selection state:** row B is selected → row background is lighter, its knob arcs and
checkbox render **blue**; unselected rows render grey arcs with white needles.
Level −inf renders the arc empty.

## 3. CENTER display (dark, contextual)

Shows the detail editor for the selected section. Reference shows **oscillator B**.

### 3a. Envelope graph (top ~55% of display)
- Blue exponential-looking curve on near-black ground.
- Square drag handles: initial level (top-left), end of attack (peak), end of decay
  (sustain level), release end (far right).
- Corner bracket top-right (display zoom affordance). Thin baseline under curve.

### 3b. "Envelope" group (left column, blue filled square + underlined header)

| Param | Type | Reference value | Format rule |
|---|---|---|---|
| Attack | number-drag | 0.00 ms | 3 significant digits + ms |
| Decay | number-drag | 15.7 ms | idem |
| Release | number-drag | 50.0 ms | idem |
| Time<Vel | number-drag | 0 % | int % |
| Initial | number-drag | −inf dB | dB, −inf floor |
| Peak | number-drag | 0.0 dB | dB one decimal |
| Sustain | number-drag | −inf dB | dB |
| Vel | number-drag | 0 % | int % |
| Loop | dropdown | None | enum: None/Trigger/Loop/Beat/Sync |
| Key | number-drag | 0 % | int % |

### 3c. "Oscillator" group (right column, hollow square header)

| Param | Type | Reference value | Notes |
|---|---|---|---|
| Wave | dropdown | Sin 4 | enum of additive waves; blue waveform thumbnail right |
| Feedback | number-drag | 0 % | value text **amber** |
| Repeat | dropdown | Off | white text |
| Phase | R-toggle + number | R on, 0 % | small **amber** "R" chip + amber value |
| Osc<Vel | number + Q-toggle | 0, Q on | amber value, **amber** "Q" chip |

Amber (#f7a827-ish) is the value-accent color inside the dark display for the
oscillator group; envelope values render light grey-white.

## 4. RIGHT rack — four rows

### Row 1 — LFO
| Control | Type | Reference |
|---|---|---|
| LFO on | checkbox | OFF (hollow) |
| Wave | dropdown | Sine |
| Dest | small dropdown | "L" (destination set) |
| R | small toggle | retrigger, off |
| Rate | knob | 64.00 |
| Amount | knob | 25 % |

### Row 2 — Filter
| Control | Type | Reference |
|---|---|---|
| Filter on | checkbox | **ON (blue)** |
| Type | dropdown (icon) | lowpass curve glyph |
| Slope | paired toggles 12 / 24 | **24 active (amber)** |
| Circuit | dropdown | Clean |
| Freq | knob | 8.61 kHz (blue arc) |
| Res | knob | 20 % |

### Row 3 — Pitch
| Control | Type | Reference |
|---|---|---|
| Pitch env on | checkbox + env glyph | ON (blue) |
| Pitch Env | knob | 81 % (blue arc) |
| Spread | knob | 0 % |
| Transpose | knob | 0 st |

### Row 4 — Global
| Control | Type | Reference |
|---|---|---|
| Osc LEDs | 4 tiny squares | yellow, green, orange, red — osc A–D on/off |
| Time | knob (+ env glyph label) | 0 % |
| Tone | knob | 70 % |
| Volume | knob | 0.0 dB |

Selecting each right-rack row swaps the center display to that section's detail
(LFO env+params, filter env+params, pitch env, global: algorithm + voice params).

## 5. Visual tokens (measured/estimated from screenshot)

```
face          #a6a6a6   device ground
row           #999999   unselected row plate
row-selected  #b4b4b4   selected row plate (lighter)
display       #161616   center dark display
display-line  #2a2a2a   grid/baseline in display
ink           #1c1c1c   text on light face
ink-dim       #3a3a3a   labels on light face
light-text    #cfcfcf   labels in dark display
blue          #58a6dd   selection/active accent (arcs, curve, checkboxes)
blue-bright   #7cc0f0   envelope curve, handles
amber         #f7a827   hot values, 24/R/Q chips, activator LED
green         #79c860   selected osc badge, meter, LED
led-yellow    #e0d048
led-orange    #e08030
led-red       #d84848
knob-body     #c8c8c8   ring, with #f2f2f2 needle on grey rows
```

Type: one small sans (Ableton Sans in Live; replica uses a close system sans),
~11 px labels, ~12 px values; values horizontally beside/below knobs; all numeric
values carry units in the same text node.

## 6. Density counts (why this panel is "dense")

- ~46 always-visible controls + ~17 contextual (center) = ~63 reachable parameters
  in ~1500×260 px, with zero scrolling and zero modal dialogs.
- Density mechanisms observed: (1) contextual center editor shared by 8 owners;
  (2) mode-switching labels (Coarse/Freq); (3) repeated row template for oscillators;
  (4) unit-bearing value text instead of separate readouts; (5) color = state, not decor.
