"""Per-block gates for src/ecad/circuits.

Every implementable block is instantiated *alone* in a ``Design`` — the only
other thing present is the device it serves, whose own power pins anchor the
rails — and gated on: definition lint has no errors, the exact
``intended_netlist()``, and unique reference designators.

``push_button`` and ``indicator_led`` were written here behind
``xfail(raises=MissingPartError)`` while their parts did not exist. Stage F1
generated ``Switch:SW_Push`` and ``Device:LED`` into
``src/ecad/library/generic/``, the tests XPASSed, and the markers came off —
so the netlist assertions below are now live gates. In particular the LED
one pins the polarity contract: KiCad's ``Device:LED`` is pad 1 = K, pad 2 =
A, so the resistor faces pad 2 and GND takes pad 1.

Everything except the one ``skip_no_kicad`` integration test is pure model —
no layout, no kicad-cli — so it runs anywhere.
"""

import inspect
import shutil
from pathlib import Path

import pytest

from src.ecad import Component, Design
from src.ecad.circuits import (
    Block,
    MissingPartError,
    Provenance,
    decoupling,
    e24_nearest,
    en_reset_rc,
    format_ohms,
    indicator_led,
    ldo_regulator,
    led_series_resistor,
    pull_resistor,
    push_button,
)
from src.ecad.circuits import blocks as blocks_mod
from src.ecad.library import get as registry_get
from src.ecad.model import FootprintRef
from src.ecad.model import pin as pinspec

KICAD_CLI = shutil.which("kicad-cli") or "/usr/bin/kicad-cli"
skip_no_kicad = pytest.mark.skipif(
    not Path(KICAD_CLI).is_file(), reason="kicad-cli not available"
)

MODULE = "ESP32-S3-WROOM-1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mcu() -> Component:
    return registry_get(MODULE)()


def _rails(design: Design, mcu: Component, *, tie_en: bool = False) -> Component:
    """Register the module and put its own power/ground pins on named rails.

    A block under test needs real anchors: a resistor to a rail nobody else
    touches is a single-pin net, which ``check()`` calls an error. This adds
    no sub-circuit of its own — the block stays the only block in the design.

    ``tie_en`` ties EN straight to the rail (the no-RC configuration) so the
    rail has a second pin in tests whose block does not touch it.
    """
    design.add(mcu)
    design.net("+3V3").connect(mcu.V3V3)
    design.net("GND").connect(mcu.pins_named("GND"))
    if tie_en:
        design.net("+3V3").connect(mcu.EN)
    return mcu


def _no_errors(design: Design) -> None:
    errors = [i for i in design.check() if i.is_error]
    assert errors == [], errors


def _refs_unique(design: Design) -> None:
    refs = [c.ref for c in design.components]
    assert all(refs), f"unassigned refs: {refs}"
    assert len(refs) == len(set(refs)), f"duplicate refs: {sorted(refs)}"


def _fake_part(name, specs, *, prefix: str = "U") -> type[Component]:
    """A throwaway Component subclass, for pinouts no shipped part has.

    The blocks below are advertised as generic over ``part``; the shipped
    parts are the only pinouts that happen to exist today, so a defect that
    needs a *different* pinout to show itself needs a part like this one.
    """
    return type(name.replace("-", "_"), (Component,), {
        "part_name": name,
        "lib_id": f"Test:{name}",
        "reference_prefix": prefix,
        # Design.check() calls a footprintless component an error, and these
        # fixtures are meant to exercise wiring, not that lint.
        "footprint": FootprintRef("Package_TO_SOT_SMD", "SOT-23-5"),
        "_PIN_SPECS": tuple(specs),
    })


def _serve(monkeypatch, lib_id: str, cls: type[Component]) -> None:
    """Make ``_registry_class(lib_id)`` return ``cls``; pass everything else
    through to the real registry, since a block usually needs its passives
    too."""
    real = blocks_mod._registry_class

    def fake(requested: str, **kwargs):
        return cls if requested == lib_id else real(requested, **kwargs)

    monkeypatch.setattr(blocks_mod, "_registry_class", fake)


# ---------------------------------------------------------------------------
# Value maths — E24, Ohm's law, formatting
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ohms,expected", [
    (260.0, 270.0),      # the LED case: 8.3% above 240, 3.8% below 270
    (240.0, 240.0),      # an exact E24 value snaps to itself
    (1234.0, 1200.0),
    (9800.0, 10000.0),   # snaps across the decade boundary
    (0.55, 0.56),
    (3.3e6, 3.3e6),
])
def test_e24_nearest(ohms, expected):
    assert e24_nearest(ohms) == pytest.approx(expected)


def test_e24_nearest_rejects_non_positive():
    with pytest.raises(ValueError):
        e24_nearest(0)


@pytest.mark.parametrize("ohms,expected", [
    (270.0, "270R"), (4700.0, "4.7k"), (10000.0, "10k"), (1e6, "1M"),
])
def test_format_ohms(ohms, expected):
    assert format_ohms(ohms) == expected


def test_led_series_resistor_math():
    """3.3 V rail, 2.0 V Vf, 5 mA -> 260 ohm ideal -> 270 ohm E24."""
    calc = led_series_resistor(supply_v=3.3, vf=2.0, current_ma=5)
    assert calc.ideal_ohms == pytest.approx(260.0)
    assert calc.ohms == pytest.approx(270.0)
    assert calc.value == "270R"
    # 1.3 V across 270 ohm is 4.81 mA, not the 5 mA asked for — the block
    # reports what the E24 part actually delivers.
    assert calc.actual_ma == pytest.approx(4.815, abs=1e-3)
    assert "260" in calc.note and "270" in calc.note and "E24" in calc.note


def test_led_series_resistor_rejects_impossible_drive():
    with pytest.raises(ValueError):
        led_series_resistor(supply_v=3.3, vf=3.3, current_ma=5)
    with pytest.raises(ValueError):
        led_series_resistor(supply_v=3.3, vf=2.0, current_ma=0)


# ---------------------------------------------------------------------------
# decoupling
# ---------------------------------------------------------------------------

def test_decoupling_alone():
    d = Design("decoupling-only")
    mcu = _mcu()
    block = decoupling(d, mcu, "+3V3", "GND")

    _no_errors(d)
    _refs_unique(d)
    # The module has exactly one 3V3 pin (pad 2) -> one 100nF + one bulk.
    assert d.intended_netlist() == {
        "+3V3": {"U1:2", "C1:1", "C2:1"},
        "GND": {"U1:1", "U1:40", "U1:41", "C1:2", "C2:2"},
    }
    assert isinstance(block, Block)
    assert block.refs == ("U1", "C1", "C2")
    assert [c.value for c in block.components[1:]] == ["100nF", "10uF"]
    assert sorted(block.nets) == ["gnd", "rail"]


def test_decoupling_defaults_are_the_cited_values():
    """The guideline text says 0.1 uF per digital power pin + 10 uF bulk."""
    params = inspect.signature(decoupling).parameters
    assert params["per_pin"].default == "100nF"
    assert params["bulk"].default == "10uF"


def test_decoupling_provenance_is_the_esp32_s3_guideline():
    d = Design("prov")
    block = decoupling(d, _mcu(), "+3V3", "GND")
    prov = block.provenance
    assert isinstance(prov, Provenance)
    assert "ESP32-S3 Hardware Design Guidelines" in prov.source
    assert prov.url.startswith("https://docs.espressif.com/")
    assert any("0.1 uF" in n for n in block.notes)
    assert any("10 uF" in n for n in block.notes)


def test_decoupling_without_bulk():
    d = Design("no-bulk")
    block = decoupling(d, _mcu(), "+3V3", "GND", bulk=None)
    _no_errors(d)
    assert block.refs == ("U1", "C1")
    assert d.intended_netlist() == {
        "+3V3": {"U1:2", "C1:1"},
        "GND": {"U1:1", "U1:40", "U1:41", "C1:2"},
    }


def test_decoupling_honours_package():
    d = Design("pkg")
    block = decoupling(d, _mcu(), "+3V3", "GND", package="C_0805")
    caps = block.components[1:]
    assert {c.footprint.lib_id for c in caps} == {
        "Capacitor_SMD:C_0805_2012Metric"}


def test_decoupling_rejects_unknown_package():
    with pytest.raises(ValueError, match="unknown C package"):
        decoupling(Design("bad"), _mcu(), "+3V3", "GND", package="C_9999")


# --- the merged-rail short --------------------------------------------------
#
# _power_pins() returns every PinRole.POWER / non-ground POWER_IN pin, and
# decoupling() tied all of them to the one `rail`. Real cases in the seed
# library alone: STM32F411CEU6 ties VBAT + VDDA + VDD_1..4, NEO-6M ties
# V_BCKP to VCC. The hazard is not theoretical: on a bare ESP32-S3, VDD_SPI
# is driven from VDD3P3_RTC through 14 ohm and is eFuse/GPIO45-selectable
# 1.8 V or 3.3 V (DS Table 7 "VDD_SPI Voltage Control"), so hard-tying it to
# 3V3 back-drives the internal flash LDO and destroys the 1.8 V option.
# PWR-003(b) in src/ecad/rules/power.py reports the same merge at design
# level.

def _bare_s3() -> Component:
    """The bare ESP32-S3 die, not the WROOM-1 module: five distinct supply
    pin names (VDD3P3, VDD3P3_RTC, VDD3P3_CPU, VDD_SPI, VDDA)."""
    return registry_get("ESP32-S3")()


def test_decoupling_refuses_to_merge_distinct_supply_pins():
    d = Design("bare-s3")
    with pytest.raises(ValueError) as excinfo:
        decoupling(d, _bare_s3(), "+3V3", "GND")
    message = str(excinfo.value)
    # It must LIST what it found, not just say no.
    for name in ("VDD3P3", "VDD3P3_RTC", "VDD3P3_CPU", "VDD_SPI", "VDDA"):
        assert name in message, message
    assert "pins=" in message, message


def test_decoupling_explicit_pins_override_the_refusal():
    """``pins=`` is the caller taking responsibility, and it still works."""
    d = Design("bare-s3-explicit")
    chip = _bare_s3()
    targets = [p for p in chip.pins if p.name == "VDD3P3"]
    block = decoupling(d, chip, "+3V3", "GND", pins=targets, bulk=None)
    netlist = d.intended_netlist()
    assert {"U1:2", "U1:3"} <= netlist["+3V3"], netlist
    # VDD_SPI (pad 29) is NOT swept onto the rail.
    assert "U1:29" not in netlist["+3V3"], netlist
    assert len(block.components) == 3      # the IC + two 100nF


def test_decoupling_rail_name_selects_its_own_supply_pins():
    """Naming the rail after the pin is the other way to disambiguate."""
    d = Design("bare-s3-vdd-spi")
    chip = _bare_s3()
    decoupling(d, chip, "VDD_SPI", "GND", bulk=None)
    netlist = d.intended_netlist()
    assert netlist["VDD_SPI"] == {"U1:29", "C1:1"}, netlist


def test_decoupling_still_works_on_a_single_rail_part():
    """The WROOM-1 module has one supply pin name (3V3), so nothing to
    disambiguate — the reference design must keep building."""
    d = Design("wroom-single-rail")
    decoupling(d, _mcu(), "+3V3", "GND")
    _no_errors(d)
    assert d.intended_netlist()["+3V3"] == {"U1:2", "C1:1", "C2:1"}


def test_decoupling_with_no_free_power_pin_raises():
    d = Design("busy")
    mcu = _mcu()
    d.add(mcu)
    d.net("VDD_OTHER").connect(mcu.V3V3)   # already committed elsewhere
    with pytest.raises(ValueError, match="no power pin"):
        decoupling(d, mcu, "+3V3", "GND")


# ---------------------------------------------------------------------------
# en_reset_rc
# ---------------------------------------------------------------------------

def test_en_reset_rc_alone():
    d = Design("en-rc-only")
    mcu = _rails(d, _mcu())
    block = en_reset_rc(d, mcu.EN, "+3V3", "GND")

    _no_errors(d)
    _refs_unique(d)
    assert d.intended_netlist() == {
        "+3V3": {"U1:2", "R1:1"},
        "GND": {"U1:1", "U1:40", "U1:41", "C1:2"},
        "EN": {"U1:3", "R1:2", "C1:1"},
    }
    assert block.refs == ("R1", "C1")
    assert [c.value for c in block.components] == ["10k", "1uF"]
    assert sorted(block.nets) == ["en", "gnd", "rail"]


def test_en_reset_rc_defaults_are_the_cited_values():
    """The guideline text says R = 10 kOhm and C = 1 uF for the RC delay."""
    params = inspect.signature(en_reset_rc).parameters
    assert params["r"].default == "10k"
    assert params["c"].default == "1uF"


def test_en_reset_rc_provenance_and_notes():
    d = Design("prov")
    mcu = _rails(d, _mcu())
    block = en_reset_rc(d, mcu.EN, "+3V3", "GND")
    assert block.provenance.section == "Chip Power-up and Reset Timing"
    assert block.provenance.url.startswith("https://docs.espressif.com/")
    assert any("10 kOhm" in n and "1 uF" in n for n in block.notes)
    assert any("10 ms" in n for n in block.notes)


def test_en_reset_rc_accepts_a_bare_net_name():
    """Without a pin, the block still builds the RC on a named net."""
    d = Design("named")
    mcu = _rails(d, _mcu())
    d.net("EN").connect(mcu.EN)
    block = en_reset_rc(d, "EN", "+3V3", "GND")
    _no_errors(d)
    assert block.nets["en"] is d.net("EN")


# ---------------------------------------------------------------------------
# pull_resistor
# ---------------------------------------------------------------------------

def test_pull_up_alone():
    d = Design("pullup-only")
    mcu = _rails(d, _mcu())
    block = pull_resistor(d, mcu.gpio(0), "+3V3", net_name="IO0")

    _no_errors(d)
    _refs_unique(d)
    assert d.intended_netlist() == {
        "+3V3": {"U1:2", "R1:1"},
        "GND": {"U1:1", "U1:40", "U1:41"},
        "IO0": {"U1:27", "R1:2"},
    }
    assert block.refs == ("R1",)
    assert block.components[0].value == "10k"


def test_pull_down_alone():
    d = Design("pulldown-only")
    mcu = _rails(d, _mcu(), tie_en=True)
    pull_resistor(d, mcu.gpio(46), "GND", value="4.7k", net_name="IO46")
    _no_errors(d)
    _refs_unique(d)
    assert d.intended_netlist() == {
        "+3V3": {"U1:2", "U1:3"},
        "GND": {"U1:1", "U1:40", "U1:41", "R1:1"},
        "IO46": {"U1:16", "R1:2"},
    }


def test_pull_resistor_is_honest_about_its_value():
    """The guideline recommends a GPIO0 pull-up but states no resistance."""
    d = Design("prov")
    mcu = _rails(d, _mcu())
    block = pull_resistor(d, mcu.gpio(0), "+3V3", net_name="IO0")
    assert block.provenance.section == "Strapping Pins"
    assert any(n.startswith("NOT VERIFIED") for n in block.notes)


def test_pull_resistor_refuses_to_pull_a_net_to_itself():
    d = Design("silly")
    _rails(d, _mcu())
    with pytest.raises(ValueError, match="cannot be pulled to itself"):
        pull_resistor(d, "+3V3", "+3V3")


# ---------------------------------------------------------------------------
# ldo_regulator
# ---------------------------------------------------------------------------

def test_ldo_regulator_alone():
    d = Design("ldo-only")
    block = ldo_regulator(d, "VBUS", "+3V3", "GND", part="AP2112K-3.3")

    _no_errors(d)
    _refs_unique(d)
    # Pad 3 (EN) is tied to VIN — always-on. Pad 4 is NC and stays floating.
    assert d.intended_netlist() == {
        "VBUS": {"U1:1", "U1:3", "C1:1"},
        "+3V3": {"U1:5", "C2:1"},
        "GND": {"U1:2", "C1:2", "C2:2"},
    }
    assert block.refs == ("U1", "C1", "C2")
    assert sorted(block.nets) == ["gnd", "vin", "vout"]


def test_ldo_regulator_cites_the_part_datasheet():
    d = Design("prov")
    block = ldo_regulator(d, "VBUS", "+3V3", "GND", part="AP2112K-3.3")
    assert "AP2112" in block.provenance.source
    assert block.provenance.url.endswith("AP2112.pdf")
    # The datasheet minimum is 1 uF; the 10 uF default exceeds it on purpose
    # and the block says so rather than pretending 10 uF is the cited value.
    assert any("1 uF ceramic" in n for n in block.notes)
    assert any("deliberately exceed" in n for n in block.notes)
    assert any(n.startswith("NOT VERIFIED") for n in block.notes)


def test_ldo_regulator_datasheet_capacitor_values():
    d = Design("min-caps")
    block = ldo_regulator(d, "VBUS", "+3V3", "GND", part="AP2112K-3.3",
                          cin="1uF", cout="1uF")
    assert [c.value for c in block.components[1:]] == ["1uF", "1uF"]
    _no_errors(d)


def test_ldo_regulator_refuses_to_invent_a_part():
    d = Design("nope")
    with pytest.raises(MissingPartError) as excinfo:
        ldo_regulator(d, "VBUS", "+3V3", "GND", part="NoSuchLDO-1234")
    assert excinfo.value.lib_id == "NoSuchLDO-1234"
    assert d.components == [] and d.nets == []


def test_ldo_regulator_rejects_a_part_with_no_output():
    d = Design("not-a-regulator")
    with pytest.raises(ValueError, match="no power_out pin"):
        ldo_regulator(d, "VBUS", "+3V3", "GND", part=MODULE)
    assert d.components == []


# --- the VIN-to-GND short ---------------------------------------------------
#
# This block advertises itself as generic over ``part``, but it classified a
# regulator's ground pin by NAME (GND*/VSS*/PAD_GND/EP_ or group=="ground",
# in src/pipeline/ecad_bridge._infer_role) and wired every *other* POWER_IN
# pin to VIN as a fall-through. AP2112K-3.3 is safe only because its ground
# pin happens to be called "GND". A regulator whose ground pin is typed
# power_in and named AGND / PGND / 0V / COM / SUB gets its ground welded to
# VIN — a dead short that every structural gate passes, because the netlist
# matches the (wrong) intent exactly. Complementary evidence: PWR-003(a) in
# src/ecad/rules/power.py reports the same short at design level.

#: SOT-23-5 LDO, AP2112 pinout, ground pin named "AGND" — which
#: ``_infer_role`` does not recognise, so the model types it power_in/POWER.
_AGND_LDO = (
    pinspec("1", "VIN", "power_in", "power"),
    pinspec("2", "AGND", "power_in", "power"),
    pinspec("3", "EN", "input", "control"),
    pinspec("4", "NC", "no_connect", "nc"),
    pinspec("5", "VOUT", "power_out", "power"),
)


@pytest.mark.parametrize("gnd_name", ["AGND", "PGND", "0V", "COM", "SUB"])
def test_ldo_regulator_refuses_to_wire_an_unclassifiable_power_in_pin(
        monkeypatch, gnd_name):
    """A ground pin the part model failed to role must ABORT, not reach VIN."""
    specs = tuple(pinspec(p.pad, gnd_name if p.name == "AGND" else p.name,
                          p.etype, p.role)
                  for p in _AGND_LDO)
    _serve(monkeypatch, "MisroledLDO", _fake_part("MisroledLDO", specs))

    d = Design("agnd-ldo")
    with pytest.raises(ValueError) as excinfo:
        ldo_regulator(d, "VBUS", "+3V3", "GND", part="MisroledLDO")
    message = str(excinfo.value)
    assert gnd_name in message, message          # names the pin
    assert "MisroledLDO" in message, message     # names the part
    # All-or-nothing: nothing was registered and no net was created.
    assert d.components == [] and d.nets == []


def test_ldo_regulator_refuses_an_unknown_power_in_pin_name(monkeypatch):
    """Not only ground-looking names: anything it cannot positively call the
    input supply is refused rather than guessed onto VIN."""
    specs = tuple(pinspec(p.pad, "VMYSTERY" if p.name == "AGND" else p.name,
                          p.etype, p.role)
                  for p in _AGND_LDO)
    _serve(monkeypatch, "MysteryLDO", _fake_part("MysteryLDO", specs))

    d = Design("mystery-ldo")
    with pytest.raises(ValueError, match="VMYSTERY"):
        ldo_regulator(d, "VBUS", "+3V3", "GND", part="MysteryLDO")
    assert d.components == [] and d.nets == []


def test_ldo_regulator_wires_a_correctly_roled_ground_whatever_its_name(
        monkeypatch):
    """The role is the contract. A pin roled GROUND goes to GND even when
    its name is one this block would otherwise refuse."""
    specs = tuple(pinspec(p.pad, "PGND" if p.name == "AGND" else p.name,
                          p.etype, "ground" if p.name == "AGND" else p.role)
                  for p in _AGND_LDO)
    _serve(monkeypatch, "PGNDLDO", _fake_part("PGNDLDO", specs))

    d = Design("pgnd-ldo")
    ldo_regulator(d, "VBUS", "+3V3", "GND", part="PGNDLDO")
    netlist = d.intended_netlist()
    assert "U1:2" in netlist["GND"], netlist
    assert "U1:2" not in netlist["VBUS"], netlist


# ---------------------------------------------------------------------------
# Missing-part contract
# ---------------------------------------------------------------------------

def test_missing_part_error_names_the_lib_id():
    with pytest.raises(MissingPartError) as excinfo:
        blocks_mod._registry_class("Device:DefinitelyNotAPart",
                                   needed_by="a test")
    err = excinfo.value
    assert err.lib_id == "Device:DefinitelyNotAPart"
    assert "Device:DefinitelyNotAPart" in str(err)
    assert "a test" in str(err)


@pytest.mark.parametrize("lib_id", ["Switch:SW_Push", "Device:LED"])
def test_the_parts_these_blocks_need_are_served_by_the_registry(lib_id):
    """Stage F1 generated both; the registry — not a pipeline fallback —
    serves them, which is what let the xfail markers below come off."""
    cls = blocks_mod._registry_class(lib_id, needed_by="a test")
    assert cls.lib_id == lib_id
    assert cls.footprint is not None, "a generated part carries a footprint"


def test_a_block_still_refuses_to_invent_a_part():
    """The all-or-nothing contract survives F1: an uncatalogued part raises
    before the design is touched."""
    d = Design("nope")
    with pytest.raises(MissingPartError) as excinfo:
        ldo_regulator(d, "VBUS", "+3V3", "GND", part="Switch:NoSuchSwitch")
    assert excinfo.value.lib_id == "Switch:NoSuchSwitch"
    assert d.components == [] and d.nets == []


# ---------------------------------------------------------------------------
# Stage F1 landed — these were xfail(raises=MissingPartError) until the
# generated Device:LED / Switch:SW_Push arrived in src/ecad/library/generic/
# ---------------------------------------------------------------------------

def test_push_button_alone():
    d = Design("button-only")
    mcu = _rails(d, _mcu(), tie_en=True)
    block = push_button(d, mcu.gpio(0), "GND", net_name="IO0")

    _no_errors(d)
    _refs_unique(d)
    sw = block.components[0]
    assert d.intended_netlist() == {
        "+3V3": {"U1:2", "U1:3"},
        "GND": {"U1:1", "U1:40", "U1:41", f"{sw.ref}:2"},
        "IO0": {"U1:27", f"{sw.ref}:1"},
    }
    assert block.provenance.source.startswith("Espressif ESP32-S3-DevKitC-1")
    assert sorted(block.nets) == ["gnd", "net"]


def test_push_button_with_series_resistor_and_debounce():
    d = Design("button-rc")
    mcu = _rails(d, _mcu(), tie_en=True)
    block = push_button(d, mcu.gpio(0), "GND", series_r="470R",
                        debounce_c="100nF", net_name="IO0")
    _no_errors(d)
    values = [getattr(c, "value", None) for c in block.components]
    assert "470R" in values and "100nF" in values


def test_indicator_led_alone():
    d = Design("led-only")
    _rails(d, _mcu(), tie_en=True)
    block = indicator_led(d, "+3V3", "GND", color="green")

    _no_errors(d)
    _refs_unique(d)
    res, led = block.components
    assert res.value == "270R"
    assert any("270" in n and "E24" in n for n in block.notes)
    # The resistor sits on the rail side; the LED's ANODE (Device:LED pad 2)
    # faces the resistor and the CATHODE (pad 1) goes to GND.
    assert d.intended_netlist() == {
        "+3V3": {"U1:2", "U1:3", f"{res.ref}:1"},
        "+3V3_LED": {f"{res.ref}:2", f"{led.ref}:2"},
        "GND": {"U1:1", "U1:40", "U1:41", f"{led.ref}:1"},
    }


# --- the positional polarity fallback ---------------------------------------
#
# _named_pin(led, ("A", "ANODE", "+"), fallback=1) resolved to comp.pins[1] —
# an index into the DECLARATION ORDER of _PIN_SPECS, not comp.pin_by_pad("2").
# The generated Device:LED happens to declare pad 1 (K) first, so pins[1] is
# the anode by luck. Reverse the declaration order and the same code wires the
# diode backwards — exactly the failure its own docstring warns about.

#: A Device:LED-shaped part with unhelpful pin names (so the name lookup
#: misses and the fallback is what decides polarity) declared ANODE-FIRST.
_REVERSED_LED = (
    pinspec("2", "~", "passive", "passive"),
    pinspec("1", "~", "passive", "passive"),
)


def test_indicator_led_polarity_is_resolved_by_pad_not_position(monkeypatch):
    """Pad 2 is the anode and pad 1 the cathode however the part declares
    them: the KiCad Device:LED contract is about PADS."""
    cls = _fake_part("ReversedLED", _REVERSED_LED, prefix="D")
    assert cls().pins[1].pad == "1", "the fixture must be declared anode-first"
    _serve(monkeypatch, "Device:LED", cls)

    d = Design("reversed-led")
    _rails(d, _mcu(), tie_en=True)
    block = indicator_led(d, "+3V3", "GND", color="green")
    res, led = block.components
    netlist = d.intended_netlist()
    assert netlist["+3V3_LED"] == {f"{res.ref}:2", f"{led.ref}:2"}, netlist
    assert f"{led.ref}:1" in netlist["GND"], netlist
    _no_errors(d)


def test_indicator_led_resistor_follows_its_parameters():
    d = Design("led-5v")
    block = indicator_led(d, "+5V", "GND", color="red", supply_v=5.0,
                          vf=1.8, current_ma=10)
    # (5.0 - 1.8) / 10 mA = 320 ohm -> nearest E24 is 330 ohm
    assert block.components[0].value == "330R"


# ---------------------------------------------------------------------------
# Composition + the engine
# ---------------------------------------------------------------------------

def _decoupled_mcu_with_reset() -> Design:
    """decoupling + en_reset_rc on a real generated module."""
    d = Design("esp32-s3-min")
    mcu = _mcu()
    decoupling(d, mcu, "+3V3", "GND")
    en_reset_rc(d, mcu.EN, "+3V3", "GND")
    return d


def test_blocks_compose_without_ref_collisions():
    d = _decoupled_mcu_with_reset()
    _no_errors(d)
    _refs_unique(d)
    assert d.intended_netlist() == {
        "+3V3": {"U1:2", "C1:1", "C2:1", "R1:1"},
        "GND": {"U1:1", "U1:40", "U1:41", "C1:2", "C2:2", "C3:2"},
        "EN": {"U1:3", "R1:2", "C3:1"},
    }


def test_every_block_carries_a_provenance():
    d = Design("all")
    mcu = _mcu()
    built = [
        decoupling(d, mcu, "+3V3", "GND"),
        en_reset_rc(d, mcu.EN, "+3V3", "GND"),
        pull_resistor(d, mcu.gpio(0), "+3V3", net_name="IO0"),
        ldo_regulator(d, "VBUS", "+3V3", "GND", part="AP2112K-3.3"),
    ]
    _no_errors(d)
    _refs_unique(d)
    for block in built:
        assert block.provenance.source, block.name
        assert block.provenance.section, block.name
        assert block.notes, block.name
        assert block.provenance.cite()


@skip_no_kicad
def test_blocks_lay_out_to_an_erc_clean_sheet(tmp_path):
    """The one non-pure test: blocks -> layout engine -> ERC 0 -> netlist.

    This is what proves the topology layer produces designs the existing
    engine can actually emit, not just objects that lint.
    """
    from src.ecad.layout.engine import emit, layout
    from src.ecad.layout.lints import lint_placed, lint_schematic_text
    from src.pipeline.roundtrip import _export_netlist, parse_kicad_netlist_xml
    from src.pipeline.validate import run_erc

    design = _decoupled_mcu_with_reset()
    placed = layout(design)
    assert lint_placed(placed) == []
    sheet = emit(placed, design)
    assert lint_schematic_text(sheet.text) == []

    sch = tmp_path / "blocks.kicad_sch"
    sch.write_text(sheet.text)
    erc = run_erc(sch)
    assert erc["success"], erc
    assert erc["errors"] == 0, erc["details"]

    xml = _export_netlist(sch, tmp_path)
    assert xml is not None, "netlist export failed"
    actual: dict[str, set[str]] = {}
    for net in parse_kicad_netlist_xml(xml)["nets"]:
        name = net["name"].lstrip("/")
        if name.startswith("unconnected-"):
            continue          # KiCad pseudo-nets for no_connect pins
        pads = {f"{n['ref']}:{n['pin']}" for n in net["nodes"]
                if not n["ref"].startswith("#")}
        if pads:
            actual[name] = pads
    assert actual == design.intended_netlist()
