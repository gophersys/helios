---
name: ui-bind
description: Stage 3 of the Dense-UI framework — write the contract that binds every control of a dense panel to one address in one parameter tree, behind a single adapter seam. Use after Gate 2 has passed, when wiring an instrument panel, bring-up bench or telemetry console to a backend (in-process engine, OSC, WebSocket, serial, firmware), or when a panel shows stale readings, echo loops, or values that move under the cursor. Produces contract.md and ends at Gate 3, whose drills are run, never asserted.
---

# Stage 3 — CONTRACT (behaviour + binding)

Every control names one address. Both sides talk to the tree, never to each
other. The output is one file, `contract.md`, in the project you are working in.

**The model, stated once:** a dense panel is one parameter tree rendered twice —
once as pixels, once as traffic on a wire. Widgets call the tree; the tree calls
an adapter; the adapter owns the transport. **No widget ever imports the
backend**, and no backend ever imports a widget. One file knows both sides, and
it is the only file you rewrite when the backend changes.

**You may not re-zone in this stage.** If binding reveals that the layout is
wrong, say so, go back to `.claude/skills/ui-layout/SKILL.md`, and re-commit
the layer that was wrong. Do not patch a layout defect with widget-local state —
that is the state duplication this stage exists to prevent.

## Read first

- `framework/ (this repo) — DENSE-UI.md` — the framework in one page.
- `demos/operator/spec/ (this repo; audits in demos/operator/build/) — canonical example: contract.md` — the worked
  contract: Operator's parameter tree, descriptor shape, event protocol and the
  per-control binding rules, all driving a real Web Audio engine. Read it beside
  `census.md` and `layers.md` in the same directory.
- `framework/ (this repo) — draft-systems.md` — the full argument for the
  seam, the sync model, and every rule of thumb below.

## Steps

### 1. One descriptor shape, no exceptions

```
{ addr, label, kind, min, max, taper, default, enum?,
  fmt(v), parse(s), step, dragScale, direction, authority, persist }
```

One shape → one renderer → a hundred controls that stay visually and
behaviourally identical. `dragScale` defaults to 200 px = full range through the
taper, and is overridden rarely; it lives in the descriptor so every widget of a
kind drags identically.

### 2. Freeze the address scheme

Dotted, stable, lowercase. No display strings. No positional indices that
renumber. Arrays keyed by stable ids. The address is simultaneously the UI key,
the preset key, the log key and the wire key.

**The tree is a flat map;** "tree" is a naming discipline. Nested objects invite
passing subtrees around, and the single write path dies the first time somebody
mutates a nested node in place.

`ui.` addresses behave like every other address — subscribable, testable,
restorable — but the adapter drops the prefix entirely and they never leave.

### 3. `fmt` is pure, total, and owns units and precision

It must render **every** state the parameter can be in:

| state | example |
|---|---|
| normal | `8.61 kHz` |
| floor | `-inf dB` |
| over-range | `over` |
| stale | `—` |
| unread | `?` |

**A formatter that cannot say "no data" will print a plausible number when the
link is down.** Formatting never lives in a widget: two widgets formatting the
same kind will eventually disagree, and disagreeing units in a dense panel are a
correctness bug wearing a typography costume.

Pair every `fmt` with a `parse` and test the pair against a fixed table. Measure
column widths from `fmt` over the whole range at **build time** — this is the
craft rule that keeps a live panel still.

### 4. Store engineering units; derive normalized [0,1] on demand

Store Hz, dB, ms, %. Normalize only for gestures and for transports that carry
only floats. Store normalized instead and a later range change silently moves
every saved preset and every device already in the field.

Taper lives in the value model, not the widget. `denorm(norm(v)) == v` within
epsilon — at min, max, default, and 1000 random samples — is a **test**, not a
hope.

### 5. The tree API is the only mutation path

```
get(addr)
set(addr, value, source)
subscribe(prefix, cb)
stream(addr, cb)
```

`set` clamps, quantizes to `step`, notifies UI subscribers, then notifies the
adapter. A control renders **only** from `get(addr)`; the sole permitted local
state is an in-flight drag delta. Any other copy drifts, and a drifted readout in
an engineering console is a wrong measurement.

`source ∈ {user, device, preset, automation, test}`. **This one field buys undo,
automation and echo handling at once:** undo records only `source: user`, and a
device echo never enters the undo stack.

**An unknown address throws.** A control bound to nothing must fail loudly, never
render a plausible default — a control bound to nothing looks exactly like a
control bound to a parameter that happens to sit at its default.

### 6. Bind the state channels, not just the values

Selection, enable, mode, staleness and alarm are addresses too. A visual state
with no address gets faked by the widget and desynchronizes.

### 7. The adapter is the only replaceable part

```
apply(addr, value)
readAll()
subscribeStreams(cb)
health()
capabilities()
```

Everything device-specific — address aliasing, unit conversion, register maps,
OSC paths, serial framing — lives behind it. Below it, a transport:
`connect · disconnect · send(frame) · onFrame(cb) · health()`.

In-process, OSC/UDP, WebSocket and serial differ in exactly four ways, and the
seam handles all four explicitly: **ordering, coalescing, latency,
back-pressure**.

**Coalesce and decimate at the seam.** Last-write-wins per address per frame
(~60 Hz). An unbounded queue is a bug, not a buffer. A knob dragged at 120
events/s over a 9600-baud link is decimated in the adapter and the widget does
not know — put rate limiting in the widget and every new widget re-invents it,
inconsistently.

### 8. Assign a latency class per address

| class | treatment | typical |
|---|---|---|
| <100 ms | render optimistically, no extra state | in-process engine |
| 100 ms – 1 s | render local value + a distinct *unconfirmed* badge until echo | OSC, WebSocket, slow serial |
| >1 s or unreliable | the control is a **request**, drawn differently, with pending/failed states | firmware writes, sweeps |

The cause is the ~100 ms causality window: past it, the user stops believing
their own gesture did it and starts probing the tool.

### 9. Model sync state as three values per address

`local` (optimistic — what the user just did) · `confirmed` (last value the
device acknowledged) · `pendingSince` (timestamp or null).

Render `local`. Badge the control when `pendingSince` exceeds the deadline.

**Suppress echoes by generation token, never by value comparison.** Every
outbound write carries a generation counter; an inbound frame carrying that token
updates `confirmed` silently. Value comparison breaks the moment a device
quantizes: you send 8610 Hz, it returns 8608 Hz, and a value-comparing UI either
loops forever or ignores a real correction.

**Let the device disagree.** A readback that differs from `local` and carries no
pending token is adopted and repainted. Silently keeping the UI value hides range
and unit bugs; adopting it makes them visible in one drag.

Echo must never look like an edit: a value that changed because the device pushed
it is a different visual class from a value the user just set.

### 10. Never move a value under the cursor

While a control is engaged, device pushes to that address are **queued** and
applied on release. Losing your grip mid-drag is the most expensive error a dense
panel can produce.

### 11. Modes rebind; they never duplicate

The same widget switches address under the governing flag, exactly as the stage-1
mode ledger recorded. Hidden duplicate widgets drift, and they double the layout
you must verify.

### 12. Streams are a separate namespace

Read-only. Sampled at a stated rate. Carrying a staleness deadline. Never
persisted in a preset, never undoable. **`set` on a stream throws** — the classic
dense-panel bug is somebody calling `set` on a meter, which either throws in
production or, worse, writes to a device register.

### 13. Document live-apply vs apply-on-next-trigger, per address

Some values rebind under a held note or mid-scan; others latch only at the next
note-on, next scan, or re-arm. **An undocumented latch reads to the user as a
broken control**, and a user who cannot tell whether a change took effect will
make it twice.

### 14. Persistence is address → engineering value + schema version

Migrate by address. An **unknown address on load reports loudly and names it**.
It is never dropped in silence: a silently dropped address is a preset that has
quietly changed sound.

### 15. Write the degraded-mode contract before shipping

On disconnect:

- Controls keep last-known values, **marked stale**.
- Streams render `—`. Never blank, never fake-zero.
- Writes queue or refuse — **state which**, per address class.
- Link state is a first-class annunciator, not a toast.

Disabled ≠ removed: a section that is off renders dimmed but stays interactive
and stays in place.

## GATE 3 — done only when every drill has been RUN

Assertions do not close this gate. Each drill below has a command and an
observed output, or it is not done.

- [ ] **Binding coverage is bijective**, tested in both directions: zero orphan
      widgets, zero unreachable addresses. Run in CI.
- [ ] Every address has a descriptor, a latency class, a taper, a default, and a
      formatter that can render "no data".
- [ ] Formatter/parser table test passes, including floor, over-range, stale and
      unknown.
- [ ] Taper round-trip test passes at min, max, default and random samples.
- [ ] Every state from the census has an address and a rendering.
- [ ] Every mode rebinds the same widgets and annunciates in two channels.
- [ ] **Unknown address throws**, proven by a test. No silent default anywhere.
- [ ] The whole panel runs **headless against a fake backend**, with no real
      device attached.
- [ ] **Echo/coercion drill run:** the fake device returns a coerced value; the
      UI shows the coerced value and does not loop.
- [ ] **Disconnect drill run mid-drag:** transport pulled during a drag; stale
      marks appear, nothing fake-zeroes, reconnect re-syncs from `readAll()`.
- [ ] **Rate/back-pressure test:** 120 Hz of drag events into a slow transport,
      queue depth bounded, final value correct.
- [ ] **A second adapter has driven the same panel unchanged** — even a trivial
      JSON-over-WebSocket echo device. This is the only proof the seam is real.
- [ ] **Cold-read test:** someone who did not build the panel names the selected
      section, the enabled sections and the current mode within 10 s, with no
      legend. If they cannot, the defect is in L4 — go back to
      `.claude/skills/ui-layout/SKILL.md`. Do not go forward into a tooltip.
- [ ] Decision ledger closed: every entry has decision, rejected alternative and
      reason.

**A drill you did not run is a failure, not a skip.** Report "disconnect drill:
UNRUN, no transport available" rather than letting an unrun drill read as a pass.
A check that silently does nothing is worse than no check, because it is
believed.

## Why this seam is the whole framework

The census tells you what exists. The layers tell you where it goes. The contract
is what lets the same front panel drive a Web Audio engine today and a
serial-linked hardware bench tomorrow — because the widgets know only `addr`,
`kind`, `taper` and `fmt`; the tree knows only the descriptor set; and the
adapter is the single replaceable part. A dense UI is testable in exactly the
proportion that this seam is honest, and no more.
