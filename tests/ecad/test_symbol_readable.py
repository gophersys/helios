"""4-side "readable" symbol geometry (layout-engine style)."""

from src.ecad import Side, SymbolModel
from src.pipeline.chip_library import esp32_s3_wroom_1
from src.pipeline.ecad_bridge import chipdef_to_component
from tests.ecad.test_model import Cap, LDO, TinyMCU


def _sides(model, unit_id=1):
    return {p.pad: p.side for p in model.unit(unit_id).pins}


def test_ldo_side_assignment():
    m = SymbolModel.from_component(LDO(), style="readable")
    sides = _sides(m)
    assert sides["1"] is Side.TOP          # VIN power_in
    assert sides["2"] is Side.BOTTOM       # GND role ground
    assert sides["3"] is Side.LEFT         # EN input
    assert sides["5"] is Side.RIGHT        # VOUT power_out


def test_passive_left_right():
    m = SymbolModel.from_component(Cap(), style="readable")
    sides = _sides(m)
    assert sides["1"] is Side.LEFT and sides["2"] is Side.RIGHT


def test_hub_bidirectional_faces_right():
    class Hub(TinyMCU):
        orientation_hint = "hub"

    hub = SymbolModel.from_component(Hub(), style="readable")
    periph = SymbolModel.from_component(TinyMCU(), style="readable")
    # IO pins (bidirectional) are in unit 2
    assert _sides(hub, 2)["2"] is Side.RIGHT
    assert _sides(periph, 2)["2"] is Side.LEFT


def test_geometry_on_grid_and_sized():
    comp = chipdef_to_component(esp32_s3_wroom_1())
    m = SymbolModel.from_component(comp, style="readable")
    for u in m.units:
        assert u.width >= 15.24
        assert round(u.width / 1.27, 6) % 1 == 0
        for p in u.pins:
            assert round(p.x * 100) % 127 == 0 or round(abs(p.x) * 100) % 127 == 0
            assert round(p.y * 100) % 127 == 0 or round(abs(p.y) * 100) % 127 == 0


def test_node_ports_schematic_space():
    m = SymbolModel.from_component(Cap(), style="readable")
    w, h = m.node_size(1)
    ports = m.node_ports(1)
    by_pad = {p[0]: p for p in ports}
    padl, padr = by_pad["1"], by_pad["2"]
    # left port on the left bbox edge, right port on the right edge
    assert padl[5][0] == 0.0
    assert padr[5][0] == w
    # dy inside the bbox, +Y down
    assert 0 <= padl[5][1] <= h
    # sides + deterministic index
    assert padl[3] is Side.LEFT and padl[4] == 0
    assert padr[3] is Side.RIGHT and padr[4] == 0


def test_readable_kicad_sym_still_valid():
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    cli = shutil.which("kicad-cli")
    if cli is None:
        import pytest
        pytest.skip("kicad-cli not available")
    comp = chipdef_to_component(esp32_s3_wroom_1())
    lib = SymbolModel.from_component(comp, style="readable").to_kicad_sym()
    out = Path(tempfile.mkdtemp())
    sym = out / "readable.kicad_sym"
    lib.to_file(str(sym))
    svg_dir = out / "svg"
    r = subprocess.run([cli, "sym", "export", "svg", str(sym), "-o", str(svg_dir)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert list(svg_dir.glob("*.svg"))
