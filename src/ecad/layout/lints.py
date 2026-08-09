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

from .ir import GRID, PlacedSheet, point_on_wire, wires_short


def _on_grid(v: float) -> bool:
    return abs(v / GRID - round(v / GRID)) < 1e-6


def lint_placed(placed: PlacedSheet, emitted=None) -> list[str]:
    """IR-level geometric violations (empty list == pass).

    ``emitted`` is the :class:`~.engine.EmittedSheet` for this placement.
    Pass it whenever it is available: power-tap stubs, satellite rows and
    PWR_FLAG ties are built by ``engine.emit`` AFTER the PlacedSheet exists
    and are absent from ``placed.routing``, so without it the wire rules
    (orthogonality, grid, net-short, junction sanity) only cover the
    router's own wires — roughly half the wires in the emitted file.
    """
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

    all_wires = (emitted.wires if emitted is not None
                 else placed.routing.wires)
    all_junctions = (emitted.junctions if emitted is not None
                     else placed.routing.junctions)

    for net, segs in all_wires.items():
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
    net_wires = sorted(all_wires.items())
    for i, (net_a, segs_a) in enumerate(net_wires):
        for net_b, segs_b in net_wires[i + 1:]:
            for wa in segs_a:
                for wb in segs_b:
                    if wires_short(wa, wb, eps):
                        errors.append(
                            f"net-short: {net_a} ({wa.x1},{wa.y1})->"
                            f"({wa.x2},{wa.y2}) touches {net_b} "
                            f"({wb.x1},{wb.y1})->({wb.x2},{wb.y2})")

    # A label attaches to EVERY wire passing through its point, so a label
    # sitting on a foreign net's wire silently merges the two nets — even
    # where the wires themselves only cross (which is otherwise legal).
    for net, entries in sorted(placed.routing.label_at.items()):
        for _anchor, lx, ly, _angle in entries:
            for other, segs in sorted(all_wires.items()):
                if other == net:
                    continue
                if any(point_on_wire(lx, ly, w) for w in segs):
                    errors.append(f"label-on-foreign-wire: {net} at "
                                  f"({lx},{ly}) on net {other}")
                    break

    # junctions must touch at least two wire segments of their net
    for net, pts in all_junctions.items():
        segs = all_wires.get(net, [])
        for (jx, jy) in pts:
            touching = sum(1 for w in segs if point_on_wire(jx, jy, w))
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
    for item in getattr(sch, "graphicalItems", []) or []:
        # kiutils models `(wire ...)`/`(bus ...)` as Connection, whose
        # `.points` is a plain list[Position] — NOT a wrapper object.
        if getattr(item, "type", None) not in ("wire", "bus"):
            continue
        xy = [(p.X, p.Y) for p in (item.points or [])]
        for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
            if x1 != x2 and y1 != y2:
                errors.append(f"diagonal-wire-in-file: ({x1},{y1})->({x2},{y2})")
            for v in (x1, y1, x2, y2):
                if not _on_grid(v):
                    errors.append(f"off-grid-wire-in-file: {v}")
                    break
    return errors
