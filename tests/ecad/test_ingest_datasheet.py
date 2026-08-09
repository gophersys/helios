"""Datasheet section finder + gated extraction, against the REAL 15 PDFs.

Section-finder expectations are the validated survey table in
``data/datasheets/SECTIONS.md`` (pdftotext page indices, 1-based).
Extraction is tested with a fake runner returning canned JSON — no live
LLM calls ever happen in this suite.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from src.ecad.ingest import datasheet as ds
from src.ecad.model import ElectricalType, PinRole

# data/ is gitignored: prefer this checkout's copy, fall back to the main
# working tree (worktree agents read real data from the main repo).
_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "data" / "datasheets",
    Path("/Users/mateo/code/hardware/data/datasheets"),
]
DATASHEETS = next((p for p in _CANDIDATES if p.is_dir()), _CANDIDATES[0])

needs_real_pdfs = pytest.mark.skipif(
    not (DATASHEETS.is_dir() and shutil.which("pdftotext")),
    reason="requires data/datasheets/ PDFs and pdftotext (poppler)",
)


# -------------------------------------------------------------------------
# PageRange (no external deps)
# -------------------------------------------------------------------------

def test_page_range_basics():
    r = ds.PageRange(10, 15)
    assert list(r.pages()) == [10, 11, 12, 13, 14, 15]
    assert r.count == 6


@pytest.mark.parametrize("start,end", [(0, 5), (5, 4), (-1, -1)])
def test_page_range_rejects_invalid(start, end):
    with pytest.raises(ValueError):
        ds.PageRange(start, end)


def test_find_sections_missing_file():
    with pytest.raises(FileNotFoundError):
        ds.find_sections(Path("/nonexistent/nope.pdf"))


# -------------------------------------------------------------------------
# Section finder vs the SECTIONS.md ground-truth table
# -------------------------------------------------------------------------

# (file, pins, strapping, electrical, peripherals-or-None) — all 15 PDFs.
# Representative structural families called out inline.
SURVEY = [
    # slim module template: strapping is subsection 3.3, no peripherals chapter
    ("esp32-s3-wroom-1.pdf", (10, 15), (13, 15), (16, 25), None),
    # legacy oddball: strapping = 2.3 inside pins, single-page peripherals table
    ("esp32-wroom-32.pdf", (8, 11), (10, 11), (14, 16), (13, 13)),
    # the one English datasheet (modern chip template)
    ("esp32-c3.pdf", (12, 25), (26, 28), (50, 54), (42, 47)),
    # full module template: top-level 启动配置项 and 外设 chapters
    ("esp32-c3-wroom-02.pdf", (10, 11), (12, 14), (20, 22), (15, 19)),
    # legacy chip: rotated logo-header pin pages, scattered 数字外设 peripherals
    ("esp32.pdf", (12, 21), (22, 25), (50, 56), (36, 49)),
    # remaining seed parts (same templates as above)
    ("esp32-wroom-32e.pdf", (10, 12), (13, 16), (26, 27), (17, 25)),
    ("esp32-s2-wroom.pdf", (9, 13), (11, 13), (14, 19), None),
    ("esp32-s3-mini-1.pdf", (10, 15), (13, 15), (16, 25), None),
    ("esp32-c3-mini-1.pdf", (10, 11), (12, 14), (20, 22), (15, 19)),
    ("esp32-c6-wroom-1.pdf", (10, 14), (11, 14), (15, 17), None),
    ("esp32-h2-mini-1.pdf", (10, 14), (11, 14), (15, 17), None),
    ("esp32-s2.pdf", (12, 18), (17, 18), (35, 41), (21, 34)),
    ("esp32-s3.pdf", (14, 28), (29, 31), (60, 64), (46, 57)),
    ("esp32-c6.pdf", (13, 27), (28, 31), (58, 62), (44, 53)),
    ("esp32-h2.pdf", (12, 21), (22, 24), (50, 53), (39, 48)),
]


@needs_real_pdfs
@pytest.mark.parametrize("fname,pins,strapping,electrical,periph",
                         SURVEY, ids=[row[0] for row in SURVEY])
def test_find_sections_matches_survey(fname, pins, strapping, electrical, periph):
    sections = ds.find_sections(DATASHEETS / fname)
    assert (sections["pins"].start, sections["pins"].end) == pins
    assert (sections["strapping"].start, sections["strapping"].end) == strapping
    assert (sections["electrical"].start, sections["electrical"].end) == electrical
    if periph is None:
        assert "peripherals" not in sections
    else:
        got = sections["peripherals"]
        assert (got.start, got.end) == periph


# -------------------------------------------------------------------------
# Slicing: only target pages, RF tail trimmed
# -------------------------------------------------------------------------

@needs_real_pdfs
def test_slice_text_trims_rf_tail():
    pdf = DATASHEETS / "esp32-s3-wroom-1.pdf"
    sections = ds.find_sections(pdf)
    text, pages = ds._slice(pdf, sections)
    # Pins 10-15 + electrical 16-25, but the electrical tail 19-25 is RF
    # (4.5 Wi-Fi 射频 sits right at the top of p19, so p19 drops too).
    assert pages == tuple(range(10, 19))
    assert ds.slice_text(pdf, sections) == text
    # Pin table and strapping content survive
    assert "Strapping" in text
    assert "功耗特性" in text          # power consumption subsection kept
    assert "[esp32-s3-wroom-1.pdf p.10]" in text
    # RF tables are gone
    assert "Wi-Fi 射频标准" not in text
    assert "p.25]" not in text


@needs_real_pdfs
def test_slice_text_keeps_untrimmed_english_electrical():
    pdf = DATASHEETS / "esp32-c3.pdf"
    sections = ds.find_sections(pdf)
    _, pages = ds._slice(pdf, sections)
    # en chip: RF is its own chapter 6, electrical 50-54 is kept whole.
    assert pages == tuple(range(12, 29)) + tuple(range(50, 55))


def test_slice_requires_mandatory_sections():
    with pytest.raises(ds.SectionNotFound):
        ds.slice_text(Path("x.pdf"), {"pins": ds.PageRange(1, 2)})


# -------------------------------------------------------------------------
# Extraction with a fake runner (no live LLM)
# -------------------------------------------------------------------------

GOOD_JSON = {
    "chip_name": "ESP32-S3-WROOM-1",
    "manufacturer": "Espressif",
    "description": "Wi-Fi + Bluetooth LE module based on ESP32-S3",
    "package": "SMD-41",
    "pins": [
        {"number": "1", "name": "GND", "type": "P", "functions": [],
         "group": "Power"},
        {"number": "2", "name": "3V3", "type": "P", "functions": [],
         "group": "Power"},
        {"number": "3", "name": "EN", "type": "I", "functions": ["CHIP_EN"],
         "group": "Control"},
        {"number": "4", "name": "IO4", "type": "I/O/T",
         "functions": ["ADC1_CH3", "TOUCH4"], "group": "GPIO"},
    ],
    "power": {"voltage_min": 3.0, "voltage_typ": 3.3, "voltage_max": 3.6,
              "power_pins": ["3V3", "GND"],
              "decoupling_caps": [{"value": "10uF", "purpose": "bulk"}]},
    "strapping": {"pins": ["IO0", "IO3", "IO45", "IO46"],
                  "notes": ["IO0 selects the boot mode"]},
}


class RecordingRunner:
    """Injectable runner: canned responses, records prompts."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses[min(len(self.prompts), len(self.responses)) - 1]


@needs_real_pdfs
def test_extract_with_fake_runner():
    pdf = DATASHEETS / "esp32-s3-wroom-1.pdf"
    runner = RecordingRunner(["```json\n" + json.dumps(GOOD_JSON) + "\n```"])
    part = ds.extract(pdf, runner=runner)

    assert len(runner.prompts) == 1
    prompt = runner.prompts[0]
    # The prompt carries ONLY the sliced pages: pin chapter in, RF tables out.
    assert "[esp32-s3-wroom-1.pdf p.10]" in prompt
    assert "Wi-Fi 射频标准" not in prompt
    assert '"pins"' in prompt and '"strapping"' in prompt

    assert part.chip_name == "ESP32-S3-WROOM-1"
    assert [p.spec.pad for p in part.pins] == ["1", "2", "3", "4"]
    gnd, v33, en, io4 = part.pins
    assert gnd.spec.role is PinRole.GROUND
    assert v33.spec.role is PinRole.POWER
    assert v33.spec.etype is ElectricalType.POWER_IN
    assert en.spec.role is PinRole.CONTROL
    assert en.spec.etype is ElectricalType.INPUT
    assert io4.spec.etype is ElectricalType.BIDIRECTIONAL
    assert io4.spec.gpio == 4
    assert io4.spec.functions == ("ADC1_CH3", "TOUCH4")
    assert io4.group == "GPIO" and io4.raw_type == "I/O/T"
    assert part.pin_specs() == tuple(p.spec for p in part.pins)

    assert part.power.voltage_typ == 3.3
    assert part.power.decoupling_caps == (ds.CapSpec("10uF", "bulk"),)
    assert part.strapping_pins == ("IO0", "IO3", "IO45", "IO46")
    assert part.strapping_notes == ("IO0 selects the boot mode",)

    prov = part.provenance
    assert prov.pdf_sha256 == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert prov.pages_used == tuple(range(10, 19))
    assert prov.page_count == 37
    assert 0.0 < prov.ratio < 0.5


@needs_real_pdfs
def test_extract_retries_then_succeeds():
    pdf = DATASHEETS / "esp32-s3-wroom-1.pdf"
    runner = RecordingRunner(["this is not JSON", json.dumps(GOOD_JSON)])
    part = ds.extract(pdf, runner=runner)
    assert len(runner.prompts) == 2
    assert part.chip_name == "ESP32-S3-WROOM-1"


@needs_real_pdfs
def test_extract_exhausts_attempts_and_raises():
    pdf = DATASHEETS / "esp32-s3-wroom-1.pdf"
    runner = RecordingRunner(["garbage forever"])
    with pytest.raises(ds.ExtractionFailed):
        ds.extract(pdf, runner=runner)
    assert len(runner.prompts) == ds.EXTRACT_ATTEMPTS


@needs_real_pdfs
def test_extract_rejects_duplicate_pads_end_to_end():
    pdf = DATASHEETS / "esp32-s3-wroom-1.pdf"
    bad = json.loads(json.dumps(GOOD_JSON))
    bad["pins"][1]["number"] = "1"  # collide with pin 1
    with pytest.raises(ds.ValidationFailed) as excinfo:
        ds.extract(pdf, runner=RecordingRunner([json.dumps(bad)]))
    assert any("duplicate pad" in p for p in excinfo.value.problems)


# -------------------------------------------------------------------------
# Validation gate (pure, no PDFs needed)
# -------------------------------------------------------------------------

def test_validate_accepts_good_candidate():
    assert ds.validate_extraction(GOOD_JSON) == []


def test_validate_rejects_non_object():
    assert ds.validate_extraction(["not", "a", "dict"]) != []


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d.pop("chip_name"), "chip_name"),
    (lambda d: d.update(pins=[]), "pins missing or empty"),
    (lambda d: d.pop("pins"), "pins missing or empty"),
    (lambda d: d["pins"][0].update(name=""), "has no name"),
    (lambda d: d["pins"][0].update(number=""), "has no number"),
    (lambda d: d["pins"][0].update(type="Z"), "unparseable type"),
    (lambda d: d["pins"][3].update(number="1"), "duplicate pad"),
    (lambda d: d["pins"][0].update(functions="ADC"), "not a string array"),
    (lambda d: d["power"].update(voltage_typ="3.3"), "not numbers"),
    (lambda d: d["power"].update(voltage_typ=2.0), "not ordered"),
    (lambda d: d.update(strapping={"pins": [1, 2]}), "strapping.pins"),
])
def test_validate_rejects_bad_candidates(mutate, needle):
    data = json.loads(json.dumps(GOOD_JSON))
    mutate(data)
    problems = ds.validate_extraction(data)
    assert any(needle in p for p in problems), problems


def test_pin_type_parsing():
    assert ds._parse_pin_type("P") is ElectricalType.POWER_IN
    assert ds._parse_pin_type("I/O/T") is ElectricalType.BIDIRECTIONAL
    assert ds._parse_pin_type("input") is ElectricalType.INPUT
    assert ds._parse_pin_type("Z") is None


def test_strip_fences():
    fenced = "```json\n{\"a\": 1}\n```"
    assert json.loads(ds._strip_fences(fenced)) == {"a": 1}
    assert ds._strip_fences('{"a": 1}') == '{"a": 1}'
