"""Choosing the sheet a drawing is emitted on.

Nothing used to choose: every sheet was emitted as A3 regardless of what
was on it, so a 41-pin module ran 300 mm down a 297 mm page and the bottom
of the schematic simply did not exist in the PDF. Picking the SMALLEST
standard page that holds the content fixes both halves of that: content
never leaves the sheet, and a drawing is no longer marooned in the corner
of a page four times its size.

The usable area is the page less a 12.7 mm border on every side, and less
KiCad's title block, which occupies a fixed rectangle in the bottom-right
corner of every standard drawing sheet. A drawing that runs under the title
block is as unreadable as one that runs off the paper, so the fit test
treats that rectangle as unusable too.

When nothing fits, :func:`fit_page` says so — it returns the largest page
plus an ``overflow`` reason rather than silently emitting a clipped sheet.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Standard ISO sheets in KiCad's landscape orientation, smallest first.
#: The names are KiCad's own ``(paper "...")`` tokens.
PAGE_SIZES: tuple[tuple[str, float, float], ...] = (
    ("A4", 297.0, 210.0),
    ("A3", 420.0, 297.0),
    ("A2", 594.0, 420.0),
    ("A1", 841.0, 594.0),
    ("A0", 1189.0, 841.0),
)

MARGIN = 12.7          # mm — drawing-sheet border, all four sides
#: Title-block footprint measured from the bottom-right page corner
#: (width, height). KiCad's standard drawing sheet reserves about this much.
TITLE_BLOCK = (110.0, 40.0)


@dataclass(frozen=True)
class PageFit:
    """Which sheet a drawing goes on, and whether it actually fits."""

    name: str
    width: float
    height: float
    content: tuple[float, float, float, float]   # x0, y0, x1, y1
    overflow: str = ""                           # "" when the content fits

    @property
    def fits(self) -> bool:
        return not self.overflow

    @property
    def fill(self) -> float:
        """Fraction of the usable area the drawing covers (0..1)."""
        x0, y0, x1, y1 = self.content
        usable = ((self.width - 2 * MARGIN) * (self.height - 2 * MARGIN))
        if usable <= 0:
            return 0.0
        return round(max(0.0, (x1 - x0) * (y1 - y0)) / usable, 4)


def _clash(content: tuple[float, float, float, float],
           width: float, height: float) -> str:
    """Why ``content`` does not fit this page, or ``""`` if it does."""
    x0, y0, x1, y1 = content
    if x0 < MARGIN - 1e-6 or y0 < MARGIN - 1e-6:
        return (f"content starts at ({x0:.1f}, {y0:.1f}), inside the "
                f"{MARGIN} mm border")
    if x1 > width - MARGIN + 1e-6 or y1 > height - MARGIN + 1e-6:
        return (f"content is {x1 - x0:.1f} x {y1 - y0:.1f} mm and reaches "
                f"({x1:.1f}, {y1:.1f}); the usable area is "
                f"{width - 2 * MARGIN:.1f} x {height - 2 * MARGIN:.1f} mm")
    tb_w, tb_h = TITLE_BLOCK
    tb_x0, tb_y0 = width - MARGIN - tb_w, height - MARGIN - tb_h
    if x1 > tb_x0 and y1 > tb_y0:
        return (f"content reaches ({x1:.1f}, {y1:.1f}), under the title "
                f"block at ({tb_x0:.1f}, {tb_y0:.1f})")
    return ""


def fit_page(content: tuple[float, float, float, float]) -> PageFit:
    """Smallest standard page that holds ``content`` (x0, y0, x1, y1) in mm.

    Returns the largest page with a non-empty ``overflow`` when the drawing
    fits none of them — the caller is expected to say so out loud rather
    than emit a sheet whose bottom is missing.
    """
    reason = ""
    for name, w, h in PAGE_SIZES:
        reason = _clash(content, w, h)
        if not reason:
            return PageFit(name=name, width=w, height=h, content=content)
    name, w, h = PAGE_SIZES[-1]
    return PageFit(name=name, width=w, height=h, content=content,
                   overflow=reason)
