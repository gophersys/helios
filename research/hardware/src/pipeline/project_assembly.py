"""Assemble a hierarchical :class:`GeneratedProject` from authored sheets.

``src/pipeline/composer.py`` turns a *spec* into a project: it invents the
sheets, then lays them out, emits them, and packs the result into a
:class:`~src.pipeline.composer.GeneratedProject`. A hand-authored reference
design (``examples/esp32_s3_reference``) already owns its sheets — they are
typed :class:`~src.ecad.Design` objects with a citation behind every part —
and only needs the second half of that job.

This module is that second half, factored so an authored design reaches the
examples bundle through the **same** contract a composed one does:
``build() -> GeneratedProject``. Without it the bundle would need a second
code path for a second shape, and every consumer downstream (the README
renderer, the gallery, the zip, the rules CLI) would have to learn both.

What it does, and why each step exists:

1. **One designator namespace.** Each authored sheet numbers its own parts
   from ``C1``/``R1``, which is right for a sheet that stands alone and wrong
   for a project: KiCad ERC reports duplicate references across a hierarchy
   as an error. References are renumbered project-wide, deterministically
   (sheet order, then the order parts were added), prefix by prefix.
2. **Cross-sheet nets become hierarchy.** A non-power net carried by more
   than one sheet is a signal that leaves its sheet, so it gets a
   hierarchical label at every anchor the router named it at, and a sheet pin
   on the root. Power rails are *not* included: they cross as KiCad global
   power symbols, which is real KiCad semantics and needs no hierarchy.
3. **One PWR_FLAG per rail, project-wide.** Power symbols are global, so a
   rail flagged on two sheets is a power-output conflict at project ERC. A
   rail with a real ``power_out`` driver (a regulator output) is never
   flagged at all.
4. **The truth is reported, not smoothed.** Geometric lint findings and
   definition-lint errors land in ``layout_issues``/``warnings``; a declared
   sheet exit the router never anchored becomes an explicit
   ``unrouted-hierarchical-net`` issue rather than a silently missing label.

Layout policy stays with the caller: ``SheetSource.place`` is the hook a
design uses to lay a sheet out its own way (the reference design sets
``NetEdge.use_labels`` for the nets it draws as labels). The default is the
stock :func:`src.ecad.layout.engine.layout`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from src.ecad import Design, ElectricalType
from src.ecad.emit import deterministic_uuids
from src.ecad.layout.engine import emit, label_anchors, layout
from src.ecad.layout.graph_build import is_power_net
from src.ecad.layout.ir import PlacedSheet
from src.ecad.layout.lints import lint_placed
from src.pipeline.composer import GeneratedProject
from src.pipeline.schematic_gen import (
    SheetContent,
    _gen_hierarchical_label,
    generate_hierarchical_project,
)

__all__ = ["SheetSource", "assemble_project", "cross_sheet_nets", "flag_owners",
           "renumber_refs"]


@dataclass
class SheetSource:
    """One authored sheet on its way into a project.

    ``name`` is the sheet's file stem (``power`` → ``power.kicad_sch``),
    ``title`` the name KiCad shows on the root sheet symbol and uses for the
    exported ``<root>-<title>.svg``. ``place`` lays the design out; leave it
    ``None`` for the stock pipeline. ``directions`` gives the hierarchical
    direction of a crossing net (default ``bidirectional``) — it never
    decides *whether* a net crosses, only how it is declared.
    """

    name: str
    title: str
    design: Design
    place: Callable[[Design], PlacedSheet] | None = None
    directions: Mapping[str, str] = field(default_factory=dict)

    @property
    def filename(self) -> str:
        return f"{self.name}.kicad_sch"

    def layout(self) -> PlacedSheet:
        if self.place is not None:
            return self.place(self.design)
        return layout(self.design, sheet=self.title)


def renumber_refs(designs: Sequence[Design]) -> dict[str, str]:
    """Give every component in ``designs`` a project-unique reference.

    Sheets authored in isolation each start at ``C1``; a KiCad hierarchy is
    one designator namespace and ERC calls the repeat a duplicate. Numbering
    runs per prefix in sheet order, then in the order components were added,
    so the same input always produces the same output.

    Returns ``{"<sheet>/<old>": "<new>"}`` for every reference that moved —
    the record the project reports rather than renaming parts in silence.
    """
    counters: dict[str, int] = {}
    moved: dict[str, str] = {}
    for design in designs:
        for comp in design.components:
            prefix = comp.reference_prefix
            counters[prefix] = counters.get(prefix, 0) + 1
            new = f"{prefix}{counters[prefix]}"
            if new != comp.ref:
                moved[f"{design.name}/{comp.ref}"] = new
                comp.ref = new
    return moved


def cross_sheet_nets(sources: Sequence[SheetSource]) -> dict[str, set[str]]:
    """``{sheet name: {net}}`` — the signal nets that leave each sheet.

    Derived, never declared: a net is a sheet exit exactly when another sheet
    carries the same name and the name is not a power rail. Rails cross as
    global power symbols instead, so promoting one to a hierarchical label
    would ask the router for an anchor it never places.
    """
    carriers: dict[str, set[str]] = {}
    for source in sources:
        for net in source.design.nets:
            if is_power_net(net.name):
                continue
            carriers.setdefault(net.name, set()).add(source.name)
    out: dict[str, set[str]] = {s.name: set() for s in sources}
    for net, sheets in carriers.items():
        if len(sheets) > 1:
            for sheet in sheets:
                out[sheet].add(net)
    return out


def flag_owners(sources: Sequence[SheetSource]) -> dict[str, str]:
    """rail → the ONE sheet name that carries its PWR_FLAG.

    Mirrors ``composer._undriven_rails``: a rail with a real ``power_out``
    driver needs no flag, and every other rail gets exactly one flag
    project-wide because power symbols are global across the hierarchy.
    """
    driven: set[str] = set()
    owner: dict[str, str] = {}
    for source in sources:
        for net in source.design.nets:
            if not is_power_net(net.name):
                continue
            if any(p.etype is ElectricalType.POWER_OUT for p in net.pins):
                driven.add(net.name)
            owner.setdefault(net.name, source.name)
    return {rail: sheet for rail, sheet in owner.items() if rail not in driven}


def _render_sheet(source: SheetSource, hier: Mapping[str, str],
                  flag_rails: Sequence[str]) -> tuple[str, list[str]]:
    """Lay out and emit one sheet. Returns ``(text, issues)``.

    One hierarchical label PER ANCHOR, not per net: a labelled net is joined
    only through its labels, so a net the router named twice (a Type-C
    receptacle carries D+ on both orientations) needs both of them replaced.
    """
    placed = source.layout()
    issues = lint_placed(placed)
    anchors = label_anchors(placed)
    hier_lines: dict[str, list[str]] = {}
    with deterministic_uuids(f"{source.design.name}/hier"):
        for net, direction in sorted(hier.items()):
            for x, y, angle in anchors.get(net, []):
                hier_lines.setdefault(net, []).append(
                    _gen_hierarchical_label(net, direction, x, y, angle))
    for net in sorted(set(hier) - set(hier_lines)):
        issues.append(f"unrouted-hierarchical-net: {net}")
    sheet = emit(placed, source.design, title=source.design.name,
                 hier_labels=hier_lines, flag_rails=flag_rails)
    return sheet.text, issues


def _bom(sources: Sequence[SheetSource]) -> list[dict]:
    return [
        {
            "ref": comp.ref,
            "value": getattr(comp, "value", "") or comp.part_name,
            "lib_id": comp.lib_id,
            "footprint": comp.footprint.lib_id if comp.footprint else "",
            "sheet": source.title,
        }
        for source in sources
        for comp in source.design.components
    ]


def assemble_project(name: str, sources: Sequence[SheetSource], *,
                     wiring_notes: Iterable[str] = ()) -> GeneratedProject:
    """Lay out, emit and pack authored sheets into a ``GeneratedProject``.

    ``name`` is the project name; the root files take its lower-cased form
    (``ESP32_S3_Reference`` → ``esp32_s3_reference.kicad_sch`` /
    ``.kicad_pro``), which is what ``scripts/build_examples.py`` opens and
    renders.

    The returned project carries the same fields a composed one does, so
    every consumer of ``build()`` sees one shape: files, BOM, wiring notes,
    warnings, the typed :class:`Design` behind each sheet (the netlist
    oracle) and the geometric lint findings per sheet.
    """
    sources = list(sources)
    notes = list(wiring_notes)
    warnings: list[str] = []

    moved = renumber_refs([s.design for s in sources])
    if moved:
        notes.append(
            f"References renumbered project-wide ({len(moved)} of "
            f"{sum(len(s.design.components) for s in sources)}): a KiCad "
            f"hierarchy is one designator namespace, and sheets authored "
            f"standalone each start at C1."
        )

    crossing = cross_sheet_nets(sources)
    flag_owner = flag_owners(sources)

    hier_by_sheet: dict[str, dict[str, str]] = {
        s.name: {net: s.directions.get(net, "bidirectional")
                 for net in sorted(crossing[s.name])}
        for s in sources
    }

    rendered: dict[str, str] = {}
    layout_issues: dict[str, list[str]] = {}
    for source in sources:
        rails = sorted(r for r, sheet in flag_owner.items()
                       if sheet == source.name)
        hier = hier_by_sheet[source.name]
        text, issues = _render_sheet(source, hier, rails)
        rendered[source.filename] = text
        if issues:
            layout_issues[source.filename] = issues
            warnings.extend(f"{source.filename}: {i}" for i in issues)
        for issue in source.design.check():
            # A net that leaves the sheet has one pin on this side; that is
            # the hierarchy showing through, and the composer waives the
            # identical issue. Everything else is reported.
            if issue.is_error and not (
                    issue.code == "single-pin-net" and issue.net in hier):
                warnings.append(
                    f"{source.filename}: {issue.code}: {issue.message}")

    sheets = {
        source.filename: SheetContent(
            title=source.title, components=[], nets=[],
            hierarchical_labels=[(net, direction) for net, direction
                                 in sorted(hier_by_sheet[source.name].items())],
        )
        for source in sources
    }
    files = generate_hierarchical_project(
        sheets, root_title=name, rendered_sheets=rendered)

    return GeneratedProject(
        name=name,
        files=files,
        bom=_bom(sources),
        wiring_notes=notes,
        warnings=warnings,
        designs={s.filename: s.design for s in sources},
        layout_issues=layout_issues,
    )
