"""Tests for rank.assign — deterministic layer assignment on synthetic graphs."""

from src.ecad.layout.ir import (
    HierPort,
    NetEdge,
    Node,
    NodeKind,
    Port,
    SchematicGraph,
)
from src.ecad.layout.rank import assign
from src.ecad.symbol import Side


# ── fixtures ────────────────────────────────────────────────────────────────


def _node(nid: str, roles: list[str], kind: NodeKind = NodeKind.IC_UNIT) -> Node:
    ports = [
        Port(number=str(i + 1), name=f"P{i + 1}", role=role, side=Side.LEFT,
             index=i, offset=(0.0, 2.54 * i))
        for i, role in enumerate(roles)
    ]
    return Node(id=nid, kind=kind, ref=nid, unit=1, lib_id="test:sym",
                size=(10.16, 7.62), ports=ports)


def _graph(nodes: list[Node], edges: list[NetEdge],
           hier_ports: list[HierPort] | None = None) -> SchematicGraph:
    return SchematicGraph(sheet="root", nodes={n.id: n for n in nodes},
                          edges=edges, satellites={}, hier_ports=hier_ports or [])


def _chain_graph() -> SchematicGraph:
    """A -> B -> C driven by output-role ports."""
    return _graph(
        [_node("A", ["output"]), _node("B", ["input", "output"]),
         _node("C", ["input"])],
        [NetEdge("n1", True, [("A", "1"), ("B", "1")]),
         NetEdge("n2", True, [("B", "2"), ("C", "1")])],
    )


def _span_graph() -> SchematicGraph:
    """Chain A->B->C->Z plus a direct net A->Z spanning 3 ranks."""
    return _graph(
        [_node("A", ["output", "output"]), _node("B", ["input", "output"]),
         _node("C", ["input", "output"]), _node("Z", ["input", "input"])],
        [NetEdge("n1", True, [("A", "1"), ("B", "1")]),
         NetEdge("n2", True, [("B", "2"), ("C", "1")]),
         NetEdge("n3", True, [("C", "2"), ("Z", "1")]),
         NetEdge("far", True, [("A", "2"), ("Z", "2")])],
    )


# ── tests ───────────────────────────────────────────────────────────────────


def test_simple_chain_ranks() -> None:
    ranking = assign(_chain_graph())
    assert ranking.rank_of == {"A": 0, "B": 1, "C": 2}
    assert ranking.ranks == [["A"], ["B"], ["C"]]
    assert ranking.segments == [("n1", "A", "B"), ("n2", "B", "C")]


def test_cycle_broken_deterministically() -> None:
    graph = _graph(
        [_node("A", ["output", "input"]), _node("B", ["input", "output"])],
        [NetEdge("n1", True, [("A", "1"), ("B", "1")]),
         NetEdge("n2", True, [("B", "2"), ("A", "2")])],
    )
    ranking = assign(graph)
    # Greedy FAS keeps the sorted-first vertex upstream: A stays at rank 0.
    assert ranking.rank_of == {"A": 0, "B": 1}
    assert ranking.segments == [("n1", "A", "B"), ("n2", "B", "A")]


def test_hier_input_pinned_and_output_clamped() -> None:
    graph = _graph(
        [_node("hier:IN", ["output"], NodeKind.HIER_PORT),
         _node("A", ["input", "output", "output"]),
         _node("B", ["input", "output"]), _node("C", ["input", "output"]),
         _node("D", ["input"]),
         _node("hier:OUT", ["input"], NodeKind.HIER_PORT)],
        [NetEdge("nin", True, [("hier:IN", "1"), ("A", "1")]),
         NetEdge("nab", True, [("A", "2"), ("B", "1")]),
         NetEdge("nbc", True, [("B", "2"), ("C", "1")]),
         NetEdge("ncd", True, [("C", "2"), ("D", "1")]),
         NetEdge("nout", True, [("A", "3"), ("hier:OUT", "1")])],
        hier_ports=[HierPort("IN", "input"), HierPort("OUT", "output")],
    )
    ranking = assign(graph)
    assert ranking.rank_of["hier:IN"] == 0
    assert ranking.rank_of["hier:OUT"] == 4  # clamped to max rank, not 2
    assert ranking.rank_of["D"] == 4
    # The clamp stretches nout across ranks 1..4 -> a proper virtual chain.
    assert ("nout", "A", "v:nout:A:hier:OUT:0") in ranking.segments
    assert ("nout", "v:nout:A:hier:OUT:1", "hier:OUT") in ranking.segments


def test_bidirectional_hub_drives() -> None:
    graph = _graph(
        [_node("MCU", ["bidirectional"] * 6), _node("R1", ["passive", "passive"])],
        [NetEdge("sig", True, [("R1", "1"), ("MCU", "3")])],
    )
    ranking = assign(graph)
    assert ranking.segments == [("sig", "MCU", "R1")]
    assert ranking.rank_of == {"MCU": 0, "R1": 1}


def test_multi_rank_span_creates_virtual_chain() -> None:
    graph = _span_graph()
    ranking = assign(graph)
    assert ranking.rank_of == {
        "A": 0, "B": 1, "C": 2, "Z": 3,
        "v:far:A:Z:0": 1, "v:far:A:Z:1": 2,
    }
    assert ranking.segments == [
        ("n1", "A", "B"), ("n2", "B", "C"), ("n3", "C", "Z"),
        ("far", "A", "v:far:A:Z:0"),
        ("far", "v:far:A:Z:0", "v:far:A:Z:1"),
        ("far", "v:far:A:Z:1", "Z"),
    ]
    assert ranking.ranks == [
        ["A"], ["B", "v:far:A:Z:0"], ["C", "v:far:A:Z:1"], ["Z"],
    ]
    for vid in ("v:far:A:Z:0", "v:far:A:Z:1"):
        dummy = graph.nodes[vid]
        assert dummy.kind is NodeKind.VIRTUAL
        assert dummy.size == (0.0, 0.0)
        assert dummy.ports == []


def test_use_labels_edge_contributes_nothing() -> None:
    graph = _graph(
        [_node("A", ["output"]), _node("B", ["input"])],
        [NetEdge("n1", True, [("A", "1"), ("B", "1")], use_labels=True)],
    )
    ranking = assign(graph)
    assert ranking.segments == []
    assert ranking.rank_of == {"A": 0, "B": 0}
    assert ranking.ranks == [["A", "B"]]


def test_connectors_pinned_rank0_same_rank_segment_kept() -> None:
    graph = _graph(
        [_node("J1", ["passive"], NodeKind.CONNECTOR),
         _node("J2", ["passive"], NodeKind.CONNECTOR)],
        [NetEdge("n1", True, [("J1", "1"), ("J2", "1")])],
    )
    ranking = assign(graph)
    assert ranking.rank_of == {"J1": 0, "J2": 0}
    assert ranking.segments == [("n1", "J1", "J2")]  # same-rank, no crash
    assert ranking.ranks == [["J1", "J2"]]


def test_deterministic_repeat() -> None:
    first = assign(_span_graph())
    second = assign(_span_graph())
    assert first.rank_of == second.rank_of
    assert first.ranks == second.ranks
    assert first.segments == second.segments
