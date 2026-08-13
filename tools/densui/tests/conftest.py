import pathlib

import pytest

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]


@pytest.fixture(scope="session")
def font_path() -> str:
    for p in FONT_CANDIDATES:
        if pathlib.Path(p).exists():
            return p
    raise AssertionError(
        "no test font found — a check that cannot run is a failure; "
        f"add this platform's path: {FONT_CANDIDATES}")
