#!/usr/bin/env python3
"""Operator overlap/containment audit — thin wrapper over ui.probe/audit.

All geometry law lives in the ui package, and every selector, text kind
and tolerance lives in panel.toml. This file declares only what the general
scorecard has no vocabulary for: the worst-case sweep values and the
osc-column alignment key. The probe config is loaded through
`ui.probe_config`, the same seam `ui audit` and `ui score` use, so
`ctl.sh geometry` and `ctl.sh score` cannot end up measuring two different part
sets of the same page. Run via
`uv run --project ../../tools/ui` (assemble.py does) so ui resolves.
"""
import pathlib
import sys
import tomllib

from ui import audit
from ui.probe_config import collect_panel, rules_from

PANEL = pathlib.Path(__file__).resolve().parents[1] / "panel.toml"

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
    cfg = tomllib.loads(PANEL.read_text())
    page = page or PANEL.parent / cfg["probe"]["page"]
    out = collect_panel(page, cfg["probe"], SWEEP_JS if sweep else "")
    fails = audit.run_battery(out, rules_from(cfg))
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
    main(pathlib.Path(args[0]) if args else None, sweep="--sweep" in sys.argv)
