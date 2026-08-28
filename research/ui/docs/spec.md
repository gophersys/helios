# panel.toml — one file drives the whole pipeline

A panel is DATA, not a code fork. One TOML file carries everything the
toolchain needs: identity and frame, font, fixed tracks, solver input, probe
selectors, audit rules, and ratio-table expectations. The sections are, by
design, exactly the input shapes of the tools that consume them:

| Section | Consumer | Purpose |
|---|---|---|
| `[panel]` | everything | name, fixed frame (width x height in CSS px) |
| `[font]` | `ui.solve`, `ui.audit.check_font_identity` | the TTF whose advances size every reserved box (A-1), and the face the page must prove it rendered |
| `[census]` | humans + gates | pointer to the stage-1 census file |
| `[tracks]` | layout CSS | L1 zoning: fixed column tracks, gaps (A-2: never content-sized) |
| `[solve.*]` | `ui.solve.solve()` | flow_rows / knob_rows — anchors, floors, labels, widest strings |
| `[probe]` | `ui.probe.collect()` | page, root, root_width, containers, parts, text_kinds |
| `[rules]` | `ui.audit.Rules` | graze, floors, declared spills, hit kinds, the axis budget |
| `[ratio]` | `ui.audit.check_ratios` | typed rows: `measure = "<kind>.<dim>"`, `ratio = [num, den]` or `span = [from, to]`, with `want` + `tol` |

Invariants the file must honour (LAYOUT-MATH):

- **Anchors are measured**, from the reference bitmap (`ui.measure`) or a
  design decision recorded in the census — never eyeballed.
- **Sizes have two legal sources**: the `[font]` advances, or a declared token
  in this file. There is no third source.
- **The solver may correct anchors** (rhythm equalisation G-1; ink clearance for
  the host font; dial parity, A-5); corrections are reported, and the corrected
  value is the built truth.
- **Every `[rules]` exception is a claim about the reference** — cite the
  measurement next to it in a comment.

## Canonical example

```toml
[panel]
name = "example"
width = 800
height = 120

[font]
path = "FONT"          # absolute TTF path; advances size all reserved boxes
size = 16

[census]
file = "spec/census.md"

[tracks]
columns = [24, 420, 348, 8]
gap = 2

[solve.knob_rows.main]
plate_width = 348
dial = 28
tuck = 10
dial_floor = 40
label_floor = 3
equalize = true

[[solve.knob_rows.main.units]]
name = "alpha"
center = 56            # measured anchor (CSS px, plate-relative)
label = "Alpha"
widest = "100 %"       # the widest string this value can ever render

[[solve.knob_rows.main.units]]
name = "beta"
center = 150
label = "Beta"
widest = "-12.3 dB"

[[solve.knob_rows.main.units]]
name = "gamma"
center = 244
label = "Gamma"
widest = "20.0 kHz"

[probe]
page = "example.html"    # the rendered page `ui score` measures (default page.html)
root = ".panel"
root_width = 800
text_kinds = ["label", "value"]

[probe.containers]
plate = ".plate"

[probe.parts]
label = ".k-label"
dial = ".k-dial"
value = ".k-value"

[rules]
graze_max_height = 2.5   # measured: value ink may graze the ring by <= 2.5px
graze_min_dx = 8.0       #           starting right of the dial centre
min_sibling_gap = 2.0
breathing_floor = 2.5

[ratio]
panel_w = { measure = "root.w", want = 800, tol = 5 }
dial = { measure = "dial.h", want = 28, tol = 1 }
text_control = { ratio = ["label.h", "dial.h"], want = 0.593, tol = 0.06 }
```

Each `[ratio]` row measures `"<kind>.<dim>"` — a `[probe.parts]` kind, or the
reserved kind `root` for the panel itself — with `dim` one of `h`, `w`, `cx`,
`cy`. A kind with several instances reduces by MEDIAN, and their spread is a
failure of its own: three dials at 27/27/33 are a defect whose median is exact.
A row that matched no element fails, because a row that measured nothing proves
nothing. The `ratio = [numerator, denominator]` form states a RELATION, which is
the identity-carrying one — text:control near 0.6 against the 0.44 of library
defaults (DENSE-UI §Ratios). The `span = [from, to]` form states a DISTANCE,
second minus first, for a claim no absolute box can carry: a row pitch is
`span = ["label.cy", "value.cy"]`, because the row's own box overlaps everything
inside it and text is ink (A-4). A span claims the difference and only the
difference, so the per-token spread rule does not apply to it.

`[rules]` also carries the axis budget (DENSE-UI A1): `axis_budget_floor`
defaults to 3.0 CONTROLS per distinct CONTROL x-axis — both sides of the
quotient are the control population, because text is glyph ink and ink centres
never coincide, so a whole-panel denominator scores every real panel below 1.0.
The rule is silent at or below the floor in controls, where the quotient has no
distribution to describe. `hit_kinds` names which part kinds are hit targets
for the 24 px WCAG pitch check (default `dial`, `checkbox`, `thumb`), and
`snap_kinds` which kinds carry an integer-edge claim (default `dial`,
`checkbox` — the two every demo authors from a token; a box whose width is
padding plus a text advance cannot be integral on both sides).

**A floor at or below 1.0 is refused.** The quotient is controls ÷ control
x-axes and a class needs a control to exist, so it never falls below 1.00: such
a floor is A1 switched OFF, written in the form that reads like A1 switched on,
and two demos shipped exactly that before this band existed. A panel whose
controls do not repeat states no floor at all — it declares
`axis_budget_exempt = true`, which `ui score` reports by name under
`axis-sprawl` (docs/scorecard.md) rather than counting as clean.

Three rules can be stepped out of — the axis budget (A1), the hit population
(A8) and the snap population (A-5) — and the pattern is the same for all three:
the step costs a written reason, and both consuming paths (`load_panel()` and
the gate path `rules_from()`) refuse it without one, because a rule enforced on
one of the two is enforced on neither. The budget has two forms, so four keys
carry three reasons:

| Key | Reason it costs | What the reason must say |
|---|---|---|
| `axis_budget_floor` | `axis_budget_reason` | which structure of THIS panel earns the lower floor |
| `axis_budget_exempt` | `axis_budget_reason` | why the panel can state no budget at all |
| `hit_kinds` | `hit_kinds_reason` | which measurement shows the dropped kinds are not targets |
| `snap_kinds` | `snap_kinds_reason` | which measurement shows those boxes are not authored |

`hit_kinds = []` or `snap_kinds = []` would otherwise switch WCAG 2.5.8 or A-5
off panel-wide in one line that reads like configuration — the consolidated
verify walked straight through the hit-target one, taking a real 12 px pitch
violation green. Declaring either key at all costs its reason: the validator
does not try to tell a widening from a narrowing, and a vocabulary worth
replacing is worth a sentence.

`[font]` is read twice, and the second read is what keeps the first honest.
`ui.solve` sizes every reserved box from its advances; then
`ui.audit.check_font_identity` measures, per text kind on the RENDERED page,
the advance of a pinned 73-glyph sentinel — always at the canonical 16px, never
at the kind's own rendered size, since identity is a property of the face and a
fractional rendered size is the ratio predicate's business — and fails when it
differs from the declared face by more than 0.5px. A page that draws a face the
solver never saw reserves room for text that is not there, and nothing else in
the battery can see it — parts carry glyph ink, and ink is where the glyphs
are, never which face drew them. The path is resolved by
`ui.fontmetrics.resolve_path` (`UI_FONT`, then the declared path, then a
face known to be present on the host), which is the same ladder the demo builds
resolve with, so the audit judges the page against the face the page was built
with; a panel that declares no `[font]` is not judged at all, as with `[ratio]`.
The `ui audit` report carries `"fonts": <text kinds compared>` beside
`"ratios"` — rc 0 with 0 compared is a declared table nothing executed, which is
exactly how the `[ratio]` rows stayed dormant for months.

The other half of that contract is the page: name the family you EMBED. All
three demos inline the solved TTF as an `@font-face` data URI
(`ui.fontmetrics.font_face_css`) and name that family in their CSS, because
a family NAME resolves to a different file on each host — or to nothing at all,
silently.

The `[solve]` table is passed verbatim (with `[font]`) to
`ui.solve.solve()`; `[probe]` + `[rules]` are exactly the `ui audit`
CLI config, which takes its page as an argument and ignores `probe.page` —
`ui score`, which is handed a directory, reads it. `ui.spec.load_panel()`
validates the file with NAMED errors — every
problem at once, full path, did-you-mean suggestions — before any consumer
runs. The operator emitter validates on load.
