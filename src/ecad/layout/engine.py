"""Engine: orchestrate the layout pipeline and emit .kicad_sch text.

    placed = layout(design)                  # rank→order→place→route
    text   = emit(placed, design)            # deterministic .kicad_sch

Power taps and satellite rows are realized here: each tapped pin gets a
grid-snapped stub wire plus a generated power symbol; each rail gets one
PWR_FLAG per sheet; satellite caps sit in rows under their owner with a
shared rail wire and per-cap ground symbols; every unconnected IC pin gets
a no_connect marker (the ERC==0 gate demands it).
"""

from __future__ import annotations

import warnings
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

from ..design import Design
from ..symbol import Side, SymbolModel
from . import order as order_mod
from . import place as place_mod
from . import rank as rank_mod
from . import route as route_mod
from .graph_build import build
from .ir import (
    GRID,
    PIN_PITCH,
    Metrics,
    PlacedSheet,
    SchematicGraph,
    Wire,
    snap,
    wires_short,
)
from .page import MARGIN, PageFit, fit_page

# Satellite cap emission geometry (Device:C stub: pins at center ±3.81).
_CAP_PIN_DY = 3.81
_CAP_PITCH = 7.62
_STUB = PIN_PITCH  # power-tap stub length

#: Advance width of one character at the 1.27 mm text size everything here
#: emits, MEASURED off kicad-cli's own SVG rather than assumed:
#: "ESP32-S3-WROOM-1" comes out 22.4 mm wide, i.e. 1.4 mm per character.
#: Guessing 0.72 em from the font metrics under-measured every field by half
#: and left visible collisions the checker called clean.
_CHAR_W = 1.4
_TEXT_HALF_H = 0.9   # mm — half the drawn height of a 1.27 mm text line


class PageOverflow(UserWarning):
    """The drawing does not fit the largest standard sheet."""


@dataclass
class EmittedSheet:
    text: str
    metrics: Metrics
    wires: dict[str, list[Wire]] = field(default_factory=dict)
    """EVERY wire in the emitted file, keyed by net — the router's wires
    plus the ones :func:`emit` generates itself (power-tap stubs, satellite
    rows, PWR_FLAG ties). Those never appear in the IR, so
    :func:`~.lints.lint_placed` can only gate them when handed this."""
    junctions: dict[str, list[tuple[float, float]]] = field(
        default_factory=dict)
    """Likewise every junction in the file, keyed by net."""
    page: PageFit | None = None
    #: Human-readable notes about the sheet's draughting (page overflow).
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _text_box(x: float, y: float, text: str, justify: str = "",
              angle: int = 0) -> tuple[float, float, float, float]:
    """Bounding box of a drawn text item, from its anchor and rotation.

    Net labels on a top or bottom pin stub are drawn at 90/270 and run UP
    the page, so their box is tall and thin — measuring them as if they were
    horizontal is how a rail name ends up written through one.
    """
    w = len(text) * _CHAR_W
    if angle in (90, 270):
        lo, hi = ((y - w, y) if angle == 270 else (y, y + w))
        return (x - _TEXT_HALF_H, lo, x + _TEXT_HALF_H, hi)
    if "left" in justify:
        x0, x1 = x, x + w
    elif "right" in justify:
        x0, x1 = x - w, x
    else:
        x0, x1 = x - w / 2, x + w / 2
    return (x0, y - _TEXT_HALF_H, x1, y + _TEXT_HALF_H)


def _hits(box: tuple[float, float, float, float],
          taken: list[tuple[float, float, float, float]]) -> bool:
    ax0, ay0, ax1, ay1 = box
    return any(ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1
               for bx0, by0, bx1, by1 in taken)


def layout(design: Design, sheet: str = "main",
           graph: SchematicGraph | None = None) -> PlacedSheet:
    """Rank → order → place → route one sheet.

    Placement is tried at each wrap budget in turn (tightest first) and the
    first result that passes the geometric lint wins; the last budget is
    "do not wrap", the pre-existing behaviour, so a sheet can only ever come
    out as good as it did before. Wrapping is what stops a long column of
    strapping resistors running off the bottom of the page, but it moves
    their net-label stubs with them, and a stub can land on another net's
    trunk wire — a short. Verifying beats assuming.
    """
    from . import lints

    g = graph if graph is not None else build(design, sheet=sheet)
    ranking = rank_mod.assign(g)
    ordering = order_mod.minimize(g, ranking)
    best: tuple[int, PlacedSheet] | None = None
    for budget in place_mod.WRAP_BUDGETS:
        placement = place_mod.coordinates(g, ranking, ordering, budget)
        routing = route_mod.route(g, ranking, ordering, placement)
        candidate = PlacedSheet(graph=g, ranking=ranking, ordering=ordering,
                                placement=placement, routing=routing)
        errors = len(lints.lint_placed(candidate))
        if errors == 0:
            return candidate
        if best is None or errors < best[0]:
            best = (errors, candidate)
    return best[1]


def label_anchors(placed: PlacedSheet) -> dict[str, list[tuple[float, float, int]]]:
    """net name → [(x, y, angle)] of every label the router placed for it.

    A net that leaves the sheet has exactly one anchor (its single port's
    stub end). Callers that replace those labels with hierarchical ports
    (the composer) render their own S-expressions at these points and pass
    them back to :func:`emit` as ``hier_labels``.
    """
    return {
        net: [(snap(x), snap(y), angle) for _anchor, x, y, angle in entries]
        for net, entries in sorted(placed.routing.label_at.items())
    }


def _free_tap(reserved: set[tuple[float, float]],
              candidates: list[tuple[float, float]],
              *, net: str = "", frm: tuple[float, float] | None = None,
              gen_wires: Mapping[str, list[Wire]] | None = None
              ) -> tuple[float, float]:
    """First acceptable candidate point, else the last one.

    A candidate must satisfy BOTH conditions, because a point can be free of
    every placed symbol and still sit on another net's wire — and a symbol
    pin landing on a wire merges those nets silently, the same mechanism as a
    label dropped on a foreign wire:

    1. unreserved — no other power symbol has claimed the point. Without this
       a USB-C shell's GND symbol lands where a VBUS pad's symbol already
       went and the two rails export as one net.
    2. its tie wire (``frm`` → candidate) shorts no OTHER net's wire. Without
       this a PWR_FLAG tie lands on an adjacent rail's tap stub when two
       power pins sit one pitch apart.

    Each condition closes a hole the other leaves open, so they belong in one
    allocation path rather than two mechanisms racing to place one symbol.
    ``net``/``frm``/``gen_wires`` are optional: omit them and only condition
    1 applies, which is correct for a point with no tie wire.

    Falling back to the last candidate rather than raising keeps emission
    total: a design so dense that every candidate is taken still produces a
    file, and the netlist-equivalence gate is what reports the damage.
    """
    for point in candidates:
        if point in reserved:
            continue
        if gen_wires is not None and frm is not None:
            tie = Wire(frm[0], frm[1], point[0], point[1])
            if any(wires_short(tie, w)
                   for other, ws in gen_wires.items() if other != net
                   for w in ws):
                continue
        return point
    return candidates[-1]


def _content_box(boxes: list[tuple[float, float, float, float]],
                 ) -> tuple[float, float, float, float]:
    """Union of every drawn thing, in absolute sheet coordinates.

    Absolute, not relative: :func:`fit_page` tests the drawing against the
    frame's border and title block, so it needs to know where on the sheet
    the drawing actually starts, not merely how big it is. An empty sheet
    degenerates to a point on the frame corner.
    """
    if not boxes:
        return (MARGIN, MARGIN, MARGIN, MARGIN)
    return (round(min(b[0] for b in boxes), 4),
            round(min(b[1] for b in boxes), 4),
            round(max(b[2] for b in boxes), 4),
            round(max(b[3] for b in boxes), 4))


def _satellite_lib_entry(alias: str, model: SymbolModel | None,
                         lib_id: str) -> str:
    """lib_symbols entry for a decoupling cap placed in a satellite row.

    Row wiring assumes the vertical two-pin stub geometry (pins at
    ``(0, ±3.81)``), so the part's own symbol may only be used when it
    really has that geometry — which a preserved ``Device:C`` does, because
    that IS where KiCad puts its pins. Using it matters: the alias branch
    used to emit ``gen_passive_stub``, a symbol with two pins and NO body,
    so every satellite cap on a sheet that also placed a ``Device:C`` in the
    signal path rendered as two floating wire ends.
    """
    from ..emit import gen_passive_stub, get_stub

    if model is not None:
        pins = model.units[0].pins if len(model.units) == 1 else ()
        if len(pins) == 2 and all(
                p.x == 0 and abs(p.y) == _CAP_PIN_DY for p in pins):
            return model.to_inline_sexp_multi(alias)
    if alias == lib_id:
        return get_stub(lib_id) or gen_passive_stub(lib_id)
    return gen_passive_stub(alias)


def metrics_of(placed: PlacedSheet) -> Metrics:
    two_pin_routed = straight = 0
    for e in placed.graph.edges:
        if e.net in placed.routing.labeled_nets or len(e.ports) != 2:
            continue
        two_pin_routed += 1
        segs = placed.routing.wires.get(e.net, [])
        if len(segs) == 1 and segs[0].is_orthogonal():
            straight += 1
    return Metrics(
        crossings=placed.ordering.crossings,
        total_wire_length=round(placed.routing.total_length, 2),
        bends=placed.routing.bends,
        alignment=(straight / two_pin_routed) if two_pin_routed else 1.0,
        labeled_nets=len(placed.routing.labeled_nets),
        routed_nets=len(placed.graph.edges) - len(placed.routing.labeled_nets),
    )


def emit(placed: PlacedSheet, design: Design,
         title: str | None = None,
         hier_labels: Mapping[str, str | Sequence[str]] | None = None,
         flag_rails: Collection[str] | None = None) -> EmittedSheet:
    """Emit a single-sheet .kicad_sch (deterministic UUIDs from the design
    name). Returns the text plus computed soft metrics.

    ``hier_labels`` maps a net name to PRE-RENDERED hierarchical-label
    S-expression(s) supplied by the caller (the composer owns hierarchy; ecad
    never imports pipeline). Those lines are emitted verbatim and the
    router's own local label for the same net is suppressed.

    Pass a LIST when the net has several label anchors — any net with more
    than 4 ports falls back to labels and gets one anchor per port. Naming
    only one of them leaves the rest with a stub connected to nothing, since
    a labeled net is joined solely through its labels. A bare string remains
    valid for the single-anchor case.

    ``flag_rails`` restricts PWR_FLAG emission to the named rails (default:
    every undriven rail on the sheet). Power symbols are GLOBAL across a
    hierarchical project, so exactly one sheet may flag a given rail —
    two flags on one net is a power-output conflict at project ERC.
    """
    from ..emit import (
        DEFAULT_FIELDS,
        ComponentPlacement,
        NetConnection,
        _gen_junction,
        _gen_label,
        _gen_no_connect,
        _gen_power_instance,
        _gen_wire,
        _uuid,
        deterministic_uuids,
        gen_symbol_instance,
        power_label_offset,
        power_symbol_lib_sexp,
    )

    g = placed.graph
    pl = placed.placement
    rt = placed.routing
    name = title or design.name
    comps = {c.ref: c for c in design.components}
    models = {ref: SymbolModel.from_component(c, style="readable")
              for ref, c in comps.items()}
    # Satellite caps hang vertically between a rail wire and a ground symbol,
    # so they need the source symbol's own upright geometry, not the
    # laid-flat one the signal path uses.
    upright = {ref: SymbolModel.from_component(c, style="readable",
                                               lay_flat=False)
               for ref, c in comps.items()}

    with deterministic_uuids(name):
        root_uuid = _uuid()
        project = name.replace(" ", "_")

        # ── lib_symbols ────────────────────────────────────────────────────
        # Placed nodes always get the readable SymbolModel geometry — the
        # router computed port points from it, so the emitted symbol must
        # match (the vertical Device:R/C/L stubs put pins at (0, ±3.81),
        # nowhere near the LEFT/RIGHT ports the router wired to).
        # Dedup key is the GEOMETRY, not the lib_id: readable widths derive
        # from pin-name lengths, so two components declaring the same lib_id
        # with different pins need two different entries — sharing one would
        # draw the second component's pins where the first's are, metres from
        # the wires the router placed against its own geometry.
        lib_entries: list[str] = []
        seen_libs: set[str] = set()
        claimed: dict[str, str] = {}        # emitted lib name → geometry
        lib_alias: dict[str, str] = {}      # component ref → emitted lib name
        power_names: set[str] = set()
        for node in g.nodes.values():   # insertion order == deterministic
            if not node.ref or node.ref in lib_alias:
                continue
            geom = models[node.ref].to_inline_sexp_multi("\x00")
            name = node.lib_id
            n = 1
            while name in claimed and claimed[name] != geom:
                n += 1
                name = f"{node.lib_id}_{n}"
            lib_alias[node.ref] = name
            if name not in claimed:
                claimed[name] = geom
                seen_libs.add(name)
                lib_entries.append(
                    models[node.ref].to_inline_sexp_multi(name))
        # Satellites keep the vertical stub (row wiring assumes pins at
        # ±_CAP_PIN_DY). When a placed node already claimed the lib_id with
        # readable geometry, the satellite stub is emitted under an alias.
        sat_lib: dict[str, str] = {}
        for sats in g.satellites.values():
            for s in sats:
                if s.lib_id in sat_lib:
                    continue
                # The alias exists whenever the row's upright geometry is not
                # what this sheet already published under that lib_id — either
                # because a placed part claimed the name, or because the
                # signal-path variant is laid flat and this one is not. One
                # lib_id must never name two different drawings.
                flat, up = models.get(s.ref), upright.get(s.ref)
                differs = flat is not up and (
                    flat is None or up is None
                    or flat.units[0].pins != up.units[0].pins)
                alias = (f"{s.lib_id}_dec"
                         if s.lib_id in seen_libs or differs else s.lib_id)
                lib_entries.append(_satellite_lib_entry(alias, up, s.lib_id))
                seen_libs.add(alias)
                sat_lib[s.lib_id] = alias

        body: list[str] = []
        wires: list[Wire] = []
        # Every wire emit() builds itself, keyed by the net it belongs to, so
        # lints.lint_placed can gate them exactly like the router's wires.
        gen_wires: dict[str, list[Wire]] = {}
        gen_junctions: dict[str, list[tuple[float, float]]] = {}

        def add_wire(net: str, w: Wire) -> None:
            wires.append(w)
            gen_wires.setdefault(net, []).append(w)

        pwr_instances: list[tuple[str, float, float, bool]] = []
        # Every text item already committed to the sheet. Power-symbol names
        # are placed last and steered clear of these.
        text_boxes: list[tuple[float, float, float, float]] = []
        # Everything drawn, for choosing the page size.
        extent: list[tuple[float, float, float, float]] = []

        def claim_fields(pos: tuple[float, float], model: SymbolModel,
                         unit: int, ref: str, value: str):
            """Reference/Value offsets for one instance, nudged clear.

            The symbol says where its fields belong; this says where they
            actually fit. Each field starts at the symbol's offset and steps
            FURTHER FROM the body along the axis that separates it from its
            partner — the reference away above, the value away below — until
            it clears everything already drawn. A field that cannot be
            cleared in 8 steps keeps its last position: an overlapping label
            is bad, one dragged 20 mm from the part it names is worse.
            """
            placed = []
            x, y = pos
            for dx, dy, just, text in (
                    (*model.field_offsets(unit)[0], ref),
                    (*model.field_offsets(unit)[1], value)):
                step = GRID if dy >= 0 else -GRID
                for k in range(9):
                    ndy = dy + step * k
                    box = _text_box(x + dx, y - ndy, text, just)
                    if not _hits(box, text_boxes):
                        break
                dy = ndy
                text_boxes.append(box)
                extent.append(box)
                placed.append((dx, dy, just))
            return (tuple(placed[0]), tuple(placed[1]))

        # Labels are anchored to wire ends and cannot move, so they are the
        # fixed obstacles every movable field is measured against.
        for _net, entries in sorted(rt.label_at.items()):
            for _anchor, lx, ly, angle in entries:
                just = "right" if angle == 180 else "left"
                text_boxes.append(
                    _text_box(snap(lx), snap(ly), _net, just, angle))
                extent.append(text_boxes[-1])

        # ── placed units ───────────────────────────────────────────────────
        placed_port_pts: dict[tuple[str, str], tuple[float, float]] = {}
        for nid, node in sorted(g.nodes.items()):
            if not node.ref:            # virtual
                continue
            ox, oy = pl.origin[nid]
            model = models[node.ref]
            # The symbol's own origin, not the middle of its bbox: preserved
            # artwork is routinely off-centre, and placing it by the centre
            # would slide every pin off the wires the router computed.
            ax, ay = model.node_anchor(node.unit)
            anchor = (snap(ox + ax), snap(oy + ay))
            comp = comps[node.ref]
            value = getattr(comp, "value", "") or comp.part_name
            body.append(gen_symbol_instance(ComponentPlacement(
                lib_id=lib_alias[node.ref], ref=node.ref, value=value,
                footprint=comp.footprint.lib_id if comp.footprint else "",
                position=anchor, unit=node.unit,
                fields=claim_fields(anchor, model, node.unit, node.ref, value)),
                project, root_uuid, [p.number for p in node.ports]))
            w_tot, h_tot = model.node_size(node.unit)
            extent.append((ox, oy, ox + w_tot, oy + h_tot))
            for port in node.ports:
                placed_port_pts[(nid, port.number)] = (
                    snap(ox + port.offset[0]), snap(oy + port.offset[1]))

        # ── power taps ─────────────────────────────────────────────────────
        # A power symbol may not land on a point something else already
        # owns. Two symbols sharing a point silently MERGE their nets — a
        # USB-C receptacle's shield tap landed on a VBUS tap and KiCad
        # exported GND and VBUS as one net, with every geometric lint clean
        # (lint_placed never sees these wires; they are built right here).
        # So: collect the points routing has already claimed, and give each
        # tap the first candidate position nobody else wants.
        reserved: set[tuple[float, float]] = set()
        for segs in rt.wires.values():
            for w in segs:
                reserved.add((snap(w.x1), snap(w.y1)))
                reserved.add((snap(w.x2), snap(w.y2)))
        for entries in rt.label_at.values():
            for _anchor, lx, ly, _angle in entries:
                reserved.add((snap(lx), snap(ly)))

        # Official symbols STACK parallel pads on one coordinate — KiCad's
        # USB-C receptacle draws its four VBUS pads and its four GND pads at
        # a single point each, which is precisely how it says "one wire
        # serves all of these". Emitting a power symbol per pad put four
        # glyphs and four names on top of each other. One tap per
        # (point, rail) is the same netlist — a wire end at that point
        # connects every pin there — and one readable symbol.
        stacked: set[tuple[float, float, str]] = set()
        for nid, node in sorted(g.nodes.items()):
            for tap in sorted(node.power_taps, key=lambda t: t.port_number):
                px, py = placed_port_pts[(nid, tap.port_number)]
                if (px, py, tap.rail) in stacked:
                    continue
                stacked.add((px, py, tap.rail))
                port = node.port(tap.port_number)
                if port.side in (Side.TOP, Side.BOTTOM):
                    dy = -_STUB if port.side is Side.TOP else _STUB
                    ex, ey = _free_tap(
                        reserved,
                        [(snap(px), snap(py + dy * k)) for k in range(1, 6)],
                        net=tap.rail, frm=(px, py), gen_wires=gen_wires)
                    add_wire(tap.rail, Wire(px, py, ex, ey))
                else:
                    dx = -_STUB if port.side is Side.LEFT else _STUB
                    # grounds hang down, rails point up: the stepped point is
                    # preferred, the plain stub end is the fallback, then the
                    # same pair one column further out.
                    vy = _STUB if tap.down else -_STUB
                    cands: list[tuple[float, float]] = []
                    for k in range(1, 4):
                        cx = snap(px + dx * k)
                        cands.append((cx, snap(py + vy)))
                        cands.append((cx, snap(py)))
                    ex, ey = _free_tap(reserved, cands, net=tap.rail,
                                       frm=(px, py), gen_wires=gen_wires)
                    add_wire(tap.rail, Wire(px, py, ex, py))
                    if ey != py:
                        add_wire(tap.rail, Wire(ex, py, ex, ey))
                reserved.add((ex, ey))
                pwr_instances.append((tap.rail, ex, ey, tap.down))
                power_names.add(tap.rail)

        # ── satellite rows (caps grouped per rail — one row may decouple
        # several different rails) ─────────────────────────────────────────
        sat_junctions: list[tuple[float, float]] = []
        for owner, row in sorted(pl.sat_rows.items()):
            sats = {s.ref: s for s in g.satellites.get(owner, [])}
            rail_tops: dict[str, list[tuple[float, float]]] = {}
            for ref, cx, cy in row:
                s = sats.get(ref)
                if s is None:
                    continue
                # the stub geometry puts pad 1 on top; when the DESIGN wires
                # pad 2 to the rail, rotate the body 180 so the rail pad is
                # the one that meets the rail wire
                flip = s.rail_pad != "1"
                sat_model = upright.get(s.ref)
                sat_pos = (snap(cx), snap(cy))
                body.append(gen_symbol_instance(ComponentPlacement(
                    lib_id=sat_lib[s.lib_id], ref=s.ref, value=s.value,
                    footprint=s.footprint, rotation=180 if flip else 0,
                    position=sat_pos,
                    fields=(claim_fields(sat_pos, sat_model, 1, s.ref, s.value)
                            if sat_model else DEFAULT_FIELDS)),
                    project, root_uuid))
                top = (snap(cx), snap(cy - _CAP_PIN_DY))
                bot = (snap(cx), snap(cy + _CAP_PIN_DY))
                rail_tops.setdefault(s.rail, []).append(top)
                # per-cap ground below
                add_wire(s.gnd,
                         Wire(bot[0], bot[1], bot[0], snap(bot[1] + _STUB)))
                pwr_instances.append((s.gnd, bot[0], snap(bot[1] + _STUB), True))
                power_names.add(s.gnd)
            # One row may decouple SEVERAL rails, and every cap in a row shares
            # the same cy. Two independent guards keep the rails apart:
            #  * graph_build keeps each rail's caps CONTIGUOUS in the row, so a
            #    rail's trunk spans only its own caps and no foreign cap stub
            #    can end on it;
            #  * each rail additionally gets its OWN horizontal track, stepped
            #    by _STUB, so the trunks are not even colinear.
            # Deriving rail_y from tops[0] alone put every rail on the identical
            # y; their spans then overlapped in x and KiCad merged them into one
            # net, shorting e.g. 3V3 to 5V whenever their caps interleaved.
            # Stubs that cross a lower track stay safe: crossing wires do not
            # connect in KiCad without a junction, and junctions are only ever
            # emitted at a rail's own cap x-positions.
            for track, (rail, tops) in enumerate(
                    (r, t) for r, t in sorted(rail_tops.items()) if r):
                rail_y = snap(tops[0][1] - _STUB * (track + 1))
                xs = [t[0] for t in tops]
                for x, y in tops:
                    add_wire(rail, Wire(x, y, x, rail_y))
                if len(xs) > 1:
                    add_wire(rail, Wire(min(xs), rail_y, max(xs), rail_y))
                    # Every cap stub T-s into that shared span. KiCad does not
                    # connect a wire endpoint that lands MID-segment without a
                    # junction dot, so without these the middle caps of a row
                    # are electrically floating: a rail with 3+ decoupling caps
                    # exported a netlist missing C2 and failed ERC with
                    # pin_not_connected. The endpoints also carry the rail's
                    # power-symbol pin, so junction every stub rather than only
                    # the interior ones.
                    pts = [(x, rail_y) for x in sorted(set(xs))]
                    sat_junctions.extend(pts)
                    gen_junctions.setdefault(rail, []).extend(pts)
                pwr_instances.append((rail, min(xs), rail_y, False))
                power_names.add(rail)

        # ── routed wires, junctions, labels ────────────────────────────────
        for net in sorted(rt.wires):
            for w in rt.wires[net]:
                add_wire(net, w)
        junctions = [pt for net in sorted(rt.junctions)
                     for pt in rt.junctions[net]]
        junctions.extend(sat_junctions)
        for net in sorted(rt.junctions):
            gen_junctions.setdefault(net, []).extend(rt.junctions[net])
        hier = dict(hier_labels or {})
        label_lines: list[str] = []
        for net in sorted(rt.label_at):
            if net in hier:
                continue        # the caller's hierarchical port names it
            for _anchor, lx, ly, angle in rt.label_at[net]:
                label_lines.append(_gen_label(NetConnection(
                    net, "local", (snap(lx), snap(ly)), angle=angle)))
        for net in sorted(hier):
            entry = hier[net]
            # A net may leave the sheet at SEVERAL ports (any net with >4
            # ports falls back to labels, one anchor each). Accept a list so
            # every anchor is named; a bare string stays valid for the common
            # single-anchor case.
            if isinstance(entry, str):
                label_lines.append(entry)
            else:
                label_lines.extend(entry)

        # ── PWR_FLAG once per rail, but never on a rail that already has a
        # real power_out driver (two power outputs on one net is an ERC
        # error — the regulator output IS the flag) ────────────────────────
        driven: set[str] = set()
        for net in design.nets:
            for p in net.pins:
                if p.etype.value == "power_out":
                    driven.add(net.name)
                    break
        allowed = None if flag_rails is None else set(flag_rails)
        flagged: set[str] = set()
        flag_extra: list[tuple[str, float, float, bool]] = []
        for rail, x, y, down in pwr_instances:
            if rail in flagged or rail in driven:
                continue
            if allowed is not None and rail not in allowed:
                continue
            flagged.add(rail)
            # offset the flag sideways so its glyph/text doesn't overlap the
            # rail symbol, and keep stepping while that spot is taken (a
            # dense connector puts a rail symbol on every pitch); tie it back
            # with a short wire.
            # Try right then left at each step, matching the ordering the
            # per-rail wire check used, so a blocked side falls back rather
            # than marching outward on one side only.
            cands = []
            for k in range(1, 9):
                cands.append((snap(x + PIN_PITCH * k), snap(y)))
                cands.append((snap(x - PIN_PITCH * k), snap(y)))
            fx, fy = _free_tap(reserved, cands, net=rail, frm=(x, y),
                               gen_wires=gen_wires)
            reserved.add((fx, fy))
            flag_extra.append(("PWR_FLAG", fx, fy, False))
            add_wire(rail, Wire(x, y, fx, fy))
        if flag_extra:
            power_names.add("PWR_FLAG")
        pwr_instances.extend(flag_extra)

        for pname in sorted(power_names):
            lib_entries.append(power_symbol_lib_sexp(pname))
        # A power symbol's NAME is the only thing that says which rail it is,
        # so two of them overlapping is a correctness-grade defect, not a
        # cosmetic one. Each name starts at its natural offset and is stepped
        # further from its glyph until it clears every text already on the
        # sheet. Order is the emission order, which is deterministic.
        for i, (rail, x, y, down) in enumerate(pwr_instances, start=1):
            base = power_label_offset(rail, down)
            step = GRID if base >= 0 else -GRID
            dy = base
            for k in range(0, 8):
                dy = round(base + step * k, 4)
                if not _hits(_text_box(x, y + dy, rail), text_boxes):
                    break
            text_boxes.append(_text_box(x, y + dy, rail))
            extent.append(text_boxes[-1])
            extent.append((x - 1.27, y - 2.54, x + 1.27, y + 2.54))
            body.append(_gen_power_instance(
                rail, f"#PWR{i:02d}", x, y, 180 if down else 0,
                project, root_uuid, label_dy=dy))

        # ── no_connect on every untouched pin ──────────────────────────────
        touched: set[tuple[str, str]] = set()
        for e in g.edges:
            touched.update(e.ports)
        for nid, node in g.nodes.items():
            for tap in node.power_taps:
                touched.add((nid, tap.port_number))
        nc_lines = []
        for key, pt in sorted(placed_port_pts.items()):
            if key not in touched:
                nc_lines.append(_gen_no_connect(*pt))

        wire_lines = [_gen_wire(w.x1, w.y1, w.x2, w.y2) for w in wires]
        junction_lines = [_gen_junction(x, y) for x, y in junctions]

        # ── page: the smallest standard sheet the drawing actually fits ────
        for w in wires:
            extent.append((min(w.x1, w.x2), min(w.y1, w.y2),
                           max(w.x1, w.x2), max(w.y1, w.y2)))
        page = fit_page(_content_box(extent))
        notes: list[str] = []
        if not page.fits:
            notes.append(
                f"{name}: drawing does not fit any standard sheet — "
                f"{page.overflow}; emitted on {page.name} anyway")
            warnings.warn(notes[-1], PageOverflow, stacklevel=2)

        lib_symbols = "\n\t\t".join(lib_entries)
        parts = "\n".join(label_lines + wire_lines + junction_lines
                          + body + nc_lines)
        text = f"""(kicad_sch
\t(version 20250114)
\t(generator "hardware-pipeline")
\t(generator_version "1.0")
\t(uuid "{root_uuid}")
\t(paper "{page.name}")
\t(lib_symbols
\t\t{lib_symbols}
\t)
{parts}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""
    return EmittedSheet(text=text, metrics=metrics_of(placed),
                        wires=gen_wires, junctions=gen_junctions,
                        page=page, warnings=tuple(notes))

