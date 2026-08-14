# panel.toml — one file drives the whole pipeline

A panel is DATA, not a code fork. One TOML file carries everything the
toolchain needs: identity and frame, font, fixed tracks, solver input, probe
selectors, audit rules, and ratio-table expectations. The sections are, by
design, exactly the input shapes of the tools that consume them:

| Section | Consumer | Purpose |
|---|---|---|
| `[panel]` | everything | name, fixed frame (width x height in CSS px) |
| `[font]` | `densui.solve` | the TTF whose advances size every reserved box (A-1) |
| `[census]` | humans + gates | pointer to the stage-1 census file |
| `[tracks]` | layout CSS | L1 zoning: fixed column tracks, gaps (A-2: never content-sized) |
| `[solve.*]` | `densui.solve.solve()` | flow_rows / knob_rows — anchors, floors, labels, widest strings |
| `[probe]` | `densui.probe.collect()` | page, root, root_width, containers, parts, text_kinds |
| `[rules]` | `densui.audit.Rules` | graze, floors, declared spills, hit kinds, the axis budget |
| `[ratio]` | `densui.audit.check_ratios` | typed rows: `measure = "<kind>.<dim>"`, `ratio = [num, den]` or `span = [from, to]`, with `want` + `tol` |

Invariants the file must honour (LAYOUT-MATH):

- **Anchors are measured**, from the reference bitmap (`densui.measure`) or a
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
page = "example.html"    # the rendered page `densui score` measures (default page.html)
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

Both exemptions cost a written reason: `axis_budget_floor` requires
`axis_budget_reason`, and narrowing `snap_kinds` requires `snap_kinds_reason`.
`load_panel()` and the gate path (`rules_from()`) both refuse them without one —
a rule enforced on only one of the two is enforced on neither, and
`snap_kinds = []` would otherwise switch A-5 off panel-wide in one line that
reads like configuration.

The `[solve]` table is passed verbatim (with `[font]`) to
`densui.solve.solve()`; `[probe]` + `[rules]` are exactly the `densui audit`
CLI config, which takes its page as an argument and ignores `probe.page` —
`densui score`, which is handed a directory, reads it. `densui.spec.load_panel()`
validates the file with NAMED errors — every
problem at once, full path, did-you-mean suggestions — before any consumer
runs. The operator emitter validates on load.
