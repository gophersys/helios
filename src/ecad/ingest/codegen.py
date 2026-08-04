"""Generated-component emission: Component subclass + sidecar + symbol + doc.

codegen is the last factory stage: it freezes a fully cross-verified part
record into four reviewable artifacts in one output directory:

- ``<id>.py``         generated ``Component`` subclass with explicit typed
                      pin accessors (``sanitize_pin_name`` idents)
- ``<id>.json``       sidecar: provenance, source hashes, evidence summary,
                      footprint/sourcing, sha256 of the generated ``.py``
- ``<id>.kicad_sym``  readable-style symbol via ``SymbolModel``
- ``<id>.md``         per-part human doc (pins by unit, strapping warnings,
                      evidence summary, sourcing links)

Clobber-safety: the sidecar records the sha256 of the ``.py`` it wrote; a
regen aborts when the file on disk no longer matches — hand edits belong in
``<id>_overrides.py``, which the ``src.ecad.library`` registry applies at
load time and codegen never touches.

Everything is deterministic: the same part record produces byte-identical
files (no timestamps, sorted iteration everywhere).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..component import Component, sanitize_pin_name
from ..model import (
    ElectricalType,
    FootprintRef,
    PinRole,
    PinSpec,
    SourcingInfo,
    SymbolArt,
    UnitDef,
)
from ..symbol import SymbolModel

GENERATOR = "src/ecad/ingest/codegen.py"
CODEGEN_VERSION = 1

_LCSC_URL = "https://www.lcsc.com/product-detail/{lcsc}.html"


class ClobberError(RuntimeError):
    """Raised when regeneration would overwrite a hand-edited generated file."""


@dataclass(frozen=True)
class GeneratedPart:
    """Paths and identity of one generated part."""

    part_id: str
    class_name: str
    py_path: Path
    sidecar_path: Path
    sym_path: Path
    md_path: Path


# ── part-record access (dict-like or attribute-style) ───────────────────────


def _get(part: Any, key: str, default: Any = None) -> Any:
    """Read a field from a mapping or an object, with a default."""
    if isinstance(part, Mapping):
        return part.get(key, default)
    return getattr(part, key, default)


def part_id_for(name: str) -> str:
    """Deterministic module id for a part name (``ESP32-S3-WROOM-1`` →
    ``esp32_s3_wroom_1``). Also the artifact basename."""
    ident = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_")
    if not ident:
        raise ValueError(f"cannot derive a part id from name {name!r}")
    if ident[0].isdigit():
        ident = "P" + ident
    return ident.lower()


def class_name_for(name: str) -> str:
    """Deterministic Python class name for a part name (case preserved)."""
    ident = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_")
    if not ident:
        raise ValueError(f"cannot derive a class name from name {name!r}")
    if ident[0].isdigit():
        ident = "P" + ident
    return ident


# ── unit auto-plan ──────────────────────────────────────────────────────────


def _interface_key(name: str) -> str:
    """Interface grouping key for a COMM pin: primary name before any slash,
    then the first ``_`` token (``USB_D+`` → ``USB``), else the name with
    trailing digits/polarity marks stripped (``TXD0`` → ``TXD``)."""
    base = name.split("/")[0]
    if "_" in base:
        return base.split("_")[0]
    stripped = base.rstrip("+-0123456789")
    return stripped or base


def _group_for(spec: PinSpec) -> str:
    if spec.role in (PinRole.POWER, PinRole.GROUND):
        return "Power"
    if spec.role is PinRole.CONTROL:
        return "Control"
    if spec.role is PinRole.STRAPPING:
        return "Strapping"
    if spec.role is PinRole.COMM:
        return _interface_key(spec.name)
    if spec.etype in (ElectricalType.POWER_IN, ElectricalType.POWER_OUT):
        return "Power"  # role didn't say, electrical type does
    return "GPIO"


def auto_unit_plan(pins: Sequence[PinSpec]) -> tuple[UnitDef, ...]:
    """Group PinSpecs into a deterministic unit plan.

    Groups: Power (power/ground roles or power etypes), Control, one unit
    per COMM interface (key from the pin name), Strapping, GPIO (everything
    else, incl. plain signals and NC pads). Unit order is fixed — Power,
    Control, interfaces alphabetically, Strapping, GPIO — and pads keep
    their original record order within each unit. Empty groups are omitted.
    """
    groups: dict[str, list[str]] = {}
    for spec in pins:
        groups.setdefault(_group_for(spec), []).append(spec.pad)
    fixed = ("Power", "Control", "Strapping", "GPIO")
    interfaces = sorted(k for k in groups if k not in fixed)
    ordered = [k for k in ("Power", "Control", *interfaces, "Strapping", "GPIO")
               if k in groups]
    return tuple(UnitDef(name=k, pads=tuple(groups[k])) for k in ordered)


# ── .py emission ────────────────────────────────────────────────────────────


def _pin_literal(s: PinSpec) -> str:
    parts = [f"pad={s.pad!r}", f"name={s.name!r}",
             f"etype=ElectricalType.{s.etype.name}",
             f"role=PinRole.{s.role.name}"]
    if s.gpio is not None:
        parts.append(f"gpio={s.gpio}")
    if s.functions:
        parts.append(f"functions={tuple(s.functions)!r}")
    return f"PinSpec({', '.join(parts)}),"


def _accessor_lines(pins: Sequence[PinSpec]) -> tuple[list[str], bool]:
    """Explicit @property accessors, one per distinct sanitized pin name.

    Properties raise KeyError (never AttributeError) internally so that
    ``Component.__getattr__`` cannot mask a real failure. Repeated names get
    a tuple accessor; idents shadowing the Component API or claimed by two
    distinct names are skipped with a comment (``pin(name)`` still works).
    Returns (lines, any_property_emitted).
    """
    pads_by_name: dict[str, list[str]] = {}
    for s in pins:
        pads_by_name.setdefault(s.name, []).append(s.pad)
    etype_by_name = {s.name: s.etype.value for s in pins}
    ident_names: dict[str, list[str]] = {}
    for name in pads_by_name:
        ident_names.setdefault(sanitize_pin_name(name), []).append(name)

    reserved = set(dir(Component)) | {"ref"}
    lines: list[str] = []
    emitted = False
    for ident in sorted(ident_names):
        names = sorted(ident_names[ident])
        if len(names) > 1:
            lines += ["", f"    # ident {ident!r} is ambiguous (pins "
                          f"{names}); use pin(name)"]
            continue
        name = names[0]
        if ident in reserved:
            lines += ["", f"    # pin {name!r} would shadow Component."
                          f"{ident}; use pin({name!r})"]
            continue
        pads = pads_by_name[name]
        etype = etype_by_name[name]
        lines.append("")
        lines.append("    @property")
        if len(pads) == 1:
            lines.append(f"    def {ident}(self) -> Pin:")
            lines.append(f'        """Pad {pads[0]} — {name!r} ({etype})."""')
            lines.append(f"        return self._pin({pads[0]!r})")
        else:
            lines.append(f"    def {ident}(self) -> tuple[Pin, ...]:")
            lines.append(f'        """Pads {", ".join(pads)} — pins named '
                         f'{name!r} ({etype})."""')
            lines.append(f"        return self._pins_named({name!r})")
        emitted = True
    return lines, emitted


def _symbol_art_lines(art: SymbolArt) -> list[str]:
    """``symbol_art = SymbolArt(...)`` for the generated class.

    Written out in full rather than referenced by lib_id: a generated part is
    source, and a part whose drawing is fetched from whatever KiCad happens
    to be installed is not reproducible. The literal is verbose, and that is
    the correct trade — it is reviewable in a diff and it pins the artwork
    the committed symbol was built from.
    """
    lines = ["", "    symbol_art = SymbolArt("]
    lines.append("        children=(")
    for suffix, items in art.children:
        lines.append(f"            ({suffix!r}, (")
        for item in items:
            lines.append(f"                {item!r},")
        lines.append("            )),")
    lines.append("        ),")
    lines.append("        pins=(")
    for p in art.pins:
        lines.append(f"            PinArt(pad={p.pad!r}, x={p.x}, y={p.y}, "
                     f"angle={p.angle}, length={p.length}, style={p.style!r}, "
                     f"unnamed={p.unnamed!r}),")
    lines.append("        ),")
    lines.append(f"        bbox={art.bbox!r},")
    lines.append(f"        hide_pin_numbers={art.hide_pin_numbers!r},")
    lines.append(f"        hide_pin_names={art.hide_pin_names!r},")
    lines.append(f"        pin_names_offset={art.pin_names_offset!r},")
    lines.append("    )")
    return lines


def _value_ctor_lines(default_value: str) -> list[str]:
    """``__init__(value=…, footprint=None)`` for a part valued per instance.

    A jellybean passive is one symbol standing for thousands of orderable
    parts: ``Device:C`` is a 100nF 0402 only once a caller says so. Generated
    classes therefore need the same ergonomics the hand-written composer
    passives had — ``Capacitor("100nF", cap_footprint("C_0402"))`` — or every
    consumer has to construct-then-mutate, and the class-level footprint
    silently becomes a lie for the instances that overrode it.
    """
    return [
        "",
        f"    value = {default_value!r}",
        "",
        f"    def __init__(self, value: str = {default_value!r},",
        "                 footprint: FootprintRef | None = None) -> None:",
        '        """Per-instance value and footprint (see class docstring)."""',
        "        super().__init__()",
        "        self.value = value",
        "        if footprint is not None:",
        "            self.footprint = footprint",
    ]


def _render_py(part_id: str, cls_name: str, name: str, lib_id: str,
               description: str, datasheet: str,
               footprint: FootprintRef | None, sourcing: SourcingInfo | None,
               unit_plan: tuple[UnitDef, ...],
               pins: Sequence[PinSpec], reference_prefix: str,
               default_value: str = "",
               symbol_art: SymbolArt | None = None) -> str:
    accessors, uses_pin = _accessor_lines(pins)

    model_names = ["ElectricalType", "PinRole", "PinSpec", "UnitDef",
                   "UnitStrategy"]
    if footprint is not None or default_value:
        model_names.append("FootprintRef")
    if sourcing is not None:
        model_names.append("SourcingInfo")
    if symbol_art is not None:
        model_names += ["PinArt", "SymbolArt"]
    comp_names = ["Component"] + (["Pin"] if uses_pin else [])

    lines = [
        f'"""{name} — typed component (ingestion-factory output).',
        "",
        f"GENERATED by {GENERATOR} — DO NOT EDIT.",
        f"Edits go in {part_id}_overrides.py (applied by the src.ecad.library "
        "registry).",
        '"""',
        "",
        f"from src.ecad.component import {', '.join(comp_names)}",
        "from src.ecad.model import (",
        *(f"    {n}," for n in sorted(model_names)),
        ")",
        "",
        "",
        f"class {cls_name}(Component):",
        f"    part_name = {name!r}",
        f"    lib_id = {lib_id!r}",
        f"    reference_prefix = {reference_prefix!r}",
        f"    description = {description!r}",
        f"    datasheet = {datasheet!r}",
    ]
    if footprint is not None:
        fp = (f"    footprint = FootprintRef(lib={footprint.lib!r}, "
              f"name={footprint.name!r}, source={footprint.source!r}")
        if footprint.path:
            fp += f", path={footprint.path!r}"
        lines.append(fp + ")")
    if sourcing is not None:
        lines.append(
            f"    sourcing = SourcingInfo(manufacturer={sourcing.manufacturer!r}, "
            f"mpn={sourcing.mpn!r}, lcsc={sourcing.lcsc!r}, "
            f"datasheet_url={sourcing.datasheet_url!r})")
    lines.append("    unit_strategy = UnitStrategy.EXPLICIT")
    lines.append("    unit_plan = (  # frozen at generation time")
    for u in unit_plan:
        lines.append(f"        UnitDef(name={u.name!r}, pads={tuple(u.pads)!r}),")
    lines.append("    )")
    lines.append("    _PIN_SPECS = (")
    for s in pins:
        lines.append("        " + _pin_literal(s))
    lines.append("    )")
    if symbol_art is not None:
        lines += _symbol_art_lines(symbol_art)
    if default_value:
        lines += _value_ctor_lines(default_value)
    lines += accessors
    return "\n".join(lines) + "\n"


# ── .md emission ────────────────────────────────────────────────────────────


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|") or "—"


def _render_md(part_id: str, name: str, lib_id: str, description: str,
               datasheet: str, footprint: FootprintRef | None,
               sourcing: SourcingInfo | None, unit_plan: tuple[UnitDef, ...],
               pins: Sequence[PinSpec], evidence_summary: Mapping) -> str:
    by_pad = {s.pad: s for s in pins}
    lines = [
        f"# {name}",
        "",
        f"> GENERATED by {GENERATOR} — DO NOT EDIT. "
        f"Edits go in `{part_id}_overrides.py`.",
        "",
    ]
    if description:
        lines += [description, ""]
    lines.append(f"- **lib_id**: `{lib_id}`")
    if footprint is not None:
        lines.append(f"- **Footprint**: `{footprint.lib_id}` ({footprint.source})")
    if datasheet:
        lines.append(f"- **Datasheet**: <{datasheet}>")
    lines += ["", "## Sourcing", ""]
    if sourcing is not None and (sourcing.manufacturer or sourcing.mpn
                                 or sourcing.lcsc or sourcing.datasheet_url):
        if sourcing.manufacturer or sourcing.mpn:
            lines.append(f"- {sourcing.manufacturer or '—'} "
                         f"`{sourcing.mpn or '—'}`")
        if sourcing.lcsc:
            lines.append(f"- LCSC: [{sourcing.lcsc}]"
                         f"({_LCSC_URL.format(lcsc=sourcing.lcsc)})")
        if sourcing.datasheet_url:
            lines.append(f"- Datasheet PDF: <{sourcing.datasheet_url}>")
    else:
        lines.append("- none recorded")
    lines += ["", "## Pins by unit", ""]
    for i, u in enumerate(unit_plan, start=1):
        lines += [f"### Unit {i}: {u.name}", "",
                  "| Pad | Name | Type | Role | GPIO | Functions |",
                  "|---|---|---|---|---|---|"]
        for pad in u.pads:
            s = by_pad[pad]
            lines.append(
                f"| {_md_cell(s.pad)} | {_md_cell(s.name)} | {s.etype.value} "
                f"| {s.role.value} "
                f"| {s.gpio if s.gpio is not None else '—'} "
                f"| {_md_cell(', '.join(s.functions))} |")
        lines.append("")
    lines += ["## Strapping warnings", ""]
    strapping = [s for s in pins if s.role is PinRole.STRAPPING]
    if strapping:
        for s in strapping:
            lines.append(
                f"- `{s.name}` (pad {s.pad}): strapping pin — the level "
                "sampled at reset selects boot/config options; verify pull "
                "resistors and boot-time bus activity before reusing it.")
    else:
        lines.append("- none")
    lines += ["", "## Evidence", ""]
    if evidence_summary:
        for key in sorted(evidence_summary):
            value = evidence_summary[key]
            if isinstance(value, (list, tuple)):
                value = ", ".join(str(v) for v in value)
            lines.append(f"- **{key}**: {value}")
    else:
        lines.append("- no evidence summary recorded")
    return "\n".join(lines) + "\n"


# ── clobber safety ──────────────────────────────────────────────────────────


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_clobber(py_path: Path, sidecar_path: Path, part_id: str) -> None:
    """Abort regeneration if the on-disk .py no longer matches its sidecar."""
    if not py_path.exists():
        return
    hint = (f"put local changes in {part_id}_overrides.py (applied by the "
            f"src.ecad.library registry) and regenerate")
    if not sidecar_path.exists():
        raise ClobberError(
            f"{py_path} exists but its sidecar {sidecar_path.name} is "
            f"missing — cannot prove it is unedited; {hint}")
    try:
        recorded = json.loads(sidecar_path.read_text())["generated"]["py_sha256"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ClobberError(
            f"sidecar {sidecar_path} is unreadable ({exc}) — cannot verify "
            f"{py_path.name}; {hint}") from exc
    if _sha256(py_path.read_bytes()) != recorded:
        raise ClobberError(
            f"{py_path} was modified after generation (sha256 mismatch vs "
            f"sidecar) — refusing to overwrite hand edits; {hint}")


# ── entry point ─────────────────────────────────────────────────────────────


def generate(part: Any, out_dir: Path) -> GeneratedPart:
    """Emit ``<id>.py`` / ``<id>.json`` / ``<id>.kicad_sym`` / ``<id>.md``.

    ``part`` is dict-like (mapping or attributes) with: name, lib_id,
    pins (PinSpec list), optional unit_plan (auto-planned when empty),
    footprint (FootprintRef|None), sourcing (SourcingInfo|None), datasheet,
    description, evidence_summary, and optional provenance / source_hashes
    for the sidecar. A non-empty ``default_value`` marks the part as valued
    per instance and emits ``__init__(value=…, footprint=None)`` — the
    jellybean-passive ergonomics. Deterministic; clobber-safe (see
    ``ClobberError``).
    """
    name = _get(part, "name") or ""
    if not name:
        raise ValueError("part record has no name")
    pins = tuple(_get(part, "pins") or ())
    if not pins:
        raise ValueError(f"part {name!r} has no pins")
    lib_id = _get(part, "lib_id") or name
    description = _get(part, "description") or ""
    datasheet = _get(part, "datasheet") or ""
    footprint: FootprintRef | None = _get(part, "footprint")
    sourcing: SourcingInfo | None = _get(part, "sourcing")
    evidence_summary: Mapping = _get(part, "evidence_summary") or {}
    provenance: Mapping = _get(part, "provenance") or {}
    source_hashes: Mapping = _get(part, "source_hashes") or {}
    reference_prefix = _get(part, "reference_prefix") or "U"
    # Non-empty => the part is valued per instance and gets a
    # ``__init__(value=…, footprint=None)``; see _value_ctor_lines.
    default_value = _get(part, "default_value") or ""
    # The source symbol's own drawing, when the ingest had one to preserve.
    symbol_art: SymbolArt | None = _get(part, "symbol_art")
    if symbol_art is not None and not symbol_art.children:
        symbol_art = None
    unit_plan = tuple(_get(part, "unit_plan") or ()) or auto_unit_plan(pins)

    part_id = part_id_for(name)
    cls_name = class_name_for(name)
    out_dir = Path(out_dir)
    py_path = out_dir / f"{part_id}.py"
    sidecar_path = out_dir / f"{part_id}.json"
    sym_path = out_dir / f"{part_id}.kicad_sym"
    md_path = out_dir / f"{part_id}.md"

    _check_clobber(py_path, sidecar_path, part_id)

    py_text = _render_py(part_id, cls_name, name, lib_id, description,
                         datasheet, footprint, sourcing, unit_plan, pins,
                         reference_prefix, default_value, symbol_art)

    # Prove the generated source is importable and use ITS class for the
    # symbol, so .py and .kicad_sym can never drift apart.
    namespace: dict[str, Any] = {}
    exec(compile(py_text, str(py_path), "exec"), namespace)  # noqa: S102
    cls: type[Component] = namespace[cls_name]
    sym_text = (SymbolModel.from_component(cls(), style="readable")
                .kicad_sym_text())
    md_text = _render_md(part_id, name, lib_id, description, datasheet,
                         footprint, sourcing, unit_plan, pins,
                         evidence_summary)

    sidecar = {
        "id": part_id,
        "class_name": cls_name,
        "part_name": name,
        "lib_id": lib_id,
        "description": description,
        "datasheet": datasheet,
        "footprint": None if footprint is None else {
            "lib": footprint.lib, "name": footprint.name,
            "source": footprint.source, "path": footprint.path,
        },
        "sourcing": None if sourcing is None else {
            "manufacturer": sourcing.manufacturer, "mpn": sourcing.mpn,
            "lcsc": sourcing.lcsc, "datasheet_url": sourcing.datasheet_url,
        },
        "pin_count": len(pins),
        "default_value": default_value,
        "unit_plan": [{"name": u.name, "pads": list(u.pads)} for u in unit_plan],
        "evidence_summary": dict(evidence_summary),
        "provenance": dict(provenance),
        "source_hashes": dict(source_hashes),
        "generated": {
            "generator": GENERATOR,
            "codegen_version": CODEGEN_VERSION,
            "py_sha256": _sha256(py_text.encode()),
            "kicad_sym_sha256": _sha256(sym_text.encode()),
            "md_sha256": _sha256(md_text.encode()),
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    py_path.write_text(py_text)
    sidecar_path.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n")
    sym_path.write_text(sym_text)
    md_path.write_text(md_text)
    return GeneratedPart(part_id=part_id, class_name=cls_name, py_path=py_path,
                         sidecar_path=sidecar_path, sym_path=sym_path,
                         md_path=md_path)
