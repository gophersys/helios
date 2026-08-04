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
   vertical to bbox top - PIN_PITCH, then across); each further escape
   over the same node steps one 2.54 increment outward and upward so
   different nets never share an escape track. One vertical trunk
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
    """Label-fallback policy: single port, fanout > 4, rank span > 2,
    backward, preset.

    A single-port net has nothing to route to on this sheet (it leaves it —
    the composer turns those labels into hierarchical ports), so it MUST be
    labeled: the routed branch below skips edges with < 2 ports and the net
    would vanish from the emitted file.
    """
    if (edge.use_labels or len(edge.ports) < 2 or len(edge.ports) > 4
            or edge.net in backward):
        return True
    ranks = [ranking.rank_of[nid] for nid, _ in edge.ports]
    # Geometry is planned from the ORIGINAL hyperedge; the VIRTUAL nodes
    # rank.assign inserts for rank-spanning edges are ignored. A net whose
    # ports are two ranks apart is therefore emitted as one horizontal wire
    # from the far port straight into the min-rank channel, crossing the
    # whole intervening column and picking up whatever pin sits at that y.
    # Only adjacent ranks can be routed; anything wider takes labels.
    return max(ranks) - min(ranks) > 1


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
    # Ports facing out of the channel leave their port y: TOP/BOTTOM ports
    # connect one stub away, far-side LEFT/RIGHT ports connect over the node
    # top (filled in by the escape pass). The track interval must cover the
    # ys the trunk will actually span, or two nets with disjoint PORT spans
    # get the same track x and their trunks overlap colinearly.
    for _nid, _pnum, _px, py, port, direct in ports:
        if direct:
            continue
        if port.side is Side.TOP:
            ys.append(snap(py - _STUB))
        elif port.side is Side.BOTTOM:
            ys.append(snap(py + _STUB))
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
        "escapes": {},
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
    plan: dict, tx: float, placement: Placement  # noqa: ARG001 — symmetry
) -> tuple[list[Wire], list[tuple[float, float]], int]:
    """Wires, junctions, and bend count for one routed net.

    Far-side escape geometry comes from ``plan["escapes"]``, filled in by
    :func:`_plan_escapes` before track assignment (the trunk interval has to
    know where the escapes land)."""
    ports: list[_PortPlan] = plan["ports"]
    if plan["straight"]:
        p, q = ports
        return [Wire(p[2], p[3], q[2], q[3])], [], 0

    ws: list[Wire] = []
    bends = 0
    conn_ys: list[float] = []
    for nid, pnum, px, py, port, direct in ports:
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
            sx, yt = plan["escapes"][(nid, pnum)]
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


def _ceiling(graph: SchematicGraph, placement: Placement, nid: str) -> float:
    """Lowest y an escape wire over ``nid`` may use.

    A far-side escape runs a horizontal wire across the top of the node, so
    it must stay clear of whatever sits directly above: the rank-mate's
    bbox bottom AND the downward power-symbol stubs hanging off its
    BOTTOM-side pins (one pin pitch), plus a grid of margin. Without this
    bound the ladder grows without limit and the third escape over a node
    lands exactly on the pins of the node above it (place.MIN_GAP between
    vertical rank-mates is 3 * PIN_PITCH).
    """
    ox, oy = placement.origin[nid]
    w, _h = graph.nodes[nid].size
    limit = -1e9
    for other, (px, py) in placement.origin.items():
        if other == nid:
            continue
        ow, oh = graph.nodes[other].size
        if ow <= 0.0 or oh <= 0.0:      # virtual nodes have no body
            continue
        if px < ox + w and ox < px + ow and py + oh <= oy:
            limit = max(limit, py + oh)
    return limit + PIN_PITCH + GRID if limit > -1e8 else -1e9


def _plan_escapes(
    plans: dict[str, dict],
    graph: SchematicGraph,
    placement: Placement,
    label_hosts: set[str],
) -> list[str]:
    """Assign every far-side port an escape track over its node.

    Tracks are allocated per node in net-name order, x one pin pitch
    further out and y one grid higher each time, so no two nets share an
    escape. Two bands are reserved before the first track:

    * x — the label point and the LEFT/RIGHT power-tap stub both sit one
      pin pitch off the pin, so track 0 would be drawn straight through
      them (a label on a foreign wire silently merges the two nets);
    * y — TOP-side pin stubs (power taps and routed TOP ports) end one
      pin pitch above the node origin.

    Returns the nets that could not be given a track inside the free band
    above their node; the caller demotes them to labels.
    """
    esc: dict[str, int] = {}
    ceiling = {nid: _ceiling(graph, placement, nid) for nid in placement.origin}
    x_res: dict[str, int] = {}
    y_res: dict[str, float] = {}
    for nid, node in graph.nodes.items():
        taps_side = {node.port(t.port_number).side for t in node.power_taps}
        x_res[nid] = int(nid in label_hosts
                         or bool(taps_side & {Side.LEFT, Side.RIGHT}))
        y_res[nid] = PIN_PITCH if any(
            p.side is Side.TOP for p in node.ports) else 0.0

    demoted: list[str] = []
    for net in sorted(plans):
        plan = plans[net]
        local = dict(esc)
        assigned: dict[tuple[str, str], tuple[float, float]] = {}
        for nid, pnum, px, _py, port, direct in plan["ports"]:
            if direct or port.side in (Side.TOP, Side.BOTTOM):
                continue
            k = local.get(nid, 0)
            yt = snap(placement.origin[nid][1] - y_res[nid] - GRID * (k + 1))
            if yt < ceiling[nid]:
                assigned = {}
                demoted.append(net)
                break
            off = _STUB * (k + 1 + x_res[nid])
            sx = snap(px + off) if port.side is Side.RIGHT else snap(px - off)
            assigned[(nid, pnum)] = (sx, yt)
            local[nid] = k + 1
        else:
            esc = local
            plan["escapes"] = assigned
            for _sx, yt in assigned.values():
                plan["y0"] = round(min(plan["y0"], yt - GRID), 4)
                plan["y1"] = round(max(plan["y1"], yt + GRID), 4)
    return demoted


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
    to_label: list[NetEdge] = []
    edges = {e.net: e for e in graph.edges}
    for edge in sorted(graph.edges, key=lambda e: e.net):
        # A single-rank graph has no channel to route through: every net
        # falls back to labels (channel_x is empty, _track_x would crash).
        if n_channels == 0 or _needs_labels(edge, ranking, backward):
            to_label.append(edge)
        elif len(edge.ports) >= 2:
            ch = _channel_index(edge, ranking, n_channels)
            plans[edge.net] = _plan(edge, graph, ranking, placement, ch)
            per_channel.setdefault(ch, []).append(edge.net)

    # Every node that will carry a label: labelled nets label all their
    # ports, routed named nets label their driver port. An escape track over
    # such a node must not be drawn through the label point.
    label_hosts = {nid for e in to_label for nid, _ in e.ports}
    label_hosts |= {_driver_label(p)[0] for p in plans.values()
                    if p["edge"].named}

    for net in _plan_escapes(plans, graph, placement, label_hosts):
        to_label.append(edges[net])
        del plans[net]
        for members in per_channel.values():
            if net in members:
                members.remove(net)

    for edge in sorted(to_label, key=lambda e: e.net):
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
