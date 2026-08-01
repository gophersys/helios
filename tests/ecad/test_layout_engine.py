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


class Res(Component):
    part_name = "R"
    lib_id = "Device:R"
    reference_prefix = "R"
    footprint = FootprintRef("Resistor_SMD", "R_0402_1005Metric")
    _PIN_SPECS = (
        pin("1", "P1", "passive", "passive"),
        pin("2", "P2", "passive", "passive"),
    )


class Header1(Component):
    part_name = "CONN_1X01"
    lib_id = "Connector_Generic:Conn_01x01"
    reference_prefix = "J"
    footprint = FootprintRef("Connector_PinHeader_2.54mm",
                             "PinHeader_1x01_P2.54mm_Vertical")
    _PIN_SPECS = (pin("1", "P1", "passive", "passive"),)


def test_satellite_caps_keep_footprint():
    """Regression: satellites were emitted with an empty Footprint property,
    so Update-PCB-from-Schematic saw every decoupling cap as unassigned."""
    design = _ldo_stage()
    sheet = emit(layout(design), design)
    assert sheet.text.count(
        '(property "Footprint" "Capacitor_SMD:C_0402_1005Metric"') == 2


def test_single_rank_design_routes_via_labels():
    """Regression: a one-rank graph has no wiring channel (channel_x == [])
    and route() crashed with IndexError instead of falling back to labels."""
    d = Design("two-headers")
    j1, j2 = d.add(Header1(), Header1())
    d.net("SIG").connect(j1.P1, j2.P1)
    placed, _sheet = _gates(d)
    assert "SIG" in placed.routing.labeled_nets


def test_no_ic_design_keeps_caps_placed():
    """Regression: with zero IC units _find_owner self-owned a node that was
    then deleted from the graph, and place.coordinates KeyError'd on it."""
    d = Design("caps-only")
    c1, c2 = d.add(Cap(), Cap())
    d.net("3V3").connect(c1.P1, c2.P1)
    d.net("GND").connect(c1.P2, c2.P2)
    placed, _sheet = _gates(d)
    assert not placed.graph.satellites
    assert set(placed.graph.nodes) == {"C1#1", "C2#1"}


def _series_cap_design() -> Design:
    """MCU with a coupling cap in a signal path plus a decoupling cap —
    both are Device:C but only the latter is a satellite."""
    d = Design("mixed-caps")
    mcu, cs, cd = d.add(TinyMCU(), Cap(), Cap())
    d.net("A").connect(mcu.gpio(0), cs.P1)
    d.net("B").connect(mcu.gpio(1), cs.P2)
    d.net("3V3").connect(mcu.VDD, cd.P1)
    d.net("GND").connect(mcu.pin("8"), cd.P2)
    return d


def test_signal_path_passive_uses_router_geometry():
    """Regression: placed R/C/L emitted the vertical Device stub (pins at
    (0, ±3.81)) while the router wired the readable LEFT/RIGHT ports —
    every wire missed its pin by ~10 mm."""
    d = Design("series-r")
    mcu, r = d.add(TinyMCU(), Res())
    d.net("A").connect(mcu.gpio(0), r.P1)
    d.net("B").connect(mcu.gpio(1), r.P2)
    placed, sheet = _gates(d)
    assert "R1#1" in placed.graph.nodes
    assert '(symbol "Device:R"' in sheet.text
    # no satellites in this design → no vertical stub pins anywhere
    assert "(at 0 3.81 270)" not in sheet.text


def test_placed_and_satellite_same_lib_id_split():
    """A signal-path cap and a satellite cap share Device:C: the satellite
    stub (vertical pins, row wiring depends on them) must be emitted under
    an alias instead of silently reusing the readable symbol."""
    placed, sheet = _gates(_series_cap_design())
    assert "C1#1" in placed.graph.nodes            # signal cap stays placed
    assert '(symbol "Device:C"' in sheet.text      # readable geometry
    assert '(symbol "Device:C_dec"' in sheet.text  # satellite stub alias
    assert '(lib_id "Device:C_dec")' in sheet.text


@skip_no_kicad
def test_signal_passive_erc_and_netlist(tmp_path):
    from src.pipeline.validate import run_erc

    design = _series_cap_design()
    _placed, sheet = _gates(design)
    sch = tmp_path / "mixed.kicad_sch"
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


# ── regressions from the adversarial review ─────────────────────────────────


def _three_cap_rail() -> Design:
    """One rail decoupled by three caps — the middle one T-s into the span."""
    d = Design("three-cap-rail")
    u, c1, c2, c3 = d.add(TinyMCU(), Cap(), Cap(), Cap())
    d.net("3V3").connect(u.VDD, c1.P1, c2.P1, c3.P1)
    d.net("GND").connect(u.GND, c1.P2, c2.P2, c3.P2)
    return d


def test_satellite_rail_emits_a_junction_per_cap():
    """Middle caps land mid-segment on the shared rail wire.

    KiCad does not connect a wire endpoint that lands mid-segment without a
    junction dot, so without these the middle cap of a row is electrically
    floating — the exported netlist dropped C2 entirely and ERC reported
    pin_not_connected.
    """
    d = _three_cap_rail()
    pl = layout(d)
    text = emit(pl, d, "three_cap_rail").text

    caps = [c for c in d.components if isinstance(c, Cap)]
    assert len(caps) == 3

    # Every cap stub meeting the rail needs a junction; with 3 caps sharing a
    # rail there must be at least one junction per cap on that row.
    junction_count = text.count("(junction")
    assert junction_count >= len(caps), (
        f"expected >= {len(caps)} junctions for a 3-cap rail, got {junction_count}"
    )


@skip_no_kicad
def test_three_cap_rail_netlist_keeps_every_cap(tmp_path):
    """The real gate: kicad-cli must see all three caps on the rail."""
    d = _three_cap_rail()
    pl = layout(d)
    text = emit(pl, d, "three_cap_rail").text
    p = tmp_path / "three_cap_rail.kicad_sch"
    p.write_text(text)

    from src.pipeline.roundtrip import _export_netlist, parse_kicad_netlist_xml

    xml = _export_netlist(p, tmp_path)
    assert xml is not None, "netlist export failed"
    nets = {}
    for net in parse_kicad_netlist_xml(xml)["nets"]:
        name = net["name"].lstrip("/").split("/")[-1]
        if "unconnected-" in net["name"]:
            continue
        nets.setdefault(name, set()).update(
            f"{n['ref']}:{n['pin']}" for n in net["nodes"]
            if not n["ref"].startswith("#"))
    rail = nets.get("3V3", set())
    cap_pins = {p for p in rail if p.startswith("C")}
    assert len(cap_pins) == 3, f"all three caps must be on 3V3, got {sorted(rail)}"
