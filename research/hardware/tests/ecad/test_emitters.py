"""Emission-substrate proof: deterministic UUIDs, junctions, no-connects,
generated power symbols — a hand-placed micro-sheet must load in kicad-cli
with ERC 0 BEFORE any layout algorithm exists (plan gate C.3)."""

import shutil
from pathlib import Path

import pytest

from src.pipeline.schematic_gen import (
    ComponentPlacement,
    NetConnection,
    _gen_junction,
    _gen_no_connect,
    deterministic_uuids,
    generate_schematic,
)
from src.pipeline.validate import run_erc

KICAD_CLI = shutil.which("kicad-cli") or "/usr/bin/kicad-cli"
skip_no_kicad = pytest.mark.skipif(
    not Path(KICAD_CLI).is_file(), reason="kicad-cli not available"
)


def _power_stage() -> str:
    """A capacitor between VCC and GND, wired to power symbols + PWR_FLAGs."""
    comps = [
        ComponentPlacement("Device:C", "C1", "100nF",
                           "Capacitor_SMD:C_0402_1005Metric",
                           position=(101.6, 101.6)),
    ]
    # Device:C stub pins are at (x, y-3.81) and (x, y+3.81). PWR_FLAG pins
    # sit exactly on those points so each rail is seen as driven.
    nets = [
        NetConnection("VCC", "power", (101.6, 97.79)),
        NetConnection("GND", "power", (101.6, 105.41)),
        NetConnection("PWR_FLAG", "power", (101.6, 97.79)),
        NetConnection("PWR_FLAG", "power", (101.6, 105.41)),
    ]
    return generate_schematic(comps, nets, title="Micro Power")


def test_deterministic_uuids_byte_identical():
    comps = [ComponentPlacement("Device:R", "R1", "10k", "", (100.0, 100.0))]
    nets = [NetConnection("A", "local", (100.0, 96.19)),
            NetConnection("B", "local", (100.0, 103.81))]
    with deterministic_uuids("det-test"):
        a = generate_schematic(comps, nets, title="Det")
    with deterministic_uuids("det-test"):
        b = generate_schematic(comps, nets, title="Det")
    assert a == b
    with deterministic_uuids("det-test-other"):
        c = generate_schematic(comps, nets, title="Det")
    assert a != c


def test_junction_and_no_connect_emitters():
    with deterministic_uuids("j"):
        j = _gen_junction(101.6, 101.6)
        nc = _gen_no_connect(50.8, 50.8)
    assert "(junction" in j and "(at 101.6 101.6)" in j
    assert "(no_connect" in nc and "(at 50.8 50.8)" in nc


def test_rotation_emitted():
    comp = ComponentPlacement("Device:R", "R1", "1k", "", (10.16, 10.16),
                              rotation=90)
    content = generate_schematic([comp], [], title="Rot")
    assert "(at 10.16 10.16 90)" in content


def test_power_symbols_replace_power_port():
    content = _power_stage()
    assert "(power_port" not in content
    assert '(symbol "power:VCC"' in content
    assert '(symbol "power:GND"' in content
    assert '(symbol "power:PWR_FLAG"' in content
    assert '(lib_id "power:GND")' in content
    # grounds point down (rot 180), rails up (rot 0)
    assert "(at 101.6 105.41 180)" in content
    assert "(at 101.6 97.79 0)" in content


@skip_no_kicad
def test_micro_sheet_loads_and_erc(tmp_path):
    content = _power_stage()
    path = tmp_path / "micro.kicad_sch"
    path.write_text(content)
    result = run_erc(path)
    assert result["success"], result
    # The hard gate: zero ERC *errors* (warnings tolerated at this stage —
    # PWR_FLAG placement is finalized by the power stage of the engine).
    assert result["errors"] == 0, result


def test_earth_net_gets_ground_glyph():
    """Regression: EARTH is a ground per graph_build._GROUND_RE but the
    emitter drew it with the (then-inverted) rail glyph."""
    from src.ecad.emit import power_symbol_lib_sexp

    earth = power_symbol_lib_sexp("EARTH")
    # the innermost triangle stroke only exists in the ground glyph
    assert "(xy -0.254 1.016)" in power_symbol_lib_sexp("GND")
    assert "(xy -0.254 1.016)" in earth
