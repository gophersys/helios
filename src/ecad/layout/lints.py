"""Geometric hard gates on layout output.

Two levels:
- IR-level (`lint_placed`): node bbox overlaps, junction sanity — checked
  on the PlacedSheet before emission.
- File-level (`lint_schematic_text`): every wire orthogonal and on-grid —
  checked on the emitted .kicad_sch via vendored kiutils.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "tools"))

from .ir import GRID, PlacedSheet


def _on_grid(v: float) -> bool:
    return abs(v / GRID - round(v / GRID)) < 1e-6


def _on_segment(x: float, y: float, w, eps: float) -> bool:
    return (min(w.x1, w.x2) - eps <= x <= max(w.x1, w.x2) + eps
            and min(w.y1, w.y2) - eps <= y <= max(w.y1, w.y2) + eps)


def _wires_short(wa, wb, eps: float) -> bool:
    """True when two orthogonal wires of different nets would connect in
    KiCad: colinear overlap of positive length, or either wire's endpoint
    lying on the other wire (mid-segment + crossings do not connect)."""
    a_h, b_h = wa.y1 == wa.y2, wb.y1 == wb.y2
    if a_h == b_h:  # parallel: short iff colinear with positive overlap
        if a_h:
            if abs(wa.y1 - wb.y1) > eps:
                return False
            lo = max(min(wa.x1, wa.x2), min(wb.x1, wb.x2))
            hi = min(max(wa.x1, wa.x2), max(wb.x1, wb.x2))
        else:
            if abs(wa.x1 - wb.x1) > eps:
                return False
            lo = max(min(wa.y1, wa.y2), min(wb.y1, wb.y2))
            hi = min(max(wa.y1, wa.y2), max(wb.y1, wb.y2))
        if hi - lo > eps:
            return True
    return any(
        _on_segment(x, y, other, eps)
        for (x, y), other in (
            ((wa.x1, wa.y1), wb), ((wa.x2, wa.y2), wb),
            ((wb.x1, wb.y1), wa), ((wb.x2, wb.y2), wa),
        )
    )


def lint_placed(placed: PlacedSheet) -> list[str]:
    """IR-level geometric violations (empty list == pass)."""
    errors: list[str] = []
    g, pl = placed.graph, placed.placement

    boxes: dict[str, tuple[float, float, float, float]] = {}
    for nid, node in g.nodes.items():
        if not node.ref:
            continue
        x, y = pl.origin[nid]
        w, h = node.size
        boxes[nid] = (x, y, x + w, y + h)
    ids = sorted(boxes)
    for i, a in enumerate(ids):
        ax1, ay1, ax2, ay2 = boxes[a]
        for b in ids[i + 1:]:
            bx1, by1, bx2, by2 = boxes[b]
            if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
                errors.append(f"bbox-overlap: {a} and {b}")

    for nid, (x, y) in pl.origin.items():
        if not (_on_grid(x) and _on_grid(y)):
            errors.append(f"off-grid-origin: {nid} at ({x}, {y})")

    for net, segs in placed.routing.wires.items():
        for w in segs:
            if not w.is_orthogonal():
                errors.append(f"diagonal-wire: net {net} "
                              f"({w.x1},{w.y1})->({w.x2},{w.y2})")
            for v in (w.x1, w.y1, w.x2, w.y2):
                if not _on_grid(v):
                    errors.append(f"off-grid-wire: net {net} coordinate {v}")
                    break

    # wires of DIFFERENT nets must never short: no colinear overlap, and no
    # endpoint of one net's wire on another net's wire (KiCad connects a
    # wire end touching a segment; plain mid-segment crossings are fine)
    eps = 1e-6
    net_wires = sorted(placed.routing.wires.items())
    for i, (net_a, segs_a) in enumerate(net_wires):
        for net_b, segs_b in net_wires[i + 1:]:
            for wa in segs_a:
                for wb in segs_b:
                    if _wires_short(wa, wb, eps):
                        errors.append(
                            f"net-short: {net_a} ({wa.x1},{wa.y1})->"
                            f"({wa.x2},{wa.y2}) touches {net_b} "
                            f"({wb.x1},{wb.y1})->({wb.x2},{wb.y2})")

    # junctions must touch at least two wire segments of their net
    for net, pts in placed.routing.junctions.items():
        segs = placed.routing.wires.get(net, [])
        for (jx, jy) in pts:
            touching = sum(
                1 for w in segs
                if (min(w.x1, w.x2) - 1e-6 <= jx <= max(w.x1, w.x2) + 1e-6
                    and min(w.y1, w.y2) - 1e-6 <= jy <= max(w.y1, w.y2) + 1e-6)
            )
            if touching < 2:
                errors.append(f"floating-junction: net {net} at ({jx},{jy})")
    return errors


def lint_schematic_text(text: str) -> list[str]:
    """File-level checks via kiutils parse of the emitted schematic."""
    from kiutils.schematic import Schematic

    with tempfile.NamedTemporaryFile("w", suffix=".kicad_sch",
                                     delete=False) as f:
        f.write(text)
        path = f.name
    try:
        sch = Schematic.from_file(path)
    finally:
        Path(path).unlink(missing_ok=True)

    errors: list[str] = []
    for wire in getattr(sch, "graphicalItems", []) or []:
        pts = getattr(wire, "points", None)
        if pts is None or not hasattr(pts, "points"):
            continue
        xy = [(p.X, p.Y) for p in pts.points]
        if len(xy) == 2:
            (x1, y1), (x2, y2) = xy
            if x1 != x2 and y1 != y2:
                errors.append(f"diagonal-wire-in-file: ({x1},{y1})->({x2},{y2})")
            for v in (x1, y1, x2, y2):
                if not _on_grid(v):
                    errors.append(f"off-grid-wire-in-file: {v}")
                    break
    return errors
