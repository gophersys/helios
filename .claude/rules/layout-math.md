# Rule: layout is computed, never judged

Applies to every file under `demos/` and `tools/`.

- Geometry has two legal sources: font metrics (via `densui.fontmetrics`) or a
  declared token/anchor in a spec file. A number typed from visual judgement is
  a defect — including "small nudges".
- Any change that can move a rendered box re-runs the demo's gates in the same
  commit.
- New checks ship with proof they can fail (a red run in the commit message or
  test).
- Declared legal overlaps (e.g. a knob's value grazing its ring) are claims
  about a measured reference — cite the measurement in the spec.
