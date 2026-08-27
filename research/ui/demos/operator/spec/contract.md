# CONTRACT — control behavior + backend binding for the Operator replica

Stage-3 output of the ui research framework. Every control binds to one address in
one parameter tree. The UI never talks to the audio engine directly; both sides
talk to the tree. This is the seam that generalizes (synth today, hardware
console tomorrow: same tree, different transport).

## 1. Parameter tree (single source of truth)

Implemented as `Params` — a flat map of address → parameter descriptor.

```
osc.{a|b|c|d}.on          bool     default: a,b=true? -> per reference LEDs: all 4 on
osc.{x}.coarse            int    0..48        default 1
osc.{x}.fine              int    0..1000      default 0
osc.{x}.fixed             bool                default false
osc.{x}.freq              float  0.1..1000 Hz default 440   (fixed mode)
osc.{x}.multi             float  0.1..1000    default 0.1   (fixed mode)
osc.{x}.level             dB     -inf..0      defaults: a=-5.4, b=-5.9, c=-14, d=-inf
osc.{x}.wave              enum   [Sine, Sin 3, Sin 4, Sin 6, Sin 8, Saw D, Square D, Triangle, Noise]
osc.{x}.feedback          int%   0..100       default 0
osc.{x}.phase             int%   0..100       default 0
osc.{x}.retrig            bool                default true   ("R" chip)
osc.{x}.oscVel            int    -48..48      default 0      ("Osc<Vel", "Q" chip = quantize)
osc.{x}.oscVelQ           bool                default true
osc.{x}.env.attack        ms     0.02..10000  default 0.02   (log taper)
osc.{x}.env.decay         ms     1..30000     default 15.7   (log)
osc.{x}.env.release       ms     1..30000     default 50     (log)
osc.{x}.env.initial       dB     -inf..0      default -inf
osc.{x}.env.peak          dB     -inf..0      default 0
osc.{x}.env.sustain       dB     -inf..0      default -inf
osc.{x}.env.timeVel       int%   0..100       default 0
osc.{x}.env.vel           int%   -100..100    default 0
osc.{x}.env.loop          enum   [None, Trigger, Loop]        default None
osc.{x}.env.key           int%   0..100       default 0

lfo.on                    bool   default false
lfo.wave                  enum   [Sine, Square, Triangle, Saw, Noise]  default Sine
lfo.dest                  enum   [L(A B C D), A, B, C, D, Filter, Pitch]  default L
lfo.retrig                bool   default false
lfo.rate                  float  0.01..100 Hz (log)  default 6.0  — display "64.00" style raw
lfo.amount                int%   0..100       default 25

filter.on                 bool   default true
filter.type               enum   [LP, HP, BP, Notch]  default LP
filter.slope              enum   [12, 24]     default 24
filter.circuit            enum   [Clean, OSR] default Clean
filter.freq               Hz     30..20000 (log) default 8610
filter.res                float% 0..125       default 20

pitch.on                  bool   default true
pitch.env                 int%   -100..100    default 81
pitch.spread              int%   0..100       default 0
pitch.transpose           st     -48..48      default 0

global.algorithm          enum   0..3  (4 routing diagrams; see §4)  default 0
global.time               int%   -100..100    default 0   (global env time scale)
global.tone               int%   0..100       default 70
global.volume             dB     -inf..0      default -12 (display "0.0 dB" is the
                                              reference's setting; ship -12 for safe ears? NO —
                                              fidelity wins: default 0.0, engine soft-clips)
ui.selected               enum   [oscA..oscD, lfo, filter, pitch, global]  default oscB
```

## 2. Parameter descriptor (one shape for every control)

```js
{ addr, label, kind: 'float|int|bool|enum|db|ms|hz|pct|st',
  min, max, taper: 'lin|log', default, enum?: [...],
  fmt(value) -> "8.61 kHz",           // display string WITH unit
  dragScale,                          // value change per 200px drag
}
```

Rules:
- `fmt` owns units and precision: dB → "-inf dB"/"-5.9 dB"/"0.0 dB"; Hz → "468 Hz"
  under 1 kHz, "8.61 kHz" above (3 significant digits); ms → 3 significant digits;
  % and st → integer + unit. LFO rate → 2 decimals, no unit.
- −inf dB floor: any dB ≤ −70 renders and sounds as −inf.
- Every mutation flows through `Params.set(addr, value)`; it clamps, notifies UI
  subscribers, and notifies the engine. `Params.get(addr)` is the only read path.

## 3. Event protocol (UI ⇄ engine)

```
UI  -> tree:   set(addr, value)         // from drag/click/menu
tree-> UI:     onChange(addr, value)    // repaint control, relabel if mode switch
tree-> engine: onChange(addr, value)    // engine updates live nodes
engine -> UI:  meter(level)             // rAF-polled AnalyserNode, right-edge meter
keyboard -> engine: noteOn(midi, vel) / noteOff(midi)
```
Computer keys A W S E D F T G Y H U J K O L = C4..E5 rows (Live convention),
Z/X octave down/up. No on-screen keyboard inside the device chrome.

## 4. Engine (Web Audio, per voice)

- 4 operators: OscillatorNode (PeriodicWave for Sin 3/4/6/8, band-limited saw/square)
  → per-op envelope GainNode → routing per algorithm.
- FM: modulator output → GainNode(index) → carrier.frequency AudioParam.
  Index scales with modulator level (dB→lin) × carrier base frequency.
- 4 algorithms (subset of Operator's 11, drawn as clickable diagrams in Global detail):
  0: D→C→B→A serial · 1: (D→C→B)+? no — use: 1: D→B, C→B, B→A fan-in
  2: D→C→A, B→A parallel pairs · 3: A+B+C+D all parallel (additive).
- Envelope: initial/peak/sustain in dB→lin gain; attack/decay/release with
  setTargetAtTime exponential approach; loop mode None/Trigger/Loop honored.
- Filter: BiquadFilter ×1 (12 dB) or ×2 chained (24 dB); circuit "OSR" adds a
  soft waveshaper before the filter.
- LFO: OscillatorNode + gain per destination; dest "L" = osc A–D levels.
- Pitch env %: scales an exponential pitch ramp per note; spread = per-voice
  detune pan pair; transpose in semitones.
- Tone: global one-pole lowpass post-mix; Time: scales all env segment times.
- Output: master gain → soft-clip waveshaper → AnalyserNode → destination.
- Polyphony 8; voice stealing oldest. No silent failures: engine throws on
  unknown addr; console.assert on all lookups (fail-loud rule).

## 5. Per-control behavior (binding rules the UI must obey)

1. A control renders ONLY from `Params.get` — no local state besides drag deltas.
2. Drag: pixel delta × dragScale × (shift ? 0.1 : 1), through taper, clamped.
3. Double-click → `set(addr, default)`.
4. Wheel → one UI step (int: ±1; float: 1/100 range; enum: next).
5. Mode switch: `osc.x.fixed` change relabels/rebinds the two left knobs of that
   row (coarse↔freq, fine↔multi) — same widgets, different addr.
6. Selection: `ui.selected` change re-renders the center display from the
   selected section's descriptor list; envelope graph rebinds to that env.
7. Disabled section (on=false): plate controls render at 40% opacity but stay
   interactive (Live behavior); engine mutes that section.
8. Every engine-affecting change is audible while a note is held (live rebind
   where Web Audio allows; else applies at next note-on — document which).

## Decision-ledger addendum (assembly)

- **Repeat omitted.** Census 3c lists Live's Repeat dropdown; the engine has no
  repeat mechanism (Web Audio scheduling scope cut). A rendered control bound to
  nothing violates Gate 3, so the control is omitted rather than shipped dead.
- **Voices and Repeat removed from the tree** (not merely hidden): binding
  coverage must be bijective — an unreachable address is a defect, not a spare.
- **Algorithm 2 = "parallel pairs"**: D→C and B→A as two independent stacks
  (carriers C and A). The contract's literal text for 2 was self-contradictory;
  `OpEngine.ALGORITHMS` is the authority and the display draws from its reading.
- **Reference state ≠ defaults.** Tree defaults follow this contract; the app
  applies the screenshot's session values on load (osc.c.coarse=3, osc.b fixed
  468 Hz "Sin 4", lfo.rate=64).

## Decision-ledger addendum (post-verification)

- **Loop enum ships all five census members** (None/Trigger/Loop/Beat/Sync);
  the engine maps Beat and Sync onto Loop scheduling — documented coarse cover,
  not a silent drop.
- **`lfo.dest` stores `'L'`** for the census's "L (A B C D)" destination set —
  display string and stored token differ by design.
- **The shared editor does not name its owner for osc A–D** ("Envelope" /
  "Oscillator" headers only). Live itself does not; fidelity outranks the
  framework rule here, and the owner is annunciated by the selected plate and
  its green badge. Recorded as a deviation from DENSE-UI L4.
- **The editor mirrors the rack controls for LFO/Filter/Pitch/Global** instead
  of adding Live's per-section extras (scope cut). The mirrors demonstrate
  two-views-one-address; the graph adds the real per-section content
  (response curve, scope, pitch curve, algorithm picker).
- **ms formatter switches to seconds at 1000 ms** ("30.0 s"), 3 significant
  digits throughout — matches Live, corrects contract §2's original wording.
- **Wheel direction is uniform**: wheel-up increments on every widget class.
- **In-process binding IS the adapter** for this example: no transport seam, no
  `set(addr, value, source)` field, no echo/disconnect handling — the engine is
  the <100 ms latency class and cannot go stale. Gate 3 status, honestly: run =
  fake-backend suite (mocked Web Audio), rate test (20k writes/s), taper
  round-trip, binding coverage (both directions, after Voices/Repeat removal),
  real-audio smoke (A4 −2.2 cents, filter sweep 86.7 dB). NOT run = second
  transport, echo/coercion drill, disconnect drill (exempt: in-process), and the
  cold-read test (needs a stranger). A generalization to OSC/serial must add the
  seam and run all eight.
- **Meter pre-audio state**: before the first note the meter renders dimmed
  (`meter-off`), not a confident zero — unknown must not look like zero.
