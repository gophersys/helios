"""Crossing minimization — ELK-style ordering stage (order.minimize).

Deterministic port-aware barycenter sweeps over the proper 1-rank
segments produced by the rank stage:

- To reorder a layer against an adjacent FIXED layer, each node gets the
  mean absolute y-proxy of its neighbor endpoints in the fixed layer.
  The y-proxy of a real neighbor is its position index plus an intra-node
  offset from its FixedOrder port geometry:
  ``pos + (port.index / max(1, ports_on_that_side)) * 0.5``.
  Virtual nodes carry no ports and contribute their bare position index.
  Nodes with no neighbors in the fixed layer keep their previous index
  as barycenter (they stay put unless displaced by a tie-break).
- Sweep schedule: down (rank 1..max, previous rank fixed) then up
  (rank max-1..0, next rank fixed), alternating. A sweep is accepted
  when total crossings do not increase; the loop stops when crossings
  hit zero, after two consecutive non-improving sweeps, or after
  MAX_SWEEPS sweeps total.
- Sort key per layer is (barycenter, previous_index, node_id): stable,
  RNG-free, all ties broken by string node ids.

Same-rank segments are ignored for crossing counting; every node stays
present in the order lists regardless.
"""

from __future__ import annotations

from .ir import NodeKind, Ordering, Port, Ranking, SchematicGraph

MAX_SWEEPS = 8


def count_crossings(
    graph: SchematicGraph, ranking: Ranking, order: list[list[str]]
) -> int:
    """Count pairwise crossings of proper 1-rank segments under ``order``.

    For each adjacent-rank gap, two segments (a1->b1) and (a2->b2) cross
    iff ``(pos(a1) - pos(a2)) * (pos(b1) - pos(b2)) < 0`` where ``pos``
    is the index within the ordered layer. Same-rank segments are
    ignored. O(n^2) per gap; fine at schematic sheet sizes.
    """
    pos: dict[str, int] = {}
    for layer in order:
        for index, node_id in enumerate(layer):
            pos[node_id] = index
    gaps: dict[int, list[tuple[int, int]]] = {}
    for _net, u, v in ranking.segments:
        ru = ranking.rank_of[u]
        rv = ranking.rank_of[v]
        if abs(ru - rv) != 1:
            continue  # same-rank segments never count
        if ru > rv:
            u, v = v, u
            ru = rv
        gaps.setdefault(ru, []).append((pos[u], pos[v]))
    total = 0
    for segments in gaps.values():
        for i, (a1, b1) in enumerate(segments):
            for a2, b2 in segments[i + 1 :]:
                if (a1 - a2) * (b1 - b2) < 0:
                    total += 1
    return total


def _net_ports(graph: SchematicGraph) -> dict[tuple[str, str], Port]:
    """Map (node_id, net) -> the Port that net attaches to on that node.

    When a net touches several ports of one node, the smallest port
    number (string order) wins — a deterministic, arbitrary choice.
    """
    chosen: dict[tuple[str, str], str] = {}
    for edge in graph.edges:
        for node_id, port_number in edge.ports:
            key = (node_id, edge.net)
            if key not in chosen or port_number < chosen[key]:
                chosen[key] = port_number
    resolved: dict[tuple[str, str], Port] = {}
    for (node_id, net), port_number in chosen.items():
        node = graph.nodes.get(node_id)
        if node is None:
            continue
        try:
            resolved[(node_id, net)] = node.port(port_number)
        except KeyError:
            continue
    return resolved


def _proxy(
    graph: SchematicGraph,
    ports: dict[tuple[str, str], Port],
    neighbor: str,
    net: str,
    pos: int,
) -> float:
    """Absolute y-proxy of a neighbor endpoint in the fixed layer."""
    node = graph.nodes.get(neighbor)
    if node is None or node.kind == NodeKind.VIRTUAL:
        return float(pos)
    port = ports.get((neighbor, net))
    if port is None:
        return float(pos)
    on_side = sum(1 for p in node.ports if p.side == port.side)
    return pos + (port.index / max(1, on_side)) * 0.5


def _reorder_layer(
    graph: SchematicGraph,
    ports: dict[tuple[str, str], Port],
    adjacency: dict[str, list[tuple[str, str]]],
    order: list[list[str]],
    rank: int,
    fixed: int,
) -> None:
    """Reorder ``order[rank]`` in place against fixed layer ``order[fixed]``."""
    pos_fixed = {node_id: i for i, node_id in enumerate(order[fixed])}
    keyed: list[tuple[float, int, str]] = []
    for prev_index, node_id in enumerate(order[rank]):
        proxies = [
            _proxy(graph, ports, nb, net, pos_fixed[nb])
            for nb, net in adjacency.get(node_id, [])
            if nb in pos_fixed
        ]
        bary = sum(proxies) / len(proxies) if proxies else float(prev_index)
        keyed.append((bary, prev_index, node_id))
    keyed.sort()
    order[rank] = [node_id for _, _, node_id in keyed]


def minimize(graph: SchematicGraph, ranking: Ranking) -> Ordering:
    """Minimize crossings with alternating port-aware barycenter sweeps.

    Pure function of its inputs: no RNG, stable sorts only, ties broken
    by (previous index, node id). ``ranking`` is not mutated.
    """
    order = [list(layer) for layer in ranking.ranks]
    ports = _net_ports(graph)
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for net, u, v in ranking.segments:
        adjacency.setdefault(u, []).append((v, net))
        adjacency.setdefault(v, []).append((u, net))

    best = count_crossings(graph, ranking, order)
    best_order = [list(layer) for layer in order]
    stale = 0
    for sweep in range(MAX_SWEEPS):
        if sweep % 2 == 0:  # down: use rank-1 as fixed
            for rank in range(1, len(order)):
                _reorder_layer(graph, ports, adjacency, order, rank, rank - 1)
        else:  # up: use rank+1 as fixed
            for rank in range(len(order) - 2, -1, -1):
                _reorder_layer(graph, ports, adjacency, order, rank, rank + 1)
        crossings = count_crossings(graph, ranking, order)
        if crossings < best:
            best = crossings
            best_order = [list(layer) for layer in order]
            stale = 0
        elif crossings == best:
            best_order = [list(layer) for layer in order]
            stale += 1
        else:
            stale += 1
        if best == 0 or stale >= 2:
            break
    return Ordering(order=best_order, crossings=best)
