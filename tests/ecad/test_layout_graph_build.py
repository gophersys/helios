"""graph_build: unit explosion, power stripping (D2a), satellite rule (D2b)."""

from src.ecad import Component, Design, FootprintRef, pin
from src.ecad.layout.graph_build import build, is_ground_net, is_power_net
from src.ecad.layout.ir import NodeKind
from tests.ecad.test_model import Cap, LDO, TinyMCU


class Res(Component):
    part_name = "R"
    lib_id = "Device:R"
    reference_prefix = "R"
    footprint = FootprintRef("Resistor_SMD", "R_0402_1005Metric")
    _PIN_SPECS = (pin("1", "P1", "passive", "passive"),
                  pin("2", "P2", "passive", "passive"))


def test_power_net_classification():
    assert is_power_net("GND") and is_ground_net("GND")
    assert is_power_net("VSSA") and is_ground_net("VSSA")
    assert is_power_net("3V3") and not is_ground_net("3V3")
    assert is_power_net("+3V3") and is_power_net("VBUS") and is_power_net("VCC")
    assert not is_power_net("GPS_TX") and not is_power_net("SDA")


def _mcu_design():
    d = Design("g")
    mcu, ldo, c1, r1 = d.add(TinyMCU(), LDO(), Cap(), Res())
    d.net("3V3").connect(mcu.VDD, ldo.VOUT, c1.P1)
    d.net("GND").connect(mcu.pin("8"), ldo.pin("2"), c1.P2)
    d.net("VIN").connect(ldo.VIN)
    d.net("EN_R").connect(ldo.EN, r1.P1)      # pull-up-ish: r1 has 1 signal edge
    d.net("3V3_PU").connect(r1.P2)            # to rail
    # make 3V3_PU actually a rail name so it's stripped:
    return d, mcu, ldo, c1, r1


def test_unit_explosion_and_kinds():
    d, *_ = _mcu_design()
    g = build(d)
    # TinyMCU has 2 units -> U1#1, U1#2; LDO single unit -> U2#1
    assert "U1#1" in g.nodes and "U1#2" in g.nodes and "U2#1" in g.nodes
    assert g.nodes["U1#1"].kind is NodeKind.IC_UNIT
    assert g.nodes["R1#1"].kind is NodeKind.PASSIVE


def test_power_stripped_to_taps():
    d, mcu, ldo, c1, r1 = _mcu_design()
    g = build(d)
    # no edge named 3V3/GND/VIN
    edge_nets = {e.net for e in g.edges}
    assert "3V3" not in edge_nets and "GND" not in edge_nets
    assert "VIN" not in edge_nets
    # the MCU power unit has taps for 3V3 (up) and GND (down)
    taps = g.nodes["U1#1"].power_taps
    rails = {(t.rail, t.down) for t in taps}
    assert ("3V3", False) in rails and ("GND", True) in rails


def test_satellite_rule():
    d, mcu, ldo, c1, r1 = _mcu_design()
    g = build(d)
    # C1 (rail-GND, zero signal edges) is a satellite; R1 (1 signal edge) is not
    assert "C1#1" not in g.nodes
    assert "R1#1" in g.nodes
    all_sats = [s.ref for sats in g.satellites.values() for s in sats]
    assert all_sats == ["C1"]
    # owner is an IC unit with a tap on the same rail
    owner = next(iter(g.satellites))
    assert any(t.rail == "3V3" for t in g.nodes[owner].power_taps)


def test_signal_edges_sorted_and_named():
    d, *_ = _mcu_design()
    g = build(d)
    assert [e.net for e in g.edges] == sorted(e.net for e in g.edges)
    assert all(e.named for e in g.edges)


def test_determinism():
    a = build(_mcu_design()[0])
    b = build(_mcu_design()[0])
    assert list(a.nodes) == list(b.nodes)
    assert [(e.net, e.ports) for e in a.edges] == [(e.net, e.ports) for e in b.edges]
