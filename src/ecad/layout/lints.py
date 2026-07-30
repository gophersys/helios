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
