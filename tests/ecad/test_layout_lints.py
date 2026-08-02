"""Regression tests for the layout hard gates (src/ecad/layout/lints.py).

Each test here corresponds to a confirmed adversarial-review finding.
"""

from src.ecad import Component, Design, FootprintRef, pin
from src.ecad.layout.engine import emit, layout
from src.ecad.layout.lints import lint_placed, lint_schematic_text
from tests.ecad.test_model import Cap, TinyMCU

_SHEET = """(kicad_sch
\t(version 20250114)
\t(generator "hardware-pipeline")
\t(generator_version "1.0")
\t(uuid "00000000-0000-0000-0000-000000000001")
\t(paper "A3")
\t(lib_symbols
\t)
%s
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""


def _wire(x1, y1, x2, y2):
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {x1} {y1}) (xy {x2} {y2})\n\t\t)\n'
            f'\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            f'\t\t(uuid "00000000-0000-0000-0000-00000000000f")\n\t)')


def test_lint_schematic_text_sees_wires():
    """The file-level gate must actually inspect the emitted wires."""
    text = _SHEET % _wire(25.4, 50.8, 22.9, 51.3)
    errs = lint_schematic_text(text)
    assert any(e.startswith("diagonal-wire-in-file") for e in errs), errs
    assert any(e.startswith("off-grid-wire-in-file") for e in errs), errs


def test_lint_schematic_text_clean_wire_passes():
    text = _SHEET % _wire(25.4, 50.8, 25.4, 55.88)
    assert lint_schematic_text(text) == []


def test_lint_schematic_text_off_grid_only():
    text = _SHEET % _wire(25.4, 50.8, 25.4, 51.3)
    errs = lint_schematic_text(text)
    assert errs == ["off-grid-wire-in-file: 51.3"], errs


class DualRailMCU(Component):
    part_name = "DUAL1"
    lib_id = "MCU_Test:DUAL1"
    footprint = FootprintRef("Package_DFN_QFN", "QFN-8")
    _PIN_SPECS = (
        pin("1", "VDD", "power_in", "power"),
        pin("2", "VDDA", "power_in", "power"),
        pin("8", "GND", "power_in", "ground"),
        pin("3", "TX", "output", "comm"),
        pin("4", "IO0", "bidirectional", "gpio", gpio=0),
    )


def _mixed_rail_row() -> Design:
    """One satellite row decoupling two different rails (C2 is on +1V8,
    C1/C3 on +3V3)."""
    d = Design("mixed-rail-row")
    mcu, c1, c2, c3 = d.add(DualRailMCU(), Cap(), Cap(), Cap())
    d.net("+3V3").connect(mcu.VDD, c1.P1, c3.P1)
    d.net("+1V8").connect(mcu.VDDA, c2.P1)
    d.net("GND").connect(mcu.pin("8"), c1.P2, c2.P2, c3.P2)
    return d


def test_lint_placed_sees_emit_generated_wires():
    """lint_placed must gate the wires emit() builds outside the IR."""
    d = _mixed_rail_row()
    placed = layout(d)
    sheet = emit(placed, d)
    ir_only = set(placed.routing.wires)
    assert set(sheet.wires) - ir_only, "emit() surfaced no generated wires"
    # every generated wire is attributed to a net and gated
    assert "+3V3" in sheet.wires and "GND" in sheet.wires
    assert lint_placed(placed, sheet) == [], lint_placed(placed, sheet)


def test_satellite_row_never_shorts_two_rails():
    """A row decoupling several rails must keep each rail's trunk clear of
    the other rails' cap stubs."""
    d = _mixed_rail_row()
    placed = layout(d)
    sheet = emit(placed, d)
    shorts = [e for e in lint_placed(placed, sheet) if e.startswith("net-short")]
    assert shorts == [], shorts


def test_satellite_cap_pads_follow_the_design():
    """A cap wired P2->rail / P1->gnd must be emitted that way round."""
    d = Design("swapped-cap")
    mcu, c1 = d.add(TinyMCU(), Cap())
    d.net("3V3").connect(mcu.VDD, c1.P2)
    d.net("GND").connect(mcu.pin("8"), c1.P1)
    g = layout(d).graph
    sats = [s for caps in g.satellites.values() for s in caps]
    assert len(sats) == 1
    assert (sats[0].rail_pad, sats[0].gnd_pad) == ("2", "1")


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


class Res(Component):
    part_name = "R"
    lib_id = "Device:R"
    reference_prefix = "R"
    footprint = FootprintRef("Resistor_SMD", "R_0402_1005Metric")
    _PIN_SPECS = (pin("1", "P1", "passive"), pin("2", "P2", "passive"))


def _label_vs_escape() -> Design:
    """Net R falls back to labels; net X escapes over the same node, and the
    fixed 2.54 stub put R's label straight onto X's escape wire."""
    d = Design("label-vs-escape")
    mcu, gps = d.add(TinyMCU(), GPS())
    d.net("3V3").connect(mcu.VDD, gps.VCC)
    d.net("GND").connect(mcu.pin("8"), gps.pin("2"))
    d.net("T").connect(mcu.TX, gps.RX)
    d.net("R").connect(gps.TX, mcu.gpio(0))
    d.net("X").connect(mcu.gpio(1), mcu.gpio(2))
    return d


def _bus_fanout() -> Design:
    """Three nets escaping over one node: their trunks were assigned tracks
    from port-y spans that ignored the escape ys, so two shared a track."""
    d = Design("bus-fanout")
    mcu, r1, r2, r3 = d.add(TinyMCU(), Res(), Res(), Res())
    d.net("3V3").connect(mcu.VDD)
    d.net("GND").connect(mcu.pin("8"))
    d.net("BUS").connect(mcu.TX, r1.P1, r2.P1, r3.P1)
    d.net("N1").connect(r1.P2, mcu.gpio(0))
    d.net("N2").connect(r2.P2, mcu.gpio(1))
    d.net("N3").connect(r3.P2, mcu.gpio(2))
    return d


def _span_two_ranks() -> Design:
    """A -> B -> C chain plus a net from A straight to C: routed as one
    horizontal wire through the whole of B's column."""
    d = Design("span-two")
    a, b, c = d.add(TinyMCU(), TinyMCU(), TinyMCU())
    d.net("GND").connect(a.pin("8"), b.pin("8"), c.pin("8"))
    d.net("3V3").connect(a.VDD, b.VDD, c.VDD)
    d.net("AB").connect(a.TX, b.gpio(0))
    d.net("BC").connect(b.TX, c.gpio(0))
    d.net("AC").connect(a.gpio(1), c.gpio(1))
    return d


def _no_shorts(design: Design) -> list[str]:
    placed = layout(design)
    sheet = emit(placed, design)
    return lint_placed(placed, sheet)


def test_label_never_lands_on_another_nets_wire():
    assert _no_shorts(_label_vs_escape()) == []


def test_escape_tracks_do_not_share_trunks():
    assert _no_shorts(_bus_fanout()) == []


def test_rank_spanning_net_is_not_routed_through_the_middle_column():
    assert _no_shorts(_span_two_ranks()) == []


def _refine_overlap() -> Design:
    """U2#1 is refined first and moves onto U1#1, which has no cross-rank
    signal segment and is therefore never repositioned."""
    d = Design("refine-overlap")
    mcu, gps, r1, r2 = d.add(TinyMCU(), GPS(), Res(), Res())
    d.net("3V3").connect(mcu.VDD, gps.VCC)
    d.net("GND").connect(mcu.pin("8"), gps.pin("2"))
    d.net("S1").connect(mcu.TX, r1.P1)
    d.net("S2").connect(r1.P2, r2.P1)
    d.net("S3").connect(r2.P2, gps.RX)
    d.net("S4").connect(gps.TX, mcu.gpio(0))
    return d


def test_refine_never_moves_a_node_onto_an_unrefined_rank_mate():
    assert _no_shorts(_refine_overlap()) == []
