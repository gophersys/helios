"""Tests for src.ecad.layout.route — orthogonal channel routing.

All fixtures are tiny synthetic SchematicGraphs built in code; the router
is deterministic so asserts are exact golden values.

Standard scene: two 10.16-wide columns at x=0 and x=25.4 with one channel
(10.16, 25.4) between them. All port offsets are GRID multiples.
"""

import pytest

from src.ecad.layout.ir import (
    GRID,
    NetEdge,
    Node,
    NodeKind,
    Ordering,
    Placement,
    Port,
    Ranking,
    SchematicGraph,
    Wire,
    snap,
)
from src.ecad.layout.route import route
from src.ecad.symbol import Side

W = 10.16  # node width
CH = (10.16, 25.4)  # the single channel of the standard 2-column scene


# ── fixture builders ────────────────────────────────────────────────────────


def _mk_node(nid, left=(), right=(), size=(W, W)):
    """Node with ports given as (number, dy) or (number, dy, role) tuples."""
    ports = []
    for side, off_x, specs in ((Side.LEFT, 0.0, left), (Side.RIGHT, size[0], right)):
        for i, spec in enumerate(specs):
            num, dy = spec[0], spec[1]
            role = spec[2] if len(spec) > 2 else "passive"
            ports.append(
                Port(number=num, name=num, role=role, side=side, index=i,
                     offset=(off_x, dy))
            )
    return Node(id=nid, kind=NodeKind.IC_UNIT, ref=nid, unit=1,
                lib_id="test:SYM", size=size, ports=ports)


def _scene(nodes, ranks, origins, edges, segments=()):
    """Assemble (graph, ranking, ordering, placement) for <= 2 ranks."""
    graph = SchematicGraph(
        sheet="s", nodes={n.id: n for n in nodes}, edges=edges,
        satellites={}, hier_ports=[],
    )
    rank_of = {nid: r for r, ids in enumerate(ranks) for nid in ids}
    ranking = Ranking(rank_of=rank_of, ranks=[list(r) for r in ranks],
                      segments=list(segments))
    ordering = Ordering(order=[list(r) for r in ranks], crossings=0)
    placement = Placement(
        origin=dict(origins),
        col_x=[0.0, 25.4][: len(ranks)],
        col_width=[W] * len(ranks),
        channel_x=[CH] if len(ranks) > 1 else [],
        sat_rows={},
    )
    return graph, ranking, ordering, placement


def _facing_scene(net="NA", named=False, a_role="passive"):
    """A.1 (right, y=5.08) facing B.1 (left, y=5.08) across the channel."""
    a = _mk_node("A", right=[("1", 5.08, a_role)])
    b = _mk_node("B", left=[("1", 5.08)])
    edge = NetEdge(net=net, named=named, ports=[("A", "1"), ("B", "1")])
    return _scene([a, b], [["A"], ["B"]], {"A": (0.0, 0.0), "B": (25.4, 0.0)},
                  [edge], segments=[(net, "A", "B")])


def _bus_scene():
    """Three 2-port nets in group BUS, port ys interleaved (no straights)."""
    a = _mk_node("A", right=[("1", 2.54), ("2", 7.62), ("3", 12.7)],
                 size=(W, 15.24))
    b = _mk_node("B", left=[("1", 5.08), ("2", 10.16), ("3", 15.24)],
                 size=(W, 17.78))
    edges = [
        NetEdge(net=f"G{k}", named=False, group="BUS",
                ports=[("A", str(k + 1)), ("B", str(k + 1))])
        for k in range(3)
    ]
    return _scene([a, b], [["A"], ["B"]], {"A": (0.0, 0.0), "B": (25.4, 0.0)},
                  edges)


def _over_node_scene():
    """Same-rank net: A right port (direct) + B LEFT port (routes over B)."""
    a = _mk_node("A", right=[("1", 2.54)])
    b = _mk_node("B", left=[("1", 2.54)])
    c = _mk_node("C")  # rank-1 dummy so a channel exists
    edge = NetEdge(net="OV", named=False, ports=[("A", "1"), ("B", "1")])
    return _scene([a, b, c], [["A", "B"], ["C"]],
                  {"A": (0.0, 0.0), "B": (0.0, 15.24), "C": (25.4, 0.0)},
                  [edge])


# ── routed geometry ─────────────────────────────────────────────────────────


def test_facing_aligned_ports_single_straight_wire():
    routing = route(*_facing_scene())
    assert routing.wires == {"NA": [Wire(10.16, 5.08, 25.4, 5.08)]}
    assert routing.junctions == {}
    assert routing.bends == 0
    assert routing.labeled_nets == []
    assert routing.label_at == {}
    assert routing.total_length == pytest.approx(15.24)


def test_three_pin_net_trunk_one_junction():
    a = _mk_node("A", right=[("1", 2.54)])
    b = _mk_node("B", right=[("1", 2.54)])
    c = _mk_node("C", left=[("1", 2.54)])
    edge = NetEdge(net="N3", named=False,
                   ports=[("A", "1"), ("B", "1"), ("C", "1")])
    routing = route(*_scene(
        [a, b, c], [["A", "B"], ["C"]],
        {"A": (0.0, 0.0), "B": (0.0, 15.24), "C": (25.4, 5.08)}, [edge]))
    # single net -> single track at channel midpoint x = 17.78
    assert routing.wires["N3"] == [
        Wire(10.16, 2.54, 17.78, 2.54),   # A stub
        Wire(10.16, 17.78, 17.78, 17.78),  # B stub
        Wire(25.4, 7.62, 17.78, 7.62),     # C stub
        Wire(17.78, 2.54, 17.78, 17.78),   # trunk
    ]
    assert routing.junctions == {"N3": [(17.78, 7.62)]}  # C's T into the trunk
    assert routing.bends == 2  # corners at both trunk ends


def test_same_rank_net_routes_in_right_channel():
    a = _mk_node("A", right=[("1", 2.54)])
    b = _mk_node("B", right=[("1", 2.54)])
    c = _mk_node("C")  # rank-1 dummy
    edge = NetEdge(net="SR", named=False, ports=[("A", "1"), ("B", "1")])
    routing = route(*_scene(
        [a, b, c], [["A", "B"], ["C"]],
        {"A": (0.0, 0.0), "B": (0.0, 15.24), "C": (25.4, 0.0)}, [edge]))
    trunk = [w for w in routing.wires["SR"] if w.x1 == w.x2]
    assert trunk == [Wire(17.78, 2.54, 17.78, 17.78)]
    assert CH[0] < trunk[0].x1 < CH[1]  # trunk inside the RIGHT channel
    assert routing.bends == 2


def test_same_rank_net_at_rightmost_rank_uses_left_channel():
    x = _mk_node("X")  # rank-0 dummy
    d = _mk_node("D", left=[("1", 2.54)])
    e = _mk_node("E", left=[("1", 2.54)])
    edge = NetEdge(net="SL", named=False, ports=[("D", "1"), ("E", "1")])
    routing = route(*_scene(
        [x, d, e], [["X"], ["D", "E"]],
        {"X": (0.0, 0.0), "D": (25.4, 0.0), "E": (25.4, 15.24)}, [edge]))
    trunk = [w for w in routing.wires["SL"] if w.x1 == w.x2]
    assert trunk == [Wire(17.78, 2.54, 17.78, 17.78)]
    assert CH[0] < trunk[0].x1 < CH[1]  # left channel of rank 1


def test_far_side_port_routes_over_its_node():
    routing = route(*_over_node_scene())
    # B's LEFT port escapes -x, climbs over B (top - GRID: escape tracks
    # step by one grid so several fit in the free band), then heads to the
    # trunk at x=17.78; A's stub is direct.
    assert routing.wires["OV"] == [
        Wire(10.16, 2.54, 17.78, 2.54),    # A direct stub
        Wire(0.0, 17.78, -2.54, 17.78),    # B escape stub
        Wire(-2.54, 17.78, -2.54, 13.97),  # up over B (origin y - GRID)
        Wire(-2.54, 13.97, 17.78, 13.97),  # across to trunk
        Wire(17.78, 2.54, 17.78, 13.97),   # trunk
    ]
    assert routing.bends == 4  # 2 on the over-route + 2 trunk corners
    assert routing.junctions == {}


# ── label policy ────────────────────────────────────────────────────────────


def test_fanout_six_net_falls_back_to_labels():
    ys = [2.54, 5.08, 7.62]
    a = _mk_node("A", right=[(str(i + 1), y) for i, y in enumerate(ys)])
    b = _mk_node("B", left=[(str(i + 1), y) for i, y in enumerate(ys)])
    edge = NetEdge(net="BIG", named=False,
                   ports=[("A", n) for n in "123"] + [("B", n) for n in "123"])
    routing = route(*_scene([a, b], [["A"], ["B"]],
                            {"A": (0.0, 0.0), "B": (25.4, 0.0)}, [edge]))
    assert routing.labeled_nets == ["BIG"]
    # one label per port: right-side stubs +x angle 0, left-side -x angle 180
    assert routing.label_at["BIG"] == [
        ("A", 12.7, 2.54, 0), ("A", 12.7, 5.08, 0), ("A", 12.7, 7.62, 0),
        ("B", 22.86, 2.54, 180), ("B", 22.86, 5.08, 180),
        ("B", 22.86, 7.62, 180),
    ]
    # and the matching 2.54-long stub wires
    assert routing.wires["BIG"] == [
        Wire(10.16, 2.54, 12.7, 2.54), Wire(10.16, 5.08, 12.7, 5.08),
        Wire(10.16, 7.62, 12.7, 7.62), Wire(25.4, 2.54, 22.86, 2.54),
        Wire(25.4, 5.08, 22.86, 5.08), Wire(25.4, 7.62, 22.86, 7.62),
    ]
    assert routing.bends == 0
    assert routing.total_length == pytest.approx(6 * 2.54)


def test_backward_segment_net_falls_back_to_labels():
    graph, ranking, ordering, placement = _facing_scene(net="NB")
    ranking.segments = [("NB", "B", "A")]  # rank 1 -> rank 0: backward
    routing = route(graph, ranking, ordering, placement)
    assert routing.labeled_nets == ["NB"]
    assert routing.label_at["NB"] == [
        ("A", 12.7, 5.08, 0), ("B", 22.86, 5.08, 180)]
    assert len(routing.wires["NB"]) == 2  # stubs only, no trunk


def test_preset_use_labels_respected():
    graph, ranking, ordering, placement = _facing_scene(net="NP")
    graph.edges[0].use_labels = True
    routing = route(graph, ranking, ordering, placement)
    assert routing.labeled_nets == ["NP"]


def test_named_routed_net_gets_one_driver_label():
    routing = route(*_facing_scene(net="NN", named=True, a_role="output"))
    assert routing.labeled_nets == []  # routed, not label-fallback
    assert routing.label_at == {"NN": [("A", 12.7, 5.08, 0)]}


# ── bus groups ──────────────────────────────────────────────────────────────


def test_bus_group_gets_contiguous_adjacent_tracks():
    routing = route(*_bus_scene())
    trunk_x = {}
    for k in range(3):
        (t,) = [w for w in routing.wires[f"G{k}"] if w.x1 == w.x2]
        trunk_x[f"G{k}"] = t.x1
    # 3 tracks in a 15.24-wide channel: x = 10.16 + (k+1) * 15.24/4, snapped
    assert trunk_x == {"G0": 13.97, "G1": 17.78, "G2": 21.59}
    # contiguous + adjacent, in block order (sorted by top y then name)
    xs = [trunk_x[f"G{k}"] for k in range(3)]
    assert xs == sorted(xs)
    assert all(b - a == pytest.approx(3.81) for a, b in zip(xs, xs[1:]))


# ── invariants ──────────────────────────────────────────────────────────────


def _all_wires(routing):
    return [w for ws in routing.wires.values() for w in ws]


def test_all_wires_orthogonal_and_snapped():
    for scene in (_bus_scene(), _over_node_scene(), _facing_scene()):
        routing = route(*scene)
        for w in _all_wires(routing):
            assert w.is_orthogonal()
            for c in (w.x1, w.y1, w.x2, w.y2):
                assert abs(snap(c) - c) < 1e-9, f"{c} off-grid"
        assert routing.total_length == pytest.approx(
            sum(abs(w.x2 - w.x1) + abs(w.y2 - w.y1) for w in _all_wires(routing))
        )


def test_interval_inflation_separates_touching_nets():
    # two independent nets whose inflated y-intervals overlap -> 2 tracks
    a = _mk_node("A", right=[("1", 2.54), ("2", 5.08)])
    b = _mk_node("B", left=[("1", 5.08), ("2", 7.62)])
    edges = [
        NetEdge(net="T1", named=False, ports=[("A", "1"), ("B", "1")]),
        NetEdge(net="T2", named=False, ports=[("A", "2"), ("B", "2")]),
    ]
    routing = route(*_scene([a, b], [["A"], ["B"]],
                            {"A": (0.0, 0.0), "B": (25.4, 0.0)}, edges))
    tx = set()
    for net in ("T1", "T2"):
        (t,) = [w for w in routing.wires[net] if w.x1 == w.x2]
        tx.add(t.x1)
    assert len(tx) == 2  # distinct tracks


def test_determinism_and_edge_order_independence():
    r1 = route(*_bus_scene())
    r2 = route(*_bus_scene())
    assert r1 == r2
    assert list(r1.wires) == list(r2.wires)
    # reversing edge insertion order must not change the result
    graph, ranking, ordering, placement = _bus_scene()
    graph.edges = list(reversed(graph.edges))
    r3 = route(graph, ranking, ordering, placement)
    assert r3 == r1
    assert list(r3.wires) == list(r1.wires)
    assert GRID == 1.27  # contract sanity


def test_escape_ladder_stops_below_the_node_above():
    """Regression: the far-side escape offset grew without bound, so the
    third track over a node ran along the bottom edge of the rank-mate
    above it — straight through that node's BOTTOM-side pin points. The
    ladder is now clamped to the free band and the overflow nets take
    labels instead."""
    from src.ecad.layout.ir import PlacedSheet
    from src.ecad.layout.lints import lint_placed

    # ABOVE sits directly over B with the standard 7.62 rank-mate gap.
    above = _mk_node("ABOVE", left=[("1", 2.54)])
    # B's ports face AWAY from the channel, so each one escapes over B
    b = _mk_node("B", right=[("1", 2.54), ("2", 3.81), ("3", 5.08),
                             ("4", 6.35)])
    srcs = [_mk_node(f"A{i}", right=[("1", 2.54)]) for i in range(1, 5)]
    edges = [
        NetEdge(net=f"E{i}", named=False,
                ports=[(f"A{i}", "1"), ("B", str(i))])
        for i in range(1, 5)
    ]
    scene = _scene(
        [*srcs, above, b], [["A1", "A2", "A3", "A4"], ["ABOVE", "B"]],
        {"A1": (0.0, 0.0), "A2": (0.0, 12.7), "A3": (0.0, 25.4),
         "A4": (0.0, 38.1), "ABOVE": (25.4, 0.0), "B": (25.4, 17.78)},
        edges)
    graph, ranking, ordering, placement = scene
    routing = route(*scene)

    # ABOVE's bbox is x 25.4..35.56, bottom y = 10.16; no wire crossing
    # that column may reach it or the power stubs hanging one pin pitch
    # under its BOTTOM pins
    for ws in routing.wires.values():
        for w in ws:
            if max(w.x1, w.x2) >= 25.4:
                assert min(w.y1, w.y2) > 10.16 + GRID, w

    placed = PlacedSheet(graph=graph, ranking=ranking, ordering=ordering,
                         placement=placement, routing=routing)
    assert lint_placed(placed) == []
    # the free band above B does not fit three tracks, so the overflow
    # falls back to labels rather than being drawn through ABOVE
    assert routing.labeled_nets
