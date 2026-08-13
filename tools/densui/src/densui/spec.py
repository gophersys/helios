"""densui.spec — panel.toml validation with named errors.

A spec typo must die at load, naming every problem at once with its full path
and a did-you-mean suggestion — not obscurely downstream in a solver
inequality. load_panel() returns the validated dict or raises SpecError
carrying ALL errors.
"""

from __future__ import annotations

import difflib
import pathlib
import tomllib

TOP = {"panel", "font", "census", "tracks", "solve", "probe", "rules", "ratio", "emit"}
FLOW_ROW = {"pad", "right_edge", "units", "trailing"}
FLOW_UNIT = {"name", "center", "box", "labels", "widest_value", "value_left_offset"}
KNOB_ROW = {
    "anchor_tolerance",
    "plate_width",
    "dial",
    "tuck",
    "dial_floor",
    "label_floor",
    "equalize",
    "units",
}
KNOB_UNIT = {"name", "center", "label", "widest"}
RULES = {"graze_max_height", "graze_min_dx", "min_sibling_gap", "breathing_floor", "spill"}


class SpecError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("invalid panel spec:\n  " + "\n  ".join(errors))


def _unknown(keys, allowed, where, errors):
    for k in keys:
        if k not in allowed:
            hint = difflib.get_close_matches(k, allowed, n=1)
            sug = f" (did you mean {hint[0]!r}?)" if hint else ""
            errors.append(f"{where}: unknown key {k!r}{sug}")


def _require(table, keys, where, errors):
    for k in keys:
        if k not in table:
            errors.append(f"{where}: missing required key {k!r}")


def load_panel(spec: dict | str | pathlib.Path) -> dict:
    if isinstance(spec, (str, pathlib.Path)):
        with open(spec, "rb") as fh:
            data = tomllib.load(fh)
    else:
        data = spec
    errors: list[str] = []
    _unknown(data, TOP, "top level", errors)
    _require(data, ["panel", "font"], "top level", errors)

    panel = data.get("panel", {})
    _require(panel, ["name", "width", "height"], "panel", errors)
    font = data.get("font", {})
    _require(font, ["path", "size"], "font", errors)
    if "path" in font and not pathlib.Path(font["path"]).exists():
        errors.append(f"font.path: {font['path']} does not exist")

    solve = data.get("solve", {})
    for rname, row in solve.get("flow_rows", {}).items():
        where = f"solve.flow_rows.{rname}"
        _unknown(row, FLOW_ROW, where, errors)
        units = row.get("units", [])
        if not units:
            errors.append(f"{where}: units must be a non-empty list")
        for i, u in enumerate(units):
            uw = f"{where}.units[{i}]"
            _unknown(u, FLOW_UNIT, uw, errors)
            _require(u, ["name", "center", "box"], uw, errors)
        trail = row.get("trailing")
        if trail is not None:
            _require(trail, ["name", "center", "width"], f"{where}.trailing", errors)
    for rname, row in solve.get("grid_rows", {}).items():
        where = f"solve.grid_rows.{rname}"
        _unknown(row, {"cell_pad", "gap", "columns"}, where, errors)
        if not row.get("columns"):
            errors.append(f"{where}: columns must be a non-empty list")
    for rname, row in solve.get("knob_rows", {}).items():
        where = f"solve.knob_rows.{rname}"
        _unknown(row, KNOB_ROW, where, errors)
        _require(row, ["plate_width"], where, errors)
        units = row.get("units", [])
        if not units:
            errors.append(f"{where}: units must be a non-empty list")
        for i, u in enumerate(units):
            uw = f"{where}.units[{i}]"
            _unknown(u, KNOB_UNIT, uw, errors)
            _require(u, KNOB_UNIT, uw, errors)

    if "probe" in data:
        _require(data["probe"], ["root"], "probe", errors)
    _unknown(data.get("rules", {}), RULES, "rules", errors)
    for k, v in data.get("ratio", {}).items():
        if not (
            isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v)
        ):
            errors.append(f"ratio.{k}: expected [want, tol], got {v!r}")

    if errors:
        raise SpecError(errors)
    return data
