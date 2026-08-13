import pytest

from densui import probe

FIXTURE = """<!doctype html><meta charset="utf-8">
<div id="root" style="position:relative;width:400px;height:200px;background:#eee">
  <div class="box" style="position:absolute;left:10px;top:10px;width:380px;height:180px">
    <div class="blk" data-addr="a.b" style="position:absolute;left:20px;top:20px;width:50px;height:30px;background:#888"></div>
    <span class="txt" style="position:absolute;left:100px;top:40px;font:20px monospace">HIII</span>
  </div>
</div>"""


@pytest.fixture()
def page(tmp_path):
    p = tmp_path / "fixture.html"
    p.write_text(FIXTURE)
    return p


def _collect(page):
    return probe.collect(
        page,
        root="#root",
        containers={"box": ".box"},
        parts={"blk": ".blk", "txt": ".txt"},
        text_kinds={"txt"},
    )


def test_rects_are_root_relative_and_exact(page):
    out = _collect(page)
    blk = next(p for p in out["parts"] if p["kind"] == "blk")
    x0, y0, x1, y1 = blk["r"]
    assert abs(x0 - 30) < 1 and abs(y0 - 30) < 1
    assert abs(x1 - 80) < 1 and abs(y1 - 60) < 1
    assert blk["owner"] == "a.b"


def test_text_measured_as_ink_not_embox(page):
    out = _collect(page)
    txt = next(p for p in out["parts"] if p["kind"] == "txt")
    x0, y0, x1, y1 = txt["r"]
    # 'HIII' at 20px: cap-height ink is far shorter than the 20px+ em box,
    # and has no descender — the ink box proves we did not measure the em box.
    assert 8 <= (y1 - y0) <= 17
    assert x1 - x0 > 20


def test_missing_root_fails_loudly(page):
    with pytest.raises(probe.ProbeError):
        probe.collect(page, root="#nope", containers={}, parts={})


def test_missing_page_fails_loudly(tmp_path):
    with pytest.raises(probe.ProbeError):
        probe.collect(tmp_path / "absent.html", root="#root", containers={}, parts={})
