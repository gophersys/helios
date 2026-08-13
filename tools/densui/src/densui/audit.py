"""densui.audit — the proof battery over probe output (LAYOUT-MATH).

Every check consumes {"containers": [...], "parts": [...]} as produced by
densui.probe.collect and returns a list of failure strings naming both parts
and the numbers. An empty list is a pass. Callers compose the battery and
fail loudly on any non-empty result — never downgrade a failure to a warning.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from densui.geometry import breathing, contains, gap_law_violations, hgap, inter

Part = dict
LegalOverlap = Callable[[Part, Part, tuple], bool]


@dataclass
class Rules:
    min_sibling_gap: float = 2.0
    breathing_floor: float = 2.5
    containment_slack: float = 1.5
    text_kinds: frozenset = frozenset({"label", "value", "checklabel", "clabel", "num"})
    rhythm_kinds: frozenset = frozenset({"dial", "checkbox", "dd", "chip", "pairopt", "led"})
    composites: frozenset = frozenset({frozenset({"checkbox", "checklabel"})})
    legal_overlap: LegalOverlap | None = None
    spill_slack: dict = field(default_factory=dict)   # (container_prefix, kind) -> px


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
                    f"by {ix[2] - ix[0]:.1f}x{ix[3] - ix[1]:.1f}px")
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
                        f"{a['kind']}({a['owner']}) and {b['kind']}({b['owner']})")
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
                mid = [q for q in ctrls_all if q is not a and q is not b
                       and a["r"][2] < (q["r"][0] + q["r"][2]) / 2 < b["r"][0]
                       and not (q["r"][3] <= a["r"][1] or a["r"][3] <= q["r"][1])]
                if mid:
                    continue
                g = b["r"][0] - a["r"][2]
                if g > 0.5:
                    gaps.append(g)
            for g1, g2 in gap_law_violations(gaps):
                fails.append(
                    f"{cid}: sloppy {kind} gap pair {g1:.1f}px vs {g2:.1f}px "
                    f"— equal or >=1.45x required")
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
                f"{p['c']}: {p['kind']}({p['owner']}) escapes its container by {worst:.1f}px")
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
                f"(clearance {clear:.1f}px < {rules.breathing_floor})")
    return fails


def check_level(parts: list[Part], kind: str = "dial", tol: float = 1.0) -> list[str]:
    fails = []
    for cid, plist in _by_container(parts).items():
        ys = [(p["r"][1] + p["r"][3]) / 2 for p in plist if p["kind"] == kind]
        if len(ys) > 1 and max(ys) - min(ys) > tol:
            fails.append(f"{cid}: {kind} centres not level (spread {max(ys) - min(ys):.1f}px)")
    return fails


def check_cross_alignment(parts: list[Part], group_key, tol: float = 1.0) -> list[str]:
    """Same-role parts across containers share a centre-x (group_key(part) ->
    hashable or None to skip)."""
    groups: dict = {}
    for p in parts:
        k = group_key(p)
        if k is not None:
            groups.setdefault(k, []).append((p["r"][0] + p["r"][2]) / 2)
    return [f"column {k} not aligned across containers (spread {max(xs) - min(xs):.1f}px)"
            for k, xs in groups.items() if len(xs) > 1 and max(xs) - min(xs) > tol]


def run_battery(probe_out: dict, rules: Rules) -> list[str]:
    parts, containers = probe_out["parts"], probe_out["containers"]
    return (check_overlaps(parts, rules) + check_crowding(parts, rules)
            + check_gap_law(parts, rules)
            + check_containment(parts, containers, rules)
            + check_breathing(parts, containers, rules)
            + check_level(parts))
