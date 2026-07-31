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

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from ..design import Design
from ..symbol import Side, SymbolModel
from . import order as order_mod
from . import place as place_mod
from . import rank as rank_mod
from . import route as route_mod
from .graph_build import build
from .ir import PIN_PITCH, Metrics, PlacedSheet, SchematicGraph, Wire, snap

# Satellite cap emission geometry (Device:C stub: pins at center ±3.81).
_CAP_PIN_DY = 3.81
_CAP_PITCH = 7.62
_STUB = PIN_PITCH  # power-tap stub length


@dataclass
class EmittedSheet:
    text: str
    metrics: Metrics


def layout(design: Design, sheet: str = "main",
           graph: SchematicGraph | None = None) -> PlacedSheet:
    g = graph if graph is not None else build(design, sheet=sheet)
    ranking = rank_mod.assign(g)
    ordering = order_mod.minimize(g, ranking)
    placement = place_mod.coordinates(g, ranking, ordering)
    routing = route_mod.route(g, ranking, ordering, placement)
    return PlacedSheet(graph=g, ranking=ranking, ordering=ordering,
                       placement=placement, routing=routing)


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
         hier_labels: Mapping[str, str] | None = None,
         flag_rails: Collection[str] | None = None) -> EmittedSheet:
    """Emit a single-sheet .kicad_sch (deterministic UUIDs from the design
    name). Returns the text plus computed soft metrics.

    ``hier_labels`` maps a net name to a PRE-RENDERED hierarchical-label
    S-expression supplied by the caller (the composer owns hierarchy; ecad
    never imports pipeline). Those lines are emitted verbatim and the
    router's own local label for the same net is suppressed, so the net is
    named exactly once — at the stub end reported by :func:`label_anchors`.

    ``flag_rails`` restricts PWR_FLAG emission to the named rails (default:
    every undriven rail on the sheet). Power symbols are GLOBAL across a
    hierarchical project, so exactly one sheet may flag a given rail —
    two flags on one net is a power-output conflict at project ERC.
    """
    from ..emit import (
        ComponentPlacement,
        NetConnection,
        _gen_junction,
        _gen_label,
        _gen_no_connect,
        _gen_power_instance,
        _gen_wire,
        _uuid,
        deterministic_uuids,
        gen_passive_stub,
        gen_symbol_instance,
        get_stub,
        power_symbol_lib_sexp,
    )

    g = placed.graph
    pl = placed.placement
    rt = placed.routing
    name = title or design.name
    comps = {c.ref: c for c in design.components}
    models = {ref: SymbolModel.from_component(c, style="readable")
              for ref, c in comps.items()}

    with deterministic_uuids(name):
        root_uuid = _uuid()
        project = name.replace(" ", "_")

        # ── lib_symbols ────────────────────────────────────────────────────
        # Placed nodes always get the readable SymbolModel geometry — the
        # router computed port points from it, so the emitted symbol must
        # match (the vertical Device:R/C/L stubs put pins at (0, ±3.81),
        # nowhere near the LEFT/RIGHT ports the router wired to).
        lib_entries: list[str] = []
        seen_libs: set[str] = set()
        power_names: set[str] = set()
        for node in g.nodes.values():
            if not node.ref or node.lib_id in seen_libs:
                continue
            seen_libs.add(node.lib_id)
            lib_entries.append(
                models[node.ref].to_inline_sexp_multi(node.lib_id))
        # Satellites keep the vertical stub (row wiring assumes pins at
        # ±_CAP_PIN_DY). When a placed node already claimed the lib_id with
        # readable geometry, the satellite stub is emitted under an alias.
        sat_lib: dict[str, str] = {}
        for sats in g.satellites.values():
            for s in sats:
                if s.lib_id in sat_lib:
                    continue
                if s.lib_id in seen_libs:
                    alias = f"{s.lib_id}_dec"
                    lib_entries.append(gen_passive_stub(alias))
                else:
                    alias = s.lib_id
                    lib_entries.append(get_stub(s.lib_id)
                                       or gen_passive_stub(s.lib_id))
                seen_libs.add(alias)
                sat_lib[s.lib_id] = alias

        body: list[str] = []
        wires: list[Wire] = []
        extra_junctions: list[tuple[float, float]] = []
        pwr_instances: list[tuple[str, float, float, bool]] = []

        # ── placed units ───────────────────────────────────────────────────
        placed_port_pts: dict[tuple[str, str], tuple[float, float]] = {}
        for nid, node in sorted(g.nodes.items()):
            if not node.ref:            # virtual
                continue
            ox, oy = pl.origin[nid]
            model = models[node.ref]
            w_tot, h_tot = model.node_size(node.unit)
            anchor = (snap(ox + w_tot / 2), snap(oy + h_tot / 2))
            comp = comps[node.ref]
            body.append(gen_symbol_instance(ComponentPlacement(
                lib_id=node.lib_id, ref=node.ref,
                value=getattr(comp, "value", "") or comp.part_name,
                footprint=comp.footprint.lib_id if comp.footprint else "",
                position=anchor, unit=node.unit), project, root_uuid,
                [p.number for p in node.ports]))
            for port in node.ports:
                placed_port_pts[(nid, port.number)] = (
                    snap(ox + port.offset[0]), snap(oy + port.offset[1]))

        # ── power taps ─────────────────────────────────────────────────────
        for nid, node in sorted(g.nodes.items()):
            for tap in sorted(node.power_taps, key=lambda t: t.port_number):
                px, py = placed_port_pts[(nid, tap.port_number)]
                port = node.port(tap.port_number)
                dx, dy = 0.0, 0.0
                if port.side is Side.TOP:
                    dy = -_STUB
                elif port.side is Side.BOTTOM:
                    dy = _STUB
                elif port.side is Side.LEFT:
                    dx = -_STUB
                else:
                    dx = _STUB
                # grounds hang down, rails point up: extend vertically after
                # the stub when the pin exits horizontally
                ex, ey = px + dx, py + dy
                if dx != 0.0:
                    vy = _STUB if tap.down else -_STUB
                    wires.append(Wire(px, py, ex, ey))
                    wires.append(Wire(ex, ey, ex, ey + vy))
                    ex, ey = ex, ey + vy
                else:
                    wires.append(Wire(px, py, ex, ey))
                pwr_instances.append((tap.rail, ex, ey, tap.down))
                power_names.add(tap.rail)

        # ── satellite rows (caps grouped per rail — one row may decouple
        # several different rails) ─────────────────────────────────────────
        for owner, row in sorted(pl.sat_rows.items()):
            sats = {s.ref: s for s in g.satellites.get(owner, [])}
            rail_tops: dict[str, list[tuple[float, float]]] = {}
            for ref, cx, cy in row:
                s = sats.get(ref)
                if s is None:
                    continue
                body.append(gen_symbol_instance(ComponentPlacement(
                    lib_id=sat_lib[s.lib_id], ref=s.ref, value=s.value,
                    footprint=s.footprint,
                    position=(snap(cx), snap(cy))), project, root_uuid))
                top = (snap(cx), snap(cy - _CAP_PIN_DY))
                bot = (snap(cx), snap(cy + _CAP_PIN_DY))
                rail_tops.setdefault(s.rail, []).append(top)
                # per-cap ground below
                wires.append(Wire(bot[0], bot[1], bot[0], snap(bot[1] + _STUB)))
                pwr_instances.append((s.gnd, bot[0], snap(bot[1] + _STUB), True))
                power_names.add(s.gnd)
            for rail, tops in sorted(rail_tops.items()):
                if not rail:
                    continue
                rail_y = snap(tops[0][1] - _STUB)
                xs = [t[0] for t in tops]
                for x, y in tops:
                    wires.append(Wire(x, y, x, rail_y))
                if len(xs) > 1:
                    wires.append(Wire(min(xs), rail_y, max(xs), rail_y))
                    # A cap between the ends meets the rail wire mid-segment:
                    # KiCad only joins a wire END to a wire BODY where a
                    # junction dot exists, so the middle caps would float.
                    extra_junctions.extend(
                        (x, rail_y) for x in sorted(xs)
                        if min(xs) < x < max(xs))
                pwr_instances.append((rail, min(xs), rail_y, False))
                power_names.add(rail)

        # ── routed wires, junctions, labels ────────────────────────────────
        for net in sorted(rt.wires):
            wires.extend(rt.wires[net])
        junctions = [pt for net in sorted(rt.junctions)
                     for pt in rt.junctions[net]] + sorted(extra_junctions)
        hier = dict(hier_labels or {})
        label_lines: list[str] = []
        for net in sorted(rt.label_at):
            if net in hier:
                continue        # the caller's hierarchical port names it
            for _anchor, lx, ly, angle in rt.label_at[net]:
                label_lines.append(_gen_label(NetConnection(
                    net, "local", (snap(lx), snap(ly)), angle=angle)))
        label_lines.extend(hier[net] for net in sorted(hier))

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
        flag_wires: list[Wire] = []
        for rail, x, y, down in pwr_instances:
            if rail in flagged or rail in driven:
                continue
            if allowed is not None and rail not in allowed:
                continue
            flagged.add(rail)
            # offset the flag one pitch sideways so its glyph/text doesn't
            # overlap the rail symbol; tie it back with a short wire
            fx = snap(x + PIN_PITCH)
            flag_extra.append(("PWR_FLAG", fx, y, False))
            flag_wires.append(Wire(x, y, fx, y))
        if flag_extra:
            power_names.add("PWR_FLAG")
        pwr_instances.extend(flag_extra)
        wires.extend(flag_wires)

        for pname in sorted(power_names):
            lib_entries.append(power_symbol_lib_sexp(pname))
        for i, (rail, x, y, down) in enumerate(pwr_instances, start=1):
            body.append(_gen_power_instance(
                rail, f"#PWR{i:02d}", x, y, 180 if down else 0,
                project, root_uuid))

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

        lib_symbols = "\n\t\t".join(lib_entries)
        parts = "\n".join(label_lines + wire_lines + junction_lines
                          + body + nc_lines)
        text = f"""(kicad_sch
\t(version 20250114)
\t(generator "hardware-pipeline")
\t(generator_version "1.0")
\t(uuid "{root_uuid}")
\t(paper "A3")
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
    return EmittedSheet(text=text, metrics=metrics_of(placed))

