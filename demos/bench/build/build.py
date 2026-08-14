#!/usr/bin/env python3
"""Bench demo — the contract's face. A scripted drill session runs against
densui.tree + FakeSerial; the page renders THE TREE'S RESULTING STATE:
coerced confirms, a stale stream as dash+red, the lost write reverted, and
the event log as the alarm rail. Then the geometry battery judges the render
against panel.toml. Run via `uv run --project ../../tools/densui`.
"""

import pathlib
import subprocess
import sys
import tomllib

from densui.fakes import FakeSerial
from densui.fontmetrics import FontError, font_face_css, resolve_path
from densui.solve import SolveError, solve
from densui.spec import SpecError, load_panel
from densui.tree import Desc, Tree

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
PANEL = ROOT / "panel.toml"
OUT = ROOT / "bench.html"
# The page names the face it EMBEDS, and embeds the face it SOLVED with, so
# the rendered face is the solved face by construction on every host. Naming a
# family instead resolves to a different file on each machine — or to nothing,
# without erroring — and densui.audit.check_font_identity fails the build.
FACE = "PanelFace"


def die(msg):
    print(f"BUILD FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def session():
    """The drill script whose outcome the page renders."""
    clock = Clock()
    events = []
    tree = Tree([
        Desc("power.rail.3v3.setpoint", "float", 2.8, 3.6, 3.30),
        Desc("power.rail.1v8.setpoint", "float", 1.6, 2.0, 1.80),
        Desc("power.ilimit", "float", 0.05, 2.0, 0.50),
        Desc("tele.rail.3v3.v", "stream", staleness_s=0.5),
        Desc("tele.rail.1v8.v", "stream", staleness_s=0.5),
    ], now=clock)
    dev = FakeSerial(tree.device_report, quantize={"power.rail.3v3.setpoint": 0.05})
    tree._adapter = dev

    tree.set("power.rail.3v3.setpoint", 3.33, source="user")
    if tree.confirmed("power.rail.3v3.setpoint") != 3.35:
        die("drill: coercion did not confirm at 3.35")
    events.append("3V3 set 3.33 → device holds 3.35 (coerced, token-confirmed)")

    tree.stream_report("tele.rail.3v3.v", 3.348)
    clock.t = 0.2
    tree.stream_report("tele.rail.1v8.v", 1.802)
    clock.t = 0.6                              # 3v3 at 0.6 s (stale), 1v8 at 0.4 s (fresh)
    if not tree.stale("tele.rail.3v3.v") or tree.stale("tele.rail.1v8.v"):
        die("drill: staleness pattern wrong")
    events.append("3V3 telemetry stale (0.6 s > 0.5 s) — renders — , never 0")

    dev.connected = False
    tree.set("power.ilimit", 1.5, source="user")
    dev.connected = True
    tree.resync()
    if tree.get("power.ilimit") != 0.50:
        die("drill: lost write did not revert")
    events.append("I-Limit 1.50 A LOST in disconnect → reverted to 0.50 A")
    return tree, events


def main():
    data = tomllib.loads(PANEL.read_text())
    try:
        data["font"]["path"] = resolve_path(data["font"]["path"])
        load_panel(data)
        sol = solve({"font": data["font"], **data["solve"]})["knob_rows"]["rails"]
    except (FontError, SpecError, SolveError) as exc:
        die(str(exc))

    tree, events = session()
    t = data["tracks"]

    def fmt(addr, unit):
        return f"{tree.get(addr):.2f} {unit}"

    def knob(name, addr, label, unit, note=""):
        u = sol[name]
        conf = tree.confirmed(addr)
        return (f'<div class="k" style="left:{u["left"]}px;width:{u["width"]}px" data-addr="{addr}">'
                f'<div class="k-label">{label}</div>'
                f'<svg class="k-dial" width="28" height="28" viewBox="0 0 28 28">'
                f'<path d="M 5 23 A 12.5 12.5 0 1 1 23 23" fill="none" stroke="#3c4650" stroke-width="4"/>'
                f'<line x1="14" y1="14" x2="21" y2="7" stroke="#dfe6ec" stroke-width="4" stroke-linecap="round"/></svg>'
                f'<div class="k-value">{fmt(addr, unit)}<span class="conf"> ✓{conf:.2f}</span>{note}</div></div>')

    stale = tree.stale("tele.rail.3v3.v")
    v3v3 = "—" if stale else f"{tree.get('tele.rail.3v3.v'):.3f} V"
    v1v8 = f"{tree.get('tele.rail.1v8.v'):.3f} V"
    rows = "".join(f"<li>{e}</li>" for e in events)

    html = f"""<meta charset="utf-8"><title>Bench Contract</title>
<style>
{font_face_css(FACE, data["font"]["path"])}
body {{ margin:0; background:#232629; font-family:'{FACE}'; }}
.panel {{ position:relative; width:{data["panel"]["width"]}px; height:{data["panel"]["height"]}px;
  background:#565b60; margin:24px auto; border-radius:3px; }}
.plate {{ position:absolute; top:8px; left:{t["margin"]}px; width:{t["columns"][0]}px;
  height:{data["panel"]["height"] - 16}px; background:#43484d; border-radius:2px; }}
.k {{ position:absolute; top:8px; text-align:center; color:#e8edf2; font-size:16px; }}
.k-label {{ height:20px; }}
.k-dial {{ display:block; margin:2px auto 0; }}
.k-value {{ position:absolute; left:calc(50% + 10px); top:50px; white-space:nowrap;
  color:#cfd8e0; font-variant-numeric:tabular-nums; }}
.conf {{ color:#7ee0a3; font-size:12px; }}
.cell {{ position:absolute; top:130px; font-size:16px; color:#9fb0be; }}
.s-label {{ color:#8494a2; font-size:13px; }}
.s-num {{ color:#7ee0a3; font-variant-numeric:tabular-nums; }}
.s-num.stale {{ color:#e07d7d; }}
.log {{ position:absolute; top:8px; left:{t["margin"] + t["columns"][0] + t["gap"]}px;
  width:{t["columns"][1] - 8}px; height:{data["panel"]["height"] - 16}px;
  background:#3a2f2f; border-radius:2px; color:#e8edf2; font-size:12.5px; padding:8px;
  box-sizing:border-box; }}
.log li {{ margin-bottom:6px; }}
</style>
<div class="panel">
  <div class="plate">
    {knob("rail-3v3", "power.rail.3v3.setpoint", "3V3", "V")}
    {knob("rail-1v8", "power.rail.1v8.setpoint", "1V8", "V")}
    {knob("ilimit", "power.ilimit", "I-Limit", "A")}
    <div class="cell" style="left:{sol["rail-3v3"]["left"]}px">
      <span class="s-label">V</span> <span class="s-num{" stale" if stale else ""}">{v3v3}</span></div>
    <div class="cell" style="left:{sol["rail-1v8"]["left"]}px">
      <span class="s-label">V</span> <span class="s-num">{v1v8}</span></div>
  </div>
  <div class="log"><b>SESSION</b><ul>{rows}</ul></div>
</div>
"""
    OUT.write_text(html)
    print(f"wrote {OUT}")

    r = subprocess.run(["uv", "run", "--project",
                        str((HERE / "../../../tools/densui").resolve()),
                        "densui", "audit", str(OUT), "--config", str(PANEL)], text=True)
    if r.returncode != 0:
        die("overlap audit failed")


if __name__ == "__main__":
    main()
