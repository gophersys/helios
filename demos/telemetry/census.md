# CENSUS — firmware bring-up telemetry console (designed BLIND)

Stage-1 output of the Dense-UI framework, with **no reference image**: every
decision below comes from the framework's own budgets and the verified
constants in `framework/research/` — this demo exists to prove the method
works without eyes on a precedent. Subject: the bench console for bringing up
an embedded target (an MCU board with three rails, a radio, and a UART link).

## 0. Frame facts

- One fixed panel,**1120 x 320 CSS px** (LAYOUT-MATH: tracks solved on a 4px
  unit; type 16px sets the ~55cm viewing distance, D_max = 3437.75·cap_mm/16).
- Zones (≤4, cut along the tree): TARGET (power/rails) · LINK (uart/radio) ·
  RUN (firmware state, log) · plus one contextual dark editor shared by the
  zone selected — the one-inverted-ground rule (A6).
- **Alarms live right and below** (psycho-math: upper-field clearance is 2.07×
  worse; put what must be noticed where clearance is cheapest).

## 1. Parameters (settable — `set` direction)

| addr | kind | range | default | widest | tier | freq | consq |
|---|---|---|---|---|---|---|---|
| power.main.on | bool | — | false | — | GLANCE | constant | costly |
| power.rail.3v3.setpoint | float V | 2.8–3.6 | 3.30 | `3.60 V` | READ | per-task | costly |
| power.rail.1v8.setpoint | float V | 1.6–2.0 | 1.80 | `2.00 V` | READ | per-task | costly |
| power.rail.io.setpoint | float V | 1.2–3.6 | 3.30 | `3.60 V` | READ | per-setup | costly |
| power.ilimit | float A | 0.05–2.0 | 0.50 | `2.00 A` | READ | per-setup | destructive |
| link.uart.baud | enum | 9600…921600 | 115200 | `921600` | READ | per-setup | visible |
| link.uart.echo | bool | — | false | — | SCAN | rare | free |
| link.radio.channel | int | 11–26 | 15 | `26` | READ | per-task | visible |
| link.radio.txpwr | int dBm | −20…+8 | 0 | `-20 dBm` | READ | per-task | visible |
| run.target.state | enum | run/halt/reset | halt | `reset` | GLANCE | constant | costly |
| run.log.level | enum | err/warn/info/dbg | info | `warn` | SCAN | per-task | free |
| run.log.follow | bool | — | true | — | SCAN | per-task | free |
| ui.selected | enum | target/link/run | target | — | GLANCE | constant | free |

13 settable. `power.ilimit` is the one destructive control (it arms current
into a DUT): per L5 it gets a larger target, its own widget class, and a
position outside the drag field.

## 2. Streams (read-only — the census the founding demo never had)

| addr | kind | rate | staleness deadline | widest | degraded render |
|---|---|---|---|---|---|
| tele.rail.3v3.v | float V | 10 Hz | 500 ms | `3.600 V` | `—` + stale mark |
| tele.rail.3v3.i | float mA | 10 Hz | 500 ms | `1999 mA` | `—` |
| tele.rail.1v8.v | float V | 10 Hz | 500 ms | `2.000 V` | `—` |
| tele.rail.io.v | float V | 10 Hz | 500 ms | `3.600 V` | `—` |
| tele.mcu.temp | float °C | 1 Hz | 3 s | `125.0 °C` | `—` |
| tele.link.rssi | int dBm | 4 Hz | 2 s | `-100 dBm` | `—` |
| tele.link.per | pct | 1 Hz | 3 s | `100 %` | `—` |
| tele.uart.rate | int B/s | 2 Hz | 2 s | `115200 B/s` | `—` |
| tele.fault.last | string | event | never stale | 24-char reserve | `(none)` |
| tele.uptime | duration | 1 Hz | 3 s | `99:59:59` | `—` |

10 streams. **Unknown must not look like zero** — every degraded render is a
dash, never a plausible number. Fault + over-limit annunciators sit right/below.

## 3. Glance questions (≤5, mapped both ways)

1. Is the DUT powered? → power.main.on (lit switch)
2. Is anything over limit / faulted? → derived over-limit flags + tele.fault.last (alarm strip, right/below)
3. Is the link alive? → tele.link.rssi staleness (link LED)
4. Is firmware running? → run.target.state (state chip)
5. Which zone am I editing? → ui.selected (plate treatment)

Every GLANCE parameter serves a question; no orphans.

## 4. Mode ledger

None at stage 1 — no control relabels under another's state. (If radio gains
a "fixed-frequency test mode" later, it enters here first.)

## 5. Decision ledger (opened)

| Decided | Rejected | Reason |
|---|---|---|
| 1120×320 fixed | resizable console | spatial constancy; tracks solved once |
| One shared dark editor for zone detail | tabs per zone | owner stays live (G: selector does work) |
| Alarms right/below | top status bar | upper-field clearance 2.07× worse (verified constant) |
| ilimit isolated + confirm-free but hard-edged | confirmation dialog | dialogs amputate context; isolation + reversal instead |
| Streams never settable | merged namespaces | `set` on a meter must throw (RoT 3) |

## 6. Counts

13 settable + 10 streams + 2 derived (over-limit flags per rail group, no
address) + 1 ui = **26 census rows** in 1120×320 — modest density on purpose:
this demo's job is proving the STREAM disciplines (staleness, degraded
renders, alarms) that the Operator demo never exercised.

## Gate 1 — walked

- Every row: kind/range/default/widest/tier/freq/consq ✓ (tables above)
- Streams have rate + staleness + degraded render ✓
- Glance questions mapped both directions ✓ · Mode ledger open (empty) ✓
- Decision ledger opened with frame-forced decisions ✓ · Counts published ✓
- Zero layout words beyond zone NAMES (no geometry) ✓ — anchors and tracks
  belong to stage 2, which starts from `panel.toml` and the solver, not from
  a reference bitmap: the first fully computed layout in this repository.
