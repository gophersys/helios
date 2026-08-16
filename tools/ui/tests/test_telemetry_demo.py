"""The blind demo's spec must validate and solve on every gate run — its
panel.toml is repository truth, and this test is what keeps it honest."""

import pathlib
import tomllib

from ui.solve import solve
from ui.spec import load_panel

PANEL = pathlib.Path(__file__).resolve().parents[3] / "demos" / "telemetry" / "panel.toml"


def _load(font_path):
    data = tomllib.loads(PANEL.read_text())
    data["font"]["path"] = font_path
    return data


def test_panel_validates(font_path):
    assert load_panel(_load(font_path))["panel"]["name"] == "telemetry"


def test_rails_solve_with_rhythm_and_tracks_decompose(font_path):
    data = _load(font_path)
    out = solve({"font": data["font"], **data["solve"]})
    rails = out["knob_rows"]["rails"]
    gap1 = rails["rail-1v8"]["center"] - rails["rail-3v3"]["center"]
    gap2 = rails["rail-io"]["center"] - rails["rail-1v8"]["center"]
    # the gap LAW (equal within max(6%, 1px)): a font-driven nudge may move a
    # rail, G-1 tolerates it, and a stricter test would outlaw the law itself
    assert abs(gap1 - gap2) <= max(0.06 * max(gap1, gap2), 1)
    t = data["tracks"]
    content = data["panel"]["width"] - 2 * t["margin"] - (len(t["columns"]) - 1) * t["gap"]
    assert content == sum(t["columns"])  # the modulo rule, executed
    for c in t["columns"]:
        assert c % 4 == 0
