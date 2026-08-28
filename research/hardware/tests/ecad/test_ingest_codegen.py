"""Tests for src/ecad/ingest/codegen.py and the src/ecad/library registry.

Real data: the official-symbol round trip uses the installed KiCad
RF_Module library (skip-guarded); the SVG smoke test uses kicad-cli
(skip-guarded). Everything else runs on a small fake part.
"""

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from src.ecad import library
from src.ecad.component import Component, sanitize_pin_name
from src.ecad.design import Design
from src.ecad.ingest.codegen import (
    ClobberError,
    auto_unit_plan,
    generate,
    part_id_for,
)
from src.ecad.model import FootprintRef, SourcingInfo, pin
from src.ecad.net import Net

_MAC_CLI = "/Applications/KiCad.app/Contents/MacOS/kicad-cli"
KICAD_CLI = (shutil.which("kicad-cli")
             or (_MAC_CLI if Path(_MAC_CLI).is_file() else "/usr/bin/kicad-cli"))


# ── fixtures ────────────────────────────────────────────────────────────────


def fake_part() -> dict:
    """Small but representative part: repeated GND, digit-leading 3V3,
    strapping pin, two COMM interfaces, GPIO with alt functions, NC."""
    return {
        "name": "FAKE-MOD-1",
        "lib_id": "Test:FAKE-MOD-1",
        "pins": [
            pin("1", "GND", "power_in", "ground"),
            pin("2", "3V3", "power_in", "power"),
            pin("3", "EN", "input", "control"),
            pin("4", "IO0", "bidirectional", "strapping", gpio=0),
            pin("5", "SPI_CLK", "output", "comm"),
            pin("6", "SPI_D", "bidirectional", "comm"),
            pin("7", "TXD0", "output", "comm"),
            pin("8", "IO4", "bidirectional", "gpio", gpio=4,
                functions=("ADC1_CH3",)),
            pin("9", "GND", "power_in", "ground"),
            pin("10", "NC", "no_connect", "nc"),
        ],
        "unit_plan": (),
        "footprint": FootprintRef("Package_SO", "SOIC-10_3.9x4.9mm_P1mm"),
        "sourcing": SourcingInfo(manufacturer="Fakespressif", mpn="FAKE-MOD-1",
                                 lcsc="C0000001",
                                 datasheet_url="https://example.com/fake.pdf"),
        "datasheet": "https://example.com/fake.pdf",
        "description": "Fake module exercising every codegen path",
        "evidence_summary": {"claims": 12, "conflicts": 0,
                             "sources": ["kicad_official", "datasheet"]},
        "provenance": {"kicad_symbol": "Test:FAKE-MOD-1"},
        "source_hashes": {"datasheet_pdf": "d" * 64},
    }


def _import_generated(py_path: Path):
    tag = hashlib.sha1(py_path.read_bytes()).hexdigest()[:10]
    name = f"gen_{py_path.stem}_{tag}"
    spec = importlib.util.spec_from_file_location(name, py_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def generated(tmp_path):
    return generate(fake_part(), tmp_path)


# ── artifact set + generated class ──────────────────────────────────────────


def test_generate_writes_all_four_artifacts(generated):
    assert generated.part_id == "fake_mod_1"
    assert generated.class_name == "FAKE_MOD_1"
    for path in (generated.py_path, generated.sidecar_path,
                 generated.sym_path, generated.md_path):
        assert path.is_file(), path


def test_generated_header_marks_do_not_edit(generated):
    text = generated.py_path.read_text()
    head = "\n".join(text.splitlines()[:6])
    assert "GENERATED" in head and "DO NOT EDIT" in head
    assert "fake_mod_1_overrides.py" in head


def test_accessors_cover_every_pin(generated):
    mod = _import_generated(generated.py_path)
    cls = mod.FAKE_MOD_1
    comp = cls()
    # every distinct pin name is reachable through its sanitized accessor,
    # and the accessor is an explicit @property (not __getattr__ fallback)
    specs = fake_part()["pins"]
    names = {s.name for s in specs}
    for name in names:
        ident = sanitize_pin_name(name)
        assert isinstance(vars(cls)[ident], property), ident
        got = getattr(comp, ident)
        expected_pads = {s.pad for s in specs if s.name == name}
        got_pads = ({p.pad for p in got} if isinstance(got, tuple)
                    else {got.pad})
        assert got_pads == expected_pads, name
    # spot checks: single, tuple (repeated name), V-prefixed digit name
    assert comp.EN.pad == "3"
    assert isinstance(comp.GND, tuple) and len(comp.GND) == 2
    assert comp.V3V3.pad == "2"
    assert comp.IO4.spec.functions == ("ADC1_CH3",)


def test_accessor_properties_raise_keyerror_internally(generated):
    # a broken @property raising AttributeError would be masked by
    # Component.__getattr__; codegen accessors go through dict access
    text = generated.py_path.read_text()
    assert "self._pin(" in text and "self._pins_named(" in text
    assert "getattr" not in text


def test_auto_unit_plan_grouping(generated):
    mod = _import_generated(generated.py_path)
    plan = mod.FAKE_MOD_1.unit_plan
    assert [u.name for u in plan] == [
        "Power", "Control", "SPI", "TXD", "Strapping", "GPIO"]
    by_name = {u.name: u.pads for u in plan}
    assert by_name["Power"] == ("1", "2", "9")
    assert by_name["Control"] == ("3",)
    assert by_name["SPI"] == ("5", "6")
    assert by_name["TXD"] == ("7",)
    assert by_name["Strapping"] == ("4",)
    assert by_name["GPIO"] == ("8", "10")
    # helper is pure + deterministic
    assert auto_unit_plan(tuple(fake_part()["pins"])) == plan


def test_generated_class_works_in_a_design(generated):
    mod = _import_generated(generated.py_path)
    comp = mod.FAKE_MOD_1()
    d = Design("codegen-smoke")
    d.add(comp)
    assert comp.ref == "U1"
    Net("3V3").connect(comp.V3V3, comp.EN)
    Net("GND").connect(comp.GND)  # tuple accessor connects both pads
    netlist = d.intended_netlist()
    assert netlist["GND"] == {"U1:1", "U1:9"}
    assert netlist["3V3"] == {"U1:2", "U1:3"}
    assert isinstance(d.check(), list)


# ── sidecar + regen behavior ────────────────────────────────────────────────


def test_sidecar_records_provenance_and_py_hash(generated):
    sidecar = json.loads(generated.sidecar_path.read_text())
    actual = hashlib.sha256(generated.py_path.read_bytes()).hexdigest()
    assert sidecar["generated"]["py_sha256"] == actual
    assert sidecar["evidence_summary"]["conflicts"] == 0
    assert sidecar["provenance"] == {"kicad_symbol": "Test:FAKE-MOD-1"}
    assert sidecar["source_hashes"] == {"datasheet_pdf": "d" * 64}
    assert sidecar["footprint"]["lib"] == "Package_SO"
    assert sidecar["sourcing"]["lcsc"] == "C0000001"
    assert sidecar["pin_count"] == 10


def test_regen_is_byte_identical(generated, tmp_path):
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    result = generate(fake_part(), tmp_path)
    assert result == generated
    after = {p: p.read_bytes() for p in tmp_path.iterdir()}
    assert before == after


def test_hand_edit_aborts_regen(generated, tmp_path):
    generated.py_path.write_text(
        generated.py_path.read_text() + "\n# sneaky local fix\n")
    with pytest.raises(ClobberError, match="fake_mod_1_overrides.py"):
        generate(fake_part(), tmp_path)


def test_missing_sidecar_aborts_regen(generated, tmp_path):
    generated.sidecar_path.unlink()
    with pytest.raises(ClobberError, match="fake_mod_1_overrides.py"):
        generate(fake_part(), tmp_path)


# ── markdown doc ────────────────────────────────────────────────────────────


def test_md_has_pin_table_strapping_and_evidence(generated):
    md = generated.md_path.read_text()
    assert "| Pad | Name | Type | Role | GPIO | Functions |" in md
    assert "| 3 | EN | input | control |" in md
    assert "| 8 | IO4 | bidirectional | gpio | 4 | ADC1_CH3 |" in md
    assert "### Unit 1: Power" in md
    assert "## Strapping warnings" in md and "`IO0` (pad 4)" in md
    assert "**conflicts**: 0" in md
    assert "https://www.lcsc.com/product-detail/C0000001.html" in md


# ── registry: discovery + overrides ─────────────────────────────────────────


@pytest.fixture
def registered(generated, tmp_path):
    library.add_search_path(tmp_path)
    library.clear_cache()
    yield generated
    library.remove_search_path(tmp_path)
    library.clear_cache()


def test_registry_serves_generated_class(registered):
    for key in ("FAKE-MOD-1", "Test:FAKE-MOD-1", "fake_mod_1"):
        cls = library.get(key)
        assert issubclass(cls, Component)
        assert cls.part_name == "FAKE-MOD-1"
    with pytest.raises(KeyError):
        library.get("NO-SUCH-PART")


def test_registry_applies_refine_override(registered, tmp_path):
    (tmp_path / "fake_mod_1_overrides.py").write_text(
        "def refine(cls):\n"
        "    class FAKE_MOD_1_Tuned(cls):\n"
        "        description = 'tuned by overrides'\n"
        "    return FAKE_MOD_1_Tuned\n")
    library.clear_cache()
    cls = library.get("FAKE-MOD-1")
    assert cls.description == "tuned by overrides"
    assert cls().EN.pad == "3"  # generated behavior intact


def test_registry_serves_override_subclass(registered, tmp_path):
    # the registry injects the generated class into the overrides module
    # under its own name, so a subclass override needs no imports at all
    (tmp_path / "fake_mod_1_overrides.py").write_text(
        "class FAKE_MOD_1(FAKE_MOD_1):  # noqa: F821 (injected by registry)\n"
        "    description = 'subclassed by overrides'\n")
    library.clear_cache()
    cls = library.get("fake_mod_1")
    assert cls.description == "subclassed by overrides"
    base = cls.__mro__[1]
    assert base is not cls and base.part_name == "FAKE-MOD-1"
    comp = cls()
    assert isinstance(comp.GND, tuple) and comp.V3V3.pad == "2"


# ── .kicad_sym: kicad-cli SVG smoke (skip-guarded) ──────────────────────────


@pytest.mark.skipif(not Path(KICAD_CLI).is_file(),
                    reason="kicad-cli not available")
def test_kicad_sym_exports_svg(generated, tmp_path):
    svg_dir = tmp_path / "svg"
    r = subprocess.run(
        [KICAD_CLI, "sym", "export", "svg", str(generated.sym_path),
         "-o", str(svg_dir)],
        capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-400:]
    assert list(svg_dir.glob("*.svg"))


# ── real data: official ESP32-S3-WROOM-1 symbol round trip ──────────────────


def test_official_esp32s3_symbol_roundtrip(tmp_path):
    from src.ecad.footprints import kicad_share_dir
    from src.ecad.ingest.kicad_official import load_official_symbol

    if not (kicad_share_dir() / "symbols" / "RF_Module.kicad_sym").is_file():
        pytest.skip("installed KiCad symbol libraries not available")
    official = load_official_symbol("RF_Module:ESP32-S3-WROOM-1")
    if official is None:
        pytest.skip("RF_Module:ESP32-S3-WROOM-1 not in installed libraries")

    fp_lib, fp_name = official.footprint.split(":", 1)
    part = {
        "name": official.name,
        "lib_id": official.lib_id,
        "pins": list(official.pins),
        "unit_plan": (),
        "footprint": FootprintRef(fp_lib, fp_name),
        "sourcing": SourcingInfo(manufacturer="Espressif",
                                 mpn="ESP32-S3-WROOM-1"),
        "datasheet": official.datasheet,
        "description": official.description,
        "evidence_summary": {"claims": len(official.pins), "conflicts": 0,
                             "sources": ["kicad_official"]},
    }
    result = generate(part, tmp_path)
    assert result.part_id == part_id_for("ESP32-S3-WROOM-1") == "esp32_s3_wroom_1"
    mod = _import_generated(result.py_path)
    comp = mod.ESP32_S3_WROOM_1()
    assert len(comp.pins) == 41  # factory acceptance: 41 pads accessible
    assert comp.pin("EN").etype.value == "input"
    assert comp.V3V3.name == "3V3"
    assert isinstance(comp.GND, tuple)
    for spec in official.pins:  # accessors == pins, on real data
        got = comp.pin(spec.pad)
        assert got.name == spec.name and got.etype is spec.etype
    md = result.md_path.read_text()
    assert "| Pad | Name | Type | Role | GPIO | Functions |" in md
