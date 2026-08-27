# Dense-UI — the COGNITION draft

A framework for fixed-size, decision-heavy panels: synth instruments, hardware
bring-up benches, firmware telemetry consoles, EE/SW dashboards. Three stages in
order, each with a hard gate: **REASON (census) → LAYERS → CONTRACT**. Every
stage is read through one lens here — what the panel costs the user's attention
and working memory, and how to spend that budget on the *task* rather than on
the *interface*. Grounded in the Ableton Operator decomposition
(`spec/census.md`, `layers.md`, `contract.md`).

## 0. The budget (constants every stage is measured against)

| Budget | Value | Why it binds |
|---|---|---|
| Working memory | **~4 chunks**, not 7 | Cowan's limit for visual items with no rehearsal. Every "remember where you were" the UI imposes spends one of four slots the user needs for the task. |
| Pre-attentive glance | **< 200 ms**, no fixation | Only position, colour, size, orientation, motion survive. Text does not. |
| Saccade + fixation | **~30 ms + ~230 ms** | The real price of "one more control on screen". |
| Causality window | **~100 ms** | Beyond this the user stops attributing the change to their own gesture and starts debugging the tool. |
| Context loss | **~1 s** action, **~10 s** total | A navigation act that takes >1 s forces a re-read of what you were doing. |
| Distinct non-focal colours | **4–6** | Above that, colour stops being a channel and becomes texture. |

**The arithmetic that justifies density.** 63 visible controls arranged as
4 zones × ≤5 chunks × ≤5 controls cost about `log2(4)+log2(5)+log2(5) ≈ 6.6` bits
of choice, all of it *recognition*. The same 63 split into 12 visible + 51 behind
tabs cost the visible ones the same and the hidden ones an unbounded amount,
because access starts with a *recall* ("which tab was Feedback under?") whose
success rate decays with time away from the tool. Hidden controls have no cost
model at all. The argument for density is a memory argument, not an aesthetic one.

**The Fitts corollary.** Movement time grows with `log2(D/W + 1)`. Spreading a
panel out grows `D` linearly and buys back only a logarithm of `W`. A dense panel
with 20 px knobs 60 px apart beats a sparse one with 40 px knobs 400 px apart.
Density is *faster to operate*, not merely smaller.

---

## Stage 1 — REASON (census)

Take a full inventory of parameters before drawing anything. The cognition lens
adds three columns to the census that decide every later layout call.

### Steps

1. **List every parameter.** Name, type, value model, range, default, unit.
   Include read-only telemetry and derived indicators — they compete for the same
   attention budget as controls.
2. **Assign a READ TIER to each.** Exactly one:
   - `GLANCE` — must be answerable in <200 ms without fixating. Encoded in
     position/colour/size/motion only. Operator: section on/off checkboxes, the
     four oscillator LEDs, the output meter, which row is selected.
   - `SCAN` — the user knows the name and points at the remembered place, then
     confirms by label. Operator: every knob on the racks.
   - `READ` — an exact number with a unit, worth a foveal stop. Operator: the
     centre display's value grid.
   A parameter in two tiers is a bug: it will be encoded twice and both
   encodings will be weaker.
3. **Score FREQUENCY** per working session: `constant / per-task / per-setup /
   rare`. Frequency decides *position*, not size.
4. **Score CONSEQUENCE of a wrong value**: `free / audible-or-visible /
   costly / destructive`. Consequence decides *error treatment* at L5, and is
   the only thing that may lower density (a destructive control gets space).
5. **Write the GLANCE QUESTIONS.** Maximum five, in the user's words: "Is it
   on?", "Which section am I editing?", "Is anything clipping?", "Is the link
   alive?". Each question maps to ≥1 `GLANCE` parameter and each `GLANCE`
   parameter serves ≥1 question. Unanswered question → missing annunciator.
   Unclaimed glance parameter → demote to `SCAN`, give the colour channel back.
6. **Open the MODE LEDGER.** A mode is any state where one widget means two
   things. Record: trigger, scope, indicator, and the relabel. Operator has
   exactly one: `osc.x.fixed` turns *Coarse/Fine* into *Freq/Multi*.
7. **Open the DECISION LEDGER** (see §4). Every decision you take away from the
   user goes here, with the alternative you rejected and the cognitive reason.
8. **Find the repeated template.** Count parameter groups with identical shape
   (Operator: 4 oscillator rows). N identical chunks cost **one** learning event;
   N bespoke chunks cost N. Prefer uniformity over per-chunk optimality.
9. **Adopt the domain's canonical order.** ADSR, signal flow, boot sequence,
   OSI layers, the order printed on the physical board. A learned order is a
   free chunk already in long-term memory. Alphabetical order and
   space-optimal order both destroy it.
10. **Count.** Total parameters, and the count per prospective chunk. Publish the
    number. "~63 reachable parameters in 1500×260 px" is a design fact.

### Gate 1 — do not draw anything until

- [ ] Every parameter has tier + frequency + consequence. No blanks.
- [ ] ≤5 glance questions, each mapped; no orphan `GLANCE` parameters.
- [ ] Mode ledger complete; every mode has an in-chunk indicator planned.
- [ ] Repeated templates identified and named.
- [ ] Canonical domain order recorded for every ordered set.
- [ ] Total count known and written down.
- [ ] No parameter is marked "we'll hide this one" — hiding is not a stage-1 move.

---

## Stage 2 — LAYERS (L0–L5)

Commit the layout one layer at a time. No control is drawn before its layer.
The cognitive job of each layer is to convert *search* into *pointing*.

### L0 — Frame
1. Fix the size. No responsive reflow, no scrolling. **Spatial constancy is the
   substrate of expertise**: an expert does not search, they point from memory.
   A layout that moves under a breakpoint resets that memory on every device.
2. Declare the frame a versioned interface. After ship, moving a control is a
   breaking change — deprecate a position, never silently relocate it.

### L1 — Zoning (spend the density budget here)
3. Cut the frame into **≤4 zones**, one per top-level mental category, ordered
   along the domain's flow. Operator: sources (left) → the thing being edited
   (centre) → shaping and output (right). A bring-up bench: target → probe →
   log. Telemetry: fleet → device → stream.
4. Choose the **contextual shared editor** now, if the census total exceeds what
   fits. One detail region, many owners (Operator: 8 sections share one dark
   centre display). This single decision is what makes 63 parameters fit.
5. A shared editor is legitimate only if all three hold:
   - **The owner stays visible and live.** An Operator row is a selector *and*
     four working knobs. A tab is only a selector — it does no work when not
     selected, so it is pure overhead.
   - **The detail always appears in the same place.** The eye learns one address
     for "which" and one for "the detail".
   - **Switching costs one click and zero memory.** No back, no depth, no
     "where was I".
6. Exactly one owner is selected at all times. There is no null state to reason
   about, and therefore no empty detail panel to explain.

### L2 — Group plates (chunking)
7. **≤5 controls per chunk, ≤5 chunks per zone.** Above five the chunk stops
   being one unit and becomes a list to be searched.
8. Delimit each chunk with **one** mechanism — a plate, or a gap, or a rule.
   Never all three. Borders and fills are pre-attentive channels; spending them
   on decoration means they are unavailable for state.
9. A separating gap needs only **~1.5×** the internal gap to read as a boundary.
   More is wasted panel.
10. Never mix chunk grammars inside one zone. Four identical rows, or four
    bespoke groups — not three and one.

### L3 — Control placement
11. Place by **frequency, then canonical order**. Constant-use controls land on
    the dominant scan path (top-left in LTR, or the physical flow direction).
12. Share axes: knobs on one horizontal line per row, labels on another
    (Operator L3). Aligned rows let one saccade sample a whole row; ragged rows
    force one saccade per item.
13. **Confusability check.** Two parameters sharing a name stem, a unit and a
    widget must not be adjacent without a distinguisher. *Coarse/Fine* may sit
    together (their values differ visibly in magnitude); *Attack/Decay/Release*
    may (the order is already memorised).
14. Put the unit **inside the value text node** (`8.61 kHz`, `−inf dB`). A value
    needing a legend elsewhere forces a working-memory carry on every read.
15. No hover-only labels. Hover-only turns a novice's parallel visual search into
    a serial one — n hovers instead of one sweep — and is the most common way a
    dense panel becomes unlearnable.

### L4 — State and annunciators
16. Give each pre-attentive channel **one meaning per zone**, and write the table:
    Operator uses blue = selected/active, amber = hot value or engaged chip,
    green = identity/level, the four LED hues = oscillator identity.
17. Check for **channel collision**: if colour means both "selected" and
    "warning" in the same zone, neither reads at a glance.
18. **Unknown must not look like zero.** A stale telemetry field, a disconnected
    link, an unmeasured value renders in its own state — never as `0`, never as
    a blank that reads as `0`. This is the fail-loud rule applied to perception.
19. Mode indicators live *inside* the chunk they modify, and the affected labels
    themselves change (Operator: `Coarse`→`Freq`, plus corner ticks). A remote
    mode indicator is the classic mode-error generator.

### L5 — Interaction affordances
20. One gesture vocabulary for the whole panel, stated once: drag = change,
    shift-drag = fine, double-click = default, wheel = step, click = select.
    A per-widget vocabulary must be relearned per widget.
21. Make the **whole chunk** the selection target, not a small badge. Big
    ballistic target, no aiming cost, no wrong-neighbour risk.
22. The cursor states the role (`ns-resize` on draggables, `pointer` on
    selectors). This is the cheapest possible affordance disclosure — it costs
    zero pixels of the density budget.
23. **Error prevention by cheap reversal, not by hard targets.** Density raises
    mis-hit probability; enlarging everything destroys the density that makes
    the panel fast. Instead: every continuous change is instantly reversible in
    one gesture, and none is ever confirmed by a dialog — a dialog costs >1 s
    and steals the context you were judging against.
24. **Destructive and continuous never share a chunk.** Irreversible commits
    (erase flash, arm output, delete a run) get a larger target, a different
    widget class, and a position outside the drag field.

### Gate 2 — do not write the contract until

- [ ] Zones ≤4; chunks per zone ≤5; controls per chunk ≤5. Count them.
- [ ] Every parameter from the census has a home; none is "to be hidden".
- [ ] Disclosure is a shared contextual editor passing all three tests of L1.5 —
      or there is none. No tabs over objects, no accordions, no modals.
- [ ] Channel table written; no channel carries two meanings in one zone.
- [ ] **Point test:** a colleague holding only the census points at 10 randomly
      named parameters, each in <2 s. Failures name the parameters to move.
- [ ] **Glance test:** cover the panel 1 s, uncover 1 s, cover again — the user
      answers all glance questions from the flash. Failures name the missing
      annunciators.
- [ ] Decision ledger updated with every layout choice taken from the user.

---

## Stage 3 — CONTRACT (behaviour + backend address)

Every control binds to one address in one parameter tree; UI and backend both
talk to the tree, never to each other. Cognition adds the timing and honesty
clauses.

### Steps

1. **One address per control.** A control with two sources of truth will
   eventually show a value the user did not set, which reads as a fault in the
   *instrument* and destroys trust in every other reading on the panel.
2. **Descriptor owns the format.** `fmt(value) -> "8.61 kHz"` — unit, precision
   and floor (`−inf dB`) live with the parameter, not in the widget. One
   formatter means one learned reading convention across the whole panel.
3. **Latency budget per address**, written in the tree:
   - `< 100 ms` — render optimistically, no extra state. In-process engines
     (Operator's Web Audio graph) live here.
   - `100 ms – 1 s` — render the local value plus a distinct *unconfirmed* state
     until the backend echoes. OSC, WebSocket telemetry, slow serial.
   - `> 1 s` or unreliable — the control is a *request*, drawn differently from a
     direct parameter, with pending/failed states. Firmware writes, sweeps.
   The cause is the causality window: past ~100 ms the user stops believing
   their own gesture did it and starts probing.
4. **Echo must be distinguishable from edit.** A value that changes because the
   device pushed a new reading must never look identical to a value the user
   just set. Read-only telemetry and writable parameters are different classes
   in the tree *and* on screen.
5. **Never move a value under the cursor.** While a control is engaged, backend
   pushes to that address are queued, not applied. Losing your grip mid-drag is
   the most expensive error a dense panel can produce.
6. **Defaults are recoverable in one gesture** (`double-click → set(addr,
   default)`). This is what makes exploration safe and is why no confirmation
   dialog is needed.
7. **Mode rebinding is contractual.** Record which widget rebinds to which
   address under which flag (Operator rule 5). A mode not in the contract will
   be reimplemented as local widget state and will drift.
8. **Disabled ≠ removed.** A section that is off renders dimmed but stays
   interactive and stays in place (Operator rule 7). Removing controls on
   disable breaks spatial constancy exactly when the user is trying to fix
   something.
9. **Fail loud on unknown addresses.** The tree throws; it never silently
   ignores. A control bound to nothing looks identical to a control bound to a
   parameter that happens to sit at its default.

### Gate 3 — done when

- [ ] Every control names one address; every address names its tier, taper,
      default, formatter and latency class.
- [ ] Unconfirmed / stale / unknown states are specified and visually distinct
      from a real value, and from zero.
- [ ] No confirmation dialogs on continuous parameters; every one is reversible
      in one gesture.
- [ ] Modes and their rebindings are in the contract, matching the mode ledger.
- [ ] Unknown address = loud failure, in a test.
- [ ] Decision ledger closed: every entry has decision, rejected alternative,
      and its cognitive reason.

---

## 4. Decisions the tool makes FOR the user

A preference is not a kindness. It is a decision the user must make, remember,
re-derive on the next machine, and cannot share with a colleague — and it
dissolves the common spatial map that makes one person's expertise transferable
to another's screen. Decide, record, do not ask.

| Decided | Rejected | Cognitive reason |
|---|---|---|
| Fixed size, no reflow | Responsive layout | Spatial constancy is the substrate of pointing-from-memory. |
| One shared detail editor | Tabs / popovers / accordions | Keeps the owner live and visible; zero navigation depth; one fixed address for "detail". |
| Selection follows any click in a chunk | An explicit edit button | Removes a mode and a step; the chunk is already the target. |
| Unit inside the value | Legends, tooltips | No working-memory carry per read. |
| Colour reserved for state | Decorative colour | Colour is a 4–6 slot channel; decoration spends slots that state needs. |
| Canonical domain order | Alphabetical or space-optimal | Reuses an order already in long-term memory. |
| Uniform repeated rows | Per-row optimisation | N instances, one learning event. |
| No user-configurable layout | Customisable panels | Preserves the shared map between users and sessions. |

---

## 5. Rules of thumb, with their reasons

- **Recognition beats recall; position beats recognition.** Rank access paths:
  stable position > visible label > recognisable icon > remembered menu path.
  Anything that demotes a control down that ranking is a regression.
- **Density delays the novice by minutes and saves the expert hours per day.**
  The mitigation is not less density — it is a *self-describing* panel: visible
  name, value and unit on everything, so a novice reads the instrument once
  instead of excavating a tree. Undocumented density (icon-only, hover-only,
  hidden) is what hurts novices.
- **Hiding moves state into the user's head.** Every collapsed section is a fact
  the user must hold: what is in it, and that it exists at all.
- **Never move things to reveal things.** Accordions re-flow the panel and
  invalidate the pointing map on every open. Reveal in a fixed region instead.
- **A modal is a context amputation.** You judge a change against the system
  state — the sound, the trace, the log. A modal hides what you are judging with.
- **Tabs may divide tasks, never objects of the same kind.** Eight oscillators in
  eight tabs is eight hidden objects; eight rows sharing one editor is one
  visible set.
- **Motion is the loudest channel — reserve it for events, never for style.** An
  animated decoration in a telemetry panel will out-shout a real alarm.
- **Confirmations tax the frequent and fail against the rare error.** Cheap undo
  always; reserve friction for the destructive controls L5 already isolated.
- **If a check cannot fail, it is not a check.** Both gate tests (point, glance)
  must be run against a person who did not draw the panel, and their failures
  must produce a named change. A gate that always passes is decoration.
