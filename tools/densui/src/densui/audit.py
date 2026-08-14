"""densui.audit — the proof battery over probe output (LAYOUT-MATH).

Every check consumes {"containers": [...], "parts": [...]} as produced by
densui.probe.collect and returns a list of failure strings naming both parts
and the numbers. An empty list is a pass. Callers compose the battery and
fail loudly on any non-empty result — never downgrade a failure to a warning.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from densui.geometry import breathing, contains, gap_law_violations, hgap, inter

Part = dict
LegalOverlap = Callable[[Part, Part, tuple], bool]

RATIO_DIMS = {
    "h": lambda r: r[3] - r[1],
    "w": lambda r: r[2] - r[0],
    "cx": lambda r: (r[0] + r[2]) / 2,
    "cy": lambda r: (r[1] + r[3]) / 2,
}


@dataclass
class Rules:
    min_sibling_gap: float = 2.0
    breathing_floor: float = 2.5
    containment_slack: float = 1.5
    text_kinds: frozenset = frozenset({"label", "value", "checklabel", "clabel", "num"})
    rhythm_kinds: frozenset = frozenset({"dial", "checkbox", "dd", "chip", "pairopt", "led"})
    composites: frozenset = frozenset({frozenset({"checkbox", "checklabel"})})
    legal_overlap: LegalOverlap | None = None
    spill_slack: dict = field(default_factory=dict)  # (container_prefix, kind) -> px
    ratio_rows: tuple = ()  # the panel's [ratio] table, as check_ratios rows


def knob_value_graze(max_height: float = 2.5, min_dx_from_center: float = 8.0) -> LegalOverlap:
    """A value may graze its OWN dial's ring lower-right by <= max_height px,
    starting at least min_dx right of the dial centre — the measured Live
    tolerance. Everything else stays illegal."""

    def legal(a: Part, b: Part, ix: tuple) -> bool:
        kinds = {a["kind"], b["kind"]}
        if kinds != {"value", "dial"} or a["owner"] != b["owner"] or not a["owner"]:
            return False
        dial = a if a["kind"] == "dial" else b
        cx = (dial["r"][0] + dial["r"][2]) / 2
        return (ix[3] - ix[1]) <= max_height and ix[0] >= cx + min_dx_from_center

    return legal


def _by_container(parts: list[Part]) -> dict[str, list[Part]]:
    out: dict[str, list[Part]] = {}
    for p in parts:
        out.setdefault(p["c"], []).append(p)
    return out


def check_overlaps(parts: list[Part], rules: Rules) -> list[str]:
    fails = []
    for cid, plist in _by_container(parts).items():
        for i in range(len(plist)):
            for j in range(i + 1, len(plist)):
                a, b = plist[i], plist[j]
                ix = inter(a["r"], b["r"])
                if not ix:
                    continue
                same = a["owner"] == b["owner"] and a["owner"]
                if same and frozenset({a["kind"], b["kind"]}) in rules.composites:
                    continue
                if rules.legal_overlap and rules.legal_overlap(a, b, ix):
                    continue
                fails.append(
                    f"{cid}: {a['kind']}({a['owner']}) overlaps {b['kind']}({b['owner']}) "
                    f"by {ix[2] - ix[0]:.1f}x{ix[3] - ix[1]:.1f}px"
                )
    return fails


def check_crowding(parts: list[Part], rules: Rules) -> list[str]:
    fails = []
    for cid, plist in _by_container(parts).items():
        for i in range(len(plist)):
            for j in range(i + 1, len(plist)):
                a, b = plist[i], plist[j]
                if a["owner"] == b["owner"]:
                    continue
                g = hgap(a["r"], b["r"])
                if g is not None and 0 <= g < rules.min_sibling_gap:
                    fails.append(
                        f"{cid}: gap {g:.1f}px < {rules.min_sibling_gap} between "
                        f"{a['kind']}({a['owner']}) and {b['kind']}({b['owner']})"
                    )
    return fails


def check_gap_law(parts: list[Part], rules: Rules) -> list[str]:
    """Similarity gates proximity: compare gaps only between ADJACENT SAME-KIND
    rhythm units on one line, with no other control interposed."""
    fails = []
    for cid, plist in _by_container(parts).items():
        ctrls_all = [p for p in plist if p["kind"] in rules.rhythm_kinds]
        by_kind: dict[str, list[Part]] = {}
        for q in ctrls_all:
            by_kind.setdefault(q["kind"], []).append(q)
        for kind, ctrls in by_kind.items():
            ctrls.sort(key=lambda q: q["r"][0])
            gaps = []
            for i in range(len(ctrls) - 1):
                a, b = ctrls[i], ctrls[i + 1]
                if a["r"][3] <= b["r"][1] or b["r"][3] <= a["r"][1]:
                    continue
                mid = [
                    q
                    for q in ctrls_all
                    if q is not a
                    and q is not b
                    and a["r"][2] < (q["r"][0] + q["r"][2]) / 2 < b["r"][0]
                    and not (q["r"][3] <= a["r"][1] or a["r"][3] <= q["r"][1])
                ]
                if mid:
                    continue
                g = b["r"][0] - a["r"][2]
                if g > 0.5:
                    gaps.append(g)
            for g1, g2 in gap_law_violations(gaps):
                fails.append(
                    f"{cid}: sloppy {kind} gap pair {g1:.1f}px vs {g2:.1f}px "
                    f"— equal or >=1.45x required"
                )
    return fails


def check_containment(parts: list[Part], containers: list[dict], rules: Rules) -> list[str]:
    fails = []
    boxes = {c["id"]: c["r"] for c in containers}
    for p in parts:
        c = boxes.get(p["c"])
        if c is None:
            fails.append(f"{p['c']}: container missing for {p['kind']}({p['owner']})")
            continue
        slack = rules.containment_slack
        for (prefix, kind), extra in rules.spill_slack.items():
            if p["c"].startswith(prefix) and p["kind"] == kind:
                slack = extra
        worst = contains(p["r"], c, slack)
        if worst is not None:
            fails.append(
                f"{p['c']}: {p['kind']}({p['owner']}) escapes its container by {worst:.1f}px"
            )
    return fails


def check_breathing(parts: list[Part], containers: list[dict], rules: Rules) -> list[str]:
    fails = []
    boxes = {c["id"]: c["r"] for c in containers}
    for p in parts:
        if p["kind"] not in rules.text_kinds or p["c"] not in boxes:
            continue
        clear = breathing(p["r"], boxes[p["c"]], rules.breathing_floor)
        if clear is not None:
            fails.append(
                f"{p['c']}: {p['kind']}({p['owner']}) ink presses the bottom edge "
                f"(clearance {clear:.1f}px < {rules.breathing_floor})"
            )
    return fails


def check_level(parts: list[Part], kind: str = "dial", tol: float = 1.0) -> list[str]:
    """Same-LINE centres must be level; a plate may hold several lines. Parts
    cluster into lines by vertical-band overlap first (the telemetry demo's
    ilimit row false-positived the single-line version)."""
    fails = []
    for cid, plist in _by_container(parts).items():
        items = [p for p in plist if p["kind"] == kind]
        items.sort(key=lambda p: p["r"][1])
        lines: list[list] = []
        for p in items:
            if lines and p["r"][1] < lines[-1][-1]["r"][3]:
                lines[-1].append(p)
            else:
                lines.append([p])
        for line in lines:
            ys = [(p["r"][1] + p["r"][3]) / 2 for p in line]
            if len(ys) > 1 and max(ys) - min(ys) > tol:
                fails.append(
                    f"{cid}: {kind} centres not level within a line "
                    f"(spread {max(ys) - min(ys):.1f}px)"
                )
    return fails


def check_cross_alignment(parts: list[Part], group_key, tol: float = 1.0) -> list[str]:
    """Same-role parts across containers share a centre-x (group_key(part) ->
    hashable or None to skip)."""
    groups: dict = {}
    for p in parts:
        k = group_key(p)
        if k is not None:
            groups.setdefault(k, []).append((p["r"][0] + p["r"][2]) / 2)
    return [
        f"column {k} not aligned across containers (spread {max(xs) - min(xs):.1f}px)"
        for k, xs in groups.items()
        if len(xs) > 1 and max(xs) - min(xs) > tol
    ]


def _ratio_series(probe_out: dict, token: str) -> list[float]:
    """Every measurement a "<kind>.<dim>" token addresses, in document order.

    "root" is the reserved kind for the probe root rect — panel_w/panel_h are
    the panel itself, which is neither a part nor a container.
    """
    kind, _, dim = token.rpartition(".")
    if dim not in RATIO_DIMS:
        raise ValueError(f"ratio token {token!r}: legal dims are {', '.join(sorted(RATIO_DIMS))}")
    of = RATIO_DIMS[dim]
    if kind == "root":
        root = probe_out.get("root")
        return [of(root)] if root else []
    return [of(p["r"]) for p in probe_out["parts"] if p["kind"] == kind]


def check_ratios(probe_out: dict, rows: Sequence[dict]) -> list[str]:
    """The declared [ratio] table, measured on the rendered page.

    A row is {"name", "want", "tol"} plus either measure="<kind>.<dim>" (an
    absolute size) or ratio=["<num>", "<den>"] (a relation — the identity
    carrier: text:control near 0.6 vs the 0.44 of library defaults).

    Multi-instance kinds reduce by MEDIAN, so one drifted instance cannot drag
    the reported value, and their spread is reported as its own failure: three
    dials at 27/27/33 are a defect whose median is exact. A row that matched
    nothing fails — zero violations from a row that measured nothing is the
    dormancy this predicate exists to end.
    """
    fails: list[str] = []
    for row in rows:
        name, want, tol = row["name"], row["want"], row["tol"]
        tokens = list(row["ratio"]) if "ratio" in row else [row["measure"]]
        series = [_ratio_series(probe_out, t) for t in tokens]
        blind = [t for t, s in zip(tokens, series) if not s]
        if blind:
            fails.append(f"{name}: {' and '.join(blind)} matched no element — measured nothing")
            continue
        meds = [statistics.median(s) for s in series]
        if len(meds) == 2 and meds[1] == 0:
            fails.append(f"{name}: {tokens[1]} measures 0 — the quotient does not exist")
            continue
        if len(meds) == 2:
            got = meds[0] / meds[1]
            # tol is in the ROW's units, so instance spread is converted into
            # them before comparison: d(q)/d(num) = 1/den, d(q)/d(den) = q/den.
            sensitivity = [1 / meds[1], got / meds[1]]
        else:
            got, sensitivity = meds[0], [1.0]
        if abs(got - want) > tol:
            fails.append(f"{name}: {got:.2f} vs {want} (tol ±{tol})")
        for token, values, k in zip(tokens, series, sensitivity):
            spread = max(values) - min(values)
            if spread * k > tol:
                px = f"{spread:.2f}px" if k == 1.0 else f"{spread:.2f}px = {spread * k:.3f} of it"
                fails.append(
                    f"{name}: {len(values)} {token} instances spread {px} "
                    f"(median {statistics.median(values):.2f}, tol ±{tol})"
                )
    return fails


def run_battery(probe_out: dict, rules: Rules) -> list[str]:
    parts, containers = probe_out["parts"], probe_out["containers"]
    return (
        check_overlaps(parts, rules)
        + check_crowding(parts, rules)
        + check_gap_law(parts, rules)
        + check_containment(parts, containers, rules)
        + check_breathing(parts, containers, rules)
        + check_level(parts)
        + check_ratios(probe_out, rules.ratio_rows)
    )
