import pytest

from densui.solve import SolveError, solve


def spec(font_path, **knob_row):
    row = {
        "plate_width": 376,
        "dial": 28,
        "tuck": 10,
        "dial_floor": 40,
        "label_floor": 3,
        "units": [
            {"name": "a", "center": 95, "label": "Alpha", "widest": "100 %"},
            {"name": "b", "center": 197, "label": "Beta", "widest": "100 %"},
            {"name": "c", "center": 292, "label": "Gamma", "widest": "-12.3 dB"},
        ],
    }
    row.update(knob_row)
    return {"font": {"path": font_path, "size": 16}, "knob_rows": {"row": row}}


def test_rhythm_equalized_by_construction(font_path):
    out = solve(spec(font_path))
    c = out["knob_rows"]["row"]
    gap1 = c["b"]["center"] - c["a"]["center"]
    gap2 = c["c"]["center"] - c["b"]["center"]
    assert abs(gap1 - gap2) <= 1
    assert any("rhythm" in x for x in out["corrections"])


def test_dial_floor_violation_names_unit(font_path):
    with pytest.raises(SolveError, match="row/a: dial left"):
        solve(spec(font_path, dial_floor=200))


def test_value_clearance_violation(font_path):
    s = spec(font_path)
    s["knob_rows"]["row"]["units"][0]["widest"] = "-1000000.00 dB"
    with pytest.raises(SolveError, match="widest value ink"):
        solve(s)


def test_insertion_order_does_not_change_output(font_path):
    s1 = spec(font_path)
    s2 = {"knob_rows": s1["knob_rows"], "font": s1["font"]}  # reordered keys
    assert solve(s1) == solve(s2)


def test_flow_row_margins_and_trailing_gap(font_path):
    s = {
        "font": {"path": font_path, "size": 16},
        "flow_rows": {
            "osc": {
                "pad": 10,
                "right_edge": 351,
                "units": [
                    {"name": "k1", "center": 25, "box": 27, "labels": ["Coarse"]},
                    {
                        "name": "k2",
                        "center": 125,
                        "box": 27,
                        "labels": ["Fine"],
                        "widest_value": "-inf dB",
                        "value_left_offset": 24,
                    },
                ],
                "trailing": {"name": "badge", "center": 333, "width": 18},
            }
        },
    }
    out = solve(s)["flow_rows"]["osc"]
    assert out["k1"]["margin_left"] >= 0 and out["k2"]["left"] == 125 - 13
    assert out["badge"]["left"] == 324 and out["badge"]["margin_right"] == 9


def test_missing_font_fails_loudly():
    with pytest.raises(SolveError, match="spec.font"):
        solve({"knob_rows": {}})


def test_wide_label_overflow_is_a_reported_correction(font_path):
    s = {
        "font": {"path": font_path, "size": 16},
        "flow_rows": {
            "r": {
                "pad": 10,
                "units": [
                    {
                        "name": "u1",
                        "center": 30,
                        "box": 15,
                        "labels": ["An Extremely Wide Label Indeed"],
                    },
                    {"name": "u2", "center": 80, "box": 27, "labels": ["B"]},
                ],
            }
        },
    }
    out = solve(s)
    r = out["flow_rows"]["r"]
    assert r["u1"]["left"] + r["u1"]["width"] <= r["u2"]["left"]
    assert any("label overflows" in c for c in out["corrections"])


def test_control_box_overflow_still_refuses(font_path):
    s = {
        "font": {"path": font_path, "size": 16},
        "flow_rows": {
            "r": {
                "pad": 0,
                "units": [
                    {"name": "u1", "center": 30, "box": 60},
                    {"name": "u2", "center": 60, "box": 27},
                ],
            }
        },
    }
    with pytest.raises(SolveError, match="control box"):
        solve(s)
