#!/usr/bin/env python3
"""Operator overlap/containment audit — thin wrapper over densui.probe/audit.

All geometry law lives in the densui package; this file only declares the
Operator's selectors, its legal graze, its declared spill, its worst-case
sweep values, and the osc-column alignment key. Run via
`uv run --project ../../tools/densui` (assemble.py does) so densui resolves.
"""
import pathlib
import sys

from densui import audit, probe

PAGE = pathlib.Path(__file__).resolve().parent.parent.parent.parent \
    / "demos" / "operator" / "../.." / "demos/operator"  # noqa: ERA001 (see below)
# resolved simply:
PAGE = pathlib.Path(__file__).resolve().parents[1] / ".." / ".." / "operator.html"

PARTS = {
    "label": ".op-knob-label", "dial": ".op-knob-dial", "value": ".op-knob-value",
    "checkbox": ".op-check-box", "checklabel": ".op-check-label",
    "dd": ".op-dd", "chip": ".op-chip", "pairopt": ".op-pair-opt",
    "led": ".op-led", "badge": ".badge", "glyph": "svg.p-pt-glyph",
    "clabel": ".clabel", "num": ".op-num", "head": ".dhead", "thumb": "canvas",
}
TEXT_KINDS = {"label", "value", "checklabel", "clabel", "num"}

RULES = audit.Rules(
    legal_overlap=audit.knob_value_graze(max_height=2.5, min_dx_from_center=8.0),
    spill_slack={("dgrid", "clabel"): 12.0},
)

SWEEP_JS = """
window.addEventListener('load', function () {
  var P = window.OpParams;
  [['osc.b.freq', 1000], ['osc.b.multi', 1000],
   ['osc.a.coarse', 48], ['osc.c.fine', 1000], ['osc.d.level', -12.3],
   ['osc.b.env.attack', 10000], ['osc.b.env.decay', 30000], ['osc.b.env.release', 30000],
   ['osc.b.env.timeVel', 100], ['osc.b.env.vel', -100], ['osc.b.env.key', 100],
   ['osc.b.env.peak', -12.3], ['osc.b.feedback', 100], ['osc.b.phase', 100],
   ['osc.b.oscVel', -48],
   ['lfo.rate', 100], ['lfo.amount', 100],
   ['filter.freq', 20000], ['filter.res', 125],
   ['pitch.env', -100], ['pitch.spread', 100], ['pitch.transpose', -48],
   ['global.time', -100], ['global.tone', 100], ['global.volume', -12.3]
  ].forEach(function (kv) { P.set(kv[0], kv[1]); });
});
"""


def osc_column_key(p):
    """Osc-ROW columns only: dials and checkboxes with osc.* owners. The
    global row's LEDs also carry osc.*.on owners — four siblings, not a
    column — so 'led' must not key (the gate caught exactly that)."""
    if p["kind"] not in {"dial", "checkbox"} or not p["owner"]:
        return None
    if not p["owner"].startswith("osc."):
        return None
    return (p["kind"], p["owner"].split(".")[-1])


def main(page, sweep: bool) -> None:
    out = probe.collect(
        page, root=".device", root_width=1253,
        containers={"plate": ".plate", "dgrid": "#dgrid"},
        parts=PARTS, text_kinds=TEXT_KINDS,
        extra_js=SWEEP_JS if sweep else "")
    fails = audit.run_battery(out, RULES)
    fails += audit.check_cross_alignment(out["parts"], osc_column_key)
    tag = "sweep" if sweep else "audit"
    pairs = len(out["parts"]) * (len(out["parts"]) - 1) // 2
    print(f"overlap {tag}: {len(out['parts'])} parts, ~{pairs} pairs checked")
    if fails:
        print(f"OVERLAP AUDIT FAILED: [{tag}] {len(fails)} geometry violations:\n  "
              + "\n  ".join(fails), file=sys.stderr)
        sys.exit(1)
    print(f"overlap {tag}: no illegal overlap, no crowding, no escape")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--sweep"]
    page = pathlib.Path(args[0]) if args \
        else pathlib.Path(__file__).resolve().parents[1] / "operator.html"
    main(page, sweep="--sweep" in sys.argv)
