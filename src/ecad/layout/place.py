"""place — coordinate assignment stage of the schematic layout engine.

Turns a ranked + ordered :class:`~.ir.SchematicGraph` into concrete
schematic-space positions (:class:`~.ir.Placement`).  Pure function of its
inputs, fully deterministic, every emitted coordinate snapped to GRID.

X — columns
-----------
Each rank becomes a column.  ``col_width[r]`` is the widest non-virtual node
in rank ``r`` (0.0 when the rank is empty or virtual-only).  Between adjacent
ranks a wiring channel is reserved, sized from the number of proper 1-rank
segments crossing that gap::

    channel_width = clamp((tracks + 2) * PIN_PITCH, 12.7, 63.5)

``col_x[0] = 25.4`` and columns accumulate left-to-right.  Nodes are centred
horizontally within their column.  ``channel_x[r]`` records the (left, right)
bounds of the gap between ranks r and r+1 for the router.

Y — Sander priority/median refinement
-------------------------------------
Nodes are first stacked top-to-bottom in ordering order starting at 25.4,
separated by ``MIN_GAP`` (pin pitch + text margin).  Two refinement sweeps
follow: down (ranks left-to-right, each node targeting its west neighbours)
then up (right-to-left, targeting east neighbours).  Within a rank, nodes
move in priority order — virtual nodes first (so long edges straighten),
then by incident-segment count descending, ties broken by node id.  The
target is the mean over sweep-side segments of ``neighbour port absolute y
- own port relative dy`` (virtual endpoints use port offset (0, 0)).  A move
is clamped so that MIN_GAP to already-finalised rank-mates is preserved,
reserving room for not-yet-final nodes sitting between.

Satellite rows
--------------
Decoupling-cap rows are placed under their owner (owner bottom + 7.62),
pitched 7.62 in x, each cap nominally 5.08 x 7.62.  A row that intersects
any ranked node bbox in the owner's column is pushed down in PIN_PITCH
steps until clear.  Ranked nodes are never moved for satellites.
"""

from __future__ import annotations

import math

from .ir import (
    GRID,
    PIN_PITCH,
    NodeKind,
    Ordering,
    Placement,
    Ranking,
    SchematicGraph,
    snap,
)

X_START = 25.4        # mm — left edge of the first column
Y_START = 25.4        # mm — top of every initial rank stack
MIN_GAP = max(PIN_PITCH, 2 * GRID) + 5.08   # vertical node gap incl. text margin
CHANNEL_MIN = 12.7    # mm — narrowest inter-rank wiring channel
CHANNEL_MAX = 63.5    # mm — widest inter-rank wiring channel
SAT_GAP = 7.62        # mm — owner bottom edge → satellite row top
SAT_PITCH = 7.62      # mm — cap-to-cap x pitch within a row
SAT_SIZE = (5.08, 7.62)   # mm — nominal decoupling-cap bbox (w, h)


def _grid_up(v: float) -> float:
    """Smallest grid multiple >= v (tolerant of float fuzz)."""
    return round(math.ceil(v / GRID - 1e-9) * GRID, 4)


def _grid_down(v: float) -> float:
    """Largest grid multiple <= v (tolerant of float fuzz)."""
    return round(math.floor(v / GRID + 1e-9) * GRID, 4)


def _overlaps(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    eps: float = 1e-6,
) -> bool:
    """Strict bbox intersection; zero-area boxes (virtuals) never overlap."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= eps or ah <= eps or bw <= eps or bh <= eps:
        return False
    return (
        ax + aw > bx + eps
        and bx + bw > ax + eps
        and ay + ah > by + eps
        and by + bh > ay + eps
    )


def coordinates(
    graph: SchematicGraph, ranking: Ranking, ordering: Ordering
) -> Placement:
    """Assign snapped schematic-space coordinates (see module docstring)."""
    ranks = ordering.order
    n = len(ranks)
    nodes = graph.nodes
    rank_of = ranking.rank_of

    # ── columns: widths, channels, x origins ────────────────────────────────
    col_width: list[float] = []
    for ids in ranks:
        widths = [
            nodes[i].size[0] for i in ids if nodes[i].kind is not NodeKind.VIRTUAL
        ]
        col_width.append(max(widths, default=0.0))

    tracks = [0] * max(n - 1, 0)
    for _net, a, b in ranking.segments:
        lo = min(rank_of[a], rank_of[b])
        if abs(rank_of[a] - rank_of[b]) == 1 and 0 <= lo < n - 1:
            tracks[lo] += 1

    col_x_raw: list[float] = [X_START] if n else []
    for r in range(n - 1):
        chan = min(max((tracks[r] + 2) * PIN_PITCH, CHANNEL_MIN), CHANNEL_MAX)
        col_x_raw.append(col_x_raw[r] + col_width[r] + chan)
    col_x = [snap(v) for v in col_x_raw]
    channel_x = [
        (snap(col_x_raw[r] + col_width[r]), col_x[r + 1]) for r in range(n - 1)
    ]

    xs: dict[str, float] = {}
    for r, ids in enumerate(ranks):
        for nid in ids:
            xs[nid] = snap(col_x_raw[r] + (col_width[r] - nodes[nid].size[0]) / 2.0)

    # ── initial y: stack each rank in ordering order ────────────────────────
    ys: dict[str, float] = {}
    for ids in ranks:
        y = Y_START
        for nid in ids:
            ys[nid] = snap(y)
            y = ys[nid] + nodes[nid].size[1] + MIN_GAP

    # ── incidence + port-dy lookup for refinement ───────────────────────────
    port_dy: dict[tuple[str, str], float] = {}
    for edge in graph.edges:
        for nid, pnum in edge.ports:
            key = (edge.net, nid)
            if key not in port_dy and nid in nodes:
                port_dy[key] = nodes[nid].port(pnum).offset[1]

    incident: dict[str, list[tuple[str, str]]] = {i: [] for ids in ranks for i in ids}
    for net, a, b in ranking.segments:
        incident[a].append((net, b))
        incident[b].append((net, a))

    def prio_key(nid: str) -> tuple[int, int, str]:
        virt = nodes[nid].kind is NodeKind.VIRTUAL
        return (0 if virt else 1, -len(incident[nid]), nid)

    def refine(r: int, nbr: int) -> None:
        """One Sander pass over rank r, targeting neighbours in rank nbr."""
        ids = ranks[r]
        pos = {nid: i for i, nid in enumerate(ids)}
        final: set[str] = set()
        for nid in sorted(ids, key=prio_key):
            own = pos[nid]
            targets = [
                ys[o] + port_dy.get((net, o), 0.0) - port_dy.get((net, nid), 0.0)
                for net, o in incident[nid]
                if rank_of[o] == nbr
            ]
            if targets:
                lb, ub = -math.inf, math.inf
                need = 0.0
                for j in range(own - 1, -1, -1):  # nearest final node above
                    m = ids[j]
                    if m in final:
                        lb = ys[m] + nodes[m].size[1] + MIN_GAP + need
                        break
                    need += nodes[m].size[1] + MIN_GAP
                need = 0.0
                for j in range(own + 1, len(ids)):  # nearest final node below
                    m = ids[j]
                    if m in final:
                        ub = ys[m] - MIN_GAP - need - nodes[nid].size[1]
                        break
                    need += nodes[m].size[1] + MIN_GAP
                y = snap(sum(targets) / len(targets))
                if ub < math.inf and y > _grid_down(ub):
                    y = _grid_down(ub)
                if lb > -math.inf and y < _grid_up(lb):
                    y = _grid_up(lb)  # upper wall wins a degenerate interval
                ys[nid] = y
            final.add(nid)

    for r in range(1, n):          # down sweep: west neighbours
        refine(r, r - 1)
    for r in range(n - 2, -1, -1):  # up sweep: east neighbours
        refine(r, r + 1)

    origin = {nid: (xs[nid], ys[nid]) for ids in ranks for nid in ids}

    # ── satellite rows (never move ranked nodes) ────────────────────────────
    sat_w, sat_h = SAT_SIZE
    sat_rows: dict[str, list[tuple[str, float, float]]] = {}
    for owner in sorted(graph.satellites):
        caps = graph.satellites[owner]
        if not caps:
            sat_rows[owner] = []
            continue
        ox, oy = origin[owner]
        row_w = (len(caps) - 1) * SAT_PITCH + sat_w
        row_y = snap(oy + nodes[owner].size[1] + SAT_GAP)
        rank_ids = ranks[rank_of[owner]]

        def clear(y: float, ox: float = ox, row_w: float = row_w) -> bool:
            for nid in rank_ids:
                nx, ny = origin[nid]
                if _overlaps((ox, y, row_w, sat_h), (nx, ny, *nodes[nid].size)):
                    return False
            return True

        while not clear(row_y):
            row_y = snap(row_y + PIN_PITCH)
        sat_rows[owner] = [
            (cap.ref, snap(ox + i * SAT_PITCH), row_y) for i, cap in enumerate(caps)
        ]

    return Placement(
        origin=origin,
        col_x=col_x,
        col_width=col_width,
        channel_x=channel_x,
        sat_rows=sat_rows,
    )
