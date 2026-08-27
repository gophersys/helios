import pathlib

import pytest

from ui import Face

CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # ubuntu CI
    "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]


def _face() -> Face:
    for p in CANDIDATES:
        if pathlib.Path(p).exists():
            return Face(p)
    raise AssertionError(
        "no test font found — a check that cannot run is a failure; "
        f"add this platform's font path to CANDIDATES: {CANDIDATES}"
    )


def test_advance_scales_linearly():
    f = _face()
    one = f.adv("Hamburgefonstiv", 16)
    two = f.adv("Hamburgefonstiv", 32)
    assert abs(two - 2 * one) < 1e-6


def test_missing_glyph_raises():
    f = _face()
    with pytest.raises(KeyError):
        f.adv("\ue003", 16)


def test_cap_height_sane():
    f = _face()
    assert 0.55 * 16 <= f.cap(16) <= 0.85 * 16


def test_metrics_table_sane_for_every_available_face():
    """The per-face cap table (typo-math appendix) regenerated as a gate:
    every face available on this machine must sit inside the R1 sanity bands,
    so the appendix cannot go stale — the fleet validates DejaVu, a Mac
    validates Arial/Ableton, and a violation names the face."""
    rows = {}
    for cand in CANDIDATES + [
        "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Fonts/AbletonSansSmall-Regular.ttf",
    ]:
        if pathlib.Path(cand).exists():
            m = Face(cand).metrics(16)
            rows[pathlib.Path(cand).name] = m
            assert 0.60 <= m["cap_em"] <= 0.78, (cand, m)
            if m["xh_em"]:
                assert 0.40 <= m["xh_em"] <= 0.60, (cand, m)
            assert abs(m["centring_dy_px"]) <= 2.0, (cand, m)
    assert rows, "no faces available — the table cannot regenerate"
