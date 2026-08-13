#!/usr/bin/env python3
"""Operator layout — a thin emitter over densui.solve + panel.toml.

All geometry law lives in the densui package; all numbers live in panel.toml.
This file only maps solved positions onto the demo's CSS selectors, in the
byte-identical format the migration was proven against
(build/expected_positions.css). Run via `uv run --project ../../tools/densui`.
"""
import argparse
import pathlib
import re
import sys
import tomllib

from densui.solve import SolveError, solve
from densui.spec import SpecError, load_panel

HERE = pathlib.Path(__file__).resolve().parent
PANEL = HERE.parent / "panel.toml"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", help="override the panel font (font-parametric build); "
                                   "positions re-solve for this font's advances")
    args = ap.parse_args()
    with open(PANEL, "rb") as fh:
        data = tomllib.load(fh)
    if args.font:
        data["font"]["path"] = args.font
    try:
        load_panel(data)
    except SpecError as exc:
        print(f"SPEC INVALID: {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        out = solve({"font": data["font"], **data["solve"]})
    except SolveError as exc:
        print(f"SOLVE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    css = ["/* rackL: solved from anchors 25/125/201/252/333 + font advances */",
           "#rackL .plate { gap: 0; }"]
    rack = out["flow_rows"]["rackL"]
    for u in data["solve"]["flow_rows"]["rackL"]["units"]:
        r = rack[u["name"]]
        css.append(f"#rackL .{u['name']} {{ flex: none; width: {r['width']}px; "
                   f"margin-left: {r['margin_left']:g}px; }}")
    badge = rack["badge"]
    css.append(f"#rackL .badge {{ margin-right: {badge['margin_right']}px; }}")

    css.append("/* rackR: solved from measured centres; boxes reserved from advances */")
    css += data["emit"]["static"]
    corr = {}
    for line in out["corrections"]:
        m = re.match(r"[^/]+/(\S+): centre (\S+) -> (\S+) \(rhythm G-1\)", line)
        if m:
            corr[m.group(1)] = (m.group(2), m.group(3))
    for row_name in data["emit"]["knob_row_order"]:
        row = out["knob_rows"][row_name]
        units = data["solve"]["knob_rows"][row_name]["units"]
        for u in units:                      # row corrections precede the row's rules
            if u["name"] in corr:
                a, b = corr[u["name"]]
                css.append(f"/* rhythm-corrected: {u['name']} centre {a} -> {b} */")
        for u in units:
            r = row[u["name"]]
            css.append(f".{u['name']} {{ left: {r['left']}px; top: 1px; width: {r['width']}px; }}")
    env = out["grid_rows"]["env"]
    osc = out["grid_rows"]["osc"]
    css.append("/* dgrid tracks: reserved from font advances (grid_rows) */")
    css.append(f".dgrid {{ grid-template-columns: {env['total']}px 1fr; }}")
    css.append(".cells { grid-template-columns: "
               + " ".join(f"{w}px" for w in env["widths"][:-1]) + " 1fr; "
               + f"column-gap: {env['gap']}px; }}")
    css.append(".cells.two { grid-template-columns: "
               + f"{osc['widths'][0]}px 1fr; column-gap: {osc['gap']}px; }}")
    print("\n".join(css))


if __name__ == "__main__":
    main()
