"""The documentation's canonical example must actually run — an example that
drifts from the tools is worse than no example."""

import pathlib
import re
import tomllib

from ui.solve import solve

DOC = pathlib.Path(__file__).resolve().parents[3] / "docs" / "spec.md"


def _example() -> str:
    m = re.search(r"```toml\n(.*?)```", DOC.read_text(), re.DOTALL)
    assert m, "docs/spec.md lost its canonical example"
    return m.group(1)


def test_example_parses_and_names_every_documented_section():
    data = tomllib.loads(_example())
    for section in ("panel", "font", "census", "tracks", "solve", "probe", "rules", "ratio"):
        assert section in data, f"documented section [{section}] missing from example"


def test_example_solves_with_a_real_font(font_path):
    data = tomllib.loads(_example().replace("FONT", font_path))
    out = solve({"font": data["font"], **data["solve"]})
    row = out["knob_rows"]["main"]
    assert set(row) == {"alpha", "beta", "gamma"}
    gap1 = row["beta"]["center"] - row["alpha"]["center"]
    gap2 = row["gamma"]["center"] - row["beta"]["center"]
    assert abs(gap1 - gap2) <= 1  # rhythm equalisation applied
