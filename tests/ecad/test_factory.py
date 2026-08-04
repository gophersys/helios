"""Factory orchestrator tests.

Unit tests drive a fake component through the orchestration against a
temp repo (no network, no LLM, no kicad-cli — external oracles injected).
The live acceptance test drives ESP32-S3-WROOM-1 through every automated
stage against the real repo data (skipped unless kicad-cli, the installed
KiCad libraries, the cached datasheet and the pinned Zephyr trees are all
present).
"""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.pipeline.validate as validate_mod
from src.ecad import library
from src.ecad.footprints import FootprintIndex, FootprintInfo, kicad_share_dir
from src.ecad.ingest import factory
from src.ecad.ingest import zephyr as zephyr_mod
from src.ecad.ingest import crossverify
from src.ecad.ingest.crossverify import load_evidence
from src.ecad.ingest.kicad_official import OfficialSymbol
from src.ecad.ingest.state import ComponentRecord, Stage
from src.ecad.model import pin

REPO = Path(__file__).resolve().parents[2]


# ── fake-repo fixture ───────────────────────────────────────────────────────

FAKE_MANIFEST = {
    "datasheets": [
        {"chip": "WIDGET-1", "file": "widget-1.pdf", "lcsc": "C123456",
         "type": "module", "source": "test", "language": "en", "size_kb": 20},
        {"chip": "WCHIP", "file": "wchip.pdf", "lcsc": "BAD-ID",
         "type": "chip", "source": "test", "language": "en", "size_kb": 20},
    ]
}


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    monkeypatch.delenv("FACTORY_LLM", raising=False)
    repo = tmp_path / "repo"
    ds = repo / "data" / "datasheets"
    ds.mkdir(parents=True)
    (ds / "widget-1.pdf").write_bytes(b"%PDF-1.4\n" + b"0" * 20_000)
    # wchip.pdf deliberately absent AND its lcsc id malformed.
    (ds / "manifest.json").write_text(json.dumps(FAKE_MANIFEST))
    return repo


FAKE_PINS = (
    pin("1", "GND", "power_in"),
    pin("2", "3V3", "power_in"),
    pin("3", "EN", "input"),
    pin("4", "IO0", "bidirectional"),
)


def fake_official(lib_id: str) -> OfficialSymbol | None:
    if lib_id != "RF_Module:WIDGET-1":
        return None
    return OfficialSymbol(library="RF_Module", name="WIDGET-1", pins=FAKE_PINS,
                          footprint="Fake_Lib:WIDGET-1", datasheet="http://x",
                          description="fake widget", extends=None)


class FakeTree:
    def soc(self, name: str) -> zephyr_mod.SocInfo:
        return zephyr_mod.SocInfo(name=name, gpio_count=4, gpios={},
                                  signals={}, peripherals=(), strapping=(0,))


FAKE_INDEX = FootprintIndex(
    {"Fake_Lib:WIDGET-1": FootprintInfo(
        lib="Fake_Lib", name="WIDGET-1", pad_numbers=("1", "2", "3", "4"),
        pad_total=4, smd=True, has_step=True)},
    {"share_dir": "fake"})


@pytest.fixture
def wired(fake_repo, monkeypatch):
    """Fake repo with every external oracle injected."""
    monkeypatch.setattr(factory, "load_official_symbol", fake_official)
    monkeypatch.setattr(factory.zephyr_mod, "ensure", lambda repo: FakeTree())
    monkeypatch.setattr(factory, "FootprintIndex",
                        SimpleNamespace(cached=lambda path: FAKE_INDEX))
    monkeypatch.setattr(validate_mod, "run_erc",
                        lambda p: {"success": True, "errors": 0,
                                   "warnings": 0, "details": []})
    yield fake_repo
    library.remove_search_path(fake_repo / "src" / "ecad" / "library" / "espressif")
    library.clear_cache()


# ── seeding + status ────────────────────────────────────────────────────────

def test_seed_and_status(fake_repo):
    records = factory.status(fake_repo)
    assert [r.id for r in records] == ["wchip", "widget-1"]
    by_id = {r.id: r for r in records}
    good = by_id["widget-1"]
    assert good.kind == "module" and good.vendor == "espressif"
    assert good.stage is Stage.DISCOVERED
    assert good.stages[Stage.DISCOVERED].status == "passed"
    assert "widget-1.pdf cached, lcsc C123456" in \
        good.stages[Stage.DISCOVERED].gate_output
    bad = by_id["wchip"]
    assert bad.stages[Stage.DISCOVERED].status == "failed"
    assert "bad LCSC id" in bad.blocked_on()
    md = (fake_repo / "COMPONENTS.md").read_text()
    assert "| widget-1 |" in md and "| wchip |" in md


def test_status_is_stable_and_seed_idempotent(fake_repo):
    factory.status(fake_repo)
    path = ComponentRecord.path_for(fake_repo / "data" / "ingest", "widget-1")
    first = path.read_text()
    records = factory.status(fake_repo)
    assert len(records) == 2                      # no duplicate seeding
    assert path.read_text() == first              # byte-stable recompute


def test_bad_pdf_magic_fails_discovered(fake_repo):
    pdf = fake_repo / "data" / "datasheets" / "widget-1.pdf"
    pdf.write_bytes(b"not a pdf" + b"0" * 20_000)
    records = factory.status(fake_repo)
    rec = next(r for r in records if r.id == "widget-1")
    assert "not a PDF" in rec.blocked_on()


# ── extraction gating (official-symbol-first, LLM env-gated) ────────────────

def test_step_blocks_on_llm_without_official_symbol(fake_repo, monkeypatch):
    monkeypatch.setattr(factory, "load_official_symbol", lambda lib_id: None)
    factory.status(fake_repo)
    rec = factory.step("widget-1", fake_repo)
    assert rec.stage is Stage.DISCOVERED
    assert "blocked-on-llm" in rec.blocked_on()
    assert rec.meta["datasheet_status"] == "blocked-on-llm"
    # idempotent: repeating the step does not change the outcome
    again = factory.step("widget-1", fake_repo)
    assert again.blocked_on() == rec.blocked_on()


def test_official_symbol_path_satisfies_extracted_gate(wired):
    factory.status(wired)
    rec = factory.step("widget-1", wired)
    assert rec.stage is Stage.EXTRACTED
    assert rec.meta["datasheet_status"] == "blocked-on-llm"
    assert "official-symbol pins" in rec.stages[Stage.EXTRACTED].gate_output
    official = json.loads(
        (wired / "data" / "ingest" / "widget-1" / "official.json").read_text())
    assert official["footprint"] == "Fake_Lib:WIDGET-1"
    # enrichment: IO0 got its gpio number and role
    io0 = next(p for p in official["pins"] if p["name"] == "IO0")
    assert io0["gpio"] == 0 and io0["role"] == "gpio"


# ── full fake walk through every automated stage ────────────────────────────

def test_fake_component_full_walk(wired):
    factory.status(wired)
    expected = [Stage.EXTRACTED, Stage.CROSS_VERIFIED, Stage.SYMBOL_DONE,
                Stage.FOOTPRINT_RESOLVED, Stage.SOURCING_LINKED,
                Stage.VALIDATED]
    for want in expected:
        rec = factory.step("widget-1", wired)
        assert rec.stage is want, (want, rec.blocked_on())
        assert not rec.blocked_on()

    root = wired / "data" / "ingest"
    ev = load_evidence(root / "widget-1" / "evidence.json")
    assert ev.summary()["conflicts"] == 0
    assert ev.find("pad_set", "pins_vs_footprint").status == "agreed"
    assert (root / "widget-1" / "widget-1.kicad_sym").stat().st_size > 0
    assert rec.meta["footprint"] == "Fake_Lib:WIDGET-1"
    assert rec.meta["footprint_has_step"] is True
    assert rec.meta["lcsc"] == "C123456"
    assert len(rec.meta["pdf_sha256"]) == 64
    assert rec.meta["erc_errors"] == 0
    assert rec.meta["accessors"] == 4 and rec.meta["accessor_properties"] == 4
    gen = wired / "src" / "ecad" / "library" / "espressif" / "widget_1.py"
    assert gen.is_file() and (root / "widget-1" / "validate.kicad_sch").is_file()

    # approved is a human action: the step blocks, the stage holds.
    held = factory.step("widget-1", wired)
    assert held.stage is Stage.VALIDATED
    assert held.blocked_on() == "awaiting human approval"
    assert "| validated |" in (wired / "COMPONENTS.md").read_text()


# ── id mapping helpers ──────────────────────────────────────────────────────

@pytest.mark.parametrize("comp_id,soc", [
    ("esp32-s3-wroom-1", "esp32s3"),
    ("esp32-s3-mini-1", "esp32s3"),
    ("esp32-s2-wroom", "esp32s2"),
    ("esp32-c3-wroom-02", "esp32c3"),
    ("esp32-c6-wroom-1", "esp32c6"),
    ("esp32-h2-mini-1", "esp32h2"),
    ("esp32-wroom-32", "esp32"),
    ("esp32-wroom-32e", "esp32"),
    ("esp32", "esp32"),
    ("esp32-s3", "esp32s3"),
])
def test_soc_for(comp_id, soc):
    assert factory.soc_for(comp_id) == soc


def test_lib_id_for():
    module = ComponentRecord(id="esp32-s3-wroom-1", vendor="espressif",
                             kind="module", meta={"chip": "ESP32-S3-WROOM-1"})
    soc = ComponentRecord(id="esp32-s3", vendor="espressif", kind="soc",
                          meta={"chip": "ESP32-S3"})
    assert factory.lib_id_for(module) == "RF_Module:ESP32-S3-WROOM-1"
    assert factory.lib_id_for(soc) == "MCU_Espressif:ESP32-S3"


# ── live acceptance: ESP32-S3-WROOM-1 end-to-end ────────────────────────────

def _live_ready() -> bool:
    if shutil.which("kicad-cli") is None or not kicad_share_dir().is_dir():
        return False
    if not (REPO / "data" / "datasheets" / "esp32-s3-wroom-1.pdf").is_file():
        return False
    try:
        zephyr_mod.ensure(REPO)
    except Exception:
        return False
    return True


needs_live = pytest.mark.skipif(
    not _live_ready(),
    reason="needs kicad-cli, installed KiCad libs, cached datasheets and "
           "the pinned data/zephyr trees")


@needs_live
def test_acceptance_esp32_s3_wroom_1(monkeypatch):
    monkeypatch.delenv("FACTORY_LLM", raising=False)
    comp = "esp32-s3-wroom-1"
    root = REPO / "data" / "ingest"
    shutil.rmtree(root / comp, ignore_errors=True)

    records = factory.status(REPO)
    assert len(records) == 15                     # all manifest entries seeded
    rec = next(r for r in records if r.id == comp)
    assert rec.stage is Stage.DISCOVERED
    assert rec.stages[Stage.DISCOVERED].status == "passed"

    expected = [Stage.EXTRACTED, Stage.CROSS_VERIFIED, Stage.SYMBOL_DONE,
                Stage.FOOTPRINT_RESOLVED, Stage.SOURCING_LINKED,
                Stage.VALIDATED]
    for want in expected:
        rec = factory.step(comp, REPO)
        assert rec.stage is want, (want, rec.blocked_on())
        assert not rec.blocked_on()

    # extracted: official-symbol source; datasheet LLM stage env-blocked
    assert rec.meta["official_symbol"] == "RF_Module:ESP32-S3-WROOM-1"
    assert rec.meta["datasheet_status"] == "blocked-on-llm"

    # cross_verified: vs Zephyr esp32s3, zero conflicts in the ledger
    assert rec.meta["soc"] == "esp32s3"
    ev = load_evidence(root / comp / "evidence.json")
    summary = ev.summary()
    assert summary["conflicts"] == 0
    assert summary["claims"] >= 30
    assert ev.find("pad_set", "pins_vs_footprint").status == "agreed"

    # footprint: pre-linked official footprint with a STEP model
    assert rec.meta["footprint"] == "RF_Module:ESP32-S3-WROOM-1"
    assert rec.meta["footprint_has_step"] is True

    # sourcing: manifest LCSC id + cached-pdf sha (no network)
    assert rec.meta["lcsc"] == "C2913202"
    assert len(rec.meta["pdf_sha256"]) == 64

    # validated: generated class imports with 40+ typed pin accessors, ERC 0
    assert rec.meta["erc_errors"] == 0
    assert rec.meta["accessors"] >= 40
    library.clear_cache()
    cls = library.get("ESP32-S3-WROOM-1")
    inst = cls()
    assert len(inst.pins) == 41
    covered = 0
    for name, value in vars(cls).items():
        if isinstance(value, property):
            got = getattr(inst, name)
            covered += len(got) if isinstance(got, tuple) else 1
    assert covered >= 40
    assert inst.EN.pad == "3" and inst.V3V3.pad == "2"
    assert len(inst.GND) == 3
    assert cls.footprint.lib_id == "RF_Module:ESP32-S3-WROOM-1"
    assert cls.sourcing.lcsc == "C2913202"

    gen_py = REPO / "src" / "ecad" / "library" / "espressif" / "esp32_s3_wroom_1.py"
    assert gen_py.is_file()
    sidecar = json.loads(gen_py.with_suffix(".json").read_text())
    assert sidecar["evidence_summary"]["conflicts"] == 0

    md = (REPO / "COMPONENTS.md").read_text()
    assert f"| {comp} | espressif | module | validated |" in md


# ── extracted.json must carry everything the extraction produced ────────────


def test_power_survives_into_extracted_json(wired, monkeypatch):
    """datasheet.extract() produces a PowerSpec; it must reach the artifact.

    _build_extracted serialized pins and strapping but dropped `power`, so
    every downstream consumer of supply voltage and recommended decoupling
    (the PWR-004/005/007 rules) could only ever answer "no data" — not
    because the datasheet lacked it, but because the one artifact carrying it
    never wrote the field. A rule that cannot fire is a gate that cannot fail.
    """
    from src.ecad.ingest import datasheet as dsmod
    from src.ecad.ingest import factory as fac

    part = dsmod.ExtractedPart(
        chip_name="WIDGET-1", manufacturer="ACME",
        description="test part", package="QFN-8",
        pins=(), power=dsmod.PowerSpec(
            voltage_min=3.0, voltage_typ=3.3, voltage_max=3.6,
            power_pins=("2",),
            decoupling_caps=(dsmod.CapSpec("22uF", "bulk"),
                             dsmod.CapSpec("0.1uF", "hf"))),
        strapping_pins=(), strapping_notes=(),
        provenance=dsmod.Provenance(pdf_name="w.pdf", pdf_sha256="deadbeef",
                                    page_count=1, pages_used=(1,)),
    )
    monkeypatch.setenv("FACTORY_LLM", "1")
    monkeypatch.setattr(dsmod, "extract", lambda pdf: part)

    factory.status(wired)
    factory.step("widget-1", wired)

    payload = json.loads(
        (wired / "data" / "ingest" / "widget-1" / "extracted.json").read_text())
    assert "power" in payload, (
        f"extracted.json dropped the power envelope: {sorted(payload)}"
    )
    power = fac._power_from_json(payload["power"])
    assert power == part.power, "power did not survive the round trip"

    # every non-empty field the extraction produced must be represented
    assert payload["manufacturer"] == "ACME"
    assert payload["description"] == "test part"


def test_cross_verified_keeps_the_footprint_claim(wired, monkeypatch):
    """Re-running cross_verified must not erase pins_vs_footprint.

    _write_evidence rebuilds the ledger from scratch, and _build_cross_verified
    passed footprint_pads=None — so a record that had already resolved its
    footprint lost that claim on the next recompute. Nothing restored it: the
    footprint_resolved gate passes on the mere presence of meta["footprint"],
    so `factory status` re-promotes the record without re-running the
    comparison, and the symbol's pins stop being checked against the
    footprint's pads permanently.
    """
    factory.status(wired)
    for _ in range(4):                      # -> footprint_resolved
        factory.step("widget-1", wired)
    root = wired / "data" / "ingest"
    ev = load_evidence(root / "widget-1" / "evidence.json")
    assert ev.find("pad_set", "pins_vs_footprint") is not None, (
        "fixture did not reach a footprint-resolved state"
    )

    # Re-run the cross_verified builder directly, as a status recompute does.
    rec = ComponentRecord.load(root, "widget-1")
    factory._build_cross_verified(rec, factory.make_ctx(wired))

    ev2 = load_evidence(root / "widget-1" / "evidence.json")
    assert ev2.find("pad_set", "pins_vs_footprint") is not None, (
        "rebuilding evidence erased the pins-vs-footprint claim"
    )


def test_validated_refuses_to_ship_with_open_conflicts(wired):
    """Codegen must not write into src/ecad/library while the ledger is red.

    The cross_verified gate runs at a different point in time than this
    builder and `step` does not re-run it in between, so a ledger that
    regressed still produced shipped artifacts — the committed
    esp32_wroom_32e.json records conflicts=2. Once a record reaches
    `validated`, next_stage() is `approved`, which has no builder, so that
    artifact is never regenerated.
    """
    factory.status(wired)
    for _ in range(5):                      # -> sourcing_linked
        factory.step("widget-1", wired)

    root = wired / "data" / "ingest"
    ev_path = root / "widget-1" / "evidence.json"
    ev = load_evidence(ev_path)
    ev.claims.append(crossverify.Claim(
        kind="pin_name", key="99", values={"datasheet": "A", "official": "B"},
        status="conflict", detail="synthetic"))
    crossverify.save_evidence(ev, ev_path)

    rec = ComponentRecord.load(root, "widget-1")
    with pytest.raises(factory.StageBlocked, match="unresolved conflict"):
        factory._build_validated(rec, factory.make_ctx(wired))
