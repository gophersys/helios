"""Factory orchestrator CLI: ``status`` | ``step <id>``.

``status`` seeds one record per cached-datasheet manifest entry, recomputes
every gate over ``data/ingest/*/record.json`` (self-healing on KiCad or
Zephyr bumps) and regenerates ``COMPONENTS.md`` at the repo root.
``step <id>`` runs exactly ONE stage transition for one component: it first
runs that stage's *builder* (the real work — official-symbol ingest,
gated LLM datasheet extraction, evidence ledger, codegen + ERC), then the
stage's deterministic gate, then persists and re-renders the projection.

Datasheet LLM extraction shells out to the real ``claude`` CLI and only
runs when ``FACTORY_LLM=1``; otherwise the record carries
``datasheet_status=blocked-on-llm`` and the official-symbol path alone
satisfies the ``extracted`` gate (official-symbol-first design).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

from ..component import Component
from ..design import Design
from ..footprints import FootprintIndex, validate_footprint
from ..model import ElectricalType, FootprintRef, PinRole, PinSpec, SourcingInfo
from ..symbol import SymbolModel
from . import codegen, crossverify
from . import datasheet as datasheet_mod
from . import zephyr as zephyr_mod
from .kicad_official import load_official_symbol
from .state import (
    ComponentRecord,
    GateResult,
    Stage,
    register_gate,
    render_components_md,
    status_all,
    utc_now,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
_LCSC_RE = re.compile(r"C\d+")
_IO_RE = re.compile(r"^(?:GPIO|IO)(\d+)$")
_SOC_VARIANTS = ("s2", "s3", "c3", "c6", "h2")
MIN_PDF_BYTES = 10_000


class StageBlocked(RuntimeError):
    """A stage builder cannot produce its artifact; message goes to the gate."""


def make_ctx(repo: Path = REPO_ROOT) -> dict:
    return {"repo": repo, "root": repo / "data" / "ingest",
            "datasheets": repo / "data" / "datasheets"}


def soc_for(comp_id: str) -> str:
    """Component id -> Zephyr SoC name (esp32-s3-wroom-1 -> esp32s3)."""
    parts = comp_id.lower().split("-")
    if len(parts) > 1 and parts[1] in _SOC_VARIANTS:
        return "esp32" + parts[1]
    return "esp32"


def strapping_for(comp_id: str) -> frozenset[int]:
    """Strapping GPIOs for a component id, empty when the SoC is unknown.

    Deliberately NOT soc_for(): that falls back to "esp32" for anything it
    does not recognize, which is survivable for a GPIO count but not for
    strapping — it would stamp IO0/IO2/IO5 as strapping pins on a part that
    is not an ESP32 at all. An unknown SoC has no strapping table, and
    inventing one is how a check starts asserting things nobody verified.
    """
    if not comp_id.lower().startswith("esp32"):
        return frozenset()
    return frozenset(zephyr_mod.STRAPPING.get(soc_for(comp_id), ()))


def lib_id_for(record: ComponentRecord) -> str:
    """Official-symbol lib_id: modules -> RF_Module, SoCs -> MCU_Espressif."""
    library = "RF_Module" if record.kind == "module" else "MCU_Espressif"
    return f"{library}:{str(record.meta.get('chip', record.id)).upper()}"


# ── pin (de)serialization + enrichment ──────────────────────────────────────

def _pin_to_json(p: PinSpec) -> dict:
    return {"pad": p.pad, "name": p.name, "etype": p.etype.value,
            "role": p.role.value, "gpio": p.gpio, "functions": list(p.functions)}


def _pin_from_json(d: dict) -> PinSpec:
    return PinSpec(pad=d["pad"], name=d["name"],
                   etype=ElectricalType(d["etype"]), role=PinRole(d["role"]),
                   gpio=d.get("gpio"),
                   functions=tuple(d.get("functions") or ()))


def _enrich(p: PinSpec, strapping: frozenset[int] = frozenset()) -> PinSpec:
    """Derive gpio number and role for an official-symbol pin (role=SIGNAL).

    ``strapping`` is the SoC's strapping GPIO set. Without it no pin ever
    received PinRole.STRAPPING, which made three things dead at once: the
    strapping cross-check could only ever return "no verdict",
    codegen.auto_unit_plan never emitted a Strapping unit, and the generated
    markdown printed "Strapping warnings: none" for parts that have them.
    """
    up = p.name.split("/", 1)[0].strip().upper()
    m = _IO_RE.fullmatch(up)
    gpio = int(m.group(1)) if m else None
    role = p.role
    if role is PinRole.SIGNAL:
        if p.etype is ElectricalType.NO_CONNECT or up == "NC":
            role = PinRole.NC
        elif up.startswith("GND") or up in ("VSS", "EPAD"):
            role = PinRole.GROUND
        elif p.etype in (ElectricalType.POWER_IN, ElectricalType.POWER_OUT):
            role = PinRole.POWER
        elif gpio is not None:
            # Strapping beats plain GPIO: these pins must be free at boot, so
            # the distinction has to survive into the generated part.
            role = PinRole.STRAPPING if gpio in strapping else PinRole.GPIO
    return PinSpec(pad=p.pad, name=p.name, etype=p.etype, role=role,
                   gpio=gpio, functions=p.functions)


def _power_to_json(p: datasheet_mod.PowerSpec) -> dict:
    """Serialize the extracted supply envelope + decoupling recommendation."""
    return {
        "voltage_min": p.voltage_min,
        "voltage_typ": p.voltage_typ,
        "voltage_max": p.voltage_max,
        "power_pins": list(p.power_pins),
        "decoupling_caps": [{"value": c.value, "purpose": c.purpose}
                            for c in p.decoupling_caps],
    }


def _power_from_json(d: dict) -> datasheet_mod.PowerSpec:
    return datasheet_mod.PowerSpec(
        voltage_min=float(d.get("voltage_min", 0.0)),
        voltage_typ=float(d.get("voltage_typ", 0.0)),
        voltage_max=float(d.get("voltage_max", 0.0)),
        power_pins=tuple(d.get("power_pins") or ()),
        decoupling_caps=tuple(
            datasheet_mod.CapSpec(value=c.get("value", ""),
                                  purpose=c.get("purpose", ""))
            for c in (d.get("decoupling_caps") or [])),
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.is_file() else {}


def _pins_for(record: ComponentRecord, root: Path) -> tuple[tuple[PinSpec, ...], str]:
    """Best pin source: datasheet extraction, else official symbol."""
    d = root / record.id
    for fname, source in (("extracted.json", "datasheet"),
                          ("official.json", "official")):
        pins = [_pin_from_json(p) for p in _read_json(d / fname).get("pins", [])]
        if pins:
            return tuple(pins), source
    raise StageBlocked("no pin source on record (run the extracted stage)")


# ── gate overrides (state.py defaults deepened for factory records) ─────────

@register_gate(Stage.DISCOVERED)
def _gate_discovered(record: ComponentRecord, ctx: dict) -> GateResult:
    missing = [f for f in ("id", "vendor", "kind") if not getattr(record, f)]
    if missing:
        return GateResult(False, f"record missing fields: {missing}")
    manifest = record.meta.get("manifest")
    if not isinstance(manifest, dict):
        return GateResult(True, "record complete")     # non-factory record
    lcsc = str(manifest.get("lcsc", ""))
    if not _LCSC_RE.fullmatch(lcsc):
        return GateResult(False, f"bad LCSC id {lcsc!r} (want C<digits>)")
    pdf = Path(ctx.get("datasheets")
               or REPO_ROOT / "data" / "datasheets") / str(record.meta.get("pdf", ""))
    if not pdf.is_file():
        return GateResult(False, f"cached datasheet missing: {pdf.name}")
    if pdf.stat().st_size < MIN_PDF_BYTES:
        return GateResult(False, f"{pdf.name} too small ({pdf.stat().st_size} B)")
    with open(pdf, "rb") as f:
        if f.read(5) != b"%PDF-":
            return GateResult(False, f"{pdf.name} is not a PDF (bad magic)")
    return GateResult(True, f"{pdf.name} cached, lcsc {lcsc}")


@register_gate(Stage.EXTRACTED)
def _gate_extracted(record: ComponentRecord, ctx: dict) -> GateResult:
    root = ctx.get("root")
    if root is None:
        return GateResult(False, "no ingest root in ctx")
    d = Path(root) / record.id
    n_ds = len(_read_json(d / "extracted.json").get("pins", []))
    n_off = len(_read_json(d / "official.json").get("pins", []))
    if n_ds:
        extra = f" + official symbol ({n_off} pins)" if n_off else ""
        return GateResult(True, f"{n_ds} datasheet pins{extra}")
    if n_off:
        note = (", datasheet blocked-on-llm (FACTORY_LLM unset)"
                if record.meta.get("datasheet_status") == "blocked-on-llm" else "")
        return GateResult(True, f"{n_off} official-symbol pins{note}")
    if record.meta.get("datasheet_status") == "blocked-on-llm":
        return GateResult(False, "blocked-on-llm: no official symbol and "
                                 "FACTORY_LLM unset")
    return GateResult(False, "extracted.json missing")


# ── stage builders (the real work; gates then judge the artifacts) ──────────

def _build_extracted(record: ComponentRecord, ctx: dict) -> None:
    d = Path(ctx["root"]) / record.id
    d.mkdir(parents=True, exist_ok=True)
    lib_id = lib_id_for(record)
    official = load_official_symbol(lib_id)
    if official is not None:
        strapping = strapping_for(record.id)
        payload = {"lib_id": lib_id, "footprint": official.footprint,
                   "datasheet": official.datasheet,
                   "description": official.description,
                   "pins": [_pin_to_json(_enrich(p, strapping))
                            for p in official.pins]}
        (d / "official.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n")
        record.meta["official_symbol"] = lib_id
    if os.environ.get("FACTORY_LLM") == "1":
        pdf = Path(ctx["datasheets"]) / str(record.meta.get("pdf", ""))
        part = datasheet_mod.extract(pdf)   # real `claude` CLI runner
        payload = {
            "chip_name": part.chip_name, "package": part.package,
            "manufacturer": part.manufacturer,
            "description": part.description,
            "pins": [_pin_to_json(p.spec) for p in part.pins],
            "power": _power_to_json(part.power),
            # datasheet.py extracts and validates a PowerSpec that used to
            # stop here: the electrical rules keyed on supply voltage and
            # decoupling (PWR-004/005/007) could only ever answer "no data",
            # because the one source that has it never reached the artifact.
            "strapping_pins": list(part.strapping_pins),
            "strapping_notes": list(part.strapping_notes),
            "provenance": {"pdf_sha256": part.provenance.pdf_sha256,
                           "pages_used": list(part.provenance.pages_used)},
        }
        (d / "extracted.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n")
        record.meta["datasheet_status"] = "extracted"
    else:
        record.meta["datasheet_status"] = "blocked-on-llm"


class _SocEvidence:
    """Adapter: zephyr.SocInfo -> the duck-typed crossverify contract."""

    def __init__(self, soc: zephyr_mod.SocInfo) -> None:
        self.ngpios = soc.gpio_count
        self.input_only = {g for g, i in soc.gpios.items() if i.input_only}
        self.strapping = set(soc.strapping)
        self.signals = {k: {v} for k, v in soc.signals.items()}


def _write_evidence(record: ComponentRecord, ctx: dict,
                    footprint_pads: set[str] | None) -> crossverify.Evidence:
    root = Path(ctx["root"])
    pins, source = _pins_for(record, root)
    # Only compare datasheet-vs-official when both exist independently
    # (feeding official pins back as "extracted" would be circular).
    official = None
    if source == "datasheet" and record.meta.get("official_symbol"):
        official = load_official_symbol(str(record.meta["official_symbol"]))
    # Only bring Zephyr silicon data to bear on a part it actually describes.
    # soc_for falls back to "esp32" for anything unrecognized, so a non-ESP32
    # part was being cross-checked against ESP32 GPIO counts, input-only lists
    # and strapping tables — assertions about silicon nobody confirmed it has.
    zephyr_view = None
    if record.id.lower().startswith("esp32"):
        tree = zephyr_mod.ensure(Path(ctx["repo"]))
        soc = tree.soc(soc_for(record.id))
        record.meta["soc"] = soc.name
        zephyr_view = _SocEvidence(soc)
    ev = crossverify.build_evidence(pins, official=official,
                                    zephyr=zephyr_view,
                                    footprint_pads=footprint_pads,
                                    component=record.id)
    ev_path = root / record.id / "evidence.json"
    # Carry recorded waivers forward: rebuilding evidence must never discard
    # a cited human decision. A waiver re-applies iff the same claim
    # (kind:key) conflicts again with the SAME values.
    if ev_path.is_file():
        try:
            prev = crossverify.load_evidence(ev_path)
        except (ValueError, KeyError):
            prev = None
        if prev is not None:
            for old in prev.claims:
                if old.status != "waived" or not old.waiver:
                    continue
                cur = ev.find(old.kind, old.key)
                if (cur is not None and cur.status == "conflict"
                        and cur.values == old.values):
                    ev.waive(old.kind, old.key, **old.waiver)
    crossverify.save_evidence(ev, ev_path)
    return ev


def _footprint_pads_for(record: ComponentRecord) -> set[str] | None:
    """Pads of the record's resolved footprint, or None if none is resolved."""
    ref = str(record.meta.get("footprint", ""))
    if ":" not in ref:
        return None
    lib, name = ref.split(":", 1)
    info = FootprintIndex.cached(
        REPO_ROOT / "data" / "footprint_index.json").get(f"{lib}:{name}")
    return set(info.pad_numbers) if info is not None else None


def _build_cross_verified(record: ComponentRecord, ctx: dict) -> None:
    # Pass the pads back in when the record already has a footprint.
    # _write_evidence rebuilds the ledger from scratch, so passing None here
    # ERASED the pins_vs_footprint claim that _build_footprint had written —
    # and nothing restored it: the footprint_resolved gate passes on the mere
    # presence of meta["footprint"], so a `factory status` recompute
    # re-promotes the record without ever re-running that comparison. The
    # symbol's pin set then stops being checked against the footprint's pads
    # for good, and a KiCad library bump could break the pairing unnoticed.
    _write_evidence(record, ctx, footprint_pads=_footprint_pads_for(record))


def _component_class(record: ComponentRecord,
                     pins: tuple[PinSpec, ...]) -> type[Component]:
    name = str(record.meta.get("chip", record.id))
    return type(codegen.class_name_for(name), (Component,), {
        "part_name": name, "lib_id": lib_id_for(record),
        "_PIN_SPECS": tuple(pins)})


def _build_symbol(record: ComponentRecord, ctx: dict) -> None:
    root = Path(ctx["root"])
    pins, _ = _pins_for(record, root)
    cls = _component_class(record, pins)
    text = SymbolModel.from_component(cls(), style="readable") \
        .to_kicad_sym().to_sexpr()
    (root / record.id / f"{record.id}.kicad_sym").write_text(text)


def _build_footprint(record: ComponentRecord, ctx: dict) -> None:
    root = Path(ctx["root"])
    official = _read_json(root / record.id / "official.json")
    fp_id = str(record.meta.get("footprint") or official.get("footprint") or "")
    if ":" not in fp_id:
        raise StageBlocked("no pre-linked footprint (official symbol absent) — "
                           "set meta.footprint to an explicit Lib:Name")
    lib, name = fp_id.split(":", 1)
    ref = FootprintRef(lib=lib, name=name)
    index = ctx.get("fp_index") or FootprintIndex.cached(
        Path(ctx["repo"]) / "data" / "footprint_index.json")
    pins, _ = _pins_for(record, root)
    val = validate_footprint(index, ref, {p.pad for p in pins})
    if not val.ok:
        raise StageBlocked(f"footprint {fp_id}: " + "; ".join(val.errors))
    record.meta["footprint"] = fp_id
    record.meta["footprint_has_step"] = bool(val.info and val.info.has_step)
    if val.info is not None:   # extend the ledger with pins-vs-pads claims
        _write_evidence(record, ctx, footprint_pads=set(val.info.pad_numbers))


def _build_sourcing(record: ComponentRecord, ctx: dict) -> None:
    manifest = record.meta.get("manifest") or {}
    lcsc = str(manifest.get("lcsc", ""))
    if not _LCSC_RE.fullmatch(lcsc):
        raise StageBlocked(f"bad LCSC id {lcsc!r} in manifest")
    pdf = Path(ctx["datasheets"]) / str(record.meta.get("pdf", ""))
    if not pdf.is_file():
        raise StageBlocked(f"cached datasheet missing: {pdf}")
    # Cached-PDF path: hash the local file, no network fetch.
    record.meta["pdf_sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    record.meta["lcsc"] = lcsc
    official = _read_json(Path(ctx["root"]) / record.id / "official.json")
    record.meta["datasheet_url"] = str(official.get("datasheet", ""))


def _build_validated(record: ComponentRecord, ctx: dict) -> None:
    from src.pipeline.validate import run_erc

    from .. import library
    from ..layout.engine import emit, layout

    root = Path(ctx["root"])
    pins, source = _pins_for(record, root)
    official = _read_json(root / record.id / "official.json")
    fp_id = str(record.meta.get("footprint", ""))
    if ":" not in fp_id:
        raise StageBlocked("meta.footprint unset (run footprint_resolved first)")
    lib, fp_name = fp_id.split(":", 1)
    evidence = crossverify.load_evidence(root / record.id / "evidence.json")
    # Re-check the ledger HERE, immediately before generating into
    # src/ecad/library/. The cross_verified gate ran at a different point in
    # time and `step` does not re-run it before this builder, so a ledger that
    # regressed in between still shipped code: the committed
    # esp32_wroom_32e.json records evidence_summary conflicts=2, meaning a part
    # was generated while its ledger had two unresolved disagreements. And
    # because next_stage() after `validated` is `approved`, which has no
    # builder, that artifact is never regenerated — the stale claim is
    # permanent.
    summary = evidence.summary()
    if summary["conflicts"] or summary.get("unverified"):
        raise StageBlocked(
            f"refusing to generate library code: {summary['conflicts']} "
            f"unresolved conflict(s), {summary.get('unverified', 0)} "
            f"unverified claim(s) — waive with a citation or fix the source")
    name = str(record.meta.get("chip", record.id))
    part = {
        "name": name,
        "lib_id": lib_id_for(record),
        "pins": pins,
        "footprint": FootprintRef(lib=lib, name=fp_name),
        "sourcing": SourcingInfo(manufacturer="Espressif Systems", mpn=name,
                                 lcsc=str(record.meta.get("lcsc", "")),
                                 datasheet_url=str(record.meta.get("datasheet_url", ""))),
        "datasheet": str(official.get("datasheet", "")),
        "description": str(official.get("description", "")),
        "evidence_summary": evidence.summary(),
        "provenance": {"pin_source": source,
                       "official_symbol": record.meta.get("official_symbol", ""),
                       "zephyr_soc": record.meta.get("soc", "")},
        "source_hashes": {"pdf_sha256": record.meta.get("pdf_sha256", "")},
    }
    out_dir = Path(ctx["repo"]) / "src" / "ecad" / "library" / (record.vendor or "espressif")
    generated = codegen.generate(part, out_dir)
    library.add_search_path(out_dir)
    library.clear_cache()
    cls = library.get(generated.part_id)
    inst = cls()
    # accessors = pins reachable through generated typed accessors (a tuple
    # accessor like GND covers several stacked pads); properties counted too.
    props = [n for n, v in vars(cls).items() if isinstance(v, property)]
    covered = 0
    for prop_name in props:
        value = getattr(inst, prop_name)
        covered += len(value) if isinstance(value, tuple) else 1
    record.meta["accessors"] = covered
    record.meta["accessor_properties"] = len(props)
    design = Design(f"{record.id}-validate")
    design.add(inst)
    # 1-part fixture: power rails are necessarily unconnected; every other
    # definition-lint error is a real defect in the generated part.
    hard = [i for i in design.check()
            if i.is_error and i.code != "unconnected-power"]
    if hard:
        raise StageBlocked("design check: " + "; ".join(i.message for i in hard))
    sheet = emit(layout(design), design)
    sch = root / record.id / "validate.kicad_sch"
    sch.write_text(sheet.text)
    erc = run_erc(sch)
    if not erc.get("success"):
        raise StageBlocked(f"ERC did not run: {erc.get('stderr', '')[:200]}")
    record.meta["erc_errors"] = int(erc.get("errors", -1))
    record.meta["generated"] = str(generated.py_path)


_BUILDERS = {
    Stage.EXTRACTED: _build_extracted,
    Stage.CROSS_VERIFIED: _build_cross_verified,
    Stage.SYMBOL_DONE: _build_symbol,
    Stage.FOOTPRINT_RESOLVED: _build_footprint,
    Stage.SOURCING_LINKED: _build_sourcing,
    Stage.VALIDATED: _build_validated,
    # DISCOVERED is built by seeding; APPROVED is a human action.
}


# ── fleet operations ────────────────────────────────────────────────────────

def seed(repo: Path = REPO_ROOT) -> list[ComponentRecord]:
    """One record per manifest datasheet (modules first); existing kept."""
    manifest = _read_json(repo / "data" / "datasheets" / "manifest.json")
    root = repo / "data" / "ingest"
    entries = sorted(manifest.get("datasheets", []),
                     key=lambda e: (e.get("type") != "module",
                                    str(e.get("file", ""))))
    records = []
    for entry in entries:
        comp_id = Path(str(entry["file"])).stem
        if ComponentRecord.path_for(root, comp_id).is_file():
            records.append(ComponentRecord.load(root, comp_id))
            continue
        rec = ComponentRecord(
            id=comp_id, vendor="espressif",
            kind="module" if entry.get("type") == "module" else "soc",
            meta={"chip": entry.get("chip", comp_id.upper()),
                  "pdf": entry["file"],
                  "manifest": {k: entry[k] for k in
                               ("lcsc", "source", "language", "size_kb")
                               if k in entry}})
        rec.save(root)
        records.append(rec)
    return records


def _render(repo: Path) -> None:
    root = repo / "data" / "ingest"
    records = [ComponentRecord.load(root, p.parent.name)
               for p in sorted(root.glob("*/record.json"))]
    (repo / "COMPONENTS.md").write_text(render_components_md(records))


def status(repo: Path = REPO_ROOT) -> list[ComponentRecord]:
    """Seed missing records, recompute all gates, rewrite COMPONENTS.md."""
    seed(repo)
    ctx = make_ctx(repo)
    records = status_all(ctx["root"], ctx)
    (repo / "COMPONENTS.md").write_text(render_components_md(records))
    return records


def step(comp_id: str, repo: Path = REPO_ROOT) -> ComponentRecord:
    """Run exactly one stage transition for one component."""
    ctx = make_ctx(repo)
    root = ctx["root"]
    record = ComponentRecord.load(root, comp_id)
    nxt = record.next_stage()
    if nxt is None:
        _render(repo)
        return record
    builder = _BUILDERS.get(nxt)
    blocked = None
    if builder is not None:
        try:
            builder(record, ctx)
        except StageBlocked as exc:
            blocked = str(exc)
        except (datasheet_mod.DatasheetError, zephyr_mod.ZephyrTreeError,
                codegen.ClobberError) as exc:
            blocked = f"{type(exc).__name__}: {exc}"
    if blocked is not None:
        st = record.stages[nxt]
        if (st.status, st.gate_output) != ("failed", blocked):
            st.status, st.gate_output, st.timestamp = "failed", blocked, utc_now()
    else:
        record.run_gate(nxt, ctx)
    record.save(root)
    _render(repo)
    return record


# ── CLI ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["status"] and len(args) == 1:
        records = status()
        sys.stdout.write(render_components_md(records))
        return 0
    if args[:1] == ["waive"] and len(args) == 6:
        # waive <id> <kind:key> <reason> <cited_source> <author>
        comp_id, claim_ref, reason, source, author = args[1:]
        kind, _, key = claim_ref.partition(":")
        root = REPO_ROOT / "data" / "ingest"
        ev = crossverify.load_evidence(root / comp_id / "evidence.json")
        ev.waive(kind, key, reason=reason, cited_source=source, author=author)
        crossverify.save_evidence(ev, root / comp_id / "evidence.json")
        print(f"{comp_id}: waived {claim_ref} ({ev.summary()})")
        return 0
    if args[:1] == ["step"] and len(args) == 2:
        record = step(args[1])
        blocked = record.blocked_on()
        line = f"{record.id}: stage={record.stage}"
        if blocked:
            line += f" blocked_on={blocked}"
        print(line)
        return 1 if blocked else 0
    print("usage: python -m src.ecad.ingest.factory status | step <id>",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
