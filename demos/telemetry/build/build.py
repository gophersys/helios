#!/usr/bin/env python3
"""Telemetry blind demo — static render (Gate 2: defaults, no backend).

Everything is generated from panel.toml: tracks, solved knob positions,
reserved cells. The page is then judged by `ui audit` reading the SAME
panel.toml — build-vs-spec, there being no bitmap. Run via
`uv run --project ../../tools/ui python3 build/build.py`.
"""

import pathlib
import subprocess
import sys
import tomllib

from ui.fontmetrics import FontError, font_face_css, resolve_path
from ui.solve import SolveError, solve
from ui.spec import SpecError, load_panel

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
PANEL = ROOT / "panel.toml"
OUT = ROOT / "telemetry.html"
# The page names the face it EMBEDS, and embeds the face it SOLVED with, so
# the rendered face is the solved face by construction on every host. Naming a
# family instead resolves to a different file on each machine — or to nothing,
# without erroring — and ui.audit.check_font_identity fails the build.
FACE = "PanelFace"

DEFAULTS = {"rail-3v3": "3.30 V", "rail-1v8": "1.80 V", "rail-io": "3.30 V",
            "ilimit": "0.50 A", "radio-ch": "15", "radio-pwr": "0 dBm"}
WORST = {"rail-3v3": "3.60 V", "rail-1v8": "2.00 V", "rail-io": "3.60 V",
         "ilimit": "2.00 A", "radio-ch": "26", "radio-pwr": "-20 dBm"}
STREAMS = [("V", "3.300 V"), ("I", "142 mA")]


def die(msg):
    print(f"BUILD FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def knob(name, sol, label, value):
    u = sol[name]
    return (f'<div class="k" style="left:{u["left"]}px;width:{u["width"]}px" data-addr="{name}">'
            f'<div class="k-label">{label}</div>'
            f'<svg class="k-dial" width="28" height="28" viewBox="0 0 28 28">'
            f'<path d="M 5 23 A 12.5 12.5 0 1 1 23 23" fill="none" stroke="#3c4650" stroke-width="4"/>'
            f'<line x1="14" y1="14" x2="21" y2="7" stroke="#dfe6ec" stroke-width="4" stroke-linecap="round"/></svg>'
            f'<div class="k-value">{value}</div></div>')


def main():
    sweep = "--sweep" in sys.argv
    values = WORST if sweep else DEFAULTS
    data = tomllib.loads(PANEL.read_text())
    try:
        data["font"]["path"] = resolve_path(data["font"]["path"])
        load_panel(data)
        out = solve({"font": data["font"], **data["solve"]})
    except (FontError, SpecError, SolveError) as exc:
        die(str(exc))
    t = data["tracks"]
    cols = t["columns"]
    xs, x = [], t["margin"]
    for c in cols:
        xs.append(x)
        x += c + t["gap"]

    rails = out["knob_rows"]["rails"]
    ilim = out["knob_rows"]["ilimit"]
    link = out["knob_rows"]["link"]

    rail_knobs = "".join(knob(n, rails, lbl, values[n]) for n, lbl in
                         [("rail-3v3", "3V3"), ("rail-1v8", "1V8"), ("rail-io", "IO")])
    stream_cells = "".join(
        f'<div class="cell" style="left:{rails[n]["center"] - 28}px;top:{92 + i * 24}px">'
        f'<span class="s-label">{sl}</span> <span class="s-num">{sv}</span></div>'
        for n in ("rail-3v3", "rail-1v8", "rail-io")
        for i, (sl, sv) in enumerate(STREAMS))
    link_knobs = "".join(knob(n, link, lbl, values[n]) for n, lbl in
                         [("radio-ch", "Channel"), ("radio-pwr", "TX Power")])

    html = f"""<meta charset="utf-8"><title>Telemetry Bench</title>
<style>
{font_face_css(FACE, data["font"]["path"])}
body {{ margin:0; background:#232629; font-family:'{FACE}'; }}
.panel {{ position:relative; width:{data["panel"]["width"]}px; height:{data["panel"]["height"]}px;
  background:#565b60; margin:24px auto; border-radius:3px; }}
.plate {{ position:absolute; top:8px; height:{data["panel"]["height"] - 16}px;
  background:#43484d; border-radius:2px; }}
.plate.dark {{ background:#1d2023; }}
.k {{ position:absolute; top:8px; text-align:center; color:#e8edf2; font-size:16px; }}
.k-label {{ height:20px; }}
.k-dial {{ display:block; margin:2px auto 0; }}
.k-value {{ position:absolute; left:calc(50% + 10px); top:50px; white-space:nowrap;
  color:#cfd8e0; font-variant-numeric:tabular-nums; }}
.cell {{ position:absolute; font-size:16px; color:#9fb0be; }}
.s-label {{ color:#8494a2; font-size:13px; }}
.s-num {{ color:#7ee0a3; font-variant-numeric:tabular-nums; }}
.ilim {{ position:absolute; left:8px; top:{8 + 72 + 48 + 24}px; width:328px; height:68px; }}
.alarm {{ position:absolute; top:8px; width:84px; padding:8px; color:#e8edf2;
  font-size:13px; background:#3a2f2f; border-radius:2px; }}
.alarm .ok {{ color:#7ee0a3; }}
</style>
<div class="panel">
  <div class="plate" style="left:{xs[0]}px;width:{cols[0]}px">
    {rail_knobs}{stream_cells}
    <div class="ilim">{knob("ilimit", ilim, "I-Limit", values["ilimit"])}</div>
  </div>
  <div class="plate" style="left:{xs[1]}px;width:{cols[1]}px">{link_knobs}</div>
  <div class="plate dark" style="left:{xs[2]}px;width:{cols[2]}px"></div>
  <div class="alarm" style="left:{xs[3]}px;height:{data["panel"]["height"] - 32}px">
    FAULTS<br><span class="ok">(none)</span></div>
</div>
"""
    OUT.write_text(html)
    print(f"wrote {OUT} ({'sweep' if sweep else 'defaults'})")
    for corr in out["corrections"]:
        print(f"  correction: {corr}")

    r = subprocess.run(["uv", "run", "--project",
                        str((HERE / "../../../tools/ui").resolve()),
                        "ui", "audit", str(OUT), "--config", str(PANEL)],
                       text=True)
    if r.returncode != 0:
        die("overlap audit failed")


if __name__ == "__main__":
    main()
