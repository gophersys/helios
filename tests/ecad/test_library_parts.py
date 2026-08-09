"""Gates for the no-datasheet library-part ingest (Stage F1).

Two layers:

1. **The flow** — ``src/ecad/ingest/library_parts.py`` run against the
   installed KiCad libraries into a tmp dir. Needs KiCad installed, so those
   tests skip without it.
2. **The committed artifacts** — ``src/ecad/library/generic/*`` are source,
   not build output, so they are checked directly: importable, instantiable
   in a ``Design``, footprint present, sidecar honest about the missing
   datasheet, and the ``.kicad_sym`` renderable by ``kicad-cli``.

The polarity gate is the one to keep: KiCad's ``Device:LED`` puts the
CATHODE on pad 1 and the ANODE on pad 2, the reverse of the "first pin is
the positive end" intuition. If a regeneration ever swapped them, every
indicator LED built on this part would sit backwards on the board and
nothing else in the suite would notice.
"""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.ecad import Design
from src.ecad.footprints import (
    FootprintIndex,
    PackageSpec,
    kicad_share_dir,
    validate_footprint,
)
from src.ecad.ingest import library_parts
from src.ecad.ingest.kicad_official import load_official_symbol
from src.ecad.ingest.library_parts import (
    CATALOG,
    CATALOG_BY_LIB_ID,
    IngestError,
    LibraryPart,
    ingest,
    ingest_all,
)
from src.ecad.library import get as registry_get

KICAD_CLI = shutil.which("kicad-cli") or "/usr/bin/kicad-cli"
skip_no_kicad = pytest.mark.skipif(
    not Path(KICAD_CLI).is_file(), reason="kicad-cli not available"
)
skip_no_symbols = pytest.mark.skipif(
    not (kicad_share_dir() / "symbols" / "Device.kicad_sym").is_file(),
    reason="installed KiCad symbol libraries not available",
)

GENERIC_DIR = Path(library_parts.OUT_DIR)
LIB_IDS = [p.lib_id for p in CATALOG]


def _sidecar(part: LibraryPart) -> dict:
    return json.loads((GENERIC_DIR / f"{part.part_id}.json").read_text())


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(scope="module")
def index() -> FootprintIndex:
    return FootprintIndex.cached(library_parts.INDEX_CACHE)


# ---------------------------------------------------------------------------
# Catalog sanity — the lib_ids must name symbols that really exist
# ---------------------------------------------------------------------------

def test_catalog_is_unique_and_covers_the_stage_f1_parts():
    assert len(CATALOG_BY_LIB_ID) == len(CATALOG), "duplicate lib_id"
    assert len({p.name for p in CATALOG}) == len(CATALOG), "duplicate name"
    assert len({p.part_id for p in CATALOG}) == len(CATALOG), "duplicate id"
    assert set(LIB_IDS) >= {
        "Device:LED", "Device:D_Schottky", "Device:C", "Device:R", "Device:L",
        "Device:Crystal_GND24", "Device:FerriteBead", "Switch:SW_Push",
        "Connector:USB_C_Receptacle_USB2.0_16P",
    }


@skip_no_symbols
@pytest.mark.parametrize("lib_id", LIB_IDS)
def test_every_catalogued_symbol_is_installed(lib_id):
    symbol = load_official_symbol(lib_id)
    assert symbol is not None, f"{lib_id} is not in the installed libraries"
    assert symbol.pins, f"{lib_id} resolved to zero pins"


@skip_no_symbols
def test_the_ferrite_bead_name_in_the_plan_does_not_exist():
    """The Stage F1 brief asked for ``Device:Ferrite_Bead``.

    KiCad 10 has no such symbol; the real one is ``Device:FerriteBead``. This
    test exists so the substitution stays a deliberate, documented choice
    rather than something a future reader has to rediscover.
    """
    assert load_official_symbol("Device:Ferrite_Bead") is None
    assert load_official_symbol("Device:FerriteBead") is not None
    assert "Device:FerriteBead" in CATALOG_BY_LIB_ID


# ---------------------------------------------------------------------------
# The ingest flow
# ---------------------------------------------------------------------------

@skip_no_symbols
def test_ingest_all_into_a_tmp_dir(tmp_path, index):
    results = ingest_all(out_dir=tmp_path, index=index)
    assert len(results) == len(CATALOG)
    for r in results:
        assert r.evidence.summary()["conflicts"] == 0
        for path in (r.generated.py_path, r.generated.sidecar_path,
                     r.generated.sym_path, r.generated.md_path):
            assert path.is_file(), path
            assert path.parent == tmp_path


@skip_no_symbols
def test_ingest_is_deterministic(tmp_path, index):
    """Same inputs, byte-identical artifacts — twice, into two dirs."""
    a, b = tmp_path / "a", tmp_path / "b"
    for out in (a, b):
        ingest_all(out_dir=out, index=index)
    for path in sorted(a.iterdir()):
        assert path.read_bytes() == (b / path.name).read_bytes(), path.name


@skip_no_symbols
def test_ingest_rejects_an_uncatalogued_part(tmp_path, index):
    with pytest.raises(IngestError, match="not in the catalog"):
        ingest("Device:NotAJellybean", out_dir=tmp_path, index=index)


@skip_no_symbols
def test_ingest_gates_the_default_footprint(tmp_path, index, monkeypatch):
    """A default footprint that cannot carry the symbol's pins is fatal."""
    bad = LibraryPart(lib_id="Device:Crystal_GND24", name="BadCrystal",
                      footprint="Capacitor_SMD:C_0402_1005Metric")
    monkeypatch.setitem(CATALOG_BY_LIB_ID, "Device:Crystal_GND24", bad)
    with pytest.raises(IngestError, match="no footprint pad"):
        ingest("Device:Crystal_GND24", out_dir=tmp_path, index=index)


@skip_no_symbols
def test_cli_list_and_ingest(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(library_parts, "OUT_DIR", tmp_path)
    assert library_parts.main(["list"]) == 0
    assert "Device:C" in capsys.readouterr().out
    assert library_parts.main(["ingest", "Device:C"]) == 0
    assert (tmp_path / "capacitor.py").is_file()
    assert library_parts.main(["ingest", "Device:Nope"]) == 1
    assert library_parts.main(["bogus"]) == 2


# ---------------------------------------------------------------------------
# The committed artifacts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lib_id", LIB_IDS)
def test_generated_part_is_importable_and_instantiable(lib_id):
    part = CATALOG_BY_LIB_ID[lib_id]
    cls = registry_get(lib_id)
    assert cls.lib_id == lib_id
    assert cls.part_name == part.name
    assert cls.footprint is not None, "class-level default footprint missing"

    design = Design(f"solo-{part.part_id}")
    inst = cls()
    design.add(inst)
    assert inst.ref.startswith(cls.reference_prefix)
    errors = [i for i in design.check() if i.is_error]
    assert errors == [], errors


@pytest.mark.parametrize("lib_id", LIB_IDS)
def test_value_and_footprint_are_per_instance(lib_id):
    """The ergonomics ``src/pipeline/stock_parts.py`` published and
    ``src/ecad/circuits/blocks.py`` calls: ``Cls(value, footprint)``."""
    cls = registry_get(lib_id)
    other = library_parts.FootprintRef("Capacitor_SMD", "C_1206_3216Metric")
    inst = cls("SOME-VALUE", other)
    assert inst.value == "SOME-VALUE"
    assert inst.footprint is other
    # The class default is untouched by an instance override.
    assert cls.footprint is not other
    assert cls().footprint is cls.footprint


def test_capacitor_and_resistor_match_the_stock_parts_defaults():
    """These two are the ones the composer already constructs by hand."""
    cap = registry_get("Device:C")
    res = registry_get("Device:R")
    assert cap().value == "100nF"
    assert res().value == "10k"
    assert cap.footprint.lib_id == "Capacitor_SMD:C_0402_1005Metric"
    assert res.footprint.lib_id == "Resistor_SMD:R_0402_1005Metric"
    assert cap.reference_prefix == "C" and res.reference_prefix == "R"


@pytest.mark.parametrize("lib_id", LIB_IDS)
def test_sidecar_says_it_was_ingested_without_a_datasheet(lib_id):
    part = CATALOG_BY_LIB_ID[lib_id]
    sidecar = _sidecar(part)
    prov = sidecar["provenance"]
    assert prov["pin_source"] == "official-symbol"
    assert prov["official_symbol"] == lib_id
    assert prov["datasheet"] == library_parts.NO_DATASHEET
    assert prov["evidence_mode"] == library_parts.EVIDENCE_MODE
    assert prov["footprint_is_default_only"] is True
    # No MPN/LCSC can exist for a generic part, and none is invented.
    assert sidecar["sourcing"] is None
    assert sidecar["source_hashes"]["pdf_sha256"] == ""
    assert sidecar["source_hashes"]["symbol_sha256"]
    # Visible to a human reading <id>.md, not just to a JSON parser.
    summary = sidecar["evidence_summary"]
    assert summary["conflicts"] == 0
    assert summary["datasheet"] == library_parts.NO_DATASHEET


@pytest.mark.parametrize("lib_id", LIB_IDS)
def test_evidence_ledger_is_two_source_and_never_says_datasheet(lib_id):
    part = CATALOG_BY_LIB_ID[lib_id]
    ledger = json.loads(
        (GENERIC_DIR / f"{part.part_id}.evidence.json").read_text())
    kinds = {c["kind"] for c in ledger["claims"]}
    assert "pad_set" in kinds, "pins-vs-footprint claim missing"
    assert "source_mode" in kinds, "no-datasheet claim missing"
    assert ledger["summary"]["conflicts"] == 0
    for claim in ledger["claims"]:
        assert "datasheet" not in claim["values"], (
            f"{part.lib_id}: claim {claim['kind']}:{claim['key']} labels a "
            f"source 'datasheet' — nothing here came from one")
    assert ledger["summary"]["claims"] == len(ledger["claims"])


def test_synthesized_pin_names_are_declared_as_ours():
    """Device:C / Device:R / Device:FerriteBead draw unnamed pins.

    P1/P2 are labels this ingest invented, and the sidecar has to say so —
    otherwise a reader takes them for names KiCad publishes.
    """
    for lib_id in ("Device:C", "Device:R", "Device:FerriteBead"):
        prov = _sidecar(CATALOG_BY_LIB_ID[lib_id])["provenance"]
        assert prov["synthesized_pin_names"] == ["P1", "P2"], lib_id
        cls = registry_get(lib_id)
        assert [p.name for p in cls().pins] == ["P1", "P2"]

    # Device:L names its pins "1"/"2" for real — nothing synthesized.
    assert _sidecar(CATALOG_BY_LIB_ID["Device:L"])[
        "provenance"]["synthesized_pin_names"] == []
    assert [p.name for p in registry_get("Device:L")().pins] == ["1", "2"]


# ---------------------------------------------------------------------------
# Polarity — the gate that stops an LED being wired backwards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lib_id", ["Device:LED", "Device:D_Schottky"])
def test_diode_polarity_is_addressable_by_name(lib_id):
    """KiCad puts the CATHODE on pad 1 and the ANODE on pad 2.

    Both ends must be reachable by NAME, so no caller has to know that, and
    the mapping must be exactly this way round.
    """
    part = registry_get(lib_id)()
    assert part.pin("K").pad == "1", "pad 1 is the CATHODE"
    assert part.pin("A").pad == "2", "pad 2 is the ANODE"
    # The generated typed accessors agree with pin() lookup.
    assert part.K.pad == "1"
    assert part.A.pad == "2"
    # Naming them by position would give the opposite answer — that is the
    # whole point of this test.
    assert part.pins[0].name == "K" and part.pins[1].name == "A"


def test_led_polarity_survives_the_symbol_and_the_md():
    sym = (GENERIC_DIR / "led.kicad_sym").read_text()
    assert '(name "K"' in sym and '(name "A"' in sym
    md = (GENERIC_DIR / "led.md").read_text()
    assert "| 1 | K |" in md and "| 2 | A |" in md
    notes = _sidecar(CATALOG_BY_LIB_ID["Device:LED"])["provenance"]["notes"]
    assert any("pad 1 = K" in n for n in notes)


# ---------------------------------------------------------------------------
# USB-C — surplus pads, pad counts, and the shield
# ---------------------------------------------------------------------------

USB_C = "Connector:USB_C_Receptacle_USB2.0_16P"


def test_usb_c_pin_model():
    conn = registry_get(USB_C)()
    assert len(conn.pins) == 17
    assert len(conn.GND) == 4 and len(conn.VBUS) == 4
    # D+ and D- each land on two pads (flip symmetry) and come back as tuples,
    # which is what lets a caller short each pair as USB 2.0 requires.
    assert {p.pad for p in conn.DP} == {"A6", "B6"}
    assert {p.pad for p in conn.DN} == {"A7", "B7"}
    assert conn.SHIELD.pad == "SH"
    assert conn.CC1.pad == "A5" and conn.CC2.pad == "B5"


def test_usb_c_shield_is_not_modelled_as_ground():
    """SH is the connector shell. Tying it to GND is a board-level decision
    (usually through an RC or a bead); calling it role=ground here would let
    a decoupling block treat the shell as a return path."""
    from src.ecad.model import PinRole
    conn = registry_get(USB_C)()
    assert conn.SHIELD.role is PinRole.PASSIVE
    assert {p.role for p in conn.GND} == {PinRole.GROUND}


@skip_no_symbols
def test_usb_c_default_footprint_carries_every_pad_including_the_shield(index):
    cls = registry_get(USB_C)
    pads = {p.pad for p in cls().pins}
    val = validate_footprint(index, cls.footprint, pads)
    assert val.ok, val.errors
    assert val.info is not None
    assert set(val.info.pad_numbers) == pads, "16P footprint must match exactly"
    assert val.info.has_step


@skip_no_symbols
def test_usb_c_24p_footprints_are_rejected_as_surplus_pads(index):
    """The finding worth recording: a 24-position receptacle does NOT fit the
    USB2.0-only 16P symbol.

    Its SuperSpeed pads A2/A3/A10/A11/B2/B3/B10/B11 are not in the symbol, and
    ``_SURPLUS_OK_RE`` only forgives EP/MP/SH/PAD/"" — so validate_footprint
    fails, which is the correct answer: those pads would end up on the board
    with nothing in the schematic to say what they are.
    """
    from src.ecad.model import FootprintRef
    pads = {p.pad for p in registry_get(USB_C)().pins}
    ref = FootprintRef("Connector_USB",
                       "USB_C_Receptacle_Amphenol_12401610E4-2A")
    if index.get(ref.lib_id) is None:
        pytest.skip("24P reference footprint not in this KiCad install")
    val = validate_footprint(index, ref, pads)
    assert not val.ok
    assert any("unexplained extra pads" in e for e in val.errors)
    assert all(p in str(val.errors) for p in ("A2", "A3", "B10", "B11"))


@skip_no_symbols
def test_usb_c_package_spec_resolves_to_exactly_one_footprint(index):
    """17 electrical pads is enough to disambiguate on its own — the 6P and
    24P receptacles have 7 and 25."""
    spec = PackageSpec(family="USB_C_Receptacle", pads=17)
    cands = index.candidates(spec)
    assert cands, "no 17-pad USB-C receptacle footprint installed"
    assert all(len(c.pad_numbers) == 17 for c in cands)


# ---------------------------------------------------------------------------
# kicad-cli smoke test — the symbol KiCad itself has to accept
# ---------------------------------------------------------------------------

@skip_no_kicad
@pytest.mark.parametrize("lib_id", LIB_IDS)
def test_generated_symbol_renders_with_kicad_cli(lib_id, tmp_path):
    part = CATALOG_BY_LIB_ID[lib_id]
    sym = GENERIC_DIR / f"{part.part_id}.kicad_sym"
    proc = subprocess.run(
        [KICAD_CLI, "sym", "export", "svg", "--output", str(tmp_path),
         str(sym)],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    svgs = list(tmp_path.glob("*.svg"))
    assert svgs, f"{sym.name}: kicad-cli produced no SVG ({proc.stdout})"
    assert all(s.stat().st_size > 0 for s in svgs)


# ---------------------------------------------------------------------------
# The committed artifacts are what the flow produces right now
# ---------------------------------------------------------------------------

@skip_no_symbols
def test_committed_artifacts_match_a_fresh_regeneration(tmp_path, index):
    """Generated parts are source, so a regeneration must be a no-op.

    A drift here means someone hand-edited src/ecad/library/generic/ or the
    installed KiCad libraries moved under us — both worth knowing.
    """
    ingest_all(out_dir=tmp_path, index=index)
    for fresh in sorted(tmp_path.iterdir()):
        committed = GENERIC_DIR / fresh.name
        assert committed.is_file(), f"{fresh.name} is not committed"
        assert committed.read_text() == fresh.read_text(), fresh.name


@pytest.mark.parametrize("part", CATALOG, ids=LIB_IDS)
def test_source_hashes_do_not_fingerprint_the_install(part):
    """A committed hash must describe the PART, not the machine.

    The regeneration gate above is only as sound as the fields it compares.
    It first went red in CI for exactly this reason: the sidecar recorded
    ``symbol_lib_sha256``, the SHA-256 of the whole installed
    ``<Lib>.kicad_sym``. ``Device.kicad_sym`` is 2.4 MB and 538 symbols, so
    that value said "this is the macOS app bundle's copy of KiCad's symbol
    library", not "this is Device:C" — and the Linux ``kicad-libraries``
    package hashes differently. The artifact could not be reproduced off the
    machine that wrote it, which makes "generated parts are source" a
    fiction.

    Whole-library file hashes are therefore banned from ``source_hashes``.
    Content hashes of the part are not: they are the point.
    """
    hashes = _sidecar(part)["source_hashes"]
    assert "symbol_lib_sha256" not in hashes, (
        "symbol_lib_sha256 fingerprints the install, not the part")

    installed = {
        _sha256_bytes(lib.read_bytes()): lib.name
        for lib in sorted((kicad_share_dir() / "symbols").glob("*.kicad_sym"))
    }
    for key, value in hashes.items():
        assert value not in installed, (
            f"{part.part_id}: source_hashes.{key} is the file hash of the "
            f"installed {installed[value]} — a different KiCad install "
            f"produces a different value, so the committed artifact could "
            f"never be regenerated there")


@skip_no_symbols
@pytest.mark.parametrize("part", CATALOG, ids=LIB_IDS)
def test_symbol_sha256_tracks_the_symbol_it_came_from(part):
    """The stable hash is still a real hash of the upstream symbol.

    Install-independence would be trivial to fake with a constant. This
    pins the other half: the value recomputes from the installed symbol, so
    it still moves — for this part alone — if upstream edits it.
    """
    symbol = load_official_symbol(part.lib_id)
    assert symbol is not None, f"{part.lib_id} not installed"
    expected = library_parts._symbol_content_sha256(symbol)
    assert _sidecar(part)["source_hashes"]["symbol_sha256"] == expected
