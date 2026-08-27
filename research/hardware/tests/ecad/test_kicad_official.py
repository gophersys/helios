"""Official-symbol ingestion against the real installed KiCad 10 libraries."""

import pytest

from src.ecad.footprints import kicad_share_dir
from src.ecad.ingest.kicad_official import OfficialLibrary, load_official_symbol
from src.ecad.model import ElectricalType

pytestmark = pytest.mark.skipif(
    not kicad_share_dir().is_dir(), reason="KiCad share dir not installed"
)


def test_esp32_s3_wroom_1():
    sym = load_official_symbol("RF_Module:ESP32-S3-WROOM-1")
    assert sym is not None
    assert sym.footprint == "RF_Module:ESP32-S3-WROOM-1"
    assert 40 <= len(sym.pins) <= 42
    by_pad = {p.pad: p for p in sym.pins}
    assert by_pad["1"].name == "GND"
    assert by_pad["2"].name == "3V3"
    assert by_pad["3"].name == "EN"
    assert by_pad["2"].etype is ElectricalType.POWER_IN
    assert sym.datasheet.startswith("http")


def test_bare_soc_esp32_s3():
    sym = load_official_symbol("MCU_Espressif:ESP32-S3")
    assert sym is not None
    assert 56 <= len(sym.pins) <= 58  # QFN-56 + EP
    assert "Package_DFN_QFN:QFN-56" in sym.footprint


def test_extends_resolution():
    lib = OfficialLibrary.open("RF_Module")
    derived = [n for n in lib.names() if lib.get(n).extends]
    assert derived, "expected at least one derived symbol in RF_Module"
    d = lib.get(derived[0])
    assert d.pins, "derived symbol must inherit parent pins"


def test_missing_symbol_returns_none():
    assert load_official_symbol("RF_Module:DOES-NOT-EXIST") is None
    assert load_official_symbol("NoSuchLib:Part") is None
    assert load_official_symbol("no-colon") is None


# ── regressions from the adversarial review ─────────────────────────────────


def test_multi_level_extends_resolves_to_grandparent_pins():
    """A derived symbol whose parent is itself derived must still get pins.

    INA281A2 -> INA281A1 -> AD8211. Resolving only one hop left pin_source on
    INA281A1, which defines no units, so the symbol came back with pins=().
    177 installed symbols are multi-level like this.
    """
    sym = load_official_symbol("Amplifier_Current:INA281A2")
    assert sym is not None
    assert len(sym.pins) == 5, "must inherit AD8211's pins through INA281A1"
    # properties resolve through the chain too
    assert sym.footprint, "footprint must be inherited from an ancestor"


def test_unnamed_pins_do_not_raise():
    """KiCad writes (name "") for unnamed pins — 12% of installed symbols.

    PinSpec requires a non-empty name, so these used to raise ValueError out
    of load_official_symbol, whose contract is `OfficialSymbol | None`.
    """
    sym = load_official_symbol("4xxx:4011")
    assert sym is not None
    assert len(sym.pins) == 14
    assert all(p.name for p in sym.pins), "every pin needs a usable name"
    # unnamed pins fall back to their pad, which is unique
    pads = [p.pad for p in sym.pins]
    assert len(pads) == len(set(pads))


def test_no_symbol_in_a_logic_library_raises():
    """Sweep a library that is entirely unnamed-pin parts."""
    lib = OfficialLibrary.open("4xxx")
    for name in lib.names()[:40]:
        sym = lib.get(name)          # must not raise
        assert sym.pins, f"{name} resolved to zero pins"


def test_cyclic_extends_is_reported():
    """A cycle must raise a clear KeyError, not loop forever."""
    lib = OfficialLibrary.open("4xxx")

    class Fake:
        def __init__(self, ext):
            self.extends = ext
            self.units = []
            self.properties = []

    lib._by_name = {"A": Fake("B"), "B": Fake("A")}
    with pytest.raises(KeyError, match="cyclic"):
        lib.get("A")
