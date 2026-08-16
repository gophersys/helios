import pathlib

import pytest

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]
# A SECOND face, for the tests that need two faces to tell apart (font
# identity: a page rendered in one while its panel declares the other). The
# CI image ships fonts-dejavu-core, which carries the Mono face beside the
# Sans one; a Mac carries Courier New beside Arial.
OTHER_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
]


def _first_present(candidates: list[str], what: str) -> str:
    for p in candidates:
        if pathlib.Path(p).exists():
            return p
    raise AssertionError(
        f"no {what} found — a check that cannot run is a failure; "
        f"add this platform's path: {candidates}"
    )


@pytest.fixture(scope="session")
def font_path() -> str:
    return _first_present(FONT_CANDIDATES, "test font")


@pytest.fixture(scope="session")
def other_font_path(font_path) -> str:
    """A face that is NOT `font_path`, so a substitution can be staged."""
    other = _first_present(OTHER_FONT_CANDIDATES, "second test font")
    assert other != font_path, f"the second test font must differ from {font_path}"
    return other
