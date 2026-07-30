"""Orthogonal channel routing (stage 5 of the layout pipeline).

Algorithm
---------
1. LABEL POLICY (per original hyperedge, before any geometry): a net falls
   back to net labels iff its fanout exceeds 4 ports, its port ranks span
   more than 2 columns, any of its decomposed segments runs backward
   (higher rank -> lower rank), or ``use_labels`` was preset. A labeled
   net gets a 2.54 mm stub wire out of every port (away from the body)
   plus one label per port at the stub end, angled with the stub
   direction (right 0, left 180, top 90, bottom 270).
2. CHANNEL + TRACKS for routed nets: each net routes inside ONE vertical
   channel — the gap at its minimum port rank; same-rank nets use the gap
   to the right of their rank (left when at the rightmost rank). Within a
   channel, vertical trunk tracks are assigned by greedy left-edge
   interval coloring over the nets' port-y spans inflated by one GRID,
   nets sorted by (top y, net name). Bus-grouped nets are packed as one
   contiguous block, members ordered by (top y, net name). Track k of n
   sits at ``left + (k + 1) / (n + 1)`` of the channel width, snapped.
3. GEOMETRY per routed net: a horizontal stub from each port to the trunk
   x; a port facing away from its channel routes over its node (2.54 out,
   vertical to bbox top - PIN_PITCH, then across). One vertical trunk
   spans all stub ys. A 2-port net whose ports face each other across the
   channel at equal y collapses to a single straight wire. Junctions sit
   at T meets strictly inside the trunk and wherever >= 3 same-net wire
   endpoints coincide. Named routed nets get one label at the driver
   port's stub end (first "output" port, else first sorted port).

Deterministic: pure function of its inputs; all ties broken by sorted
string keys (net name, then node id, then port number).
"""

from __future__ import annotations

from collections import Counter

from ..symbol import Side
from .ir import (
    GRID,
    PIN_PITCH,
    NetEdge,
    Ordering,
    Placement,
    Port,
    Ranking,
    Routing,
    SchematicGraph,
    Wire,
    snap,
)

_STUB = PIN_PITCH  # label / escape stub length, mm

_ANGLE = {Side.RIGHT: 0, Side.LEFT: 180, Side.TOP: 90, Side.BOTTOM: 270}
_DIR = {
    Side.RIGHT: (1.0, 0.0),
    Side.LEFT: (-1.0, 0.0),
    Side.TOP: (0.0, -1.0),   # schematic +Y grows downward: top stubs go up
    Side.BOTTOM: (0.0, 1.0),
}

# per-port plan entry: (node_id, port_number, px, py, Port, direct)
_PortPlan = tuple[str, str, float, float, Port, bool]


def _port_point(
    graph: SchematicGraph, placement: Placement, nid: str, pnum: str
) -> tuple[float, float, Port]:
    """Absolute schematic-space connection point of one port."""
    port = graph.nodes[nid].port(pnum)
    ox, oy = placement.origin[nid]
    return snap(ox + port.offset[0]), snap(oy + port.offset[1]), port


def _needs_labels(edge: NetEdge, ranking: Ranking, backward: set[str]) -> bool:
    """Label-fallback policy: fanout > 4, rank span > 2, backward, preset."""
    if edge.use_labels or len(edge.ports) > 4 or edge.net in backward:
        return True
    ranks = [ranking.rank_of[nid] for nid, _ in edge.ports]
    return max(ranks) - min(ranks) > 2


def _channel_index(edge: NetEdge, ranking: Ranking, n_channels: int) -> int:
    """Channel (column gap) a routed net lives in.

    Spanning nets use the gap at their minimum rank; same-rank nets use
    the gap to the right of their rank, or the left one at the rightmost
    rank. Clamped to the valid gap range.
    """
    ranks = [ranking.rank_of[nid] for nid, _ in edge.ports]
    lo, hi = min(ranks), max(ranks)
    ch = (lo if lo < n_channels else lo - 1) if lo == hi else lo
    return max(0, min(ch, n_channels - 1))


def _plan(
    edge: NetEdge,
    graph: SchematicGraph,
    ranking: Ranking,
    placement: Placement,
    ch: int,
) -> dict:
    """Per-net routing plan: port geometry, y-interval, straight-wire flag."""
    ports: list[_PortPlan] = []
    for nid, pnum in sorted(edge.ports):
        px, py, port = _port_point(graph, placement, nid, pnum)
        direct = (port.side is Side.RIGHT and ranking.rank_of[nid] <= ch) or (
            port.side is Side.LEFT and ranking.rank_of[nid] > ch
        )
        ports.append((nid, pnum, px, py, port, direct))
    ys = [p[3] for p in ports]
    straight = (
        len(ports) == 2
        and ports[0][5]
        and ports[1][5]
        and {ports[0][4].side, ports[1][4].side} == {Side.LEFT, Side.RIGHT}
        and ys[0] == ys[1]
    )
    return {
        "edge": edge,
        "ports": ports,
        "y0": round(min(ys) - GRID, 4),
        "y1": round(max(ys) + GRID, 4),
        "straight": straight,
    }


def _assign_tracks(
    nets: list[str], plans: dict[str, dict]
) -> tuple[dict[str, int], int]:
    """Greedy left-edge interval coloring; bus groups packed contiguously.

    Units (single nets, or whole group blocks) are sorted by (top y,
    name) and each takes the lowest run of tracks whose occupied
    intervals do not overlap its members' intervals.
    """
    units: list[tuple[tuple[float, str], list[str]]] = []
    groups: dict[str, list[str]] = {}
    for net in nets:
        g = plans[net]["edge"].group
        if g is None:
            units.append(((plans[net]["y0"], net), [net]))
        else:
            groups.setdefault(g, []).append(net)
    for g in sorted(groups):
        members = sorted(groups[g], key=lambda n: (plans[n]["y0"], n))
        units.append(((min(plans[n]["y0"] for n in members), g), members))
    units.sort(key=lambda u: u[0])

    tracks: list[list[tuple[float, float]]] = []
    track_of: dict[str, int] = {}
    for _, members in units:
        s = 0
        while True:
            while len(tracks) < s + len(members):
                tracks.append([])
            ok = all(
                all(
                    plans[m]["y1"] < a or plans[m]["y0"] > b
                    for a, b in tracks[s + i]
                )
                for i, m in enumerate(members)
            )
            if ok:
                break
            s += 1
        for i, m in enumerate(members):
            tracks[s + i].append((plans[m]["y0"], plans[m]["y1"]))
            track_of[m] = s + i
    return track_of, len(tracks)


def _track_x(placement: Placement, ch: int, k: int, n: int) -> float:
    """Center x of track k of n in channel ch, snapped to GRID."""
    left, right = placement.channel_x[ch]
    return snap(left + (k + 1) * ((right - left) / (n + 1)))


def _add(ws: list[Wire], x1: float, y1: float, x2: float, y2: float) -> None:
    if (x1, y1) != (x2, y2):
        ws.append(Wire(x1, y1, x2, y2))


def _emit(
    plan: dict, tx: float, placement: Placement
) -> tuple[list[Wire], list[tuple[float, float]], int]:
    """Wires, junctions, and bend count for one routed net."""
    ports: list[_PortPlan] = plan["ports"]
    if plan["straight"]:
        p, q = ports
        return [Wire(p[2], p[3], q[2], q[3])], [], 0

    ws: list[Wire] = []
    bends = 0
    conn_ys: list[float] = []
    for nid, _pnum, px, py, port, direct in ports:
        if direct:
            _add(ws, px, py, tx, py)
            conn_ys.append(py)
        elif port.side in (Side.TOP, Side.BOTTOM):
            sy = snap(py - _STUB) if port.side is Side.TOP else snap(py + _STUB)
            _add(ws, px, py, px, sy)
            _add(ws, px, sy, tx, sy)
            conn_ys.append(sy)
            bends += 1
        else:  # far-side LEFT/RIGHT port: route over the node body
            sx = snap(px + _STUB) if port.side is Side.RIGHT else snap(px - _STUB)
            yt = snap(placement.origin[nid][1] - PIN_PITCH)
            _add(ws, px, py, sx, py)
            _add(ws, sx, py, sx, yt)
            _add(ws, sx, yt, tx, yt)
            conn_ys.append(yt)
            bends += 2

    ymin, ymax = min(conn_ys), max(conn_ys)
    juncs = {(tx, y) for y in conn_ys if ymin < y < ymax}
    if ymax > ymin:
        ws.append(Wire(tx, ymin, tx, ymax))
        cnt = Counter(conn_ys)
        bends += sum(1 for y in (ymin, ymax) if cnt[y] == 1)  # corner bends
    ep: Counter[tuple[float, float]] = Counter()
    for w in ws:
        ep[(w.x1, w.y1)] += 1
        ep[(w.x2, w.y2)] += 1
    juncs |= {p for p, c in ep.items() if c >= 3}
    return ws, sorted(juncs), bends


def _driver_label(plan: dict) -> tuple[str, float, float, int]:
    """Label entry at the driver port's stub of a named routed net."""
    ports: list[_PortPlan] = plan["ports"]
    outs = [p for p in ports if p[4].role == "output"]
    nid, _pnum, px, py, port, _direct = (outs or ports)[0]
    dx, dy = _DIR[port.side]
    return (nid, snap(px + dx * _STUB), snap(py + dy * _STUB), _ANGLE[port.side])


def route(
    graph: SchematicGraph,
    ranking: Ranking,
    ordering: Ordering,  # noqa: ARG001 — API symmetry; order is baked into placement
    placement: Placement,
) -> Routing:
    """Route all nets of one sheet: wires + junctions + labels + metrics."""
    backward = {
        net
        for net, a, b in ranking.segments
        if ranking.rank_of.get(a, 0) > ranking.rank_of.get(b, 0)
    }
    n_channels = len(placement.channel_x)

    wires: dict[str, list[Wire]] = {}
    junctions: dict[str, list[tuple[float, float]]] = {}
    labeled_nets: list[str] = []
    label_at: dict[str, list[tuple[str, float, float, int]]] = {}
    bends = 0

    plans: dict[str, dict] = {}
    per_channel: dict[int, list[str]] = {}
    for edge in sorted(graph.edges, key=lambda e: e.net):
        if _needs_labels(edge, ranking, backward):
            labeled_nets.append(edge.net)
            stubs: list[Wire] = []
            labels: list[tuple[str, float, float, int]] = []
            for nid, pnum in sorted(edge.ports):
                px, py, port = _port_point(graph, placement, nid, pnum)
                dx, dy = _DIR[port.side]
                lx, ly = snap(px + dx * _STUB), snap(py + dy * _STUB)
                stubs.append(Wire(px, py, lx, ly))
                labels.append((nid, lx, ly, _ANGLE[port.side]))
            wires[edge.net] = stubs
            label_at[edge.net] = labels
        elif len(edge.ports) >= 2:
            ch = _channel_index(edge, ranking, n_channels)
            plans[edge.net] = _plan(edge, graph, ranking, placement, ch)
            per_channel.setdefault(ch, []).append(edge.net)

    track_x: dict[str, float] = {}
    for ch in sorted(per_channel):
        trunked = [n for n in per_channel[ch] if not plans[n]["straight"]]
        track_of, n = _assign_tracks(trunked, plans)
        for net, k in track_of.items():
            track_x[net] = _track_x(placement, ch, k, n)

    for net in sorted(plans):
        ws, js, b = _emit(plans[net], track_x.get(net, 0.0), placement)
        wires[net] = ws
        if js:
            junctions[net] = js
        bends += b
        if plans[net]["edge"].named:
            label_at[net] = [_driver_label(plans[net])]

    total = sum(
        abs(w.x2 - w.x1) + abs(w.y2 - w.y1) for ws in wires.values() for w in ws
    )
    return Routing(
        wires=wires,
        junctions=junctions,
        labeled_nets=labeled_nets,
        label_at=label_at,
        bends=bends,
        total_length=round(total, 4),
    )
