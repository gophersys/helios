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
| `[probe]` | `densui.probe.collect()` | root, root_width, containers, parts, text_kinds |
| `[rules]` | `densui.audit.Rules` | graze, floors, declared spills |
| `[ratio]` | ratio audit | `name = [want, tol]` rows measured from the reference |

Invariants the file must honour (LAYOUT-MATH):

- **Anchors are measured**, from the reference bitmap (`densui.measure`) or a
  design decision recorded in the census — never eyeballed.
- **Sizes have two legal sources**: the `[font]` advances, or a declared token
  in this file. There is no third source.
- **The solver may correct anchors** (rhythm equalisation, G-1); corrections
  are reported, and the corrected value is the built truth.
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
panel_w = [800, 5]
dial = [28, 1]
```

The `[solve]` table is passed verbatim (with `[font]`) to
`densui.solve.solve()`; `[probe]` + `[rules]` are exactly the `densui audit`
CLI config. Loader-side validation with named errors is a separate PLAN box
(P2.3); until it lands, tomllib syntax + the consumers' own fail-loud checks
are the guard.
