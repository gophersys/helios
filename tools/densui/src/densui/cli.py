"""densui CLI — solve / audit / score / zoom / compare from the shell.

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


def _collect(page, probe_cfg: dict, extra_js: str = "") -> dict:
    from densui import probe

    return probe.collect(
        page,
        root=probe_cfg["root"],
        containers=probe_cfg.get("containers", {}),
        parts=probe_cfg.get("parts", {}),
        text_kinds=set(probe_cfg.get("text_kinds", [])),
        owner_attr=probe_cfg.get("owner_attr", "data-addr"),
        root_width=probe_cfg.get("root_width"),
        extra_js=extra_js,
    )


def _rules(cfg: dict):
    from densui import audit

    rules_cfg = cfg.get("rules", {})
    legal = None
    if "graze_max_height" in rules_cfg:
        legal = audit.knob_value_graze(
            rules_cfg["graze_max_height"], rules_cfg.get("graze_min_dx", 8.0)
        )
    return audit.Rules(
        min_sibling_gap=rules_cfg.get("min_sibling_gap", 2.0),
        breathing_floor=rules_cfg.get("breathing_floor", 2.5),
        legal_overlap=legal,
        spill_slack={(c, k): float(v) for c, k, v in rules_cfg.get("spill", [])},
    )


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
        sweep_js = pathlib.Path(args.sweep_js).read_text() if args.sweep_js else ""
        out = _collect(args.page, cfg["probe"], sweep_js)
    except (KeyError, probe.ProbeError) as exc:
        return _die(f"probe failed: {exc}")
    fails = audit.run_battery(out, _rules(cfg))
    print(json.dumps({"parts": len(out["parts"]), "failures": fails}, indent=2))
    return 1 if fails else 0


def cmd_score(args) -> int:
    from densui import probe, score

    corpus = pathlib.Path(args.corpus)
    seeds = sorted(d for d in corpus.iterdir() if d.is_dir()) if corpus.is_dir() else []
    if not seeds:
        return _die(f"no seed directories under {corpus} — a corpus that cannot be scored fails")
    targets = []
    for d in seeds:
        try:
            with open(d / "panel.toml", "rb") as fh:
                cfg = tomllib.load(fh)
            out = _collect(d / "page.html", cfg["probe"])
        except (OSError, tomllib.TOMLDecodeError, KeyError, probe.ProbeError) as exc:
            return _die(f"corpus seed {d.name}: {exc}")
        targets.append(score.Target(name=str(d), probe_out=out, seeds=d.name, rules=_rules(cfg)))
    report = score.run_scorecard(targets)
    print(json.dumps(report, indent=2))
    return 1 if report["failures"] else 0


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

    sc = sub.add_parser("score", help="craft scorecard over a seeded corpus")
    sc.add_argument("--corpus", required=True, help="directory of <defect-class>/ seed dirs")
    sc.set_defaults(fn=cmd_score)

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
