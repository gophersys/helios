# RATIOS — measured object-dimension table for the Operator replica

Measured programmatically (Pillow, luminance-transition scans) from the
reference screenshot at its native scale: 2506×666 @2x → **1253×333 CSS**.
The replica is built at this scale, 1:1. Estimating these by eye is what made
the first build look generic; every number below is a pixel measurement.

## Frame
| Object | Measured (CSS px) | Ratio |
|---|---|---|
| Device | 1253 × 333 | aspect 3.76 |
| Title strip | 26 high, no rule (face runs unbroken to y≈27) | 7.8% of H |
| Grip strip (left, dark) | 19 wide, full body height | — |
| Left rack | 361 wide | 28.8% of W |
| Center display | ~478 wide, rises to y≈13 (into the title zone) | 38.2% of W |
| Right rack | 376 wide | 30.0% of W |
| Meter lane | 8 wide | 0.6% of W |
| Body padding | 9 top · 3 sides · 5 bottom | — |

## Rows and plates
| Object | Measured | Note |
|---|---|---|
| Row plate | 67 high (built: 1fr → 69.25, +3.4%, zero dead band under the last row) | 20% of H |
| Row gap | 5 | face shows through |
| Plate color | **#7b7b7b** | DARKER than the face |
| Face / gaps / title / selected plate | **#9b9b9b** | selected = face, not lighter |

## Controls (the ratios that kill the generic look)
| Object | Measured | Ratio |
|---|---|---|
| Knob outer Ø | **27** (right rack 28) | 40% of row height |
| Text (labels AND values) | **16 px** (Ableton Sans Small) | text:knob ≈ 0.6 |
| Row anatomy | label y5–18 · knob y23–43 · value y52–64 | label above, value below |
| Label alignment | left, at the knob's left edge | never centered |
| Value alignment | left, offset ≈ +13 px right of knob left | sits below-right (4–5 o'clock) |
| Checkbox box | 15 (13 + border) | ≈ 75% of knob Ø |
| Badge | 18 × 18, font 12 bold | right-aligned, row-centered |
| Osc-row knob centers | x ≈ 25 / 125 / (checkbox 201) / 252, badge 333 (rel. plate) | |

## Display
| Object | Measured | |
|---|---|---|
| Background | **#242424** | not near-black |
| Graph : parameter grid | **151 : 160** (≈ half and half) | graph 151 px |
| Grid label / value | 12 / 15 px | labels dim #9f9f9f |

## State colors (sampled)
```
blue (arcs, curve, checks)  #7cccf6
amber (hot values, chips)   #e98c29
badge green                 #63bd36
title LED amber             #e98c29
```

## The rule this file encodes
Derive every dimension from a measured table of the reference (or of the
design's own ratio decisions) — never from a widget library's defaults.
Text:control size ratio is the single most identity-carrying ratio in a dense
panel; get it wrong and the panel reads as generated. Gate 2's ratio audit
compares rendered `getBoundingClientRect` boxes against this table at ±5%.

## Executable form

`build/ratio_audit.py` renders the page headlessly, measures every row of this
table from the live DOM, and fails the build outside tolerance. It runs inside
`build/assemble.py` — geometry drift cannot ship silently. It has failed twice
for real (badge center 351 vs 333; grid clip), which is what makes it a check.

## Component anatomy (measured at 8× zoom — round 3)

The first two builds looked generated because the widgets had INVENTED anatomy.
The real Live 12 components, from the zoom crops:

- **Knob**: flat — NO body disc. A track arc (270°, open at the bottom) + a
  value arc + a **dark charcoal needle** (#1f1f1f–#575757) from center to ring.
  Ring/needle stroke ≈ 4.4 at this scale. Arcs: sky **#79cdfa** on the selected
  row and enabled sections, grey **#bababa** on unselected rows; right-rack
  track is thick dark #4a4a4a. Bipolar knobs carry a wedge marker at zero.
  Values tuck into the dial's lower-right (4–5 o'clock), overlapping the ring.
- **Right rack rows are TWO-LINE**: section toggle + knob labels on the top
  line; enums, chips and dials on the bottom line. Measured positions are in
  the shell's `.p-*` classes.
- **Checkbox**: sky #79cdfa inside a thick slate border #3d4f59; unchecked =
  lighter-than-plate fill (#9f9f9f) with a dark border. 15 px on osc rows,
  21 px in the right rack.
- **Dropdowns**: bordered flat boxes on the rack (1.5px #4a4a4a on #a1a1a1);
  borderless value+caret in the dark display. Caret solid, dark, 9×6.
- **Chips (R/Q/24)**: solid amber #eeab48 with dark glyph when engaged.
- **Display value families**: envelope group **blue #7cc0f0**, oscillator
  group **amber #f7a827**; labels #8f8f8f at 15.5 px — same size as values.
- **LEDs**: 12 px, colors #f6d23a / #56d45c / #63e3c1 / #ef8b39.
- **Type**: real **Ableton Sans Small** (embedded from the licensed Live 12
  install). The face is half the identity.

## Corrections log (what eyeballing got wrong, twice)

1. Round 1: knobs Ø34/text 11 — invented. 2. Round 2: Ø20 from a **chord scan**
(the scanline missed the ring's widest point — always scan through the measured
center). 3. Round 3: Ø27, measured at center, verified against A/B composites.
The graph:grid split was called 63:37 from a misread; it is 151:160. Rule:
after the table, build **ref-vs-built composites** per region and look at them
— the ratio audit catches drift, only the composite catches wrong anatomy.
