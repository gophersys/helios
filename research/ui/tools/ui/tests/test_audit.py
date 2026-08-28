from ui.audit import (
    Rules,
    check_breathing,
    check_containment,
    check_cross_alignment,
    check_crowding,
    check_gap_law,
    check_level,
    check_overlaps,
    knob_value_graze,
    run_battery,
)


def part(c, kind, owner, r):
    return {"c": c, "kind": kind, "owner": owner, "r": list(r)}


RULES = Rules(legal_overlap=knob_value_graze())


def test_overlap_fails_and_names_both_parts():
    parts = [part("p", "dial", "a", (0, 0, 27, 27)), part("p", "value", "b", (10, 10, 60, 24))]
    fails = check_overlaps(parts, RULES)
    assert len(fails) == 1 and "dial(a)" in fails[0] and "value(b)" in fails[0]


def test_own_value_graze_is_legal_but_deep_overlap_is_not():
    dial = part("p", "dial", "a", (0, 0, 27, 27))
    graze = part("p", "value", "a", (22, 25.5, 60, 40))  # <=2.5px, right of centre
    deep = part("p", "value", "a", (2, 10, 60, 24))
    assert check_overlaps([dial, graze], RULES) == []
    assert len(check_overlaps([dial, deep], RULES)) == 1


def test_crowding_floor():
    parts = [part("p", "dial", "a", (0, 0, 27, 27)), part("p", "led", "b", (28, 5, 40, 17))]
    assert "gap 1.0px" in check_crowding(parts, RULES)[0]
    parts[1]["r"][0] = 30
    assert check_crowding(parts, RULES) == []


def test_gap_law_similarity_and_interposition_gating():
    dials = [
        part("p", "dial", x, (i, 0, i + 27, 27)) for x, i in (("a", 0), ("b", 77), ("c", 214))
    ]  # gaps 50, 110: ratio 2.2 OK
    assert check_gap_law(dials, RULES) == []
    dials[2]["r"] = [164, 0, 191, 27]  # gaps 50, 60: forbidden zone
    assert len(check_gap_law(dials, RULES)) == 1
    blocker = part("p", "checkbox", "x", (120, 0, 135, 27))  # interposed control
    assert check_gap_law(dials + [blocker], RULES) == []


def test_containment_with_declared_spill():
    box = [{"id": "grid", "r": (0, 0, 100, 100)}]
    lab = part("grid", "clabel", "t", (90, 10, 108, 22))
    assert len(check_containment([lab], box, RULES)) == 1
    spilly = Rules(spill_slack={("grid", "clabel"): 12.0})
    assert check_containment([lab], box, spilly) == []


def test_breathing_floor_bites():
    box = [{"id": "p", "r": (0, 0, 100, 67)}]
    v = part("p", "value", "a", (10, 50, 60, 66))
    assert "presses the bottom edge" in check_breathing([v], box, RULES)[0]
    v["r"][3] = 63
    assert check_breathing([v], box, RULES) == []


def test_level_and_cross_alignment():
    a = part("p1", "dial", "x", (0, 10, 27, 37))
    b = part("p1", "dial", "y", (50, 13, 77, 40))
    assert "not level" in check_level([a, b])[0]
    rows = [
        part("p1", "dial", "osc.a.coarse", (10, 0, 37, 27)),
        part("p2", "dial", "osc.b.coarse", (13, 0, 40, 27)),
    ]
    key = lambda p: p["owner"].split(".")[-1] if p["kind"] == "dial" else None
    assert "not aligned" in check_cross_alignment(rows, key)[0]


def test_run_battery_composes_and_passes_clean_input():
    out = {
        "containers": [{"id": "p", "r": (0, 0, 200, 67)}],
        "parts": [
            part("p", "dial", "a", (10, 20, 37, 47)),
            part("p", "value", "a", (34, 50, 80, 62)),
        ],
    }
    assert run_battery(out, RULES) == []


def test_level_clusters_lines_before_judging():
    top = [part("p", "dial", "a", (10, 10, 37, 37)), part("p", "dial", "b", (60, 10, 87, 37))]
    low = part("p", "dial", "c", (10, 200, 37, 227))
    assert check_level(top + [low]) == []  # two lines, each level
    top[1]["r"] = [60, 13, 87, 40]
    assert "within a line" in check_level(top + [low])[0]
