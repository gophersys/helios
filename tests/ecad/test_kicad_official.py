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
