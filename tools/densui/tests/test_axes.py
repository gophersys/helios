"""The alignment axioms stop being prose (W2 of deep-craft).

A1 ("crowding is axis proliferation, not control count"), A7/A-5 ("all box
edges are integers") and A8 (WCAG 2.5.8's 24 px circle test) are stated in
`framework/DENSE-UI.md`, `framework/LAYOUT-MATH.md` and
`framework/research/psycho-math.md`, cited by three skills, and executed by
nothing. Prose an engine cannot run is the same believed-check failure the
[ratio] rows had — it just fails quieter, because no table reports it as
UNMEASURED. These tests are what makes the three axioms real.

Six properties are load-bearing and each has a test here:

1. an alignment class is a CLUSTER within a declared quantum (default 0.5 px,
   R7.4's "exactly detectable" drift), and a class may never be wider than its
   quantum — single-link chaining would merge a whole sloppy panel into one
   axis and report it as calm;
2. Omega is Bonsiepe's layout-complexity measure exactly as
   `framework/research/psycho-math.md` R6.3 states it — the formula is quoted
   from that file here (the idiom of tests/test_spec_doc.py: a document whose
   number the code has drifted from is worse than no document);
3. the axis budget divides CONTROLS by DISTINCT X-AXES, and an override of the
   floor must carry a written reason — a per-panel exemption nobody had to
   justify is how a rule dies while still appearing in the config;
4. hit pitch is CENTRE-TO-CENTRE distance, never the edge gap. The two are not
   monotone in each other for targets of different sizes, and the edge-gap
   reading of SC 2.5.8 is the common wrong one;
5. fractional edges are a defect at scale 1 and legitimate at any other scale —
   a page rendered at 1.25x has root-relative CSS px that are FRACTIONS of a
   device pixel by construction, and a check that fires there teaches the
   engine to round away real geometry;
6. the three predicates run inside run_battery on default rules, so no gate
   path can leave them dormant;
7. the research file's validator (psycho-math §8) names, per axiom, the symbol
   that RUNS it — and the axioms W2 implements must carry that mark. A rule
   whose document cannot say what executes it is prose again the moment the
   symbol is renamed, and the marker is the only cheap way to tell an axiom
   with a predicate from an axiom with a paragraph.

Imports of the new symbols are attribute lookups on `densui.audit` inside each
test on purpose: a module-level `from densui.audit import axis_census` would
collapse this whole file into one collection error before the feature lands,
and a red that names no test is not evidence.
"""

import importlib
import math
import pathlib
import re
import tomllib

import pytest

from densui import audit
from densui.probe_config import rules_from
from densui.spec import SpecError, load_panel

REPO = pathlib.Path(__file__).resolve().parents[3]
PSYCHO = REPO / "framework" / "research" / "psycho-math.md"
TELEMETRY = REPO / "demos" / "telemetry" / "panel.toml"


def part(c, kind, owner, r):
    return {"c": c, "kind": kind, "owner": owner, "r": list(r)}


def target(kind, owner, cx, cy, size=12.0):
    """A hit target of `size` px centred on (cx, cy) — the pitch tests speak in
    centres, because that is what SC 2.5.8's circles are drawn on."""
    half = size / 2
    return part("p", kind, owner, (cx - half, cy - half, cx + half, cy + half))


def minimal_spec(font_path: str, *, rules=None, ratio=None) -> dict:
    """The smallest spec that validates today, so a failure below is about the
    table under test and nothing else."""
    spec = {
        "panel": {"name": "t", "width": 400, "height": 400},
        "font": {"path": font_path, "size": 16},
    }
    if rules is not None:
        spec["rules"] = rules
    if ratio is not None:
        spec["ratio"] = ratio
    return spec


def r63_omega_formula() -> str:
    """The Omega block, quoted from the research file that owns it."""
    body = PSYCHO.read_text().split("**R6.3")[1].split("**R6.4")[0]
    m = re.search(r"```\n(.*?)```", body, re.DOTALL)
    assert m, "psycho-math.md R6.3 lost its Omega block"
    return m.group(1).strip()


def psycho_validator_rows() -> dict[str, str]:
    """psycho-math §8's validator block as {axiom: one folded row of text}.

    §8 is the file's own statement of "assertions a program runs, in order", so
    it is the right place for a row to name the program. Continuation lines are
    indented and fold into the row above."""
    body = PSYCHO.read_text().split("## 8. The validator")[1]
    m = re.search(r"```\n(.*?)```", body, re.DOTALL)
    assert m, "psycho-math.md §8 lost its validator block"
    rows: dict[str, str] = {}
    axiom = None
    for line in m.group(1).splitlines():
        head = re.match(r"(A\d+)\s+(.*)", line)
        if head:
            axiom = head.group(1)
            rows[axiom] = head.group(2)
        elif axiom and line.strip():
            rows[axiom] += " " + line.strip()
    return rows


# The marker: a validator row that HAS an implementation says so, as a dotted
# densui symbol after an arrow — `A7  all box edges are integers.
# → densui.audit.check_integer_edges`. One token, greppable from either side,
# and resolvable, which is what makes the claim checkable rather than decorative.
IMPLEMENTED_BY = re.compile(r"→\s*(densui\.[\w.]+)")

# What W2 owes the file. The row text is asserted too, so a renumbering of §8
# cannot move a marker onto the wrong axiom and still pass.
W2_MARKS = {
    "A7": ({"densui.audit.check_integer_edges"}, "integer"),
    "A8": ({"densui.audit.check_hit_pitch"}, "24 px"),
    "A12": ({"densui.audit.axis_census", "densui.audit.check_axis_budget"}, "Omega"),
}


def omega_of(classes: dict[str, list[int]], n: int) -> float:
    """R6.3 applied here, independently of the implementation: per coordinate
    family, `-N * sum_i(p_i * log2(p_i))` over that family's class sizes."""
    return sum(-n * sum((c / n) * math.log2(c / n) for c in counts) for counts in classes.values())


# Four 27x27 dials on a 2x2 grid: two left classes, two right, two centre, one
# width, one height. Every number below is hand-derived from these rects.
GRID = [
    part("p", "dial", "a", (10, 10, 37, 37)),
    part("p", "dial", "b", (60, 10, 87, 37)),
    part("p", "dial", "c", (10, 60, 37, 87)),
    part("p", "dial", "d", (60, 60, 87, 87)),
]
GRID_CLASSES = {"left": [2, 2], "right": [2, 2], "cx": [2, 2], "w": [4], "h": [4]}

# The same four dials in one column: every family collapses to one class, so
# Omega is 0 — the direction R6.3 tells the engine to move in.
COLUMN = [
    part("p", "dial", o, (10, y, 37, y + 27))
    for o, y in (("a", 10), ("b", 50), ("c", 90), ("d", 130))
]

# Five dials, each on its own line, no two sharing any x coordinate: five left
# classes, five right, five centre. Clean under every OTHER battery check (no
# vertical band overlaps, so no crowding pair, no gap-law pair, no line holds
# two dials), which is what makes the run_battery test below precise.
SPRAWL = [
    part("p", "dial", "a", (10, 10, 37, 37)),
    part("p", "dial", "b", (50, 50, 77, 77)),
    part("p", "dial", "c", (90, 90, 117, 117)),
    part("p", "dial", "d", (130, 130, 157, 157)),
    part("p", "dial", "e", (170, 170, 197, 197)),
]
SPRAWL_OMEGA = 3 * 5 * math.log2(5)  # 34.83: three x families, five classes each
SPRAWL_OUT = {"containers": [{"id": "p", "r": (0, 0, 220, 220)}], "parts": SPRAWL}

# Six dials in two columns of three: two x-axes for six controls is exactly the
# A1 target of 3.0.
COLUMNS_OF_THREE = [
    part("p", "dial", f"{c}{i}", (x, y, x + 27, y + 27))
    for c, x in (("l", 10), ("r", 100))
    for i, y in enumerate((10, 60, 110))
]


def test_axis_census_counts_one_class_per_shared_coordinate():
    """The census is the vocabulary everything else in W2 speaks: how many
    distinct lines the panel draws, per coordinate family. Counts, not
    coordinates — 'controls per axis' is the A1 quantity."""
    census = audit.axis_census(GRID)

    assert set(census) >= {"n", "quantum", "counts", "x_axes", "omega"}, sorted(census)
    assert census["counts"] == {"left": 2, "right": 2, "cx": 2, "w": 1, "h": 1}, census["counts"]
    assert census["n"] == 4, census
    assert census["quantum"] == 0.5, "the clustering quantum is declared, never implicit"


def test_omega_is_the_layout_complexity_measure_psycho_math_r63_states():
    """Omega is quoted, not invented. R6.3 carries Bonsiepe's measure (adopted
    by Tullis, whose 520-display study found layout complexity one of the two
    strongest predictors of search time), and the research file is the source
    of truth for the formula — so the formula is read OUT of it here, the way
    tests/test_spec_doc.py executes the documented example rather than trusting
    that it still matches."""
    assert r63_omega_formula() == "Omega = -N * sum_i( p_i * log2(p_i) )", r63_omega_formula()

    expected = omega_of(GRID_CLASSES, 4)
    assert expected == pytest.approx(12.0), "hand-check: three families at 1 bit, N=4"
    assert audit.axis_census(GRID)["omega"] == pytest.approx(expected), "R6.3, per family, summed"

    # "Minimise Omega" is the objective; merging axes is what moves it.
    assert audit.axis_census(COLUMN)["omega"] == pytest.approx(0.0)
    assert audit.axis_census(SPRAWL)["omega"] == pytest.approx(SPRAWL_OMEGA)


def test_axis_classes_cluster_within_the_declared_quantum_and_never_chain():
    """Three left edges at 10.0 / 10.3 / 10.6. With a 0.5 px quantum that is
    TWO classes, not one: a class holds coordinates within the quantum of the
    class, so it can never be wider than the quantum. Single-link chaining
    (each value compared to its neighbour) would swallow all three, and on a
    real panel it merges an entire drifting column into one axis and reports
    the sprawl as calm. The quantum is a parameter, so the same parts split
    three ways under three tolerances."""
    near = [
        part("p", "dial", "a", (10.0, 0, 37.0, 27)),
        part("p", "dial", "b", (10.3, 40, 37.3, 67)),
        part("p", "dial", "c", (10.6, 80, 37.6, 107)),
    ]

    assert audit.axis_census(near)["counts"]["left"] == 2, "0.5px: {10.0,10.3} and {10.6}"
    assert audit.axis_census(near, quantum=0.25)["counts"]["left"] == 3, "tighter: three axes"
    assert audit.axis_census(near, quantum=1.0)["counts"]["left"] == 1, "looser: one axis"
    assert audit.axis_census(near, quantum=0.25)["quantum"] == 0.25, "the census reports its own"


def test_x_axes_counts_the_alignment_strategy_not_every_edge():
    """A label, a dial and a value stacked on ONE centreline draw ONE vertical
    line, though their left edges and right edges are all different: that is a
    centred column, the most common dense-panel unit. `x_axes` is therefore the
    SMALLEST of the x families — the fewest lines that account for every part —
    not the sum (7 here) and not the pooled set of every distinct x (also 7).
    Either of those makes the A1 budget unreachable for any real panel, which
    is how a rule gets overridden everywhere and then ignored."""
    stack = [
        part("p", "label", "a", (10, 0, 90, 12)),
        part("p", "dial", "a", (36, 20, 64, 48)),
        part("p", "value", "a", (25, 55, 75, 67)),
    ]

    census = audit.axis_census(stack)
    assert census["counts"] == {"left": 3, "right": 3, "cx": 1, "w": 3, "h": 2}, census["counts"]
    assert census["x_axes"] == 1, f"one centreline: {census}"
    assert audit.axis_census(GRID)["x_axes"] == 2, "the grid draws two columns"


def test_empty_parts_censuses_to_zero_and_the_budget_stays_silent():
    """A panel whose probe matched nothing must not divide by it. This is the
    shape a mis-typed selector produces, and a ZeroDivisionError inside a gate
    reads as a broken tool rather than as the empty measurement it is."""
    census = audit.axis_census([])

    assert census["n"] == 0 and census["x_axes"] == 0, census
    assert census["omega"] == 0.0, census
    assert audit.check_axis_budget([], audit.Rules()) == []


def test_axis_budget_failure_carries_the_counts_and_omega():
    """Five controls on five axes is a ratio of 1.0 against A1's floor of 3.0.
    The message is the whole product of the failure: whoever reads the gate
    must be able to act without re-running anything, so the control count, the
    axis count, the floor and Omega all travel with it. Omega goes out with at
    least one decimal — rounded to an integer it stops being usable as the
    objective R6.3 says to minimise."""
    fails = audit.check_axis_budget(SPRAWL, audit.Rules())

    assert len(fails) == 1, f"the budget is one panel-wide verdict: {fails}"
    msg = fails[0]
    nums = re.findall(r"-?\d+(?:\.\d+)?", msg)
    assert nums.count("5") >= 2, f"both counts (5 controls, 5 axes) belong in it: {msg}"
    assert {"3", "3.0"} & set(nums), f"the floor it failed against belongs in it: {msg}"
    assert re.search(r"34\.8", msg), f"Omega must travel with the failure: {msg}"
    assert "Ω" in msg or "omega" in msg.lower(), f"and be named as Omega: {msg}"


def test_axis_budget_is_silent_when_controls_share_their_axes():
    """The companion that makes the failure above load-bearing: six dials in
    two columns is exactly 3.0, and the floor is a floor — a panel that hits
    the target passes. Without this, a predicate that fails everything would
    satisfy every other test in this file."""
    assert audit.check_axis_budget(COLUMNS_OF_THREE, audit.Rules()) == []
    assert audit.check_axis_budget(COLUMN, audit.Rules()) == [], "four controls on one axis"


def test_only_controls_count_toward_the_budget():
    """Two dials and seven labels on a single centreline: the axis is shared,
    but the panel bought it with two controls, so the ratio is 2.0 and it
    fails. A1 says CONTROLS per axis — counting text as well would let a panel
    buy its budget with labels, which is the opposite of the rule's intent.
    Text is still censused: labels move the axis COUNT, never the numerator."""
    parts = [target("dial", "d0", 50, 20, 28), target("dial", "d1", 50, 60, 28)]
    parts += [target("label", f"t{i}", 50, 100 + 20 * i, 12) for i in range(7)]

    fails = audit.check_axis_budget(parts, audit.Rules())
    assert len(fails) == 1, f"2 controls on 1 axis is 2.0 < 3.0: {fails}"


def test_axis_budget_floor_is_a_declared_override_not_a_constant():
    """A panel that genuinely needs a lower floor declares one. The predicate
    reads it off the rules — a hard-coded 3.0 makes the override a lie the
    config tells."""
    lowered = audit.Rules(axis_budget_floor=1.0, axis_budget_reason="five isolated test points")

    assert audit.check_axis_budget(SPRAWL, lowered) == []
    assert audit.Rules().axis_budget_floor == 3.0, "DENSE-UI A1's ~3 is the default"


def test_axis_budget_override_without_a_reason_is_a_spec_error(font_path):
    """An exemption nobody had to justify is how a rule dies while still
    appearing in the config. Both consuming paths refuse it: load_panel, which
    validates a panel spec, and rules_from, which is what `densui audit` and
    `densui score` actually call — a rule enforced on only one of the two is
    enforced on neither."""
    with pytest.raises(SpecError) as exc:
        load_panel(minimal_spec(font_path, rules={"axis_budget_floor": 1.5}))
    assert any("axis_budget_reason" in e for e in exc.value.errors), exc.value.errors

    with pytest.raises(SpecError) as gate:
        rules_from({"rules": {"axis_budget_floor": 1.5}})
    assert any("axis_budget_reason" in e for e in gate.value.errors), gate.value.errors


def test_declared_rules_reach_the_predicate(font_path):
    """The other half: a justified override, and the hit-target vocabulary,
    survive both the validator and the one function every gate builds its Rules
    with. A key that validates but never reaches the predicate is a config that
    silently does nothing."""
    declared = {
        "axis_budget_floor": 1.6,
        "axis_budget_reason": "bench holds one control per column by design (contract.md)",
        "hit_kinds": ["dial", "chip"],
    }

    assert load_panel(minimal_spec(font_path, rules=declared))["rules"] == declared

    rules = rules_from({"rules": declared})
    assert rules.axis_budget_floor == 1.6
    assert rules.axis_budget_reason.startswith("bench holds"), rules.axis_budget_reason
    assert rules.hit_kinds == frozenset({"dial", "chip"}), rules.hit_kinds


def test_hit_pitch_is_centre_pitch_not_the_edge_gap():
    """WCAG 2.2 SC 2.5.8, operationalised in psycho-math R3.4: 24 px circles
    centred on each target's bounding box must not intersect, i.e. every pair
    is at least 24 px centre to centre. Two 12 px targets 20 px apart fail with
    an 8 px gap between them; the SAME two 26 px apart pass with a 14 px gap.
    An implementation that measured the edge gap against 24 would fail both,
    and one that measured it against some other floor would pass both — this
    pair is the discriminator."""
    tight = [target("dial", "a", 100, 100), target("dial", "b", 120, 100)]
    fine = [target("dial", "a", 100, 100), target("dial", "b", 126, 100)]

    fails = audit.check_hit_pitch(tight, audit.Rules())
    assert len(fails) == 1, f"20px pitch is inside the 24px circle: {fails}"
    assert "dial(a)" in fails[0] and "dial(b)" in fails[0], fails[0]
    # "20", "20.0" or "20.00", however it is spelled, and not inside "120".
    assert re.search(r"\b20(\.0+)?(?!\d)", fails[0]), f"the measured pitch belongs in: {fails[0]}"

    assert audit.check_hit_pitch(fine, audit.Rules()) == [], "26px pitch clears the circle"


def test_hit_pitch_is_the_wcag_circle_in_two_dimensions():
    """The circles are circles: 18 px right and 18 px down is 25.5 px of pitch,
    which clears 24 although NEITHER axis does. A per-axis implementation fails
    this pair, and it is the layout a diagonal control cluster produces."""
    diagonal = [target("dial", "a", 100, 100), target("dial", "b", 118, 118)]

    assert math.dist((100, 100), (118, 118)) == pytest.approx(25.46, abs=0.01)
    assert audit.check_hit_pitch(diagonal, audit.Rules()) == []
    assert audit.WCAG_TARGET_PITCH_PX == 24.0, "SC 2.5.8's number, named where it is used"


def test_hit_pitch_judges_only_the_declared_interactive_kinds():
    """A label 18 px from a dial is not a mis-click risk — nothing happens when
    you hit it. Which kinds are targets is the panel's vocabulary, declared in
    the rules; the default is the interactive set this framework ships."""
    mixed = [target("dial", "a", 100, 100), target("label", "a", 118, 100, 20)]

    assert audit.check_hit_pitch(mixed, audit.Rules()) == [], "a label is not a hit target"
    widened = audit.Rules(hit_kinds=frozenset({"dial", "label"}))
    assert len(audit.check_hit_pitch(mixed, widened)) == 1, "declared as one, it is judged as one"
    assert audit.Rules().hit_kinds == frozenset({"dial", "checkbox", "thumb"})


def test_fractional_edges_fail_at_scale_one_naming_the_part_and_the_edge():
    """A-5 / A7: sub-pixel positions shift the perceived centroid, and
    hyperacuity reads the centroid — an antialiased half pixel is SEEN as half
    a pixel (psycho-math R6.2), so it does not average away. The failure names
    which part and which edge, because 'something is fractional' is not a fix."""
    parts = [
        part("p", "dial", "a", (10.5, 20, 37.5, 47)),
        part("p", "dial", "b", (60, 20, 87, 47.25)),
        part("p", "dial", "c", (110, 20, 137, 47)),
    ]

    fails = audit.check_integer_edges(parts, 1)
    assert any("dial(a)" in f and "left" in f for f in fails), fails
    assert any("dial(b)" in f and "bottom" in f for f in fails), fails
    assert not any("dial(c)" in f for f in fails), f"an integer part is silent: {fails}"
    assert re.search(r"10\.5", " | ".join(fails)), f"the offending value travels: {fails}"


def test_fractional_edges_are_legitimate_when_the_page_is_not_at_scale_one():
    """The guard, and the reason the scale is an argument: at 1.25x a page's
    root-relative CSS px are fractions of a device pixel BY CONSTRUCTION. A
    check that fires there teaches the engine to round away real geometry, and
    every reserved box it computed from font metrics moves."""
    parts = [part("p", "dial", "a", (10.5, 20, 37.5, 47))]

    assert audit.check_integer_edges(parts, 1) != [], "scale 1: the defect is real"
    assert audit.check_integer_edges(parts, 1.25) == [], "scaled page: fractions are expected"
    assert audit.check_integer_edges(parts, 2) == []


def test_probe_rects_feed_the_integer_check_at_scale_one(tmp_path):
    """The one place a hand-built parts list cannot answer the question: real
    Chrome rects. A block at left:120.5px must be caught, and — the half that
    matters — a block at integer CSS px must stay silent through
    getBoundingClientRect's binary floats. A check that flags every measured
    box is unusable, and would be discovered on the demos, not here."""
    from densui import probe

    page = tmp_path / "page.html"
    page.write_text("""<!doctype html><meta charset="utf-8">
<div id="root" style="position:relative;width:300px;height:100px">
 <div class="plate" style="position:absolute;left:0;top:0;width:300px;height:100px">
  <div class="blk" data-addr="whole"
       style="position:absolute;left:20px;top:10px;width:50px;height:30px"></div>
  <div class="blk" data-addr="half"
       style="position:absolute;left:120.5px;top:10px;width:50px;height:30px"></div>
 </div></div>""")

    out = probe.collect(page, root="#root", containers={"plate": ".plate"}, parts={"blk": ".blk"})
    assert out["scale"] == 1, out["scale"]

    fails = audit.check_integer_edges(out["parts"], out["scale"])
    assert any("blk(half)" in f and "left" in f for f in fails), fails
    assert not any("blk(whole)" in f for f in fails), f"integer boxes measure integer: {fails}"


def test_run_battery_composes_the_axis_budget():
    """Every gate in this repository runs run_battery. A predicate that exists
    but is only reachable by calling it directly is the dormancy W1 ended for
    the ratio rows, one module over. Default rules, no opt-in.

    This probe output carries no `scale` key on purpose: the field is additive
    and older callers (tests/test_audit.py's battery case, the operator gate)
    do not set it, so its absence must read as 1 rather than KeyError."""
    fails = audit.run_battery(SPRAWL_OUT, audit.Rules())

    assert any("Ω" in f or "omega" in f.lower() for f in fails), f"axis budget dormant: {fails}"
    assert len(fails) == 1, f"this geometry violates the axis budget and nothing else: {fails}"


def test_run_battery_scale_guards_the_integer_check_and_never_judges_glyph_ink():
    """Two compositions in one geometry. Three dials on a shared left edge at
    x=10.5 fail A-5 at scale 1 and are silent at scale 2. The value's ink box
    is fractional too and must NEVER be reported: a glyph-ink rect (A-4) is
    where the glyphs ARE — it is measured, not authored, and cannot be snapped.
    Since check_integer_edges takes only (parts, scale), the text exemption
    lives at this composition seam, where the rules are known.

    (Three controls on one axis also clears the axis budget, so these failures
    are the fractional edges and nothing else.)"""
    ink = {
        "scale": 1,
        "containers": [{"id": "p", "r": (0, 0, 200, 160)}],
        "parts": [
            part("p", "dial", "a", (10.5, 20, 37.5, 47)),
            part("p", "dial", "b", (10.5, 60, 37.5, 87)),
            part("p", "dial", "c", (10.5, 100, 37.5, 127)),
            part("p", "value", "a", (10.4, 130, 60.2, 142.5)),
        ],
    }

    fails = audit.run_battery(ink, audit.Rules())
    assert fails and all("dial(" in f for f in fails), f"glyph ink is not a snappable edge: {fails}"
    assert any("dial(a)" in f and "left" in f for f in fails), fails

    assert audit.run_battery({**ink, "scale": 2}, audit.Rules()) == [], (
        "scaled: no edge is a defect"
    )


def test_span_row_is_the_difference_of_ink_centres_second_minus_first():
    """The row form W1 left open, decided in .dev/deep-craft.md: telemetry's
    `row = [72, 4]` claims a row PITCH, which no absolute box can express (the
    row's own box overlaps everything inside it, and text is ink, so the line
    boxes are invisible). It is expressible as a DIFFERENCE of ink centres, and
    a difference is font-independent where the two absolute positions are not.

    Direction is part of the contract: second minus first, so a reversed span
    reports a negative number instead of quietly agreeing via abs()."""
    out = {
        "parts": [
            part("p", "label", "a", (10, 14, 60, 26)),  # cy 20
            part("p", "value", "a", (10, 64, 60, 76)),  # cy 70
        ]
    }
    row = {"name": "row", "span": ["label.cy", "value.cy"], "want": 50, "tol": 4}

    assert audit.check_ratios(out, [row]) == []

    reversed_row = {**row, "span": ["value.cy", "label.cy"]}
    fails = audit.check_ratios(out, [reversed_row])
    assert len(fails) == 1 and "-50" in fails[0], fails

    wrong = {**row, "want": 72}
    fails = audit.check_ratios(out, [wrong])
    assert len(fails) == 1, fails
    assert "row" in fails[0] and "50" in fails[0] and "72" in fails[0], fails[0]


def test_span_row_reduces_by_median_and_does_not_judge_absolute_spread():
    """Telemetry's labels live in three knob rows at three different heights,
    so `label.cy` spreads by hundreds of px — and that spread is not a defect,
    it is the panel. A span row claims the DIFFERENCE and only the difference,
    so the per-token spread rule that guards `measure` rows must not fire here.
    The reduction is still the MEDIAN: the drifted third value below would drag
    a mean to a difference of 117 and blame the wrong thing."""
    out = {
        "parts": [
            part("p", "label", "a", (10, 14, 60, 26)),  # cy 20
            part("p", "label", "b", (10, 114, 60, 126)),  # cy 120
            part("p", "label", "c", (10, 214, 60, 226)),  # cy 220
            part("p", "value", "a", (10, 64, 60, 76)),  # cy 70
            part("p", "value", "b", (10, 164, 60, 176)),  # cy 170
            part("p", "value", "c", (10, 464, 60, 476)),  # cy 470 — drifted
        ]
    }
    row = {"name": "row", "span": ["label.cy", "value.cy"], "want": 50, "tol": 4}

    assert audit.check_ratios(out, [row]) == [], "medians 120 and 170 differ by exactly 50"


def test_span_rows_validate_and_malformed_ones_are_named(font_path):
    """Typed does not mean rubber-stamped. A one-sided span, an illegal
    dimension and a row carrying two forms at once are three different
    mistakes, each named at its full path."""
    good = {"row": {"span": ["label.cy", "value.cy"], "want": 50, "tol": 4}}
    out = load_panel(minimal_spec(font_path, ratio=good))
    assert out["ratio"]["row"]["span"] == ["label.cy", "value.cy"]

    bad = {
        "one_sided": {"span": ["label.cy"], "want": 50, "tol": 4},
        "bad_dim": {"span": ["label.cy", "value.q"], "want": 50, "tol": 4},
        "two_forms": {"span": ["label.cy", "value.cy"], "measure": "dial.h", "want": 50, "tol": 4},
    }
    with pytest.raises(SpecError) as exc:
        load_panel(minimal_spec(font_path, ratio=bad))
    errs = exc.value.errors
    for name in ("ratio.one_sided", "ratio.bad_dim", "ratio.two_forms"):
        assert any(name in e for e in errs), f"{name} unnamed in {errs}"


def test_telemetry_carries_its_row_pitch_again(font_path):
    """The row this workstream owes the file. `row = [72, 4]` was dropped in W1
    with a comment saying no probe expression existed for it; the span form is
    that expression, and the number is the one the comment derives — value.cy -
    label.cy = 50.00 measured (20 + 2 + 28 by construction), tol 4 as declared
    since the demo was written. A claim parked in a comment is a claim nothing
    executes."""
    text = TELEMETRY.read_text()
    data = tomllib.loads(text)

    row = data.get("ratio", {}).get("row")
    assert row, "demos/telemetry/panel.toml still owes its row-pitch claim"
    assert row["span"] == ["label.cy", "value.cy"], row
    assert row["want"] == 50 and row["tol"] == 4, row
    assert "NOT MIGRATED" not in text, "the comment stands down when the row runs"

    data["font"]["path"] = font_path
    assert load_panel(data)["ratio"]["row"], "the restored row must validate"


def test_the_three_axis_classes_are_measured_in_the_registry():
    """W2's point in the one table that reports coverage: three classes stop
    reading UNMEASURED. tests/test_scorecard.py then demands corpus/axis-sprawl,
    corpus/hit-pitch and corpus/fractional-edges automatically — its exemption
    list is derived from the registry, and W1 proved by execution that flipping
    a row alone turns that test red."""
    from densui.score import REGISTRY, UNMEASURED

    expected = {
        "axis-sprawl": "densui.audit.check_axis_budget",
        "hit-pitch": "densui.audit.check_hit_pitch",
        "fractional-edges": "densui.audit.check_integer_edges",
    }
    for cls, symbol in expected.items():
        row = REGISTRY[cls]
        assert row.predicate is not UNMEASURED, f"{cls} must be measured after W2"
        assert row.predicate == symbol, f"{cls} -> {row.predicate}"


def test_corpus_seeds_exist_for_the_three_new_classes():
    """A measured class with no seed is a check nobody has proven can fail.
    `densui score` reports seed_caught per class, and that field means nothing
    without a page holding exactly one deliberate defect of that class."""
    missing = []
    for cls in ("axis-sprawl", "hit-pitch", "fractional-edges"):
        d = REPO / "corpus" / cls
        absent = [f for f in ("page.html", "panel.toml", "TELL.md") if not (d / f).exists()]
        if absent:
            missing.append(f"corpus/{cls}: {absent}")
            continue
        cfg = tomllib.loads((d / "panel.toml").read_text())
        if "root" not in cfg.get("probe", {}):
            missing.append(f"corpus/{cls}/panel.toml: no [probe] root to measure from")
    assert not missing, f"measured classes without a usable corpus seed: {missing}"


def test_marked_research_rows_name_a_live_consumer():
    """Forward sweep: every axiom that CLAIMS an implementation must name one
    that resolves. This is tests/test_scorecard.py's dangling-symbol check
    pointed at the research file instead of the registry — a document that
    names `densui.audit.check_axes` is a believed check in prose form, and it
    survives a rename silently because nothing imports a markdown file.

    The sweep also refuses to run over nothing: zero markers is not a clean
    sweep, it is the '0 tests ran' result wearing a green shirt."""
    rows = psycho_validator_rows()
    marked = {a: IMPLEMENTED_BY.findall(t) for a, t in rows.items()}
    marked = {a: symbols for a, symbols in marked.items() if symbols}

    assert marked, (
        f"psycho-math §8 marks no row with the symbol that runs it — "
        f"{len(rows)} axioms, none traceable to code"
    )

    dangling = []
    for axiom, symbols in sorted(marked.items()):
        for dotted in symbols:
            module_name, _, symbol = dotted.rpartition(".")
            try:
                obj = getattr(importlib.import_module(module_name), symbol)
            except (ImportError, AttributeError) as exc:
                dangling.append(f"{axiom} -> {dotted} ({exc})")
                continue
            if not callable(obj):
                dangling.append(f"{axiom} -> {dotted} (not callable)")
    assert not dangling, f"psycho-math §8 rows naming symbols that do not exist: {dangling}"


def test_the_axioms_w2_implements_are_marked_in_the_research_file():
    """Reverse guard, and the half that cannot be satisfied by doing nothing:
    A7 (integer edges), A8 (the 24 px circle) and A12 (Omega over coordinate
    classes) stop being paragraphs in this workstream, so they must say which
    symbol they became. The row text is checked with the marker — a §8
    renumbering must not be able to move a mark onto a different axiom."""
    rows = psycho_validator_rows()

    missing = []
    for axiom, (expected, phrase) in W2_MARKS.items():
        assert axiom in rows, f"psycho-math §8 lost {axiom} — the sweep is measuring nothing"
        assert phrase in rows[axiom], f"{axiom} is not the row this mark belongs on: {rows[axiom]}"
        found = set(IMPLEMENTED_BY.findall(rows[axiom]))
        if not expected <= found:
            missing.append(f"{axiom}: unmarked {sorted(expected - found)}, has {sorted(found)}")
    assert not missing, f"W2 axioms whose research row does not name its predicate: {missing}"
