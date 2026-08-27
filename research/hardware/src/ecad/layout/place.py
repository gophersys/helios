"""place — coordinate assignment stage of the schematic layout engine.

Turns a ranked + ordered :class:`~.ir.SchematicGraph` into concrete
schematic-space positions (:class:`~.ir.Placement`).  Pure function of its
inputs, fully deterministic, every emitted coordinate snapped to GRID.

X — columns
-----------
Each rank becomes a column, which may be split into SUB-COLUMNS when its
stack would run past ``wrap_height`` (see :func:`_wrap_rank`); only nodes
with no routed edge are moved.  ``col_width[r]`` spans the whole wrapped
rank, sub-columns separated by ``WRAP_GAP``.  Between adjacent ranks a wiring
channel is reserved, sized from the number of proper 1-rank segments crossing
that gap::

    channel_width = clamp((tracks + 2) * PIN_PITCH, 12.7, 63.5)

``col_x[0] = 25.4`` and columns accumulate left-to-right.  Nodes are centred
horizontally within their sub-column.  ``channel_x[r]`` records the (left,
right) bounds of the gap between ranks r and r+1 for the router.

Y — Sander priority/median refinement
-------------------------------------
Nodes are first stacked top-to-bottom in ordering order starting at 25.4,
separated by ``MIN_GAP`` (pin pitch + text margin).  Two refinement sweeps
follow over each rank's FIRST sub-column: down (ranks left-to-right, each
node targeting its west neighbours) then up (right-to-left, targeting east
neighbours).  Within a sub-column, nodes
move in priority order — virtual nodes first (so long edges straighten),
then by incident-segment count descending, ties broken by node id.  The
target is the mean over sweep-side segments of ``neighbour port absolute y
- own port relative dy`` (virtual endpoints use port offset (0, 0)).  A move
is clamped so that MIN_GAP to already-finalised rank-mates is preserved,
reserving room for not-yet-final nodes sitting between.

Finally the whole drawing is translated so its top-left corner sits on
``(X_START, Y_START)``: the refinement is free to move a node above the page
origin, and nothing downstream can rescue content placed off the paper.

Satellite rows
--------------
Decoupling-cap rows are placed under their owner (owner bottom + ``SAT_GAP``),
pitched ``SAT_PITCH`` in x, each cap nominally ``SAT_SIZE``.  The row y is the
caps' CENTRE, which is how the engine consumes it.  A row that intersects any
ranked node bbox in the owner's column is pushed down in PIN_PITCH steps until
clear.  Ranked nodes are never moved for satellites.
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
#: A rank taller than this wraps into another sub-column. Before wrapping,
#: the ESP32-S3 MCU sheet was 308 mm of content in a 65 mm column — off the
#: bottom of an A3, with 80% of the sheet blank.
#:
#: Wrapping is NOT unconditionally safe, so this is a budget to try, not a
#: rule: moving a node sideways moves its net-label stub with it, and that
#: stub can land on another net's trunk wire. ``engine.layout`` therefore
#: tries :data:`WRAP_BUDGETS` in order and keeps the first that passes the
#: geometric lint, ending at ``inf`` — the unwrapped layout, which is the
#: behaviour that shipped before.
WRAP_HEIGHT = 120.0
WRAP_BUDGETS: tuple[float, ...] = (120.0, 165.0, math.inf)
WRAP_GAP = 15.24      # mm — gap between a rank's sub-columns
#: Owner bottom edge → satellite row centre. 7.62 mm left the row's shared
#: rail wire and its rail symbol's name drawn along the owner's own Value.
SAT_GAP = 12.7
#: Cap-to-cap x pitch within a satellite row. 7.62 mm packed the caps so
#: tightly that each one's value ("100nF" is ~5 mm of text) was drawn across
#: its neighbour's plates; a cap plus its fields needs ~10 mm.
SAT_PITCH = 10.16
SAT_SIZE = (5.08, 7.62)   # mm — nominal decoupling-cap bbox (w, h)
# half-height of what engine.emit actually draws BELOW a cap centre: the body
# plus the ground symbol one pin pitch under the bottom pin
SAT_BAND = SAT_SIZE[1] / 2 + PIN_PITCH


def sat_band_up(n_rails: int) -> float:
    """Height engine.emit draws ABOVE a satellite row's cap centres.

    One row may decouple several rails, and emit gives each rail its OWN
    horizontal track stepped by one pin pitch above the cap top pins. A
    fixed band only ever matched a single-rail row: with two rails the
    upper track ran a pitch outside the reserved space, back through the
    pins of whatever `clear` had allowed to sit there.
    """
    return SAT_SIZE[1] / 2 + PIN_PITCH * max(1, n_rails)


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


def _wrap_rank(ids: list[str], nodes, loose: set[str],
               budget: float) -> list[list[str]]:
    """Split one rank's stack into sub-columns so it stops running off the page.

    Only ``loose`` nodes — those with no routed edge at all, i.e. a passive
    whose two ends are a power tap and a net label — may leave the first
    sub-column. Those are exactly the nodes lengthening the column without
    contributing to the left-to-right flow, and they carry no trunk wire
    that a sideways move would drag across their old neighbours.

    They do still carry a 2.54 mm label stub, which CAN land on another
    net's trunk. That is why ``budget`` is offered by the caller rather than
    fixed here: the engine tries the budgets in turn and keeps the first
    whose routing passes the geometric lint.
    """
    stacks: list[list[str]] = [[]]
    heights: list[float] = [0.0]

    def add(col: int, nid: str) -> None:
        while len(stacks) <= col:
            stacks.append([])
            heights.append(0.0)
        heights[col] += nodes[nid].size[1] + (MIN_GAP if stacks[col] else 0.0)
        stacks[col].append(nid)

    for nid in ids:
        if nid not in loose:
            add(0, nid)
    if heights[0] <= budget:
        # Refill the first column with loose nodes until it is full, then
        # open the next one. Ordering within a column stays the rank order.
        col = 0
        for nid in ids:
            if nid not in loose:
                continue
            need = nodes[nid].size[1] + (MIN_GAP if stacks[col] else 0.0)
            if stacks[col] and heights[col] + need > budget:
                col += 1
            add(col, nid)
    else:
        for nid in ids:                 # column 0 is already over budget
            if nid in loose:
                add(0, nid)
    # Restore rank order inside each column (add() above preserves it).
    return [s for s in stacks if s]


def coordinates(
    graph: SchematicGraph, ranking: Ranking, ordering: Ordering,
    wrap_height: float = WRAP_HEIGHT,
) -> Placement:
    """Assign snapped schematic-space coordinates (see module docstring)."""
    ranks = ordering.order
    n = len(ranks)
    nodes = graph.nodes
    rank_of = ranking.rank_of

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

    # ── sub-columns: keep a rank from growing past the page ─────────────────
    loose = {nid for ids in ranks for nid in ids if not incident[nid]}
    sub_cols: list[list[list[str]]] = [
        _wrap_rank(ids, nodes, loose, wrap_height) for ids in ranks]

    # ── columns: widths, channels, x origins ────────────────────────────────
    sub_width: list[list[float]] = []
    col_width: list[float] = []
    for cols in sub_cols:
        widths = [
            max((nodes[i].size[0] for i in col
                 if nodes[i].kind is not NodeKind.VIRTUAL), default=0.0)
            for col in cols
        ]
        sub_width.append(widths)
        span = sum(widths) + WRAP_GAP * max(len(widths) - 1, 0)
        col_width.append(span)

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
    for r, cols in enumerate(sub_cols):
        left = col_x_raw[r]
        for j, col in enumerate(cols):
            for nid in col:
                xs[nid] = snap(
                    left + (sub_width[r][j] - nodes[nid].size[0]) / 2.0)
            left += sub_width[r][j] + WRAP_GAP

    # ── initial y: stack each sub-column in ordering order ──────────────────
    ys: dict[str, float] = {}
    for cols in sub_cols:
        for col in cols:
            y = Y_START
            for nid in col:
                ys[nid] = snap(y)
                y = ys[nid] + nodes[nid].size[1] + MIN_GAP

    def prio_key(nid: str) -> tuple[int, int, str]:
        virt = nodes[nid].kind is NodeKind.VIRTUAL
        return (0 if virt else 1, -len(incident[nid]), nid)

    def refine(r: int, nbr: int) -> None:
        """One Sander pass over rank r, targeting neighbours in rank nbr.

        Only the rank's FIRST sub-column: everything wrapped into a later one
        is loose by construction, has no neighbour to align to, and would
        otherwise act as a phantom wall on nodes it no longer shares a
        column with.
        """
        ids = sub_cols[r][0]
        pos = {nid: i for i, nid in enumerate(ids)}

        def sweep_targets(nid: str) -> list[float]:
            return [
                ys[o] + port_dy.get((net, o), 0.0) - port_dy.get((net, nid), 0.0)
                for net, o in incident[nid]
                if rank_of[o] == nbr
            ]

        # A node with no neighbour in the swept rank is never repositioned,
        # so it is a WALL from the start: the bound scans below only stop at
        # nodes already in `final`, and without seeding them the first node
        # refined in a rank lands straight on top of a rank-mate that will
        # never move away.
        final: set[str] = {nid for nid in ids if not sweep_targets(nid)}
        for nid in sorted(ids, key=prio_key):
            own = pos[nid]
            targets = sweep_targets(nid)
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

    # ── normalise: the drawing starts at the top-left of the frame ──────────
    # The y refinement sweeps are free to move a node above Y_START, and on
    # the ESP32-S3 MCU sheet they moved two of them 12.7 mm ABOVE the page
    # origin — off the top of the paper, where no page size can rescue them.
    # Shifting every origin by one constant preserves relative geometry
    # exactly (routing is computed from these origins afterwards), so this
    # cannot change a single connection.
    if xs and ys:
        dx = X_START - min(xs.values())
        dy = Y_START - min(ys.values())
        if dx or dy:
            for nid in xs:
                xs[nid] = snap(xs[nid] + dx)
                ys[nid] = snap(ys[nid] + dy)
            col_x = [snap(v + dx) for v in col_x]
            col_x_raw = [v + dx for v in col_x_raw]
            channel_x = [(snap(a + dx), snap(b + dx)) for a, b in channel_x]

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
        band_up = sat_band_up(len({c.rail for c in caps if c.rail}))

        def clear(y: float, ox: float = ox, row_w: float = row_w,
                  band_up: float = band_up) -> bool:
            # `y` is the cap CENTRE (that is what engine.emit places the
            # symbol at), and the emitted row is taller than the cap body:
            # one rail wire per rail above the top pin, stepped a pin pitch
            # apart, and the ground symbol one pitch below the bottom pin.
            # Reserving only the body left the rail stub running through the
            # pins of the node above — a signal pin silently tied to the rail.
            band = (ox, y - band_up, row_w, band_up + SAT_BAND)
            for nid in rank_ids:
                nx, ny = origin[nid]
                nw, nh = nodes[nid].size
                # nodes carry power stubs one pitch outside their bbox
                if _overlaps(band, (nx - PIN_PITCH, ny - PIN_PITCH,
                                    nw + 2 * PIN_PITCH, nh + 2 * PIN_PITCH)):
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
