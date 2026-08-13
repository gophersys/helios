import json

import pytest

from densui.cli import main


def test_solve_cli_roundtrip(font_path, tmp_path, capsys):
    spec = tmp_path / "s.toml"
    spec.write_text(f"""
[font]
path = "{font_path}"
size = 16
[[knob_rows.row.units]]
name = "a"
center = 95
label = "Alpha"
widest = "100 %"
[[knob_rows.row.units]]
name = "b"
center = 197
label = "Beta"
widest = "100 %"
[[knob_rows.row.units]]
name = "c"
center = 292
label = "Gamma"
widest = "-12.3 dB"
[knob_rows.row]
plate_width = 376
dial_floor = 40
label_floor = 3
""")
    assert main(["solve", str(spec)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["knob_rows"]["row"]["b"]["center"] in (193, 194)


def test_solve_cli_fails_loudly(tmp_path, capsys):
    spec = tmp_path / "bad.toml"
    spec.write_text("[font]\nsize = 16\n")
    assert main(["solve", str(spec)]) == 2
    assert "solve failed" in capsys.readouterr().err


def test_audit_cli_end_to_end(tmp_path, capsys):
    pytest.importorskip("PIL")
    page = tmp_path / "p.html"
    page.write_text("""<!doctype html><meta charset="utf-8">
<div id="root" style="position:relative;width:300px;height:100px">
 <div class="plate" style="position:absolute;left:0;top:0;width:300px;height:100px">
  <div class="a" data-addr="one" style="position:absolute;left:10px;top:10px;width:50px;height:30px"></div>
  <div class="a" data-addr="two" style="position:absolute;left:40px;top:20px;width:50px;height:30px"></div>
 </div></div>""")
    cfg = tmp_path / "cfg.toml"
    cfg.write_text("""
[probe]
root = "#root"
[probe.containers]
plate = ".plate"
[probe.parts]
blk = ".a"
""")
    assert main(["audit", str(page), "--config", str(cfg)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert any("overlaps" in f for f in out["failures"])


def test_compare_cli(tmp_path, capsys):
    pytest.importorskip("PIL")
    from PIL import Image
    for name in ("r.png", "b.png"):
        Image.new("RGB", (40, 30), "#9b9b9b").save(tmp_path / name)
    rc = main(["compare", str(tmp_path / "r.png"), str(tmp_path / "b.png"),
               "--region", "q=0,0,20,20", "--out-dir", str(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert (tmp_path / "cmp_q.png").exists() and "q" in out
