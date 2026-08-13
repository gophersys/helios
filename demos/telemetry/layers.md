# LAYERS — telemetry console, every number derived (no reference exists)

Stage-2 of the blind demo. Each value below shows its derivation from
LAYOUT-MATH; nothing is eyeballed, because there is nothing to eyeball.

## L0 — Frame

1120 × 320, unit u = 4px. Type 16px (cap ≈ 11.4px at Ableton-class 0.71em;
with DejaVu 0.73em ≈ 11.7 — both within the cap-sanity band).

## L1 — Tracks (the modulo rule)

Content = W − 2M − Σgaps must decompose into integral tracks (typo-math R7).
M = 8, three gaps of 4: 1120 − 16 − 12 = 1092 = 360 + 292 + 340 + 100, all ≡ 0
(mod 4):

| track | width | subtree |
|---|---|---|
| TARGET plate | 360 | power.* (+ tele.rail.*) |
| LINK plate | 292 | link.* (+ tele.link/uart) |
| shared dark editor | 340 | detail of ui.selected (A6: the one inverted ground) |
| ALARM rail | 100 | derived flags + tele.fault.last (right = cheap clearance) |

RUN zone lives as the third selectable plate stacked under LINK (see L2) —
two plates share the 292 column: LINK 148, RUN 148, gap 8 (between-group gap
= 2× the 4px within-group gap, G-2 at the pre-attentive grade).

## L2 — Row anatomy (line-box arithmetic, not taste)

Font 16 → line box ⌈16×1.2/4⌉×4 = 20. Rail row = label line 20 + 2 + dial 28
+ 3 + value line 20 = 73 → snap 72 (label margin −1, inside the em slack).
TARGET content = 320 − 16(pad) = 304 = 20 (main switch line) + 3×72 (rails)
+ 24 (ilimit isolation pitch, WCAG 24px circle) + 44 (ilimit row) = 304 ✓
exact. The destructive control's isolation is the 24px: no drag field within
one hit-circle of it (L5).

## L3 — Streams sit beside their setpoints

Rail row flow (solver flow_row, anchors computed):
label reserve = adv("3V3")+2 ≈ 34 → knob centre at 8+34+14 = 56;
live V cell reserve = adv("3.600 V") ≈ 56 at x = 56+14+16 = 116 (wait —
computed in panel.toml from the font actually loaded; the numbers here show
the METHOD: centre = pad + label_reserve + gap + dial/2, cell = prev_right +
gap, gaps from the 4/8 scale). Stream cells are read-only: rendered in the
stream ink colour, never draggable, `set` throws (RoT 3).

## L4 — Channels and staleness

| channel | meaning | source |
|---|---|---|
| blue | selected plate + its editor | ui.selected |
| green | within-limits stream text | tele.* fresh |
| amber | warning band (V out of ±5%, RSSI < −85) | derived |
| red | fault / over-limit / STALE | derived + staleness deadlines |

Staleness is a state, not a colour alone: a stale stream renders `—` AND the
red channel (unknown ≠ zero, twice over). The alarm rail is the only place
red may occupy area (A2: smallest area, strongest contrast — inverted here
deliberately and locally: alarms are the exception that proves the ground).

## L5 — Gestures

Identical vocabulary to every Dense-UI panel (drag/shift/dblclick/wheel);
ilimit additionally requires a 300ms hold-to-engage (reversal stays cheap —
release aborts; no dialog). The whole plate selects; the editor shows the
selected zone's full parameter grid.

## Gate 2 status

Squint/greyscale/point/glance/composite: UNRUN (no render exists yet) — they
run when the page exists; the ratio table IS this file + panel.toml (nothing
to measure a reference against; the audit checks build-vs-spec instead of
build-vs-bitmap). This is the blind test's core inversion: the spec is the
only truth, so drift has nowhere to hide.
