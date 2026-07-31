"""Factory stage machine + evidence ledger tests.

Real data: the official ESP32-S3-WROOM-1 symbol from the installed KiCad
libraries drives the evidence tests (skipped when KiCad is absent);
everything else runs against a temp ingest root with an injected clock.
"""

import json

import pytest

from src.ecad.footprints import kicad_share_dir
from src.ecad.ingest import crossverify
from src.ecad.ingest.kicad_official import load_official_symbol
from src.ecad.ingest.state import (
    STAGE_ORDER,
    ComponentRecord,
    Stage,
    render_components_md,
    status_all,
)
from src.ecad.model import ElectricalType, PinRole, pin

HAS_KICAD = kicad_share_dir().is_dir()


def make_clock():
    """Deterministic injectable clock: T0001, T0002, ..."""
    n = 0

    def clock() -> str:
        nonlocal n
        n += 1
        return f"T{n:04d}"
    return clock


def seeded_record(root, comp_id="esp32-s3-wroom-1"):
    rec = ComponentRecord(id=comp_id, vendor="espressif", kind="module")
    rec.save(root)
    return rec


def satisfy_all_gates(root, rec):
    """Write the artifacts every default gate checks for."""
    d = rec.record_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / "extracted.json").write_text(json.dumps(
        {"pins": [{"pad": "1", "name": "GND"}, {"pad": "2", "name": "3V3"}]}))
    ev = crossverify.build_evidence(
        [pin("1", "GND", "power_in"), pin("2", "3V3", "power_in")],
        footprint_pads={"1", "2", "EP"})
    crossverify.save_evidence(ev, d / "evidence.json")
    (d / f"{rec.id}.kicad_sym").write_text("(kicad_symbol_lib)")
    rec.meta.update(footprint="RF_Module:ESP32-S3-WROOM-1",
                    lcsc="C2913204", erc_errors=0, approved_by="mateo")


# ── stage machine ───────────────────────────────────────────────────────────────

def test_stage_order():
    assert [s.value for s in STAGE_ORDER] == [
        "discovered", "extracted", "cross_verified", "symbol_done",
        "footprint_resolved", "sourcing_linked", "validated", "approved"]
    assert Stage.DISCOVERED == "discovered"  # StrEnum semantics


def test_record_roundtrip(tmp_path):
    rec = seeded_record(tmp_path)
    rec.stages[Stage.DISCOVERED].status = "passed"
    rec.stages[Stage.DISCOVERED].timestamp = "T0001"
    rec.meta["footprint"] = "RF_Module:ESP32-S3-WROOM-1"
    rec.save(tmp_path)
    loaded = ComponentRecord.load(tmp_path, rec.id)
    assert loaded == rec
    assert loaded.stage is Stage.DISCOVERED


def test_full_transition_walk(tmp_path):
    clock = make_clock()
    ctx = {"root": tmp_path}
    rec = seeded_record(tmp_path)
    satisfy_all_gates(tmp_path, rec)
    seen = []
    for _ in STAGE_ORDER:
        res = rec.advance(ctx, clock)
        assert res.ok, f"gate failed at {rec.next_stage()}: {res.detail}"
        seen.append(rec.stage)
    assert seen == list(STAGE_ORDER)
    assert rec.stage is Stage.APPROVED
    assert rec.advance(ctx, clock).detail == "already approved"
    # every gate stamped from the injected clock, in order
    stamps = [rec.stages[s].timestamp for s in STAGE_ORDER]
    assert stamps == [f"T{i:04d}" for i in range(1, 9)]


def test_advance_blocks_on_unmet_gate(tmp_path):
    clock = make_clock()
    ctx = {"root": tmp_path}
    rec = seeded_record(tmp_path)
    assert rec.advance(ctx, clock).ok            # discovered
    res = rec.advance(ctx, clock)                # extracted: no file yet
    assert not res.ok and "extracted.json" in res.detail
    assert rec.stage is Stage.DISCOVERED
    assert "extracted.json" in rec.blocked_on()
    # idempotent failure: same outcome does not re-stamp the clock
    stamp = rec.stages[Stage.EXTRACTED].timestamp
    rec.advance(ctx, clock)
    assert rec.stages[Stage.EXTRACTED].timestamp == stamp


def test_status_all_demotes_on_refail_and_reheals(tmp_path):
    clock = make_clock()
    rec = seeded_record(tmp_path)
    satisfy_all_gates(tmp_path, rec)
    rec.recompute({"root": tmp_path}, clock)
    assert rec.stage is Stage.APPROVED
    rec.save(tmp_path)

    # Induce a conflict in the evidence: cross_verified must re-fail.
    ev_path = rec.record_dir(tmp_path) / "evidence.json"
    ev = crossverify.build_evidence(
        [pin("1", "GND", "power_in"), pin("2", "3V3", "power_in")],
        footprint_pads={"1", "9"})  # pin 2 unplaceable, pad 9 unexplained
    crossverify.save_evidence(ev, ev_path)
    records = status_all(tmp_path, clock=clock)
    assert [r.id for r in records] == [rec.id]
    demoted = records[0]
    assert demoted.stage is Stage.EXTRACTED     # self-healing demotion
    assert "conflict" in demoted.blocked_on()

    # Waive the conflict → next status_all re-heals all the way back.
    ev = crossverify.load_evidence(ev_path)
    ev.waive("pad_set", "pins_vs_footprint", reason="module EP variant",
             cited_source="esp32-s3-wroom-1.pdf p10", author="mateo")
    crossverify.save_evidence(ev, ev_path)
    healed = status_all(tmp_path, clock=clock)[0]
    assert healed.stage is Stage.APPROVED


def test_status_all_is_byte_stable(tmp_path):
    rec = seeded_record(tmp_path)
    satisfy_all_gates(tmp_path, rec)
    status_all(tmp_path, clock=make_clock())
    first = ComponentRecord.path_for(tmp_path, rec.id).read_text()
    status_all(tmp_path, clock=make_clock())
    assert ComponentRecord.path_for(tmp_path, rec.id).read_text() == first


def test_render_components_md(tmp_path):
    clock = make_clock()
    ctx = {"root": tmp_path}
    done = seeded_record(tmp_path, "esp32-c3")
    satisfy_all_gates(tmp_path, done)
    done.recompute(ctx, clock)
    stuck = seeded_record(tmp_path, "esp32-h2")
    stuck.recompute(ctx, clock)
    md = render_components_md([stuck, done])
    lines = md.splitlines()
    assert "| id | vendor | kind | stage | gate | blocked_on | updated |" in lines
    rows = [ln for ln in lines if ln.startswith("| esp32")]
    assert rows[0].startswith("| esp32-c3 ")     # sorted by id
    assert "| approved | 8/8 ✓ |" in rows[0]
    assert "| discovered | 1/8 → extracted | extracted.json missing |" in rows[1]


# ── normalization rules ───────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("GPIO4", "IO4"),                 # GPIOn ≡ IOn
    ("IO4", "IO4"),
    ("gpio12", "IO12"),               # case fold
    ("GPIO04", "IO4"),                # leading zeros dropped
    ("TXD0/GPIO1", "TXD0"),           # primary name before slash
    ("GPIO1/TXD0", "IO1"),
    (" EN ", "EN"),
    ("3V3", "3V3"),
    ("MTCK", "MTCK"),
])
def test_normalize_name(raw, expected):
    assert crossverify.normalize_name(raw) == expected


# ── evidence math (real official symbol where installed) ────────────────────

@pytest.mark.skipif(not HAS_KICAD, reason="KiCad share dir not installed")
def test_evidence_agrees_with_itself_and_conflict_blocks_then_waiver_unblocks():
    official = load_official_symbol("RF_Module:ESP32-S3-WROOM-1")
    assert official is not None
    extracted = list(official.pins)  # a perfect datasheet extraction
    ev = crossverify.build_evidence(extracted, official=official,
                                    footprint_pads={p.pad for p in official.pins},
                                    component="esp32-s3-wroom-1")
    s = ev.summary()
    assert s["conflicts"] == 0
    assert s["agreed"] == s["claims"] > len(official.pins)

    # Induce one transposed pin name → exactly one per-pad conflict
    # plus the deduped name-set conflict.
    mutated = list(extracted)
    victim = next(p for p in mutated if p.name == "EN")
    mutated[mutated.index(victim)] = pin(victim.pad, "IO99", victim.etype)
    ev2 = crossverify.build_evidence(mutated, official=official)
    s2 = ev2.summary()
    assert s2["conflicts"] == 2
    bad = ev2.find("pin_name", victim.pad)
    assert bad.status == "conflict" and "IO99" in bad.detail

    ev2.waive("pin_name", victim.pad, reason="datasheet rev mismatch",
              cited_source="esp32-s3-wroom-1.pdf p11", author="mateo")
    ev2.waive("name_set", "datasheet_vs_official", reason="follows pin waiver",
              cited_source="esp32-s3-wroom-1.pdf p11", author="mateo")
    assert ev2.summary()["conflicts"] == 0
    assert ev2.summary()["waived"] == 2


def test_waiver_requires_citation_and_conflict():
    ev = crossverify.build_evidence([pin("1", "GND", "power_in")],
                                    footprint_pads={"1", "7"})
    claim = ev.find("pad_set", "pins_vs_footprint")
    assert claim.status == "conflict" and "7" in claim.detail
    with pytest.raises(ValueError):
        ev.waive("pad_set", "pins_vs_footprint", reason="", cited_source="x",
                 author="y")
    with pytest.raises(KeyError):
        ev.waive("pad_set", "nope", reason="r", cited_source="s", author="a")
    ev.waive("pad_set", "pins_vs_footprint", reason="mech pad",
             cited_source="fp drawing", author="mateo")
    with pytest.raises(ValueError):  # already waived, no double-waive
        ev.waive("pad_set", "pins_vs_footprint", reason="r",
                 cited_source="s", author="a")


class StubSoc:
    """Duck-typed stand-in for ingest.zephyr.SocInfo (ESP32-S3 numbers
    from data/zephyr/VALIDATION.md: 54 GPIOs, UART0_TX default IO43)."""

    ngpios = 54
    input_only = {46}
    strapping = {0, 3, 45, 46}
    signals = {"UART0_TX": {43}, "I2C0_SDA": {2}}


def test_zephyr_checks():
    pins = [
        pin("4", "IO43", "bidirectional", role=PinRole.GPIO, gpio=43,
            functions=("UART0_TX",)),
        pin("5", "IO2", "bidirectional", role=PinRole.GPIO, gpio=2,
            functions=("I2C0_SDA",)),
        pin("6", "IO60", "bidirectional", role=PinRole.GPIO, gpio=60),
        pin("7", "IO46", "bidirectional", role=PinRole.GPIO, gpio=46),
        pin("8", "IO0", "bidirectional", role=PinRole.STRAPPING, gpio=0),
    ]
    ev = crossverify.build_evidence(pins, zephyr=StubSoc())
    assert ev.find("gpio_range", "4").status == "agreed"
    assert ev.find("gpio_range", "6").status == "conflict"      # 60 > 53
    assert ev.find("signal_placement", "4:UART0_TX").status == "agreed"
    assert ev.find("input_only", "7").status == "conflict"      # IO46 in-only
    strap = ev.find("strapping", "set")
    assert strap.status == "conflict"                           # {0} != {0,3,45,46}
    assert "only_zephyr=[3, 45, 46]" in strap.detail
    # wrong signal placement
    bad = [pin("4", "IO10", "bidirectional", role=PinRole.GPIO, gpio=10,
               functions=("UART0_TX",))]
    ev2 = crossverify.build_evidence(bad, zephyr=StubSoc())
    assert ev2.find("signal_placement", "4:UART0_TX").status == "conflict"


def test_input_only_agrees_when_etype_input():
    pins = [pin("7", "IO46", ElectricalType.INPUT, role=PinRole.GPIO, gpio=46)]
    ev = crossverify.build_evidence(pins, zephyr=StubSoc())
    assert ev.find("input_only", "7").status == "agreed"


def test_gnd_dedup_in_name_set():
    """Nine stacked GND pads on one side ≡ one GND entry on the other."""
    from src.ecad.ingest.kicad_official import OfficialSymbol
    official = OfficialSymbol(
        library="Test", name="X", footprint="", datasheet="", description="",
        extends=None,
        pins=tuple(pin(str(i), "GND", "power_in") for i in range(1, 10)))
    extracted = [pin(str(i), "GND", "power_in") for i in range(1, 10)]
    ev = crossverify.build_evidence(extracted, official=official)
    assert ev.find("name_set", "datasheet_vs_official").status == "agreed"
    assert ev.summary()["conflicts"] == 0


def test_evidence_save_load_roundtrip(tmp_path):
    ev = crossverify.build_evidence([pin("1", "GND", "power_in")],
                                    footprint_pads={"1", "7"},
                                    component="x")
    ev.waive("pad_set", "pins_vs_footprint", reason="mech pad",
             cited_source="drawing", author="mateo")
    path = crossverify.save_evidence(ev, tmp_path / "evidence.json")
    loaded = crossverify.load_evidence(path)
    assert loaded == ev
    assert loaded.summary()["waived"] == 1
    # persisted summary matches recomputed one
    assert json.loads(path.read_text())["summary"] == loaded.summary()
