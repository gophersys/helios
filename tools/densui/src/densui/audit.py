"""densui.audit — the proof battery over probe output (LAYOUT-MATH).

Every check consumes {"containers": [...], "parts": [...]} as produced by
densui.probe.collect and returns a list of failure strings naming both parts
and the numbers. An empty list is a pass. Callers compose the battery and
fail loudly on any non-empty result — never downgrade a failure to a warning.
"""

from __future__ import annotations

import math
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

WCAG_TARGET_PITCH_PX = 24.0  # SC 2.5.8's circle diameter (psycho-math R3.4)
AXIS_QUANTUM_PX = 0.5  # R7.4: 0.5px is exactly detectable, so it is the class width
_EDGE_NAMES = ("left", "top", "right", "bottom")
# Chrome's LayoutUnit is 1/64 px, so a real fractional edge is at least 0.015625
# off an integer; anything smaller is binary-float noise from the root subtraction.
_EDGE_EPS = 1e-6


@dataclass
class Rules:
    min_sibling_gap: float = 2.0
    breathing_floor: float = 2.5
    containment_slack: float = 1.5
    axis_budget_floor: float = 3.0  # DENSE-UI A1: controls / distinct control x-axes
    axis_budget_reason: str = ""  # spec.py refuses a lowered floor without one
    text_kinds: frozenset = frozenset({"label", "value", "checklabel", "clabel", "num"})
    rhythm_kinds: frozenset = frozenset({"dial", "checkbox", "dd", "chip", "pairopt", "led"})
    hit_kinds: frozenset = frozenset({"dial", "checkbox", "thumb"})
    snap_kinds: frozenset = frozenset({"dial", "checkbox"})  # A-5's population
    snap_kinds_reason: str = ""  # spec.py refuses a narrowed population without one
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


def _centre(r) -> tuple[float, float]:
    return ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)


def _coordinate_classes(values: list[float], quantum: float) -> list[int]:
    """Class sizes for one coordinate family: a class holds every value within
    `quantum` of where it OPENED, so no class is ever wider than the quantum.
    Chaining each value to its neighbour instead would swallow a whole drifting
    column into one axis and report the sprawl as calm."""
    counts: list[int] = []
    opened = 0.0
    for v in sorted(values):
        if not counts or v - opened > quantum:
            counts.append(0)
            opened = v
        counts[-1] += 1
    return counts


def axis_census(parts: list[Part], quantum: float = AXIS_QUANTUM_PX) -> dict:
    """How many distinct lines the panel draws, per coordinate family.

    `x_axes` is the SMALLEST of the x families, not their sum: a label, a dial
    and a value stacked on one centreline draw ONE vertical line though their
    left and right edges all differ. `omega` is Bonsiepe's layout-complexity
    measure exactly as psycho-math R6.3 states it, summed over the families —
    an objective to minimise, never a threshold (Tullis's coefficients are
    unverified, research §9).
    """
    n = len(parts)
    families = {
        "left": [p["r"][0] for p in parts],
        "right": [p["r"][2] for p in parts],
        "cx": [_centre(p["r"])[0] for p in parts],
        "w": [p["r"][2] - p["r"][0] for p in parts],
        "h": [p["r"][3] - p["r"][1] for p in parts],
    }
    classes = {fam: _coordinate_classes(vals, quantum) for fam, vals in families.items()}
    omega = 0.0
    if n:
        omega = sum(
            -n * sum((c / n) * math.log2(c / n) for c in counts) for counts in classes.values()
        )
    return {
        "n": n,
        "quantum": quantum,
        "counts": {fam: len(counts) for fam, counts in classes.items()},
        "x_axes": min(len(classes[fam]) for fam in ("left", "right", "cx")) if n else 0,
        "omega": omega,
    }


def check_axis_budget(parts: list[Part], rules: Rules) -> list[str]:
    """DENSE-UI A1: crowding is axis proliferation, not control count — every
    vertical line must be bought with ~3 controls, and a crowded panel is fixed
    by merging axes, never by deleting parameters.

    Both sides of the quotient come from the CONTROL population. Measured on the
    demos, a whole-panel denominator scores telemetry 0.26 and operator 0.69,
    because text is glyph ink and ink centres never coincide — every panel would
    need an override below 1.0, which is A1 dying in config while still
    appearing in it. Over controls the same panels read 1.00 and 1.63.

    Below the floor IN CONTROLS the quotient is degenerate — at three controls
    it can only pass in the all-on-one-axis case — so the rule stays silent
    there: A1 is about repeated structure, and repetition begins beyond the
    floor. Omega stays the PANEL's, because R6.3's objective is the whole
    layout's complexity, not the controls'.
    """
    controls = [p for p in parts if p["kind"] in rules.rhythm_kinds]
    if len(controls) <= rules.axis_budget_floor:
        return []
    axes = axis_census(controls)["x_axes"]
    per_axis = len(controls) / axes
    if per_axis >= rules.axis_budget_floor:
        return []
    return [
        (
            f"axis budget: {len(controls)} controls on {axes} distinct control x-axes "
            f"= {per_axis:.2f} per axis, floor {rules.axis_budget_floor} "
            f"(panel Ω {axis_census(parts)['omega']:.1f} — merge axes, do not delete controls)"
        )
    ]


def check_hit_pitch(parts: list[Part], rules: Rules) -> list[str]:
    """WCAG 2.2 SC 2.5.8 as psycho-math R3.4 operationalises it: 24px circles
    centred on each target's bounding box must not intersect, i.e. every pair of
    hit targets is at least 24px CENTRE TO CENTRE. The edge gap is the common
    misreading of the SC and is not monotone in the pitch once two targets
    differ in size.
    """
    targets = [p for p in parts if p["kind"] in rules.hit_kinds]
    fails = []
    for i in range(len(targets)):
        for j in range(i + 1, len(targets)):
            a, b = targets[i], targets[j]
            pitch = math.dist(_centre(a["r"]), _centre(b["r"]))
            if pitch < WCAG_TARGET_PITCH_PX:
                fails.append(
                    f"hit pitch {pitch:.1f}px < {WCAG_TARGET_PITCH_PX} between "
                    f"{a['kind']}({a['owner']}) and {b['kind']}({b['owner']})"
                )
    return fails


def check_integer_edges(parts: list[Part], scale: float) -> list[str]:
    """LAYOUT-MATH A-5 / psycho-math R6.2: every authored edge is a whole CSS px.
    Hyperacuity reads a luminance centroid, so an antialiased half pixel is SEEN
    as half a pixel — it does not average away.

    `scale` is an argument because the rule holds at scale 1 only: a page
    rendered at 1.25x has root-relative CSS px that are fractions of a device
    pixel by construction, and a check that fires there teaches the engine to
    round away real geometry.
    """
    if scale != 1:
        return []
    return [
        f"{p['kind']}({p['owner']}) {edge} edge {v:g} is not an integer px"
        for p in parts
        for edge, v in zip(_EDGE_NAMES, p["r"])
        if abs(v - round(v)) > _EDGE_EPS
    ]


def snappable(parts: list[Part], rules: Rules) -> list[Part]:
    """The parts whose box came from a TOKEN rather than from a string.

    A glyph-ink box (A-4) is where the glyphs are — measured, not placed — and a
    control sized by its own content is no better off: measured on operator,
    every led, chip, badge and dropdown carries fractional edges, because a
    width of padding plus a text advance cannot be integral on both sides.
    Asserting A-5 of those turns it into noise nobody reads, so the population
    is declared, and the default is the two kinds every demo authors from a
    token."""
    return [p for p in parts if p["kind"] in rules.snap_kinds]


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

    A row is {"name", "want", "tol"} plus exactly one of measure="<kind>.<dim>"
    (an absolute size), ratio=["<num>", "<den>"] (a relation — the identity
    carrier: text:control near 0.6 vs the 0.44 of library defaults) or
    span=["<from>", "<to>"] (a distance, second minus first — the row pitch a
    panel claims, which no absolute box can express).

    Multi-instance kinds reduce by MEDIAN, so one drifted instance cannot drag
    the reported value, and their spread is reported as its own failure: three
    dials at 27/27/33 are a defect whose median is exact. A row that matched
    nothing fails — zero violations from a row that measured nothing is the
    dormancy this predicate exists to end.
    """
    fails: list[str] = []
    for row in rows:
        name, want, tol = row["name"], row["want"], row["tol"]
        form = next(f for f in ("ratio", "span", "measure") if f in row)
        tokens = [row["measure"]] if form == "measure" else list(row[form])
        series = [_ratio_series(probe_out, t) for t in tokens]
        blind = [t for t, s in zip(tokens, series) if not s]
        if blind:
            fails.append(f"{name}: {' and '.join(blind)} matched no element — measured nothing")
            continue
        meds = [statistics.median(s) for s in series]
        if form == "ratio" and meds[1] == 0:
            fails.append(f"{name}: {tokens[1]} measures 0 — the quotient does not exist")
            continue
        if form == "ratio":
            got = meds[0] / meds[1]
            # tol is in the ROW's units, so instance spread is converted into
            # them before comparison: d(q)/d(num) = 1/den, d(q)/d(den) = q/den.
            sensitivity = [1 / meds[1], got / meds[1]]
        elif form == "span":
            # A span claims the DIFFERENCE and only the difference: telemetry's
            # labels sit in knob rows hundreds of px apart, and that spread is
            # the panel, not a defect. Direction is part of the claim, so a
            # reversed span reports a negative number instead of agreeing.
            got, sensitivity = meds[1] - meds[0], []
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
    # `scale` is additive: callers written before it exists measure at 1.
    scale = probe_out.get("scale", 1)
    return (
        check_overlaps(parts, rules)
        + check_crowding(parts, rules)
        + check_gap_law(parts, rules)
        + check_containment(parts, containers, rules)
        + check_breathing(parts, containers, rules)
        + check_level(parts)
        + check_axis_budget(parts, rules)
        + check_hit_pitch(parts, rules)
        + check_integer_edges(snappable(parts, rules), scale)
        + check_ratios(probe_out, rules.ratio_rows)
    )
