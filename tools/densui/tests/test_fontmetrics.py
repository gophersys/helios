import pathlib

import pytest

from densui import Face

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
