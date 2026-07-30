"""End-to-end layout-engine fixture gates.

Hard gates per fixture: definition lint clean → geometric lints clean →
kicad-cli loads → ERC errors == 0 → netlist equivalence vs the Design's
intended netlist. Soft metrics asserted with fixture-specific ceilings.
"""

import shutil
from pathlib import Path

import pytest

from src.ecad import Component, Design, FootprintRef, pin
from src.ecad.layout.engine import emit, layout
from src.ecad.layout.lints import lint_placed, lint_schematic_text
from tests.ecad.test_model import Cap, LDO, TinyMCU

KICAD_CLI = shutil.which("kicad-cli") or "/usr/bin/kicad-cli"
skip_no_kicad = pytest.mark.skipif(
    not Path(KICAD_CLI).is_file(), reason="kicad-cli not available"
)


class GPS(Component):
    part_name = "GPSMOD"
    lib_id = "RF_GPS:GPSMOD"
    footprint = FootprintRef("RF_GPS", "ublox_NEO-6M")
    _PIN_SPECS = (
        pin("1", "VCC", "power_in", "power"),
        pin("2", "GND", "power_in", "ground"),
        pin("3", "TX", "output", "comm"),
        pin("4", "RX", "input", "comm"),
    )


def _ldo_stage() -> Design:
    d = Design("ldo-stage")
    u, cin, cout = d.add(LDO(), Cap(), Cap())
    d.net("VIN").connect(u.VIN, cin.P1, u.EN)
    d.net("3V3").connect(u.VOUT, cout.P1)
    d.net("GND").connect(u.pin("2"), cin.P2, cout.P2)
    return d


def _mcu_gps() -> Design:
    d = Design("mcu-gps")
    mcu, gps, c1 = d.add(TinyMCU(), GPS(), Cap())
    d.net("3V3").connect(mcu.VDD, gps.VCC, c1.P1)
    d.net("GND").connect(mcu.pin("8"), gps.pin("2"), c1.P2)
    d.net("GPS_TX").connect(gps.TX, mcu.gpio(0))
    d.net("GPS_RX").connect(gps.RX, mcu.TX)
    return d


def _gates(design: Design):
    placed = layout(design)
    geo = lint_placed(placed)
    assert geo == [], geo
    sheet = emit(placed, design)
    file_lints = lint_schematic_text(sheet.text)
    assert file_lints == [], file_lints
    return placed, sheet


def _netlist_of(text: str, tmp: Path) -> dict[str, set[str]]:
    from src.pipeline.roundtrip import _export_netlist, parse_kicad_netlist_xml

    sch = tmp / "sheet.kicad_sch"
    sch.write_text(text)
    xml = _export_netlist(sch, tmp)
    assert xml is not None, "netlist export failed"
    parsed = parse_kicad_netlist_xml(xml)
    out: dict[str, set[str]] = {}
    for net in parsed["nets"]:
        name = net["name"].lstrip("/")
        if name.startswith("unconnected-"):
            continue  # KiCad pseudo-nets for no_connect pins
        pins = {f"{n['ref']}:{n['pin']}" for n in net["nodes"]
                if not n["ref"].startswith("#")}
        if pins:
            out[name] = pins
    return out


def test_ldo_stage_layout_metrics():
    placed, sheet = _gates(_ldo_stage())
    m = sheet.metrics
    assert m.crossings == 0
    assert m.alignment == 1.0 or m.routed_nets == 0
    # caps are satellites: not in the routed graph
    assert not any(n.startswith("C") for n in placed.graph.nodes)


def test_mcu_gps_layout_metrics():
    placed, sheet = _gates(_mcu_gps())
    m = sheet.metrics
    # The TX/RX crossover is intrinsic: it resolves as either one wire
    # crossing or one label fallback (backward edge after FAS), never both.
    assert m.crossings + m.labeled_nets <= 1
    assert m.bends <= 12


def test_determinism_byte_identical():
    d1, d2 = _mcu_gps(), _mcu_gps()
    a = emit(layout(d1), d1).text
    b = emit(layout(d2), d2).text
    assert a == b


@skip_no_kicad
def test_ldo_stage_erc_and_netlist(tmp_path):
    from src.pipeline.validate import run_erc

    design = _ldo_stage()
    placed, sheet = _gates(design)
    sch = tmp_path / "ldo.kicad_sch"
    sch.write_text(sheet.text)
    erc = run_erc(sch)
    assert erc["success"], erc
    assert erc["errors"] == 0, erc

    actual = _netlist_of(sheet.text, tmp_path)
    intended = design.intended_netlist()
    assert actual == intended, {
        "missing": {k: v for k, v in intended.items() if actual.get(k) != v},
        "actual": actual,
    }


@skip_no_kicad
def test_mcu_gps_erc_and_netlist(tmp_path):
    from src.pipeline.validate import run_erc

    design = _mcu_gps()
    placed, sheet = _gates(design)
    sch = tmp_path / "gps.kicad_sch"
    sch.write_text(sheet.text)
    erc = run_erc(sch)
    assert erc["success"], erc
    assert erc["errors"] == 0, erc
    assert _netlist_of(sheet.text, tmp_path) == design.intended_netlist()


def test_unknown_passive_lib_id_gets_stub():
    """Regression: every placed lib_id must have a lib_symbols definition
    (the get_stub(...) or "" bug emitted empty entries for non-R/C/L)."""
    class OddCap(Cap):
        lib_id = "Device:C_Polarized"

    d = Design("odd")
    u, c = d.add(LDO(), OddCap())
    d.net("VIN").connect(u.VIN, c.P1, u.EN)
    d.net("GND").connect(u.pin("2"), c.P2)
    sheet = emit(layout(d), d)
    assert '(symbol "Device:C_Polarized"' in sheet.text
