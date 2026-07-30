"""Design → SchematicGraph: unit explosion, power stripping, satellites.

Implements the two load-bearing rules from the engine design:

D2a — power/GND nets are never edges. Every pin on a power-classified net
gets a PowerTap (rendered later as a stub + power symbol); the net vanishes
from the routing graph.

D2b — satellite rule: after stripping, a node with ZERO remaining signal
edges is a satellite (decoupling/bulk caps). It leaves the graph and is
placed in a row next to its owner IC unit. Pull-ups (1 signal edge),
crystals and series elements (2 signal edges) stay in the graph naturally.
"""

from __future__ import annotations

import re

from ..component import Component
from ..design import Design
from ..model import ElectricalType
from ..symbol import SymbolModel
from .ir import (
    HierPort,
    NetEdge,
    Node,
    NodeKind,
    Port,
    PowerTap,
    SatelliteCap,
    SchematicGraph,
)

# Power-net name classification (mirrors pipeline nets._POWER_PATTERNS;
# pipeline will delegate here at the Phase E cutover).
_GROUND_RE = re.compile(r"^(GND\w*|VSS\w*|AGND|DGND|PGND|EARTH)$", re.IGNORECASE)
_RAIL_RE = re.compile(
    r"^(\+?\d+V\d*|\+?\d+\.\d+V|VCC\w*|VDD\w*|VBAT\w*|VBUS|VIN|VOUT|VSYS|"
    r"V\d+\w*|\+\d+\.?\d*V?\w*)$",
    re.IGNORECASE,
)


def is_ground_net(name: str) -> bool:
    return bool(_GROUND_RE.match(name))


def is_power_net(name: str) -> bool:
    return is_ground_net(name) or bool(_RAIL_RE.match(name))


def _node_kind(comp: Component, unit_count: int) -> NodeKind:
    if comp.reference_prefix in ("J", "P", "X"):
        return NodeKind.CONNECTOR
    if comp.reference_prefix in ("R", "C", "L") and len(comp.pins) == 2:
        return NodeKind.PASSIVE
    return NodeKind.IC_UNIT


def build(design: Design, sheet: str = "main",
          hier_ports: list[HierPort] | None = None) -> SchematicGraph:
    """Build the single-sheet layout graph for a Design.

    Multi-sheet decomposition is the composer's job (it calls build() once
    per sheet with that sheet's components in a sub-Design).
    """
    nodes: dict[str, Node] = {}
    node_of_pin: dict[int, tuple[str, str]] = {}  # id(Pin) → (node_id, pad)
    models: dict[str, SymbolModel] = {}

    for comp in design.components:
        model = SymbolModel.from_component(comp, style="readable")
        models[comp.ref] = model
        kind = _node_kind(comp, len(model.units))
        for unit in model.units:
            node_id = f"{comp.ref}#{unit.unit_id}"
            ports = [
                Port(number=pad, name=name, role=etype, side=side,
                     index=index, offset=offset)
                for pad, name, etype, side, index, offset
                in model.node_ports(unit.unit_id)
            ]
            nodes[node_id] = Node(
                id=node_id, kind=kind, ref=comp.ref, unit=unit.unit_id,
                lib_id=comp.lib_id, size=model.node_size(unit.unit_id),
                ports=ports,
            )
            for p in unit.pins:
                node_of_pin[id(comp._pin(p.pad))] = (node_id, p.pad)

    # ── split nets: power → taps, signal → edges ────────────────────────────
    edges: list[NetEdge] = []
    signal_degree: dict[str, int] = {nid: 0 for nid in nodes}
    for net in design.nets:
        ports = []
        for pin in net.pins:
            loc = node_of_pin.get(id(pin))
            if loc is not None:
                ports.append(loc)
        if not ports:
            continue
        if is_power_net(net.name):
            down = is_ground_net(net.name)
            for node_id, pad in ports:
                nodes[node_id].power_taps.append(
                    PowerTap(port_number=pad, rail=net.name, down=down))
        else:
            edge = NetEdge(net=net.name, named=True,
                           ports=sorted(ports), group=net.group)
            edges.append(edge)
            for node_id, _pad in ports:
                signal_degree[node_id] += 1

    # ── satellite extraction (D2b) ──────────────────────────────────────────
    satellites: dict[str, list[SatelliteCap]] = {}
    doomed: list[str] = []
    for node_id, node in nodes.items():
        if node.kind is not NodeKind.PASSIVE:
            continue
        if signal_degree[node_id] > 0 or not node.power_taps:
            continue
        rails = [t.rail for t in node.power_taps if not t.down]
        gnds = [t.rail for t in node.power_taps if t.down]
        rail = rails[0] if rails else (gnds[0] if gnds else "")
        owner = _find_owner(nodes, node_id, rail)
        comp = next(c for c in design.components if c.ref == node.ref)
        satellites.setdefault(owner, []).append(SatelliteCap(
            ref=node.ref, lib_id=node.lib_id,
            value=getattr(comp, "value", "") or comp.part_name,
            rail=rail, gnd=gnds[0] if gnds else "GND"))
        doomed.append(node_id)
    for node_id in doomed:
        del nodes[node_id]

    edges.sort(key=lambda e: e.net)
    return SchematicGraph(sheet=sheet, nodes=nodes, edges=edges,
                          satellites=satellites,
                          hier_ports=list(hier_ports or []))


def _find_owner(nodes: dict[str, Node], sat_id: str, rail: str) -> str:
    """Owner of a satellite cap: the IC unit with a power tap on the same
    rail (lowest ref, then lowest unit); fallback: first IC unit; fallback:
    the satellite's own id (kept in sat_rows under itself)."""
    candidates = []
    for node in nodes.values():
        if node.kind is not NodeKind.IC_UNIT or node.id == sat_id:
            continue
        if any(t.rail == rail and not t.down for t in node.power_taps):
            candidates.append(node.id)
    if not candidates:
        candidates = [n.id for n in nodes.values()
                      if n.kind is NodeKind.IC_UNIT and n.id != sat_id]
    return sorted(candidates)[0] if candidates else sat_id


__all__ = ["build", "is_power_net", "is_ground_net"]


# Re-export for callers that need the electrical roles when post-processing
_ = ElectricalType
