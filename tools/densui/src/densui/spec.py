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

# The legal [ratio] dimensions come from the predicate that measures them: a
# validator with its own copy of the set can accept a row nothing can measure.
from densui.audit import RATIO_DIMS

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
RULES = {
    "graze_max_height",
    "graze_min_dx",
    "min_sibling_gap",
    "breathing_floor",
    "spill",
    "axis_budget_floor",
    "axis_budget_reason",
    "axis_budget_exempt",
    "hit_kinds",
    "hit_kinds_reason",
    "snap_kinds",
    "snap_kinds_reason",
}
RATIO_ROW = {"measure", "ratio", "span", "want", "tol"}
RATIO_FORMS = ("measure", "ratio", "span")
# Keys that let a panel out of a shipped rule, each with the reason key it costs
# and what that reason must say. An exemption nobody had to justify is how a
# rule dies while still appearing in the config.
EXEMPTIONS = {
    "axis_budget_floor": ("axis_budget_reason", "which structure of THIS panel earns it"),
    "axis_budget_exempt": ("axis_budget_reason", "why this panel can state no budget at all"),
    "hit_kinds": ("hit_kinds_reason", "which measurement shows the dropped kinds are not targets"),
    "snap_kinds": ("snap_kinds_reason", "which measurement shows those boxes are not authored"),
}
# A1's quotient is controls ÷ control x-axes, and a class needs a control to
# exist, so it never falls below 1.00. A floor at or under that is the rule
# switched OFF wearing the costume of the rule switched on — two demos shipped
# exactly that. axis_budget_exempt is where a panel says so out loud.
AXIS_BUDGET_DEAD_FLOOR = 1.0


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


def _ratio_token(tok, where, errors) -> None:
    if not isinstance(tok, str) or tok.rpartition(".")[2] not in RATIO_DIMS:
        legal = ", ".join(sorted(RATIO_DIMS))
        errors.append(f"{where}: {tok!r} is not <kind>.<dim> — legal dims are {legal}")


def _ratio_row(k, v, errors) -> None:
    """One [ratio] row: exactly one of measure/ratio/span, plus want and tol.

    The dead `name = [want, tol]` pair form gets its own message: those rows
    were validated and executed by nothing for months, and their meaning
    changed when check_ratios landed — silently accepting the old shape is how
    a dormant check survives its own rewrite.
    """
    where = f"ratio.{k}"
    if not isinstance(v, dict):
        errors.append(
            f"{where}: the [want, tol] pair form is gone (it named no measurement) — use "
            f'{{ measure = "dial.h", want = .., tol = .. }} or '
            f'{{ ratio = ["label.h", "dial.h"], want = .., tol = .. }}, got {v!r}'
        )
        return
    _unknown(v, RATIO_ROW, where, errors)
    _require(v, ["want", "tol"], where, errors)
    for key in ("want", "tol"):
        if key in v and not isinstance(v[key], (int, float)):
            errors.append(f"{where}: {key} must be a number, got {v[key]!r}")
    forms = [f for f in RATIO_FORMS if f in v]
    if len(forms) != 1:
        errors.append(
            f'{where}: needs exactly one of measure = "<kind>.<dim>", ratio = [n, d] '
            f"or span = [from, to], got {forms or 'none'}"
        )
    elif forms[0] == "measure":
        _ratio_token(v["measure"], where, errors)
    elif not (isinstance(v[forms[0]], list) and len(v[forms[0]]) == 2):
        pair = "[numerator, denominator]" if forms[0] == "ratio" else "[from, to]"
        errors.append(f"{where}: {forms[0]} must be a {pair} pair, got {v[forms[0]]!r}")
    else:
        for tok in v[forms[0]]:
            _ratio_token(tok, where, errors)


def _rules_table(spec: dict, errors: list[str]) -> dict:
    """The [rules] table's own validation, in one place.

    A1's budget, A8's hit population and A-5's snap population are the shipped
    rules a panel can legally step out of, and each costs a written reason —
    `snap_kinds = []` or `hit_kinds = []` would otherwise switch a rule off
    panel-wide in one line that reads like configuration.
    """
    table = spec.get("rules", {})
    _unknown(table, RULES, "rules", errors)
    for key, (reason_key, what) in EXEMPTIONS.items():
        if key in table and not str(table.get(reason_key, "")).strip():
            errors.append(f"rules: {key} is declared without {reason_key} — state {what}")
    floor = table.get("axis_budget_floor")
    if isinstance(floor, (int, float)) and floor <= AXIS_BUDGET_DEAD_FLOOR:
        errors.append(
            f"rules: axis_budget_floor = {floor} cannot fire — controls ÷ control x-axes "
            f"never falls below {AXIS_BUDGET_DEAD_FLOOR:.2f}, so this floor is A1 switched "
            f"off; a panel that can state no budget declares axis_budget_exempt instead"
        )
    return table


def rules_table(spec: dict) -> dict:
    """The validated [rules] table. Separate from load_panel() for the reason
    ratio_rows() is: an audit config is often a PARTIAL panel.toml, and a rule
    honoured on the gate path must be refused there too."""
    errors: list[str] = []
    table = _rules_table(spec, errors)
    if errors:
        raise SpecError(errors)
    return table


def ratio_rows(spec: dict) -> list[dict]:
    """The [ratio] table as densui.audit.check_ratios rows, validated.

    Separate from load_panel() because an audit config is often a PARTIAL
    panel.toml (a corpus seed declares [probe] and [ratio] and nothing else),
    and a declared row must still be refused rather than silently skipped.
    """
    errors: list[str] = []
    rows = []
    for k, v in spec.get("ratio", {}).items():
        _ratio_row(k, v, errors)
        if isinstance(v, dict):
            rows.append({"name": k, **v})
    if errors:
        raise SpecError(errors)
    return rows


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
    _rules_table(data, errors)
    for k, v in data.get("ratio", {}).items():
        _ratio_row(k, v, errors)

    if errors:
        raise SpecError(errors)
    return data
