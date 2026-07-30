"""Tests for the ecad typed design model core."""

import pytest

from src.ecad import (
    Component,
    Design,
    ElectricalType,
    FootprintRef,
    Net,
    PinSpec,
    UnitDef,
    UnitStrategy,
    pin,
    sanitize_pin_name,
)


# ── fixtures ────────────────────────────────────────────────────────────────


class LDO(Component):
    part_name = "AP2112K-3.3"
    lib_id = "Regulator_Linear:AP2112K-3.3"
    reference_prefix = "U"
    footprint = FootprintRef("Package_TO_SOT_SMD", "SOT-23-5")
    _PIN_SPECS = (
        pin("1", "VIN", "power_in", "power"),
        pin("2", "GND", "power_in", "ground"),
        pin("3", "EN", "input", "control"),
        pin("4", "NC", "no_connect", "nc"),
        pin("5", "VOUT", "power_out", "power"),
    )


class Cap(Component):
    part_name = "C"
    lib_id = "Device:C"
    reference_prefix = "C"
    footprint = FootprintRef("Capacitor_SMD", "C_0402_1005Metric")
    _PIN_SPECS = (
        pin("1", "P1", "passive", "passive"),
        pin("2", "P2", "passive", "passive"),
    )


class TinyMCU(Component):
    part_name = "TINY1"
    lib_id = "MCU_Test:TINY1"
    footprint = FootprintRef("Package_DFN_QFN", "QFN-8")
    unit_strategy = UnitStrategy.EXPLICIT
    unit_plan = (
        UnitDef("Power", ("1", "8")),
        UnitDef("GPIO", ("2", "3", "4", "5", "6", "7")),
    )
    _PIN_SPECS = (
        pin("1", "VDD", "power_in", "power"),
        pin("8", "GND", "power_in", "ground"),
        pin("2", "IO0", "bidirectional", "gpio", gpio=0),
        pin("3", "IO1", "bidirectional", "gpio", gpio=1),
        pin("4", "IO2", "bidirectional", "gpio", gpio=2),
        pin("5", "IO3", "bidirectional", "gpio", gpio=3),
        pin("6", "3V3_SENSE", "input"),
        pin("7", "TX", "output", "comm"),
    )


# ── model basics ────────────────────────────────────────────────────────────


def test_electrical_type_parse_aliases():
    assert ElectricalType.parse("power") is ElectricalType.POWER_IN
    assert ElectricalType.parse("BIDIR") is ElectricalType.BIDIRECTIONAL
    assert ElectricalType.parse("tri-state") is ElectricalType.TRI_STATE
    assert ElectricalType.parse("open_drain") is ElectricalType.OPEN_COLLECTOR
    assert ElectricalType.parse("nc") is ElectricalType.NO_CONNECT
    assert ElectricalType.parse("garbage") is ElectricalType.UNSPECIFIED


def test_pinspec_validation():
    with pytest.raises(ValueError):
        PinSpec(pad="", name="X", etype=ElectricalType.INPUT)
    with pytest.raises(ValueError):
        PinSpec(pad="1", name="", etype=ElectricalType.INPUT)


def test_sanitize_pin_name():
    assert sanitize_pin_name("3V3") == "V3V3"
    assert sanitize_pin_name("USB_D-") == "USB_DN"
    assert sanitize_pin_name("USB_D+") == "USB_DP"
    assert sanitize_pin_name("+5V") == "P5V"
    assert sanitize_pin_name("~RST") == "nRST"
    assert sanitize_pin_name("~{RST}") == "nRST"
    assert sanitize_pin_name("#CS") == "nCS"
    assert sanitize_pin_name("IO4") == "IO4"
    assert sanitize_pin_name("SPI/CLK") == "SPI_CLK"
    assert sanitize_pin_name("class") == "class_"


def test_usb_pair_accessors_distinct():
    class Usb(Component):
        footprint = FootprintRef("Connector_USB", "USB_C")
        _PIN_SPECS = (
            pin("1", "USB_D+", "bidirectional"),
            pin("2", "USB_D-", "bidirectional"),
        )

    u = Usb()
    assert u.USB_DP.pad == "1"
    assert u.USB_DN.pad == "2"


def test_ambiguous_ident_refused():
    class Amb(Component):
        footprint = FootprintRef("X", "Y")
        _PIN_SPECS = (
            pin("1", "IO-4", "bidirectional"),
            pin("2", "IO_4", "bidirectional"),
        )

    a = Amb()
    with pytest.raises(AttributeError, match="ambiguous"):
        a.IO_4
    assert a.pin("IO-4").pad == "1"
    assert a.pin("IO_4").pad == "2"


def test_active_low_pin_reachable():
    class R(Component):
        footprint = FootprintRef("X", "Y")
        _PIN_SPECS = (pin("1", "~RST", "input"), pin("2", "GND", "power_in"))

    assert R().nRST.pad == "1"


def test_duplicate_pads_rejected():
    with pytest.raises(TypeError, match="duplicate pads"):
        class Bad(Component):
            _PIN_SPECS = (pin("1", "A", "input"), pin("1", "B", "input"))


def test_unit_plan_must_cover_all_pads():
    with pytest.raises(TypeError, match="unit_plan"):
        class Bad(Component):
            unit_strategy = UnitStrategy.EXPLICIT
            unit_plan = (UnitDef("Power", ("1",)),)
            _PIN_SPECS = (pin("1", "VDD", "power_in"), pin("2", "GND", "power_in"))


# ── pin access ──────────────────────────────────────────────────────────────


def test_pin_accessors():
    u = LDO()
    assert u.pin("VIN").pad == "1"
    assert u.pin("3").name == "EN"
    assert u.EN.pad == "3"
    assert u.VOUT.etype is ElectricalType.POWER_OUT
    with pytest.raises(KeyError):
        u.pin("NOPE")
    with pytest.raises(AttributeError):
        u.NOPE


def test_leading_digit_accessor():
    m = TinyMCU()
    assert m.V3V3_SENSE.pad == "6"


def test_gpio_helper():
    m = TinyMCU()
    assert m.gpio(2).pad == "4"
    with pytest.raises(KeyError):
        m.gpio(99)


def test_units_single_vs_explicit():
    c = Cap()
    assert len(c.units()) == 1
    assert c.units()[0].pads == ("1", "2")
    m = TinyMCU()
    assert [u.name for u in m.units()] == ["Power", "GPIO"]
    assert m.unit_of("8") == 1
    assert m.unit_of("5") == 2


# ── nets ────────────────────────────────────────────────────────────────────


def test_net_connect_and_idempotence():
    u, c = LDO(), Cap()
    n = Net("3V3")
    n.connect(u.VOUT, c.P1)
    n.connect(u.VOUT)  # idempotent
    assert len(n.pins) == 2
    assert u.VOUT.net is n


def test_net_conflict_raises():
    u = LDO()
    Net("A").connect(u.VOUT, LDO().VIN)
    with pytest.raises(ValueError, match="already on"):
        Net("B").connect(u.VOUT)


def test_net_connect_iterable():
    m = TinyMCU()
    gnd = Net("GND")
    gnd.connect(m.pins_named("GND"), LDO().pin("GND"))
    assert len(gnd.pins) == 2


# ── design + lint ───────────────────────────────────────────────────────────


def _codes(design, severity=None):
    return [i.code for i in design.check()
            if severity is None or i.severity == severity]


def test_design_ref_assignment():
    d = Design("t")
    u1 = d.add(LDO())
    c1, c2 = d.add(Cap(), Cap())
    assert (u1.ref, c1.ref, c2.ref) == ("U1", "C1", "C2")


def test_check_clean_design():
    d = Design("t")
    u, cin = d.add(LDO(), Cap())
    Net("VIN").connect(u.VIN, cin.P1, u.EN)
    Net("GND").connect(u.pin("GND"), cin.P2)
    out = Cap()
    d.add(out)
    Net("3V3").connect(u.VOUT, out.P1)
    Net("GND2").connect(out.P2, d.add(Cap()).P1)  # keep everything 2-pin
    errors = [i for i in d.check() if i.is_error]
    assert errors == []


def test_check_unconnected_power_is_error():
    d = Design("t")
    d.add(LDO())
    assert "unconnected-power" in _codes(d, "error")


def test_check_floating_input_is_warning():
    d = Design("t")
    u, c = d.add(LDO(), Cap())
    Net("VIN").connect(u.VIN, c.P1)
    Net("GND").connect(u.pin("GND"), c.P2)
    # EN left floating
    assert "floating-input" in _codes(d, "warning")


def test_check_single_pin_net():
    d = Design("t")
    u = d.add(LDO())
    Net("X").connect(u.VOUT)
    assert "single-pin-net" in _codes(d, "error")


def test_check_output_conflict():
    d = Design("t")
    a, b = d.add(TinyMCU(), TinyMCU())
    Net("BUS").connect(a.TX, b.TX)
    assert "output-conflict" in _codes(d, "error")


def test_check_missing_footprint():
    class NoFp(Component):
        _PIN_SPECS = (pin("1", "A", "passive"), pin("2", "B", "passive"))

    d = Design("t")
    d.add(NoFp())
    assert "missing-footprint" in _codes(d, "error")


def test_check_nc_connected_warns():
    d = Design("t")
    u, c = d.add(LDO(), Cap())
    Net("OOPS").connect(u.pin("4"), c.P1)
    assert "nc-connected" in _codes(d, "warning")


def test_intended_netlist():
    d = Design("t")
    u, c = d.add(LDO(), Cap())
    Net("3V3").connect(u.VOUT, c.P1)
    nl = d.intended_netlist()
    assert nl["3V3"] == {"U1:5", "C1:1"}


def test_preset_ref_never_collides_with_auto():
    d = Design("t")
    a = LDO()
    a.ref = "U1"
    d.add(a)
    b = d.add(LDO())
    assert b.ref == "U2"


def test_duplicate_preset_ref_rejected():
    d = Design("t")
    a = LDO()
    a.ref = "U7"
    d.add(a)
    b = LDO()
    b.ref = "U7"
    with pytest.raises(ValueError, match="Duplicate ref"):
        d.add(b)


def test_duplicate_net_name_lint_and_netlist_merge():
    d = Design("t")
    a, b = d.add(Cap(), Cap())
    c, e = d.add(Cap(), Cap())
    Net("GND").connect(a.P1, b.P1)
    Net("GND").connect(c.P1, e.P1)  # second distinct object, same name
    assert "duplicate-net-name" in _codes(d, "error")
    # netlist merges rather than dropping pins
    assert d.intended_netlist()["GND"] == {"C1:1", "C2:1", "C3:1", "C4:1"}


def test_design_net_get_or_create():
    d = Design("t")
    n1 = d.net("3V3")
    n2 = d.net("3V3")
    assert n1 is n2
    u, c = d.add(LDO(), Cap())
    n1.connect(u.VOUT, c.P1)
    assert "duplicate-net-name" not in _codes(d)
    # an empty registered net is visible to lint
    d.net("ORPHAN")
    assert "single-pin-net" in _codes(d, "error")


def test_check_ok():
    d = Design("t")
    d.add(LDO())
    assert d.check_ok() is False
