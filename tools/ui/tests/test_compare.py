import pytest

pytest.importorskip("PIL")
from PIL import Image

from ui import compare


@pytest.fixture()
def pair():
    ref = Image.new("RGB", (60, 40), "#9b9b9b")
    built = Image.new("RGB", (60, 40), "#9b9b9b")
    ref.load()[10, 10] = (0, 0, 0)  # ref-only mark
    built.load()[20, 20] = (255, 255, 255)  # built-only mark
    return ref, built


def test_side_by_side_layout_and_content(pair, tmp_path):
    ref, built = pair
    out = compare.side_by_side(ref, built, {"r": (0, 0, 30, 30)}, tmp_path, scale=2)
    img = Image.open(out["r"])
    assert img.size == (60, 60 * 2 + 8)
    assert img.load()[20, 20][:3] == (0, 0, 0)  # ref mark in top half
    assert img.load()[40, 60 + 8 + 40][:3] == (255, 255, 255)  # built mark below
    assert img.load()[5, 61][:3] == compare.DIVIDER


def test_find_color_row_exact_and_absent(pair):
    ref, _ = pair
    assert compare.find_color_row(ref, 10, "#000000") == 10
    assert compare.find_color_row(ref, 11, "#123456") is None
