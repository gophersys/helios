"""Footprint index + resolver against the real installed KiCad 10 libraries."""

from pathlib import Path

import pytest

from src.ecad.footprints import (
    FootprintIndex,
    PackageSpec,
    kicad_share_dir,
    validate_footprint,
)
from src.ecad.model import FootprintRef

pytestmark = pytest.mark.skipif(
    not kicad_share_dir().is_dir(), reason="KiCad share dir not installed"
)

CACHE = Path(__file__).resolve().parent.parent.parent / "data" / "footprint_index.json"


@pytest.fixture(scope="module")
def index() -> FootprintIndex:
    return FootprintIndex.cached(CACHE)


def test_index_builds_and_caches(index):
    assert len(index) > 10_000
    assert CACHE.is_file()
    # reload from cache is fast and equivalent
    again = FootprintIndex.cached(CACHE)
    assert len(again) == len(index)


def test_known_module_footprint_present(index):
    info = index.get("RF_Module:ESP32-S3-WROOM-1")
    assert info is not None
    assert info.smd
    assert info.has_step
    assert "1" in info.pad_numbers and "41" in info.pad_numbers


def test_qfn56_descriptor_resolves_uniquely(index):
    spec = PackageSpec(family="QFN-56", pitch=0.4, body="7x7", ep=True)
    cands = index.candidates(spec)
    assert len(cands) >= 1
    assert all(c.lib == "Package_DFN_QFN" for c in cands)
    # With the EP size implicit there may be several EP variants; adding pad
    # count keeps it honest but QFN EPs share the count — full uniqueness needs
    # the explicit name, which resolve() enforces by failing loudly:
    if len(cands) > 1:
        with pytest.raises(LookupError, match="Ambiguous"):
            index.resolve(spec)
    else:
        assert index.resolve(spec) is cands[0]


def test_resolve_no_match_fails(index):
    with pytest.raises(LookupError, match="No installed footprint"):
        index.resolve(PackageSpec(family="QFN-999"))


def test_validate_footprint_ok(index):
    pins = {str(n) for n in range(1, 42)}  # ESP32-S3-WROOM-1 pads 1..41
    v = validate_footprint(index,
                           FootprintRef("RF_Module", "ESP32-S3-WROOM-1"), pins)
    assert v.ok, v.errors


def test_validate_footprint_missing_pin(index):
    pins = {str(n) for n in range(1, 43)}  # pad 42 does not exist
    v = validate_footprint(index,
                           FootprintRef("RF_Module", "ESP32-S3-WROOM-1"), pins)
    assert not v.ok
    assert "42" in v.errors[0]


def test_validate_footprint_unknown(index):
    v = validate_footprint(index, FootprintRef("Nope", "Missing"), {"1"})
    assert not v.ok


def test_validate_surplus_pads_rule(index):
    # A 2-pad chip resistor footprint against a 1-pin symbol: pad "2" is a
    # genuine surplus electrical pad → must fail.
    v = validate_footprint(
        index, FootprintRef("Resistor_SMD", "R_0402_1005Metric"), {"1"})
    assert not v.ok
    assert "extra pads" in v.errors[0]
