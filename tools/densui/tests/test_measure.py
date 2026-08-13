import pytest

pytest.importorskip("PIL")
from PIL import Image

from densui import measure


@pytest.fixture()
def img():
    im = Image.new("RGB", (100, 60), "#9b9b9b")
    px = im.load()
    for x in range(20, 40):  # dark bar on row 10, x 20..39
        px[x, 10] = (30, 30, 30)
    for y in range(30, 50):  # dark plate band on column 5, y 30..49
        for x in range(100):
            px[x, y] = (123, 123, 123)
    px[70, 5] = (121, 205, 250)  # one sky pixel
    return im


def test_sample_exact(img):
    assert measure.sample(img, 70, 5) == "#79cdfa"
    assert measure.sample(img, 0, 0) == "#9b9b9b"


def test_dark_runs_finds_the_bar_and_nothing_else(img):
    assert measure.dark_runs(img, y=10, threshold=96) == [(20, 39)]
    assert measure.dark_runs(img, y=11, threshold=96) == []


def test_level_bands_reads_the_plate(img):
    bands = measure.level_bands(img, x=5)
    plate = [b for b in bands if b[0] == 30]
    assert plate and plate[0][1] == 49 and plate[0][2] == 112  # 123 -> level 112


def test_region_stats_names_extremes(img):
    st = measure.region_stats(img, (0, 0, 100, 30))
    assert st["darkest"] == "#1e1e1e" and st["darkest_at"][1] == 10
    assert st["lightest"] == "#79cdfa"
    assert st["top"][0][0] == "#9b9b9b"


def test_zoom_writes_scaled_grid(img, tmp_path):
    out = tmp_path / "z.png"
    measure.zoom(img, (0, 0, 50, 30), out, scale=4, grid_step=10)
    z = Image.open(out)
    assert z.size == (200, 120)
    assert z.load()[40, 60][0] == 255  # gridline pixel is red
