"""The README's gate-failure example must stay a real refusal.

README.md quotes a verbatim `densui solve` refusal for docs/examples/
crowded.toml. If the solver ever starts absorbing that spec silently, the
README becomes fiction — this pins the refusal's shape (both part names,
the crowding clause, the bound) without pinning face-dependent ink decimals.
"""

import pathlib
import tomllib

import pytest

from densui.solve import SolveError, solve

EXAMPLE = pathlib.Path(__file__).resolve().parents[3] / "docs" / "examples" / "crowded.toml"


def _load(font_path: str) -> dict:
    spec = tomllib.loads(EXAMPLE.read_text())
    spec["font"]["path"] = font_path
    return spec


def test_readme_refusal_fires(font_path):
    with pytest.raises(SolveError) as exc:
        solve(_load(font_path))
    msg = str(exc.value)
    assert "row/coarse" in msg
    assert "crowds next dial" in msg
    assert "anchor_tolerance 2" in msg


def test_refusal_is_load_bearing(font_path):
    """The same spec with a generous bound must solve — proving the refusal
    comes from the stated tolerance, not from the spec being malformed."""
    spec = _load(font_path)
    spec["knob_rows"]["row"]["anchor_tolerance"] = 200
    out = solve(spec)
    assert set(out["knob_rows"]["row"]) == {"coarse", "fine"}
