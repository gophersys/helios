"""Ingest jellybean parts that already exist in the installed KiCad libraries.

The Espressif factory (``ingest/factory.py``) is built around a datasheet:
it seeds from a PDF manifest, gates on the cached PDF, extracts pins with an
LLM and cross-verifies four sources. None of that applies to a 100nF
capacitor or a tactile switch. Those parts are *already* curated by KiCad
upstream, and there is no per-part datasheet to corroborate — a "generic
0402 capacitor" is a symbol standing for thousands of orderable parts.

So this module is a second, much shorter ingest flow for the same
artifacts:

    official KiCad symbol  →  pins (pad / name / etype)
    PackageSpec            →  one installed footprint  →  pads
    crossverify            →  2-source ledger: symbol pins × footprint pads
    codegen                →  <id>.py / .json / .kicad_sym / .md

into ``src/ecad/library/generic/``, where ``src.ecad.library`` serves them
exactly like the Espressif parts.

What this flow deliberately does NOT do
---------------------------------------
It never claims datasheet corroboration. Each sidecar records
``provenance.pin_source = "official-symbol"``,
``provenance.datasheet = "none — ingested without a datasheet"`` and an
``evidence_mode`` of ``"2-source"``, and the ledger itself carries a
``source_mode:no_datasheet`` claim. The 4-source Espressif evidence and this
2-source evidence must never be mistaken for each other by a reader of
``COMPONENTS.md`` or of the sidecar.

It also does not invent pin names. Where KiCad draws a pin unnamed
(``Device:C``, ``Device:R``, ``Device:FerriteBead``), ``load_official_symbol``
synthesizes ``P<pad>`` and lists it in ``OfficialSymbol.synthesized_names``;
that list is copied into the sidecar so a reader can see which labels came
from KiCad and which came from us.

Per-instance value and footprint
--------------------------------
Every part here is generic, so its value *and* its footprint are instance
choices, not part identity. The generated classes therefore take
``__init__(value=…, footprint=None)`` (``codegen.default_value``), which is
the constructor shape ``src/pipeline/stock_parts.py`` already published and
``src/ecad/circuits/blocks.py`` calls. The class-level footprint is the
sane default (0402 for chip passives) and it is the *default* that
``validate_footprint`` gates — no single footprint could be right for every
instance.

CLI::

    python -m src.ecad.ingest.library_parts list
    python -m src.ecad.ingest.library_parts ingest Device:C
    python -m src.ecad.ingest.library_parts ingest --all
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..footprints import (
    FootprintIndex,
    PackageSpec,
    kicad_share_dir,
    validate_footprint,
)
from ..model import FootprintRef, PinRole, PinSpec, UnitDef
from . import codegen, crossverify
from .kicad_official import OfficialSymbol, load_official_symbol

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "src" / "ecad" / "library" / "generic"
INDEX_CACHE = REPO_ROOT / "data" / "footprint_index.json"

#: Recorded in every sidecar so the 2-source ledger can never be read as
#: datasheet-corroborated.
EVIDENCE_MODE = "2-source: official symbol pins x installed footprint pads"
NO_DATASHEET = "none - ingested without a datasheet"


class IngestError(RuntimeError):
    """A library part cannot be ingested; the message names the reason."""


# ── catalog ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LibraryPart:
    """One jellybean part: an installed symbol plus a default footprint.

    ``footprint`` is a :class:`PackageSpec` wherever the descriptor resolves
    to exactly one installed footprint; where it does not (``D_SOD-123`` also
    prefix-matches ``D_SOD-123F``) it is an explicit ``"Lib:Name"`` and
    ``footprint_note`` says why.
    """

    lib_id: str                                  # installed KiCad symbol
    name: str                                    # generated part name
    footprint: PackageSpec | str                 # DEFAULT footprint only
    roles: dict[str, PinRole] = field(default_factory=dict)  # pad -> role
    default_value: str = ""                      # "" -> the symbol's Value
    unit_name: str = ""                          # "" -> the part name
    footprint_note: str = ""
    notes: tuple[str, ...] = ()

    @property
    def part_id(self) -> str:
        return codegen.part_id_for(self.name)


_PASSIVE_2PIN = {"1": PinRole.PASSIVE, "2": PinRole.PASSIVE}

# Diode/LED polarity is carried by the pin NAME, never by position: KiCad's
# Device:LED puts the CATHODE on pad 1 and the ANODE on pad 2, which is the
# reverse of what "pins[0] is the positive end" intuition suggests.
_DIODE_ROLES = {"1": PinRole.PASSIVE, "2": PinRole.PASSIVE}

_USB_C_ROLES = {
    "A1": PinRole.GROUND, "A12": PinRole.GROUND,
    "B1": PinRole.GROUND, "B12": PinRole.GROUND,
    "A4": PinRole.POWER, "A9": PinRole.POWER,
    "B4": PinRole.POWER, "B9": PinRole.POWER,
    "A5": PinRole.CONTROL, "B5": PinRole.CONTROL,      # CC1 / CC2
    "A6": PinRole.COMM, "A7": PinRole.COMM,            # D+ / D-
    "B6": PinRole.COMM, "B7": PinRole.COMM,
    "A8": PinRole.SIGNAL, "B8": PinRole.SIGNAL,        # SBU1 / SBU2
    "SH": PinRole.PASSIVE,                             # chassis, not GND
}

CATALOG: tuple[LibraryPart, ...] = (
    LibraryPart(
        lib_id="Device:C",
        name="Capacitor",
        footprint=PackageSpec(family="C_0402", pads=2),
        roles=_PASSIVE_2PIN,
        default_value="100nF",
        notes=(
            "Pins are unnamed in Device:C; P1/P2 are synthesized labels.",
            "Value and footprint are per instance: Capacitor('10uF', "
            "FootprintRef('Capacitor_SMD', 'C_0805_2012Metric')).",
        ),
    ),
    LibraryPart(
        lib_id="Device:R",
        name="Resistor",
        footprint=PackageSpec(family="R_0402", pads=2),
        roles=_PASSIVE_2PIN,
        default_value="10k",
        notes=("Pins are unnamed in Device:R; P1/P2 are synthesized labels.",),
    ),
    LibraryPart(
        lib_id="Device:L",
        name="Inductor",
        footprint=PackageSpec(family="L_0603", pads=2),
        roles=_PASSIVE_2PIN,
        default_value="10uH",
    ),
    LibraryPart(
        lib_id="Device:FerriteBead",
        name="FerriteBead",
        footprint=PackageSpec(family="L_0603", pads=2),
        roles=_PASSIVE_2PIN,
        default_value="600R@100MHz",
        footprint_note=(
            "Chip ferrite beads ship in the same 0603 chip package as chip "
            "inductors; KiCad has no Ferrite_SMD library."
        ),
        notes=(
            "'Device:Ferrite_Bead' does not exist in KiCad 10 — the installed "
            "symbol is 'Device:FerriteBead' (there is also "
            "'Device:FerriteBead_Small', the small-symbol variant).",
            "The default value states impedance at a frequency, which is how "
            "beads are specified; it is a placeholder, not a datasheet value.",
        ),
    ),
    LibraryPart(
        lib_id="Device:LED",
        name="LED",
        footprint=PackageSpec(family="LED_0603", pads=2),
        roles=_DIODE_ROLES,
        default_value="LED",
        notes=(
            "POLARITY: pad 1 = K (cathode), pad 2 = A (anode). Both names "
            "come from the installed symbol, not from this ingest — wire by "
            "name (led.A / led.K), never by position.",
        ),
    ),
    LibraryPart(
        lib_id="Device:D_Schottky",
        name="D_Schottky",
        footprint="Diode_SMD:D_SOD-123",
        roles=_DIODE_ROLES,
        default_value="D_Schottky",
        footprint_note=(
            "Explicit lib_id: PackageSpec(family='D_SOD-123') prefix-matches "
            "D_SOD-123F too, and FootprintIndex.resolve refuses to guess "
            "between them."
        ),
        notes=(
            "POLARITY: pad 1 = K (cathode), pad 2 = A (anode), same as "
            "Device:LED.",
        ),
    ),
    LibraryPart(
        lib_id="Device:Crystal_GND24",
        name="Crystal_GND24",
        footprint=PackageSpec(family="Crystal_SMD_3225-4Pin_3.2x2.5mm", pads=4),
        roles={"1": PinRole.PASSIVE, "2": PinRole.GROUND,
               "3": PinRole.PASSIVE, "4": PinRole.GROUND},
        default_value="40MHz",
        notes=(
            "Pads 2 and 4 are the can/shield ground (named 'G' in the "
            "symbol), pads 1 and 3 the resonator terminals.",
        ),
    ),
    LibraryPart(
        lib_id="Switch:SW_Push",
        name="SW_Push",
        footprint=PackageSpec(family="SW_SPST_TL3342", pads=2),
        roles=_PASSIVE_2PIN,
        default_value="SW_Push",
        footprint_note=(
            "TL3342 is a mainstream 4.5x3.5mm SMD tactile switch with a STEP "
            "model; any 2-pad Button_Switch_SMD footprint substitutes."
        ),
        notes=(
            "SPST-NO: the two pads are interchangeable, so this is one of the "
            "few parts a caller MAY wire by position.",
        ),
    ),
    LibraryPart(
        lib_id="Connector:USB_C_Receptacle_USB2.0_16P",
        name="USB_C_Receptacle_USB2.0_16P",
        footprint=PackageSpec(family="USB_C_Receptacle_GCT_USB4105", pads=17),
        roles=_USB_C_ROLES,
        default_value="USB_C_Receptacle_USB2.0_16P",
        unit_name="USB-C",
        footprint_note=(
            "The 16P symbol only fits a 16-position receptacle footprint. The "
            "24-position footprints (Amphenol 12401610E4-2A, JAE DX07S024*, "
            "Molex 105450-0101, GCT USB4115, CNCTech C-ARA1-AK51X) carry the "
            "SuperSpeed pads A2/A3/A10/A11/B2/B3/B10/B11, which this symbol "
            "does not model; validate_footprint rejects them as unexplained "
            "surplus pads, and correctly so — those pads would be left "
            "floating with nothing in the schematic to say why."
        ),
        notes=(
            "17 distinct pads: 4x GND, 4x VBUS, CC1/CC2, 2x D+, 2x D-, "
            "SBU1/SBU2 and the shield pad SH.",
            "SH is the connector shell. It is deliberately NOT role=ground: "
            "the shell is normally tied to GND through an RC or a bead, not "
            "shorted to it, and calling it ground would let a decoupling "
            "block treat it as a return path.",
            "D+ appears on pads A6 and B6 and D- on A7 and B7 (flip "
            "symmetry); the generated accessors DP and DN return both pads as "
            "a tuple, which is what lets a caller short each pair as the "
            "USB 2.0 spec requires.",
        ),
    ),
)

CATALOG_BY_LIB_ID = {p.lib_id: p for p in CATALOG}


# ── ingest ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class IngestResult:
    """What one ingested part produced (for the CLI and for tests)."""

    part: LibraryPart
    symbol: OfficialSymbol
    pins: tuple[PinSpec, ...]
    footprint: FootprintRef
    has_step: bool
    warnings: tuple[str, ...]
    evidence: crossverify.Evidence
    generated: codegen.GeneratedPart

    @property
    def summary(self) -> str:
        return (f"{self.part.lib_id} -> {self.generated.py_path.name} "
                f"({len(self.pins)} pins, {self.footprint.lib_id}, "
                f"step={'yes' if self.has_step else 'no'}, "
                f"evidence={self.evidence.summary()})")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _symbol_content_sha256(symbol: OfficialSymbol) -> str:
    """Hash the SYMBOL's content, never the library file that contains it.

    Generated parts are source, so ``tests/ecad/test_library_parts.py``
    demands that a regeneration on any machine reproduces the committed
    sidecar byte for byte. That rules out hashing the installed
    ``<Lib>.kicad_sym`` file, which is what this ingest used to record:
    ``Device.kicad_sym`` is 2.4 MB and 538 symbols, of which a capacitor
    ingest consumes exactly one. Its file hash is therefore a fingerprint of
    *which build of KiCad's symbol library is installed* — different between
    the macOS app bundle and the Linux ``kicad-libraries`` package, and
    liable to move again the next time the PPA publishes — rather than
    provenance of ``Device:C``. Recording it made the committed artifact
    unreproducible off the machine that generated it.

    What is hashed here is the symbol as this ingest consumes it: identity,
    the KiCad-sourced metadata, and the pads. That is install-independent,
    and it still changes — loudly, and only for the affected part — if
    upstream edits the symbol under us, which is the drift the regeneration
    test exists to catch.

    "As this ingest consumes it" is the precise claim, and it is weaker than
    "as KiCad stores it": where KiCad draws a pin unnamed, ``pin=`` below
    carries the ``P<pad>`` label ``load_official_symbol`` synthesized, not a
    name from the library. That is deliberate — this hash pins the input the
    generated part was actually built from — but it does mean the value is a
    hash of the symbol *plus this module's reading of it*, and would move if
    that reading changed. ``provenance.synthesized_pin_names`` is where a
    reader sees which labels are ours.

    Symbol graphics are not covered: nothing downstream reads them. The
    emitted symbol's own geometry is already hashed as
    ``generated.kicad_sym_sha256``.
    """
    lines = [
        f"lib_id={symbol.lib_id}",
        f"reference={symbol.reference}",
        f"datasheet={symbol.datasheet}",
        f"description={symbol.description}",
        f"footprint={symbol.footprint}",
        f"extends={symbol.extends or ''}",
    ]
    # Sorted, so the hash cannot move with the library's pin declaration
    # order. Pads are unique within a symbol, so the sort is total.
    lines += [f"pin={p.pad}\t{p.name}\t{p.etype.value}"
              for p in sorted(symbol.pins, key=lambda p: p.pad)]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _resolve_footprint(part: LibraryPart,
                       index: FootprintIndex) -> FootprintRef:
    """Resolve the part's DEFAULT footprint descriptor to one footprint.

    "Default" is the operative word: these parts are valued per instance and
    a caller may pass any footprint at construction time. Gating the default
    is the honest gate — pretending one footprint fits every instance is not.
    """
    if isinstance(part.footprint, PackageSpec):
        try:
            info = index.resolve(part.footprint)
        except LookupError as exc:
            raise IngestError(f"{part.lib_id}: {exc}") from exc
        return FootprintRef(lib=info.lib, name=info.name)
    lib_id = part.footprint
    if ":" not in lib_id:
        raise IngestError(
            f"{part.lib_id}: footprint {lib_id!r} must be 'Lib:Name'")
    lib, fp_name = lib_id.split(":", 1)
    return FootprintRef(lib=lib, name=fp_name)


def _enrich(spec: PinSpec, part: LibraryPart) -> PinSpec:
    """Apply the catalog's role for this pad (default PASSIVE).

    The official symbol carries no roles — every pin arrives as
    ``PinRole.SIGNAL`` — and role is what drives design lint, the layout
    engine's power/ground handling and ``blocks.decoupling``. A jellybean
    two-terminal part is passive unless the catalog says otherwise.
    """
    role = part.roles.get(spec.pad, PinRole.PASSIVE)
    return PinSpec(pad=spec.pad, name=spec.name, etype=spec.etype, role=role,
                   gpio=spec.gpio, functions=spec.functions)


def _build_evidence(part: LibraryPart, symbol: OfficialSymbol,
                    pins: tuple[PinSpec, ...],
                    footprint_pads: set[str]) -> crossverify.Evidence:
    """2-source ledger: symbol pins x footprint pads, and nothing else.

    ``official``/``zephyr`` are deliberately left out. Feeding the symbol in
    as a second opinion on itself would be circular, and worse, crossverify
    labels the primary side "datasheet" in every claim it writes — which is
    exactly the false impression this flow must not leave behind.
    """
    evidence = crossverify.build_evidence(
        pins, official=None, zephyr=None,
        footprint_pads=footprint_pads, component=part.part_id)
    evidence.claims.append(crossverify.Claim(
        kind="source_mode", key="no_datasheet",
        values={"symbol": symbol.lib_id, "footprint": "installed KiCad library"},
        status="single_source",
        detail=("no datasheet was consulted; pin truth is the installed "
                "official symbol, corroborated only by the footprint pads"),
    ))
    if symbol.synthesized_names:
        evidence.claims.append(crossverify.Claim(
            kind="pin_names", key="synthesized",
            values={"symbol": ",".join(symbol.synthesized_names)},
            status="single_source",
            detail=("KiCad draws these pins unnamed; the P<pad> labels are "
                    "this ingest's, not the symbol's"),
        ))
    return evidence


def ingest(lib_id: str, *, out_dir: Path | None = None,
           index: FootprintIndex | None = None,
           share_dir: Path | None = None) -> IngestResult:
    """Ingest one catalogued library part and emit its four artifacts."""
    part = CATALOG_BY_LIB_ID.get(lib_id)
    if part is None:
        known = ", ".join(sorted(CATALOG_BY_LIB_ID))
        raise IngestError(f"{lib_id!r} is not in the catalog (known: {known})")

    symbol = load_official_symbol(part.lib_id, share_dir)
    if symbol is None:
        raise IngestError(
            f"{part.lib_id}: no such symbol in the installed KiCad libraries")
    if not symbol.pins:
        raise IngestError(f"{part.lib_id}: symbol resolved to zero pins")

    pins = tuple(_enrich(p, part) for p in symbol.pins)
    index = index or FootprintIndex.cached(INDEX_CACHE, share_dir)
    footprint = _resolve_footprint(part, index)

    validation = validate_footprint(index, footprint, {p.pad for p in pins})
    if not validation.ok or validation.info is None:
        raise IngestError(
            f"{part.lib_id}: default footprint {footprint.lib_id}: "
            + "; ".join(validation.errors or ("not in the installed index",)))
    info = validation.info
    has_step = info.has_step

    evidence = _build_evidence(part, symbol, pins, set(info.pad_numbers))
    conflicts = evidence.summary()["conflicts"]
    if conflicts:
        raise IngestError(
            f"{part.lib_id}: evidence ledger has {conflicts} conflict(s)")

    share = share_dir or kicad_share_dir()
    footprint_file = (share / "footprints" / f"{footprint.lib}.pretty"
                      / f"{footprint.name}.kicad_mod")

    record = {
        "name": part.name,
        "lib_id": part.lib_id,
        "pins": pins,
        "unit_plan": (UnitDef(name=part.unit_name or part.name,
                              pads=tuple(p.pad for p in pins)),),
        "footprint": footprint,
        "sourcing": None,       # generic part: no MPN, no LCSC, by definition
        "datasheet": symbol.datasheet,
        "description": symbol.description,
        "reference_prefix": symbol.reference or "U",
        "default_value": part.default_value or symbol.name,
        # The two string keys ride along in the summary on purpose: codegen
        # renders evidence_summary into <id>.md, and that is the one place a
        # human reads a part's evidence. A 4-source Espressif ledger and this
        # 2-source one otherwise look identical there — same counters, no hint
        # that nobody ever opened a datasheet.
        "evidence_summary": {**evidence.summary(),
                             "source_mode": EVIDENCE_MODE,
                             "datasheet": NO_DATASHEET},
        "provenance": {
            "ingest": "src/ecad/ingest/library_parts.py",
            "pin_source": "official-symbol",
            "official_symbol": part.lib_id,
            "datasheet": NO_DATASHEET,
            "evidence_mode": EVIDENCE_MODE,
            "footprint_source": (
                f"PackageSpec(family={part.footprint.family!r})"
                if isinstance(part.footprint, PackageSpec)
                else f"explicit {part.footprint!r}"),
            "footprint_is_default_only": True,
            "footprint_has_step": has_step,
            "synthesized_pin_names": list(symbol.synthesized_names),
            "notes": list(part.notes) + (
                [part.footprint_note] if part.footprint_note else []),
        },
        # Every hash here must be reproducible on a machine that is not this
        # one, or "generated parts are source" is a fiction. Hash the parts
        # consumed, at the granularity consumed — never the container they
        # were installed in; see _symbol_content_sha256.
        "source_hashes": {
            # Content of the one symbol, not of its 538-symbol library file.
            "symbol_sha256": _symbol_content_sha256(symbol),
            # A .kicad_mod IS one footprint, so the file hash is already at
            # per-part granularity: it moves only when THIS footprint moves.
            "footprint_sha256": (_sha256_file(footprint_file)
                                 if footprint_file.is_file() else ""),
            "pdf_sha256": "",   # no datasheet: stated, not omitted
        },
    }

    out = Path(out_dir) if out_dir is not None else OUT_DIR
    generated = codegen.generate(record, out)
    crossverify.save_evidence(evidence, out / f"{part.part_id}.evidence.json")
    return IngestResult(part=part, symbol=symbol, pins=pins,
                        footprint=footprint, has_step=has_step,
                        warnings=validation.warnings, evidence=evidence,
                        generated=generated)


def ingest_all(*, out_dir: Path | None = None,
               index: FootprintIndex | None = None,
               share_dir: Path | None = None) -> list[IngestResult]:
    """Ingest the whole catalog, in catalog order."""
    index = index or FootprintIndex.cached(INDEX_CACHE, share_dir)
    return [ingest(p.lib_id, out_dir=out_dir, index=index, share_dir=share_dir)
            for p in CATALOG]


# ── CLI ─────────────────────────────────────────────────────────────────────

_USAGE = ("usage: python -m src.ecad.ingest.library_parts "
          "list | ingest <lib_id> | ingest --all")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["list"] and len(args) == 1:
        for p in CATALOG:
            fp = (p.footprint.family if isinstance(p.footprint, PackageSpec)
                  else p.footprint)
            print(f"{p.lib_id:42s} -> {p.part_id:28s} {fp}")
        return 0
    if args[:1] == ["ingest"] and len(args) == 2:
        targets = ([p.lib_id for p in CATALOG] if args[1] == "--all"
                   else [args[1]])
        failed = 0
        index = FootprintIndex.cached(INDEX_CACHE)
        for lib_id in targets:
            try:
                print(ingest(lib_id, index=index).summary)
            except (IngestError, codegen.ClobberError) as exc:
                print(f"{lib_id}: FAILED: {exc}", file=sys.stderr)
                failed += 1
        return 1 if failed else 0
    print(_USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
