import pytest

from ui.drive import DriveError, run_scenario

FIXTURE = """<!doctype html><meta charset="utf-8">
<div id="pad" style="position:absolute;left:100px;top:100px;width:200px;height:200px;background:#888"
     data-count="0" data-drag="0" data-wheel="0"></div>
<script>
const pad = document.getElementById('pad');
let downY = null;
pad.addEventListener('mousedown', e => { downY = e.clientY;
  pad.dataset.count = String(Number(pad.dataset.count) + 1); });
window.addEventListener('mousemove', e => { if (downY !== null)
  pad.dataset.drag = String(e.clientY - downY); });
window.addEventListener('mouseup', () => { downY = null; });
pad.addEventListener('wheel', e => { pad.dataset.wheel = String(e.deltaY); });
</script>"""


@pytest.fixture()
def page(tmp_path):
    p = tmp_path / "fixture.html"
    p.write_text(FIXTURE)
    return p


def test_click_drag_wheel_and_eval_roundtrip(page):
    out = run_scenario(
        page,
        [
            {"op": "click", "x": 150, "y": 150},
            {"op": "drag", "x": 150, "y": 150, "dx": 0, "dy": 60},
            {"op": "wheel", "x": 150, "y": 150, "deltaY": -120},
            {"op": "eval", "js": "JSON.stringify(document.getElementById('pad').dataset)"},
        ],
    )
    import json

    state = json.loads(out[3])
    assert state["count"] == "2"  # click + drag both pressed
    assert state["drag"] == "60"  # the drag really travelled 60px
    assert state["wheel"] == "-120"


def test_eval_exception_fails_loudly(page):
    with pytest.raises(DriveError, match="scenario failed"):
        run_scenario(page, [{"op": "eval", "js": "nope.nope"}])


def test_missing_page_fails_loudly(tmp_path):
    with pytest.raises(DriveError, match="page not found"):
        run_scenario(tmp_path / "absent.html", [])
