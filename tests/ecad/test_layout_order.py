"""Tests for the crossing-minimization stage (src/ecad/layout/order.py).

All fixtures are tiny synthetic SchematicGraph/Ranking pairs built in
code; determinism makes exact golden asserts stable.
"""

import src.ecad.layout.order as order_mod
from src.ecad.layout.ir import (
    NetEdge,
    Node,
    NodeKind,
    Port,
    Ranking,
    SchematicGraph,
)
from src.ecad.layout.order import count_crossings, minimize
from src.ecad.symbol import Side


# ── fixture helpers ─────────────────────────────────────────────────────────


def _node(node_id: str, left: int = 0, right: int = 0) -> Node:
    """Node with `left` ports numbered 1..left and `right` ports after."""
    ports: list[Port] = []
    for i in range(left):
        ports.append(
            Port(
                number=str(i + 1),
                name=f"L{i}",
                role="passive",
                side=Side.LEFT,
                index=i,
                offset=(0.0, 2.54 * (i + 1)),
            )
        )
    for i in range(right):
        ports.append(
            Port(
                number=str(left + i + 1),
                name=f"R{i}",
                role="passive",
                side=Side.RIGHT,
                index=i,
                offset=(10.16, 2.54 * (i + 1)),
            )
        )
    return Node(
        id=node_id,
        kind=NodeKind.IC_UNIT,
        ref=node_id,
        unit=1,
        lib_id="Test:Box",
        size=(10.16, 10.16),
        ports=ports,
    )


def _vnode(node_id: str) -> Node:
    return Node(
        id=node_id,
        kind=NodeKind.VIRTUAL,
        ref=node_id,
        unit=1,
        lib_id="",
        size=(0.0, 0.0),
        ports=[],
    )


def _graph(nodes: list[Node], edges: list[NetEdge]) -> SchematicGraph:
    return SchematicGraph(
        sheet="root",
        nodes={n.id: n for n in nodes},
        edges=edges,
        satellites={},
        hier_ports=[],
    )


def _edge(net: str, *pins: tuple[str, str]) -> NetEdge:
    return NetEdge(net=net, named=True, ports=list(pins))


def _ranking(ranks: list[list[str]], segments: list[tuple[str, str, str]]) -> Ranking:
    rank_of = {n: r for r, layer in enumerate(ranks) for n in layer}
    return Ranking(rank_of=rank_of, ranks=[list(x) for x in ranks], segments=segments)


def _two_by_two() -> tuple[SchematicGraph, Ranking]:
    """a1->b2 and a2->b1: one crossing, fully resolvable."""
    nodes = [
        _node("a1", right=1),
        _node("a2", right=1),
        _node("b1", left=1),
        _node("b2", left=1),
    ]
    edges = [
        _edge("N1", ("a1", "1"), ("b2", "1")),
        _edge("N2", ("a2", "1"), ("b1", "1")),
    ]
    ranking = _ranking(
        [["a1", "a2"], ["b1", "b2"]],
        [("N1", "a1", "b2"), ("N2", "a2", "b1")],
    )
    return _graph(nodes, edges), ranking


def _k22() -> tuple[SchematicGraph, Ranking]:
    """UART-style full crossover (K2,2): 1 crossing in ANY order."""
    nodes = [
        _node("a", right=2),
        _node("b", right=2),
        _node("c", left=2),
        _node("d", left=2),
    ]
    edges = [
        _edge("TX", ("a", "1"), ("c", "1")),
        _edge("RX", ("a", "2"), ("d", "1")),
        _edge("CTS", ("b", "1"), ("c", "2")),
        _edge("RTS", ("b", "2"), ("d", "2")),
    ]
    ranking = _ranking(
        [["a", "b"], ["c", "d"]],
        [
            ("TX", "a", "c"),
            ("RX", "a", "d"),
            ("CTS", "b", "c"),
            ("RTS", "b", "d"),
        ],
    )
    return _graph(nodes, edges), ranking


def _reversal_chain() -> tuple[SchematicGraph, Ranking]:
    """4 ranks of 3; each gap fully reverses order: 9 initial crossings."""
    nodes: list[Node] = []
    ranks: list[list[str]] = []
    for r in range(4):
        layer = [f"a{r}", f"b{r}", f"c{r}"]
        ranks.append(layer)
        nodes.extend(_node(n, left=1, right=1) for n in layer)
    edges: list[NetEdge] = []
    segments: list[tuple[str, str, str]] = []
    for r in range(3):
        for src, dst in (
            (f"a{r}", f"c{r + 1}"),
            (f"b{r}", f"b{r + 1}"),
            (f"c{r}", f"a{r + 1}"),
        ):
            net = f"G{r}_{src}_{dst}"
            edges.append(_edge(net, (src, "2"), (dst, "1")))
            segments.append((net, src, dst))
    return _graph(nodes, edges), _ranking(ranks, segments)


# ── count_crossings ─────────────────────────────────────────────────────────


def test_count_crossings_basic():
    graph, ranking = _two_by_two()
    assert count_crossings(graph, ranking, [["a1", "a2"], ["b1", "b2"]]) == 1
    assert count_crossings(graph, ranking, [["a1", "a2"], ["b2", "b1"]]) == 0


def test_count_crossings_ignores_same_rank_segments():
    graph, ranking = _two_by_two()
    ranking.segments.append(("SR", "a1", "a2"))  # same-rank: never counted
    assert count_crossings(graph, ranking, ranking.ranks) == 1


def test_count_crossings_reversal_chain():
    graph, ranking = _reversal_chain()
    assert count_crossings(graph, ranking, ranking.ranks) == 9


# ── minimize ────────────────────────────────────────────────────────────────


def test_two_by_two_cross_resolves_to_zero():
    graph, ranking = _two_by_two()
    result = minimize(graph, ranking)
    assert result.order == [["a1", "a2"], ["b2", "b1"]]
    assert result.crossings == 0


def test_irreducible_uart_crossover_stays_one():
    graph, ranking = _k22()
    result = minimize(graph, ranking)
    assert result.crossings == 1
    assert result.order == [["a", "b"], ["c", "d"]]  # ties keep input order


def test_isolated_node_keeps_position():
    nodes = [
        _node("p", right=1),
        _node("q", right=1),
        _node("x", left=1),
        _node("iso"),  # no ports, no edges
        _node("y", left=1),
    ]
    edges = [
        _edge("NP", ("p", "1"), ("x", "1")),
        _edge("NQ", ("q", "1"), ("y", "1")),
    ]
    ranking = _ranking(
        [["p", "q"], ["x", "iso", "y"]],
        [("NP", "p", "x"), ("NQ", "q", "y")],
    )
    result = minimize(_graph(nodes, edges), ranking)
    assert result.order == [["p", "q"], ["x", "iso", "y"]]
    assert result.crossings == 0


def test_port_aware_barycenter_orders_by_port_index():
    """Both free nodes attach to the same fixed node; the one wired to the
    lower port index (higher on the symbol) must come first."""
    nodes = [_node("hub", right=2), _node("n1", left=1), _node("n2", left=1)]
    edges = [
        _edge("A", ("hub", "2"), ("n1", "1")),  # hub right port index 1
        _edge("B", ("hub", "1"), ("n2", "1")),  # hub right port index 0
    ]
    ranking = _ranking(
        [["hub"], ["n1", "n2"]],
        [("A", "hub", "n1"), ("B", "hub", "n2")],
    )
    result = minimize(_graph(nodes, edges), ranking)
    assert result.order == [["hub"], ["n2", "n1"]]
    assert result.crossings == 0


def test_virtual_node_uses_bare_position_index():
    nodes = [
        _vnode("v1"),
        _node("big", right=2),
        _node("m1", left=1),
        _node("m2", left=1),
    ]
    edges = [
        _edge("L", ("m1", "1")),  # v1 is a dummy: no port entry for it
        _edge("M", ("big", "1"), ("m2", "1")),
    ]
    ranking = _ranking(
        [["v1", "big"], ["m2", "m1"]],
        [("L", "v1", "m1"), ("M", "big", "m2")],
    )
    result = minimize(_graph(nodes, edges), ranking)
    assert result.order == [["v1", "big"], ["m1", "m2"]]
    assert result.crossings == 0


def test_determinism_and_no_input_mutation():
    graph, ranking = _reversal_chain()
    ranks_before = [list(x) for x in ranking.ranks]
    first = minimize(graph, ranking)
    second = minimize(graph, ranking)
    assert first.order == second.order
    assert first.crossings == second.crossings
    assert ranking.ranks == ranks_before  # minimize must not mutate input
    graph2, ranking2 = _reversal_chain()
    third = minimize(graph2, ranking2)
    assert third.order == first.order


def test_sweep_cap_and_monotonic_accepted_crossings(monkeypatch):
    graph, ranking = _reversal_chain()
    real = order_mod.count_crossings
    seen: list[int] = []

    def spy(g, r, o):
        c = real(g, r, o)
        seen.append(c)
        return c

    monkeypatch.setattr(order_mod, "count_crossings", spy)
    result = order_mod.minimize(graph, ranking)  # must terminate
    # one initial count + at most MAX_SWEEPS per-sweep counts
    assert len(seen) <= 1 + order_mod.MAX_SWEEPS
    # accepted (running-best) crossings are monotonically non-increasing
    running = seen[0]
    accepted = [running]
    for c in seen[1:]:
        if c <= running:
            running = c
            accepted.append(c)
    assert all(a >= b for a, b in zip(accepted, accepted[1:]))
    assert result.crossings == min(seen)
    assert result.crossings <= seen[0]
    # reported metric matches the returned order
    assert result.crossings == real(graph, ranking, result.order)
