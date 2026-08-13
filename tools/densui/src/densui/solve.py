"""densui.solve — layout positions computed from a spec, never hand-written.

LAYOUT-MATH applied generically: sizes come only from font metrics or declared
tokens (A-1); no coordinate is a function of a live text width — boxes are
reserved from the WIDEST declared string (A-2); edges are integers (A-5); a
run of >=3 same-kind units gets equal gaps by construction (G-1); every
constraint is checked before a single position is emitted, and a violation
raises SolveError naming the unit and the numbers.

Spec input is a dict (or a TOML path — tomllib is stdlib). Two row models:

flow_rows: sequential reserved boxes on one line, each anchored at a measured
  centre; an optional trailing element anchored from the right; optional
  value-ink clearance against the next unit.
knob_rows: two-line rows (labels above, dials+values below) with separate
  line-1/line-2 floors, centred labels, values tucked at centre+tuck.

Determinism: solve() output depends only on spec CONTENT, not dict insertion
order — verified by test; re-solving a canonicalised spec twice is identical.
"""

from __future__ import annotations

import pathlib
import tomllib
from dataclasses import dataclass

from densui.fontmetrics import Face

MIN_INK_GAP = 3.0


class SolveError(RuntimeError):
    pass


@dataclass
class _Ctx:
    face: Face
    size: float

    def adv(self, text: str) -> float:
        return self.face.adv(text, self.size)


def _load(spec: dict | str | pathlib.Path) -> dict:
    if isinstance(spec, (str, pathlib.Path)):
        with open(spec, "rb") as fh:
            return tomllib.load(fh)
    return spec


def solve(spec: dict | str | pathlib.Path) -> dict:
    """Returns {"flow_rows": {name: {unit: {...}}}, "knob_rows": {...},
    "corrections": [...]} — pure data; CSS emission is the caller's concern."""
    data = _load(spec)
    font = data.get("font") or {}
    if "path" not in font or "size" not in font:
        raise SolveError("spec.font needs path and size — sizes come from metrics (A-1)")
    ctx = _Ctx(Face(font["path"]), float(font["size"]))
    out = {"flow_rows": {}, "knob_rows": {}, "corrections": []}
    for name in sorted(data.get("flow_rows", {})):
        out["flow_rows"][name] = _solve_flow(name, data["flow_rows"][name], ctx)
    for name in sorted(data.get("knob_rows", {})):
        sol, corr = _solve_knobs(name, data["knob_rows"][name], ctx)
        out["knob_rows"][name] = sol
        out["corrections"] += corr
    return out


def _solve_flow(name: str, row: dict, ctx: _Ctx) -> dict:
    pad = float(row.get("pad", 0))
    cursor = pad
    sol: dict = {}
    units = row["units"]
    for u in units:
        box = float(u["box"])  # control width: a declared token
        left = round(u["center"] - box / 2)
        width = int(max([box] + [ctx.adv(t) for t in u.get("labels", [])]) + 0.999) + 1
        margin = left - cursor
        if margin < 0:
            raise SolveError(f"{name}/{u['name']}: reserved boxes collide (margin {margin})")
        sol[u["name"]] = {"left": left, "width": width, "margin_left": margin}
        cursor = left + width
    trail = row.get("trailing")
    if trail:
        t_left = round(trail["center"] - trail["width"] / 2)
        if t_left - cursor < MIN_INK_GAP:
            raise SolveError(
                f"{name}/{trail['name']}: gap {t_left - cursor:.1f} "
                f"< {MIN_INK_GAP} before trailing element"
            )
        last = units[-1]
        if "widest_value" in last:
            v_right = (
                sol[last["name"]]["left"]
                + float(last.get("value_left_offset", 0))
                + ctx.adv(last["widest_value"])
            )
            if v_right > t_left - MIN_INK_GAP:
                raise SolveError(
                    f"{name}/{last['name']}: widest value ink ends "
                    f"{v_right:.1f}, reaches trailing at {t_left}"
                )
        sol[trail["name"]] = {
            "left": t_left,
            "width": int(trail["width"]),
            "margin_right": int(row["right_edge"] - (t_left + trail["width"]))
            if "right_edge" in row
            else 0,
        }
    return sol


def _solve_knobs(name: str, row: dict, ctx: _Ctx) -> tuple[dict, list[str]]:
    dial = float(row.get("dial", 28))
    tuck = float(row.get("tuck", 10))
    plate_w = float(row["plate_width"])
    dial_floor = float(row.get("dial_floor", 0))
    label_floor = float(row.get("label_floor", 0))
    units = row["units"]
    centers = {u["name"]: float(u["center"]) for u in units}
    corrections: list[str] = []
    if row.get("equalize", True) and len(units) >= 3:
        first, last = centers[units[0]["name"]], centers[units[-1]["name"]]
        for k, u in enumerate(units):
            fixed = round(first + (last - first) * k / (len(units) - 1))
            if fixed != centers[u["name"]]:
                corrections.append(
                    f"{name}/{u['name']}: centre {centers[u['name']]:g} -> {fixed} (rhythm G-1)"
                )
            centers[u["name"]] = fixed
    sol: dict = {}
    prev_label_right = label_floor
    for k, u in enumerate(units):
        center = centers[u["name"]]
        label_adv = ctx.adv(u["label"])
        w = int(max(label_adv, dial) + 0.999) + 2
        left = round(center - w / 2)
        dial_left = round(center - dial / 2)
        if dial_left < dial_floor:
            raise SolveError(
                f"{name}/{u['name']}: dial left {dial_left} crosses floor {dial_floor:g}"
            )
        label_ink_l = center - label_adv / 2
        if label_ink_l < prev_label_right + MIN_INK_GAP:
            raise SolveError(
                f"{name}/{u['name']}: label ink {label_ink_l:.1f} crowds "
                f"line-1 neighbour (ends {prev_label_right:.1f})"
            )
        value_right = center + tuck + ctx.adv(u["widest"])
        if k + 1 < len(units):
            nxt = centers[units[k + 1]["name"]] - dial / 2
            if value_right + MIN_INK_GAP > nxt:
                raise SolveError(
                    f"{name}/{u['name']}: widest value ink ends "
                    f"{value_right:.1f}, crowds next dial at {nxt:.1f}"
                )
        elif value_right > plate_w - 4:
            raise SolveError(
                f"{name}/{u['name']}: last value ink {value_right:.1f} "
                f"escapes the plate ({plate_w:g})"
            )
        prev_label_right = center + label_adv / 2
        sol[u["name"]] = {"left": left, "width": w, "center": center}
    return sol, corrections
