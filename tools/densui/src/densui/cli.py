"""densui CLI — solve / audit / zoom / compare from the shell.

Every subcommand fails loudly with a named cause and a non-zero exit; output
is JSON on stdout so pipelines can consume it.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tomllib


def _die(msg: str) -> int:
    print(f"densui: {msg}", file=sys.stderr)
    return 2


def cmd_solve(args) -> int:
    from densui.solve import SolveError, solve

    try:
        print(json.dumps(solve(args.spec), indent=2))
    except SolveError as exc:
        return _die(f"solve failed: {exc}")
    return 0


def cmd_audit(args) -> int:
    from densui import audit, probe

    try:
        with open(args.config, "rb") as fh:
            cfg = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return _die(f"bad audit config {args.config}: {exc}")
    try:
        pr = cfg["probe"]
        sweep_js = pathlib.Path(args.sweep_js).read_text() if args.sweep_js else ""
        out = probe.collect(
            args.page,
            root=pr["root"],
            containers=pr.get("containers", {}),
            parts=pr.get("parts", {}),
            text_kinds=set(pr.get("text_kinds", [])),
            owner_attr=pr.get("owner_attr", "data-addr"),
            root_width=pr.get("root_width"),
            extra_js=sweep_js,
        )
    except (KeyError, probe.ProbeError) as exc:
        return _die(f"probe failed: {exc}")
    rules_cfg = cfg.get("rules", {})
    legal = None
    if "graze_max_height" in rules_cfg:
        legal = audit.knob_value_graze(
            rules_cfg["graze_max_height"], rules_cfg.get("graze_min_dx", 8.0)
        )
    rules = audit.Rules(
        min_sibling_gap=rules_cfg.get("min_sibling_gap", 2.0),
        breathing_floor=rules_cfg.get("breathing_floor", 2.5),
        legal_overlap=legal,
        spill_slack={(c, k): float(v) for c, k, v in rules_cfg.get("spill", [])},
    )
    fails = audit.run_battery(out, rules)
    print(json.dumps({"parts": len(out["parts"]), "failures": fails}, indent=2))
    return 1 if fails else 0


def cmd_zoom(args) -> int:
    from densui import measure

    img = measure.load(args.image)
    box = tuple(int(v) for v in args.box.split(","))
    if len(box) != 4:
        return _die("--box needs x0,y0,x1,y1")
    measure.zoom(
        img, box, args.out, scale=args.scale, grid_step=args.grid, grid_divisor=args.grid_divisor
    )
    print(json.dumps({"out": str(args.out)}))
    return 0


def cmd_compare(args) -> int:
    from densui import compare, measure

    regions = {}
    for spec in args.region:
        name, coords = spec.split("=", 1)
        box = tuple(int(v) for v in coords.split(","))
        if len(box) != 4:
            return _die(f"region {name}: needs x0,y0,x1,y1")
        regions[name] = box
    written = compare.side_by_side(
        measure.load(args.ref), measure.load(args.built), regions, args.out_dir, scale=args.scale
    )
    print(json.dumps({k: str(v) for k, v in written.items()}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="densui")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("solve", help="solve a layout spec (TOML) to positions JSON")
    s.add_argument("spec")
    s.set_defaults(fn=cmd_solve)

    a = sub.add_parser("audit", help="run the proof battery over a rendered page")
    a.add_argument("page")
    a.add_argument("--config", required=True, help="TOML: [probe] + [rules]")
    a.add_argument("--sweep-js", help="JS file injected before probing (content sweep)")
    a.set_defaults(fn=cmd_audit)

    z = sub.add_parser("zoom", help="gridline-labelled anatomy zoom of a bitmap region")
    z.add_argument("image")
    z.add_argument("--box", required=True)
    z.add_argument("--out", required=True)
    z.add_argument("--scale", type=int, default=8)
    z.add_argument("--grid", type=int, default=None)
    z.add_argument("--grid-divisor", type=float, default=1.0)
    z.set_defaults(fn=cmd_zoom)

    c = sub.add_parser("compare", help="ref-vs-built A/B composites per region")
    c.add_argument("ref")
    c.add_argument("built")
    c.add_argument("--region", action="append", required=True, help="name=x0,y0,x1,y1 (repeatable)")
    c.add_argument("--out-dir", required=True)
    c.add_argument("--scale", type=int, default=2)
    c.set_defaults(fn=cmd_compare)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
