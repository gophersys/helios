"""Layer (rank) assignment — the `rank.assign` stage of the layout pipeline.

Algorithm
---------
1. Decompose each routed NetEdge (use_labels=False) into directed binary
   segments driver-node -> other-node. The driver port is the first port by
   (node_id, port_number) sort whose role is "output"/"power_out"; failing
   that, a port on the edge node with the most total ports (hub drives
   spokes, ties by node id sort); failing that, the first port by sort.
   Self-loops and repeated node pairs per net are deduplicated. Edges with
   use_labels=True contribute no segments.
2. Orient arcs so HIER_PORT(input)/CONNECTOR nodes are sources and
   HIER_PORT(output) nodes are sinks in the ranking digraph.
3. Break remaining cycles with the Eades-Lin-Smyth greedy FAS heuristic
   (vertices processed in sorted-id order); feedback arcs are reversed.
4. Longest-path layering from sources (rank 0 = sources).
5. Clamp output hier ports to the max rank, run one median-compaction pass
   in sorted-id order, then compress away any empty ranks.
6. Rewrite segments spanning >1 rank into chains of proper 1-rank segments
   through VIRTUAL nodes added to graph.nodes ("v:<net>:<from>:<to>:<k>").
   1-rank and same-rank segments pass through unchanged.

Pure function of the graph; all ties broken by sorted string keys.
"""

from __future__ import annotations

import heapq
import math

from .ir import NetEdge, Node, NodeKind, Ranking, SchematicGraph

_DRIVER_ROLES = frozenset({"output", "power_out"})

Arc = tuple[str, str]
Segment = tuple[str, str, str]


def _driver_node(edge: NetEdge, graph: SchematicGraph) -> str:
    """Pick the driving node of a net per the driver-port rules."""
    ports = sorted(set(edge.ports))
    for nid, pnum in ports:
        node = graph.nodes.get(nid)
        if node is None:
            continue
        try:
            if node.port(pnum).role in _DRIVER_ROLES:
                return nid
        except KeyError:
            continue
    nids = sorted({nid for nid, _ in ports if nid in graph.nodes})
    if nids:
        return min(nids, key=lambda n: (-len(graph.nodes[n].ports), n))
    return ports[0][0]


def _raw_segments(graph: SchematicGraph) -> list[Segment]:
    """Directed binary (net, driver, other) segments for routed edges."""
    segs: list[Segment] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in graph.edges:
        if edge.use_labels or not edge.ports:
            continue
        driver = _driver_node(edge, graph)
        for other in sorted({nid for nid, _ in edge.ports if nid != driver}):
            key = (edge.net, *sorted((driver, other)))
            if key not in seen:
                seen.add(key)
                segs.append((edge.net, driver, other))
    return segs


def _pinned(graph: SchematicGraph) -> tuple[set[str], set[str]]:
    """(rank-0 pinned node ids, max-rank pinned node ids)."""
    dirs = {hp.name: hp.direction for hp in graph.hier_ports}
    pin0: set[str] = set()
    pinmax: set[str] = set()
    for nid, node in graph.nodes.items():
        if node.kind is NodeKind.CONNECTOR:
            pin0.add(nid)
        elif node.kind is NodeKind.HIER_PORT:
            direction = dirs.get(nid.removeprefix("hier:"), dirs.get(node.ref, ""))
            if direction == "input":
                pin0.add(nid)
            elif direction == "output":
                pinmax.add(nid)
    return pin0, pinmax


def _greedy_fas(vertices: list[str], arcs: set[Arc]) -> set[Arc]:
    """Eades-Lin-Smyth greedy feedback arc set; returns arcs to reverse."""
    out: dict[str, set[str]] = {v: set() for v in vertices}
    inn: dict[str, set[str]] = {v: set() for v in vertices}
    for u, v in arcs:
        out[u].add(v)
        inn[v].add(u)
    remaining = set(vertices)

    def drop(v: str) -> None:
        remaining.discard(v)
        for u in inn[v]:
            out[u].discard(v)
        for w in out[v]:
            inn[w].discard(v)

    left: list[str] = []
    right: list[str] = []
    while remaining:
        progressed = True
        while progressed:
            progressed = False
            for v in sorted(remaining):
                if not out[v]:  # sink
                    right.append(v)
                    drop(v)
                    progressed = True
            for v in sorted(remaining):
                if not inn[v]:  # source
                    left.append(v)
                    drop(v)
                    progressed = True
        if remaining:
            v = min(remaining, key=lambda n: (len(inn[n]) - len(out[n]), n))
            left.append(v)
            drop(v)
    pos = {v: i for i, v in enumerate(left + right[::-1])}
    return {(u, v) for u, v in arcs if pos[u] > pos[v]}


def _longest_path(
    vertices: list[str], dag: set[Arc]
) -> tuple[dict[str, int], dict[str, set[str]], dict[str, set[str]]]:
    """Longest-path layering of a DAG; sources (in-degree 0) get rank 0."""
    preds: dict[str, set[str]] = {v: set() for v in vertices}
    succs: dict[str, set[str]] = {v: set() for v in vertices}
    for u, v in dag:
        succs[u].add(v)
        preds[v].add(u)
    indeg = {v: len(preds[v]) for v in vertices}
    rank = dict.fromkeys(vertices, 0)
    ready = [v for v in vertices if indeg[v] == 0]
    heapq.heapify(ready)
    while ready:
        u = heapq.heappop(ready)
        for v in sorted(succs[u]):
            rank[v] = max(rank[v], rank[u] + 1)
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(ready, v)
    return rank, preds, succs


def _compact(
    rank: dict[str, int],
    preds: dict[str, set[str]],
    succs: dict[str, set[str]],
    frozen: set[str],
) -> None:
    """One pass in sorted-id order: move to floor(median neighbor rank)."""
    for v in sorted(rank):
        if v in frozen:
            continue
        neigh = sorted(rank[u] for u in (*preds[v], *succs[v]))
        if not neigh:
            continue
        n = len(neigh)
        median = neigh[n // 2] if n % 2 else (neigh[n // 2 - 1] + neigh[n // 2]) / 2
        cand = math.floor(median)
        if cand == rank[v]:
            continue
        if all(rank[p] < cand for p in preds[v]) and all(cand < rank[s] for s in succs[v]):
            rank[v] = cand


def _proper_segments(
    graph: SchematicGraph, raw: list[Segment], rank: dict[str, int]
) -> list[Segment]:
    """Chain >1-rank segments through VIRTUAL nodes; others pass through."""
    segments: list[Segment] = []
    for net, u, v in raw:
        span = rank[v] - rank[u]
        if abs(span) <= 1:
            segments.append((net, u, v))
            continue
        step = 1 if span > 0 else -1
        prev = u
        for k in range(abs(span) - 1):
            vid = f"v:{net}:{u}:{v}:{k}"
            graph.nodes[vid] = Node(
                id=vid, kind=NodeKind.VIRTUAL, ref="", unit=0,
                lib_id="", size=(0.0, 0.0), ports=[],
            )
            rank[vid] = rank[u] + step * (k + 1)
            segments.append((net, prev, vid))
            prev = vid
        segments.append((net, prev, v))
    return segments


def assign(graph: SchematicGraph) -> Ranking:
    """Assign a layer (rank) to every node; mutates graph.nodes with the
    VIRTUAL dummies needed to make every routed segment proper."""
    raw = _raw_segments(graph)
    vertices = sorted(graph.nodes)
    pin0, pinmax = _pinned(graph)
    arcs: set[Arc] = set()
    for _net, u, v in raw:
        if u in pin0 and v in pin0:
            continue  # both pinned to rank 0: segment stays, arc constrains nothing
        if v in pin0 and u not in pin0:
            u, v = v, u  # pinned rank-0 nodes act as sources
        elif u in pinmax and v not in pinmax:
            u, v = v, u  # output hier ports act as sinks
        arcs.add((u, v))
    reversed_arcs = _greedy_fas(vertices, arcs)
    dag = {(v, u) if (u, v) in reversed_arcs else (u, v) for u, v in arcs}
    rank, preds, succs = _longest_path(vertices, dag)
    if rank:
        top = max(rank.values())
        for v in pinmax:
            rank[v] = top
        _compact(rank, preds, succs, pin0 | pinmax)
        remap = {r: i for i, r in enumerate(sorted(set(rank.values())))}
        for v in rank:
            rank[v] = remap[rank[v]]
    segments = _proper_segments(graph, raw, rank)
    ranks: list[list[str]] = [[] for _ in range(max(rank.values()) + 1 if rank else 0)]
    for v in sorted(rank):
        ranks[rank[v]].append(v)
    return Ranking(rank_of=rank, ranks=ranks, segments=segments)
