"""Synthetic-graph tests for place.coordinates (coordinate assignment).

All fixtures are built in code; determinism makes golden asserts stable.
"""

import pytest

from src.ecad.layout.ir import (
    GRID,
    NetEdge,
    Node,
    NodeKind,
    Ordering,
    Port,
    Ranking,
    SatelliteCap,
    SchematicGraph,
)
from src.ecad.layout.place import MIN_GAP, coordinates
from src.ecad.symbol import Side


def _port(num: str, side: Side, dx: float, dy: float, index: int = 0) -> Port:
    return Port(
        number=num, name=f"P{num}", role="passive", side=side,
        index=index, offset=(dx, dy),
    )


def _node(nid: str, w: float, h: float, ports: list[Port],
          kind: NodeKind = NodeKind.IC_UNIT) -> Node:
    return Node(
        id=nid, kind=kind, ref=nid.split("#")[0], unit=1,
        lib_id="Lib:Sym", size=(w, h), ports=ports,
    )


def _graph(nodes: list[Node], edges: list[NetEdge],
           satellites: dict | None = None) -> SchematicGraph:
    return SchematicGraph(
        sheet="root", nodes={n.id: n for n in nodes}, edges=edges,
        satellites=satellites or {}, hier_ports=[],
    )


def _cap(ref: str) -> SatelliteCap:
    return SatelliteCap(ref=ref, lib_id="Device:C", value="100n",
                        rail="+3V3", gnd="GND")


def _port_abs_y(graph, placement, nid: str, pnum: str) -> float:
    return placement.origin[nid][1] + graph.nodes[nid].port(pnum).offset[1]


def _assert_no_overlap(graph, placement) -> None:
    ids = list(placement.origin)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ax, ay = placement.origin[a]
            aw, ah = graph.nodes[a].size
            bx, by = placement.origin[b]
            bw, bh = graph.nodes[b].size
            if min(aw, ah, bw, bh) <= 1e-9:   # zero-area virtuals
                continue
            hit = (ax + aw > bx + 1e-6 and bx + bw > ax + 1e-6
                   and ay + ah > by + 1e-6 and by + bh > ay + 1e-6)
            assert not hit, f"{a} overlaps {b}"


def _assert_snapped(placement) -> None:
    def ok(v: float) -> None:
        assert abs(v / GRID - round(v / GRID)) < 1e-6, f"{v} not on grid"

    for x, y in placement.origin.values():
        ok(x)
        ok(y)
    for v in placement.col_x:
        ok(v)
    for left, right in placement.channel_x:
        ok(left)
        ok(right)
    for rows in placement.sat_rows.values():
        for _ref, x, y in rows:
            ok(x)
            ok(y)


# ── fixtures ────────────────────────────────────────────────────────────────


def _chain_fixture():
    """U1 --N1--> R1 (series passive) --N2--> U2, one node per rank."""
    a = _node("U1#1", 10.16, 10.16, [_port("1", Side.RIGHT, 10.16, 5.08)])
    b = _node(
        "R1#1", 7.62, 2.54,
        [_port("1", Side.LEFT, 0.0, 1.27), _port("2", Side.RIGHT, 7.62, 1.27)],
        kind=NodeKind.PASSIVE,
    )
    c = _node("U2#1", 10.16, 10.16, [_port("1", Side.LEFT, 0.0, 5.08)])
    g = _graph([a, b, c], [
        NetEdge(net="N1", named=False, ports=[("U1#1", "1"), ("R1#1", "1")]),
        NetEdge(net="N2", named=False, ports=[("R1#1", "2"), ("U2#1", "1")]),
    ])
    rk = Ranking(
        rank_of={"U1#1": 0, "R1#1": 1, "U2#1": 2},
        ranks=[["U1#1"], ["R1#1"], ["U2#1"]],
        segments=[("N1", "U1#1", "R1#1"), ("N2", "R1#1", "U2#1")],
    )
    od = Ordering(order=[["U1#1"], ["R1#1"], ["U2#1"]], crossings=0)
    return g, rk, od


def _parallel_fixture(k: int):
    """Two ranks joined by k parallel nets (drives channel width)."""
    h = 2.54 * (k + 1)
    a = _node("U1#1", 10.16, h,
              [_port(str(i + 1), Side.RIGHT, 10.16, 2.54 * (i + 1), i)
               for i in range(k)])
    b = _node("U2#1", 10.16, h,
              [_port(str(i + 1), Side.LEFT, 0.0, 2.54 * (i + 1), i)
               for i in range(k)])
    edges = [
        NetEdge(net=f"N{i}", named=False,
                ports=[("U1#1", str(i + 1)), ("U2#1", str(i + 1))])
        for i in range(k)
    ]
    rk = Ranking(
        rank_of={"U1#1": 0, "U2#1": 1},
        ranks=[["U1#1"], ["U2#1"]],
        segments=[(f"N{i}", "U1#1", "U2#1") for i in range(k)],
    )
    od = Ordering(order=[["U1#1"], ["U2#1"]], crossings=0)
    return _graph([a, b], edges), rk, od


def _fanout_fixture(satellites: dict | None = None):
    """One driver fanning out to three sinks stacked in rank 1."""
    h = _node("U1#1", 12.7, 12.7, [
        _port("1", Side.RIGHT, 12.7, 2.54, 0),
        _port("2", Side.RIGHT, 12.7, 5.08, 1),
        _port("3", Side.RIGHT, 12.7, 7.62, 2),
    ])
    sinks = [
        _node(f"R{tag}#1", 7.62, 5.08, [_port("1", Side.LEFT, 0.0, 1.27)],
              kind=NodeKind.PASSIVE)
        for tag in ("a", "b", "c")
    ]
    edges = [
        NetEdge(net=f"N{i + 1}", named=False,
                ports=[("U1#1", str(i + 1)), (s.id, "1")])
        for i, s in enumerate(sinks)
    ]
    rk = Ranking(
        rank_of={"U1#1": 0, "Ra#1": 1, "Rb#1": 1, "Rc#1": 1},
        ranks=[["U1#1"], ["Ra#1", "Rb#1", "Rc#1"]],
        segments=[("N1", "U1#1", "Ra#1"), ("N2", "U1#1", "Rb#1"),
                  ("N3", "U1#1", "Rc#1")],
    )
    od = Ordering(order=[["U1#1"], ["Ra#1", "Rb#1", "Rc#1"]], crossings=0)
    return _graph([h] + sinks, edges, satellites), rk, od


# ── tests ───────────────────────────────────────────────────────────────────


def test_chain_aligns_pin_to_pin():
    g, rk, od = _chain_fixture()
    p = coordinates(g, rk, od)
    # The series passive is refined onto the shared pin line: all four
    # connected port ys are equal, so both nets route as straight wires.
    for nid, pnum in (("U1#1", "1"), ("R1#1", "1"), ("R1#1", "2"), ("U2#1", "1")):
        assert _port_abs_y(g, p, nid, pnum) == pytest.approx(30.48, abs=1e-6)
    assert p.origin == {
        "U1#1": (25.4, 25.4),
        "R1#1": (48.26, 29.21),
        "U2#1": (68.58, 25.4),
    }


def test_chain_columns_and_channels_golden():
    g, rk, od = _chain_fixture()
    p = coordinates(g, rk, od)
    assert p.col_width == [10.16, 7.62, 10.16]
    # 1 track per gap -> (1+2)*2.54 = 7.62, clamped up to CHANNEL_MIN 12.7.
    assert p.col_x == [25.4, 48.26, 68.58]
    assert p.channel_x == [(35.56, 48.26), (55.88, 68.58)]


def test_channel_width_scales_and_clamps():
    def width(k: int) -> float:
        p = coordinates(*_parallel_fixture(k))
        left, right = p.channel_x[0]
        return round(right - left, 4)

    assert width(1) == 12.7           # (1+2)*2.54 clamped up to the minimum
    assert width(3) == 12.7           # (3+2)*2.54 = 12.7 exactly
    assert width(8) == 25.4           # (8+2)*2.54
    assert width(30) == 63.5          # 81.28 clamped down to the maximum
    assert width(8) > width(3)


def test_fanout_min_gap_and_no_overlap():
    g, rk, od = _fanout_fixture()
    p = coordinates(g, rk, od)
    _assert_no_overlap(g, p)
    # Sinks pulled toward one driver: gaps compress exactly to MIN_GAP.
    ys = [p.origin[i][1] for i in ("Ra#1", "Rb#1", "Rc#1")]
    assert ys == [26.67, 39.37, 52.07]
    for above, below in zip(ys, ys[1:]):
        assert below - (above + 5.08) >= MIN_GAP - 1e-6
    # Up sweep centres the driver on the mean of its three sink targets.
    assert p.origin["U1#1"] == (25.4, 35.56)


def test_virtual_node_column_width_and_priority():
    """Virtuals are excluded from col_width and refined first (straighten)."""
    a = _node("U1#1", 10.16, 10.16, [
        _port("1", Side.RIGHT, 10.16, 2.54, 0),
        _port("2", Side.RIGHT, 10.16, 5.08, 1),
    ])
    b = _node("R1#1", 7.62, 2.54,
              [_port("1", Side.LEFT, 0.0, 1.27),
               _port("2", Side.RIGHT, 7.62, 1.27)],
              kind=NodeKind.PASSIVE)
    v = _node("v1", 0.0, 0.0, [], kind=NodeKind.VIRTUAL)
    c = _node("U2#1", 10.16, 10.16, [
        _port("1", Side.LEFT, 0.0, 2.54, 0),
        _port("2", Side.LEFT, 0.0, 5.08, 1),
    ])
    g = _graph([a, b, c], [
        NetEdge(net="N1", named=False,
                ports=[("U1#1", "1"), ("R1#1", "1")]),
        NetEdge(net="NB", named=False,
                ports=[("R1#1", "2"), ("U2#1", "1")]),
        NetEdge(net="N2", named=False,
                ports=[("U1#1", "2"), ("U2#1", "2")]),
    ])
    g.nodes["v1"] = v          # added by the rank stage
    rk = Ranking(
        rank_of={"U1#1": 0, "R1#1": 1, "v1": 1, "U2#1": 2},
        ranks=[["U1#1"], ["R1#1", "v1"], ["U2#1"]],
        segments=[("N1", "U1#1", "R1#1"), ("NB", "R1#1", "U2#1"),
                  ("N2", "U1#1", "v1"), ("N2", "v1", "U2#1")],
    )
    od = Ordering(order=[["U1#1"], ["R1#1", "v1"], ["U2#1"]], crossings=0)
    p = coordinates(g, rk, od)
    assert p.col_width[1] == 7.62      # virtual's zero width ignored
    # Highest priority: the virtual moved unclamped onto its east port line.
    assert p.origin["v1"][1] == pytest.approx(
        _port_abs_y(g, p, "U2#1", "2"), abs=1e-6
    )
    _assert_no_overlap(g, p)
    _assert_snapped(p)


def test_satellite_row_below_owner():
    sats = {"U1#1": [_cap("C1"), _cap("C2")]}
    u = _node("U1#1", 15.24, 10.16, [])
    g = _graph([u], [], sats)
    rk = Ranking(rank_of={"U1#1": 0}, ranks=[["U1#1"]], segments=[])
    od = Ordering(order=[["U1#1"]], crossings=0)
    p = coordinates(g, rk, od)
    # Row top = owner bottom (25.4 + 10.16) + 7.62; pitch 7.62 in x.
    assert p.sat_rows == {"U1#1": [("C1", 25.4, 43.18), ("C2", 33.02, 43.18)]}


def test_satellite_row_pushed_past_collision():
    sats = {"U1#1": [_cap("C1"), _cap("C2")]}
    u = _node("U1#1", 15.24, 10.16, [])
    v = _node("R9#1", 15.24, 10.16, [])
    g = _graph([u, v], [], sats)
    rk = Ranking(rank_of={"U1#1": 0, "R9#1": 0},
                 ranks=[["U1#1", "R9#1"]], segments=[])
    od = Ordering(order=[["U1#1", "R9#1"]], crossings=0)
    p = coordinates(g, rk, od)
    # Nominal row top 43.18 collides with R9#1 (43.18..53.34): pushed down
    # in 2.54 steps until clear of its bottom edge.
    assert p.sat_rows == {"U1#1": [("C1", 25.4, 53.34), ("C2", 33.02, 53.34)]}
    # Ranked nodes are NEVER moved to make room for satellites.
    assert p.origin["R9#1"] == (25.4, 43.18)


def test_snap_invariant_with_off_grid_sizes():
    a = _node("U1#1", 9.9, 9.0, [_port("1", Side.RIGHT, 9.9, 2.5)])
    b = _node("R1#1", 7.62, 2.54,
              [_port("1", Side.LEFT, 0.0, 1.27),
               _port("2", Side.RIGHT, 7.62, 1.27)],
              kind=NodeKind.PASSIVE)
    g = _graph([a, b],
               [NetEdge(net="N1", named=False,
                        ports=[("U1#1", "1"), ("R1#1", "1")])],
               {"U1#1": [_cap("C1")]})
    rk = Ranking(rank_of={"U1#1": 0, "R1#1": 1},
                 ranks=[["U1#1"], ["R1#1"]],
                 segments=[("N1", "U1#1", "R1#1")])
    od = Ordering(order=[["U1#1"], ["R1#1"]], crossings=0)
    p = coordinates(g, rk, od)
    _assert_snapped(p)
    _assert_no_overlap(g, p)


def test_determinism():
    p1 = coordinates(*_fanout_fixture({"U1#1": [_cap("C1"), _cap("C2")]}))
    p2 = coordinates(*_fanout_fixture({"U1#1": [_cap("C1"), _cap("C2")]}))
    assert p1.origin == p2.origin
    assert p1.col_x == p2.col_x
    assert p1.col_width == p2.col_width
    assert p1.channel_x == p2.channel_x
    assert p1.sat_rows == p2.sat_rows
