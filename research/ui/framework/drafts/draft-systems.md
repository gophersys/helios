# Dense-UI — the SYSTEMS AND BINDING lens

A dense panel is not a picture with handlers attached. It is **one parameter tree
rendered twice**: once as pixels, once as traffic on a wire. The three stages
(REASON → LAYERS → CONTRACT) are the order in which that tree is discovered,
constrained, and bound. Everything below assumes the backend is unknown at design
time: a synth engine in-process today, an OSC device, a serial firmware link, or a
WebSocket telemetry bus tomorrow. The panel must not care.

**The seam, stated once:** widgets call the tree; the tree calls an adapter; the
adapter owns the transport. No widget ever imports the backend, and no backend ever
imports a widget. One file knows both sides, and it is the only file you rewrite
when the backend changes.

---

## STAGE 1 — REASON (census as schema draft)

The census is normally read as an inventory of *things on screen*. Under this lens
it is the **first draft of the parameter schema**. Every row you write is a row you
will later have to address, format, transmit, and test.

### Steps

1. **List every control** with type and observed value, as in the Operator census
   (`Coarse`, `Level −5.9 dB`, `Freq 8.61 kHz`).
2. **Assign a candidate address** to each, immediately, in the census table.
   Dotted, lowercase, machine-first: `osc.b.level`, `filter.freq`, `lfo.amount`.
   Do this now, not in stage 3 — an address you cannot write down is a parameter
   you do not yet understand.
3. **Classify direction** for every entry: `set` (UI writes it), `read` (device
   emits it, UI can never write it), `derived` (computed from other addresses, has
   no address of its own). Operator: `osc.a.on` is `set`; the right-edge level
   meter is `read`; the four Global LEDs are `derived` from `osc.{a..d}.on`.
4. **Census the streams the screenshot does not show as controls.** Meters,
   scopes, connection state, error/last-fault, sample counters, link latency.
   These are real panel content with no knob. A census that lists only knobs
   guarantees a stage-3 surprise.
5. **Record the value model** per entry: kind, min, max, taper, default, enum
   members, and the *display intent* (`3 significant digits + ms`, `−inf floor`).
6. **Name the authority** for each: who owns truth. UI-only (`ui.selected`),
   host/preset-owned, or device-owned (a firmware value you can request but the
   device may coerce). Authority decides who wins a conflict later.
7. **Flag slots, not just controls.** Operator's left knobs are two *slots* whose
   address depends on `osc.x.fixed` (`coarse|freq`, `fine|multi`). Write the
   slot as `addr = f(other addr)`. This is a binding fact that constrains layout.
8. **Count the address prefixes.** `osc.{a,b,c,d}.*` is one repeated prefix with
   four instances; `lfo`, `filter`, `pitch`, `global` are singletons that share a
   large suffix set (`.env.*`). Write these counts down.

### Rules of thumb

- **RoT 1 — Address before pixel.** *Why:* the address is the durable identity. It
  is the test name, the log key, the preset key, the automation id, and the
  telemetry column. Layout is the thing most likely to be redone; the address is
  the thing that must survive the redo.
- **RoT 2 — Units belong to the parameter, not the label.** `8.61 kHz` and
  `468 Hz` are the same parameter with one formatter. *Why:* if units live in
  static label text, a range change silently produces a lying panel.
- **RoT 3 — If it can be `set`, it is a parameter; if it only arrives, it is a
  stream.** Keep them in separate namespaces from the first table. *Why:* the
  classic dense-panel bug is somebody calling `set` on a meter — which either
  throws in production or, worse, writes to a device register.
- **RoT 4 — Repeated prefix predicts repeated plate; shared suffix set predicts a
  shared editor.** *Why:* Operator's one-editor-many-owners decision is readable
  directly off the schema: eight sections share `.env.*`, so one envelope editor
  serves eight owners. The tree's shape is the density argument.
- **RoT 5 — A parameter with no default is not censused.** *Why:* double-click
  reset, preset load, and device-disconnect fallback all need it; discovering
  three defaults during implementation means three guesses.

### Checklist

- [ ] Every control has: candidate address, kind, range, taper, default, direction.
- [ ] Every displayed *number or light* that is not a control appears as a stream.
- [ ] Slots (address = f(state)) are marked, with the governing address named.
- [ ] Enum members are listed in full, in wire order, with the wire encoding
      (index or token) stated.
- [ ] Counts recorded: N settable, N read-only streams, N derived, N UI-only.
- [ ] Namespaces chosen: parameter roots, `ui.` (local, never transmitted),
      telemetry root (inbound only, never persisted).

### GATE 1 — do not proceed until…

1. Every censused entry has an address, a direction, and an authority.
2. Settable / stream / derived / UI-only counts are written down and sum to the
   census total.
3. At least one non-control stream is listed (a panel with none is a panel whose
   telemetry was forgotten, not a panel without telemetry).
4. No layout, no zone, no pixel dimension has been decided.

---

## STAGE 2 — LAYERS (layout constrained by the tree)

Layout is committed layer by layer, L0…L5. The systems contribution is that each
layer carries a binding obligation, and a layout that cannot satisfy it is wrong
regardless of how it looks.

### Steps

1. **L0 Frame — fixed canvas, therefore static binding.** A fixed-size instrument
   has a fixed widget count, so the entire binding table is known at build time.
   Refuse virtualization, lazy mounting, and responsive reflow: they make binding
   dynamic and untestable for no user benefit on a panel that never scrolls.
2. **L1 Zoning — a zone is a subtree.** Draw zone boundaries along address
   prefixes (`osc.*` left, selected-section detail center, `lfo|filter|pitch|
   global` right). If a zone must mix prefixes, declare an explicit **view model**
   for it and name it; an undeclared mix is where state duplication starts.
3. **L2 Plates — one plate, one subscription root.** A plate subscribes to its
   prefix, not each control to its own address. *Why:* one prefix subscription
   repaints a row atomically; per-control subscriptions let a row render half-old
   and half-new during a preset load.
4. **L3 Placement — geometry from the descriptor, never from a value.** Knob size,
   digit width, and column width derive from `kind`, `range`, and the widest
   string the formatter can produce (`−inf dB`, `8.61 kHz`). *Why:* a layout that
   reflows when a value changes flickers, and reserves the wrong width at
   disconnect when the widest string is exactly the one you must render.
5. **L4 Annunciators — every indicator names a source address AND a staleness
   deadline.** Selection color ← `ui.selected`. Section-on ← `filter.on`. Meter ←
   the telemetry stream, with a deadline (e.g. 500 ms) after which it renders
   *stale*, not zero. *Why:* a synth never taught this because the engine is
   in-process and cannot go silent; a serial bench goes silent constantly, and a
   meter that decays to a confident 0.0 dB is a fabricated reading.
6. **L5 Interaction — gestures emit intents, not writes.** A drag produces
   `intent(addr, pixelDelta, modifiers)`; the tree converts through taper and
   clamps. *Why:* the same intent is then replayable in tests, recordable as
   automation, and rate-limitable at the seam without touching the widget.
7. **Record every decision made FOR the user as a binding decision too.** "One
   shared detail editor" is also "the center zone rebinds on `ui.selected`".

### Rules of thumb

- **RoT 6 — No layout decision may require a backend round trip.** *Why:* the
  panel must render completely and correctly from a schema alone, before any
  device is attached. This is what makes the UI bootable against a fake backend.
- **RoT 7 — Reserve space for the failure string.** Column widths sized to
  `"—"`, `"stale"`, `"over"`, `"−inf dB"`. *Why:* dense panels have no slack; the
  degraded state is the one that will shift everything if you did not measure it.
- **RoT 8 — Contextual editors need a rebind rule written in the layer, not
  improvised in code.** On owner change: unsubscribe old prefix, clear transient
  drag state, resubscribe, repaint. *Why:* skipping "clear drag state" is how a
  drag started on oscillator B lands on oscillator C.

### Checklist

- [ ] Every pixel region maps to an owning address prefix or a named view model.
- [ ] Every annunciator lists: source address, mapping, staleness deadline,
      degraded appearance.
- [ ] The whole panel can be rendered from one tree snapshot, offline.
- [ ] Rebind procedure written for every contextual/shared region.
- [ ] No responsive, virtualized, or lazily mounted binding survives.

### GATE 2 — do not proceed until…

1. A region→prefix map exists with zero orphan regions and zero orphan prefixes.
2. Every live indicator has a staleness rule and a defined stale look.
3. A static render of the panel from defaults alone has been produced, with no
   backend present.

---

## STAGE 3 — CONTRACT (behavior + binding)

### Steps

1. **One descriptor shape for every parameter**, no exceptions:
   `{ addr, label, kind, min, max, taper, default, enum?, unit, fmt(v), parse(s),
   step, dragScale, direction, authority, persist }`.
   `dragScale` is computed by default (200 px = full range through the taper) and
   overridden rarely — it lives in the descriptor so every widget of a kind drags
   identically.
2. **Fix the address scheme and freeze it.** Dotted, stable, no display strings,
   no positional indices that renumber, arrays keyed by stable ids (`osc.a`, not
   `osc.0` if the order can change). The address is simultaneously the UI key, the
   preset key, the log key and the wire key — one string, four jobs.
3. **Two coordinate systems, one storage.** Store engineering units (Hz, dB, ms,
   %); derive normalized [0,1] on demand for gestures and for transports that only
   carry floats. *Why:* store normalized and a later range change silently moves
   every saved preset and every device already in the field.
4. **Taper is part of the value model, not the widget.** `filter.freq 30–20000 Hz`
   is log; `pitch.transpose −48…48 st` is linear. Round-trip must be idempotent:
   `denorm(norm(v)) == v` within epsilon, for min, max, default, and 1000 samples.
5. **Formatters are pure and total.** `fmt` must render every case the parameter
   can be in: normal, floor (`−inf dB`), out-of-range (`over`), unknown/stale
   (`—`), and not-yet-read (`?`). A formatter that cannot express "no data" will
   print a plausible number when the link is down. Pair every `fmt` with a
   `parse` and unit-test the pair against a fixed table.
6. **Write the tree API and make it the only mutation path.**
   `get(addr) · set(addr, value, source) · subscribe(prefix, cb) · stream(addr, cb)`.
   `set` clamps, quantizes to `step`, notifies UI subscribers, then notifies the
   adapter. Every mutation carries `source ∈ {user, device, preset, automation,
   test}`. *This one field buys undo, automation and echo handling at once:* undo
   records only `source: user`; a device echo must never enter the undo stack.
7. **Define the adapter interface** — the whole backend contract, small on purpose:
   `apply(addr, value)`, `readAll()`, `subscribeStreams(cb)`, `health()`,
   `capabilities()`. Everything device-specific (address aliasing, unit
   conversion, register maps, OSC paths, serial framing) lives behind it.
8. **Define the transport interface** below the adapter: `connect`, `disconnect`,
   `send(frame)`, `onFrame(cb)`, `health()`. In-process, OSC/UDP, WebSocket, and
   serial differ in exactly four ways that the seam must handle explicitly:
   ordering, coalescing, latency, and back-pressure.
9. **Coalesce at the seam, decimate at the seam.** Last-write-wins per address per
   frame (~60 Hz); an unbounded queue is a bug, not a buffer. A knob dragged at
   120 events/s over a 9600-baud serial link must be decimated in the adapter, and
   the widget must not know. *Why:* put rate limiting in the widget and every new
   widget re-invents it, inconsistently.
10. **Model each parameter's sync state as three values**: `local` (optimistic,
    what the user just did), `confirmed` (last value the device acknowledged),
    `pendingSince` (timestamp or null). Render `local`; badge the control when
    `pendingSince` exceeds a deadline.
11. **Suppress echoes by token, never by value comparison.** Every outbound write
    carries a generation counter; an inbound frame carrying that token updates
    `confirmed` silently. *Why:* value comparison breaks the moment a device
    quantizes — you send 8610 Hz, it returns 8608 Hz, and a value-comparing UI
    either loops or ignores a real correction.
12. **Let the device disagree.** If a readback differs from `local` and carries no
    pending token, adopt the device value and repaint. *Why:* silently keeping the
    UI value hides range and unit bugs; adopting it makes them visible in one drag.
13. **Keep telemetry in its own namespace with its own rules**: read-only, sampled
    at a stated rate, carrying a staleness deadline, never persisted in a preset,
    never undoable, never `set`-able (the tree throws on attempt — fail loud).
14. **Persistence is address→engineering-value plus a schema version.** Migrate by
    address. An unknown address on load reports loudly and names it; it is never
    dropped in silence, because a silently dropped address is a preset that has
    quietly changed sound.
15. **Write the degraded-mode contract before shipping**: on disconnect, controls
    keep last-known values marked stale, streams render `—`, writes queue or
    refuse (state which), and the panel shows link state as a first-class
    annunciator. Never blank, never fake-zero.

### Rules of thumb

- **RoT 9 — The tree is a flat map; "tree" is a naming discipline.** *Why:* nested
  objects invite passing subtrees around, and the single write path dies the first
  time someone mutates a nested node in place.
- **RoT 10 — UI state lives in the tree but in a namespace that never leaves.**
  `ui.selected` behaves like every other address (subscribable, testable,
  restorable) but the adapter drops the `ui.` prefix entirely.
- **RoT 11 — Derived values get no address.** The Global LEDs read `osc.{x}.on`.
  *Why:* two addresses for one truth is the state-duplication bug that dense
  panels are especially good at hiding.
- **RoT 12 — Live-apply vs apply-on-next-trigger must be documented per address.**
  Operator can rebind some values under a held note and not others; a firmware
  bench has registers that latch only on re-arm. *Why:* an undocumented latch
  reads to the user as a broken control.

### Checklist

- [ ] Every widget resolves to a live address; every address is reachable from
      some widget (the **binding coverage test**, run in CI, both directions).
- [ ] Formatter/parser table test, including floor, over-range, stale, unknown.
- [ ] Taper round-trip idempotence test at min/max/default plus random samples.
- [ ] Fake backend exists and the whole panel runs against it, headless.
- [ ] Echo-suppression test: device returns a coerced value; UI shows the coerced
      value and does not loop.
- [ ] Disconnect drill executed: pull the transport mid-drag, observe stale marks,
      reconnect, observe re-sync from `readAll()`.
- [ ] Rate/back-pressure test: 120 Hz of drag events into a slow transport, with
      queue depth bounded and last value correct.
- [ ] Second adapter written (even a trivial one — a JSON-over-WebSocket echo
      device) to prove the seam holds.

### GATE 3 — do not proceed until…

1. Binding coverage is bijective: zero orphan widgets, zero unreachable addresses.
2. Every address has a descriptor and a formatter that can render "no data".
3. The panel passes its full test suite against the fake backend with no real
   device attached.
4. The disconnect drill and the echo/coercion drill have both been *run*, not
   asserted.
5. A second transport has driven the same panel unchanged.

---

## Why this seam is the whole framework

The census tells you what exists. The layers tell you where it goes. The contract
is what lets the same front panel drive a Web Audio engine today and a serial-linked
hardware bench tomorrow — because the widgets know only `addr`, `kind`, `taper`,
`fmt`; the tree knows only the descriptor set; and the adapter is the single
replaceable part. A dense UI is testable in exactly the proportion that this seam is
honest, and no more.
