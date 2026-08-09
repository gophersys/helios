"""Layout-engine intermediate representation — THE contract between stages.

Pipeline per sheet:

    graph_build.build(design)         -> dict[sheet, SchematicGraph]
    rank.assign(graph)                -> Ranking
    order.minimize(graph, ranking)    -> Ordering
    place.coordinates(graph, ranking, ordering) -> Placement
    route.route(graph, ranking, ordering, placement) -> Routing
    power.taps(...)/engine.emit(...)  -> PlacedSheet -> .kicad_sch text

Coordinate conventions
----------------------
- SCHEMATIC space: +Y grows DOWNWARD (KiCad file convention). Everything
  in Placement/Routing is schematic space, snapped to the 1.27 mm grid.
- Port.offset is in schematic space relative to the node ORIGIN (its body
  top-left corner): (dx, dy) with dy >= 0 growing downward. Ports are the
  pin CONNECTION points (tip of the pin, where a wire attaches).
- Node.size is (width, height) of the full node bbox including pin length
  and text margin. Bboxes must not overlap after placement.

Determinism
-----------
Every stage must be a pure function of its inputs with NO randomness and
no dict-iteration-order dependence on anything but insertion order (which
is itself deterministic from graph_build). Ties are always broken by
sorted string keys (node id, then port number, then net name).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..symbol import Side

GRID = 1.27          # mm — all coordinates snap to this
PIN_PITCH = 2.54     # mm — pin spacing on symbol sides


def snap(v: float, grid: float = GRID) -> float:
    """Snap to grid with stable rounding (round-half-away-from-zero)."""
    import math
    q = v / grid
    r = math.floor(q + 0.5) if q >= 0 else math.ceil(q - 0.5)
    return round(r * grid, 4)


class NodeKind(str, Enum):
    IC_UNIT = "ic_unit"      # one unit of a (possibly multi-unit) component
    PASSIVE = "passive"      # 2-pin R/C/L in the signal graph
    CONNECTOR = "connector"
    HIER_PORT = "hier_port"  # pseudo-node for a hierarchical label
    VIRTUAL = "virtual"      # rank-spanning edge dummy (inserted by rank stage)


@dataclass(frozen=True)
class Port:
    """A connectable pin on a node, geometry fixed by the symbol."""

    number: str              # pad number
    name: str
    role: str                # ElectricalType value string
    side: Side
    index: int               # order along its side, top→bottom / left→right
    offset: tuple[float, float]  # schematic-space (dx, dy) from node origin


@dataclass(frozen=True)
class PowerTap:
    """Marker: this port connects to a power/ground rail via a local
    power-symbol stub instead of a routed edge."""

    port_number: str
    rail: str                # net name, e.g. "+3V3", "GND"
    down: bool               # True → ground symbol below; False → rail above


@dataclass
class Node:
    id: str                  # "U1#2" (ref + unit) / "C3#1" / "hier:GPS_TX"
    kind: NodeKind
    ref: str
    unit: int
    lib_id: str
    size: tuple[float, float]
    ports: list[Port]
    rotation: int = 0        # degrees CW: 0/90/180/270 (passives only in v1)
    power_taps: list[PowerTap] = field(default_factory=list)

    def port(self, number: str) -> Port:
        for p in self.ports:
            if p.number == number:
                return p
        raise KeyError(f"{self.id}: no port {number}")


@dataclass
class NetEdge:
    """A signal net as a hyperedge (kept whole; stages may decompose)."""

    net: str
    named: bool              # named nets get a label even when fully routed
    ports: list[tuple[str, str]]   # (node_id, port_number)
    group: str | None = None       # bus ribbon grouping ("SPI0", ...)
    use_labels: bool = False       # set by route policy: label fallback


@dataclass
class HierPort:
    name: str
    direction: str           # "input" | "output" | "bidirectional"


@dataclass
class SchematicGraph:
    """Input IR for one sheet. Power nets are ALREADY stripped to taps;
    satellites (decoupling caps) are ALREADY extracted."""

    sheet: str
    nodes: dict[str, Node]                 # insertion order = deterministic
    edges: list[NetEdge]
    satellites: dict[str, list["SatelliteCap"]]  # owner node id → caps
    hier_ports: list[HierPort]


@dataclass(frozen=True)
class SatelliteCap:
    ref: str
    lib_id: str
    value: str
    rail: str                # power net it decouples
    gnd: str                 # ground net name
    footprint: str = ""      # footprint lib_id, threaded through to emit
    rail_pad: str = "1"      # pad the DESIGN connects to `rail`
    gnd_pad: str = "2"       # pad the DESIGN connects to `gnd`


# ── stage outputs ───────────────────────────────────────────────────────────


@dataclass
class Ranking:
    """rank.assign output. Virtual nodes for rank-spanning routed edges are
    ADDED to graph.nodes by the rank stage (kind=VIRTUAL, one per crossed
    rank), and edges are rewritten into 2-port segments via `segments`."""

    rank_of: dict[str, int]                # node id → rank (0 = leftmost)
    ranks: list[list[str]]                 # rank → node ids (initial order)
    segments: list[tuple[str, str, str]]   # (net, from_node, to_node) proper
                                           # edges spanning exactly 1 rank


@dataclass
class Ordering:
    """order.minimize output: final top→bottom order per rank."""

    order: list[list[str]]                 # rank → node ids
    crossings: int                         # final crossing count (metric)


@dataclass
class Placement:
    """place.coordinates output. Origins in schematic space, snapped."""

    origin: dict[str, tuple[float, float]]     # node id → (x, y) body top-left
    col_x: list[float]                          # rank → column left edge
    col_width: list[float]                      # rank → widest node width
    channel_x: list[tuple[float, float]]        # per gap: (left, right) bounds
    sat_rows: dict[str, list[tuple[str, float, float]]]
    # owner node id → [(cap ref, x, y)] positions of its satellite caps


@dataclass(frozen=True)
class Wire:
    x1: float
    y1: float
    x2: float
    y2: float

    def is_orthogonal(self) -> bool:
        return self.x1 == self.x2 or self.y1 == self.y2


def point_on_wire(x: float, y: float, w: Wire, eps: float = 1e-6) -> bool:
    """True when (x, y) lies on wire ``w`` (endpoints included)."""
    return (min(w.x1, w.x2) - eps <= x <= max(w.x1, w.x2) + eps
            and min(w.y1, w.y2) - eps <= y <= max(w.y1, w.y2) + eps)


def wires_short(wa: Wire, wb: Wire, eps: float = 1e-6) -> bool:
    """True when two orthogonal wires of DIFFERENT nets would connect in
    KiCad: colinear overlap of positive length, or either wire's endpoint
    lying on the other wire. A plain mid-segment crossing does not connect
    and is not reported."""
    a_h, b_h = wa.y1 == wa.y2, wb.y1 == wb.y2
    if a_h == b_h:  # parallel: short iff colinear with positive overlap
        if a_h:
            if abs(wa.y1 - wb.y1) > eps:
                return False
            lo = max(min(wa.x1, wa.x2), min(wb.x1, wb.x2))
            hi = min(max(wa.x1, wa.x2), max(wb.x1, wb.x2))
        else:
            if abs(wa.x1 - wb.x1) > eps:
                return False
            lo = max(min(wa.y1, wa.y2), min(wb.y1, wb.y2))
            hi = min(max(wa.y1, wa.y2), max(wb.y1, wb.y2))
        if hi - lo > eps:
            return True
    return any(
        point_on_wire(x, y, other, eps)
        for (x, y), other in (
            ((wa.x1, wa.y1), wb), ((wa.x2, wa.y2), wb),
            ((wb.x1, wb.y1), wa), ((wb.x2, wb.y2), wa),
        )
    )


@dataclass
class Routing:
    """route.route output."""

    wires: dict[str, list[Wire]]           # net → segments
    junctions: dict[str, list[tuple[float, float]]]
    labeled_nets: list[str]                # nets falling back to labels
    label_at: dict[str, list[tuple[str, float, float, int]]]
    # net → [(node_id anchor, x, y, angle)] label positions
    bends: int
    total_length: float


@dataclass
class PlacedSheet:
    """Everything engine.emit needs for one sheet."""

    graph: SchematicGraph
    ranking: Ranking
    ordering: Ordering
    placement: Placement
    routing: Routing


@dataclass
class Metrics:
    crossings: int
    total_wire_length: float
    bends: int
    alignment: float          # fraction of 2-pin routed nets that are 1 straight segment
    labeled_nets: int
    routed_nets: int
