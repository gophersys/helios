"""Pure geometry predicates of the proof battery (LAYOUT-MATH).

Rectangles are (x0, y0, x1, y1) in CSS px. Every predicate returns evidence,
never a bare bool, so a failed check can always name its numbers.
"""

from __future__ import annotations


def inter(a, b, eps: float = 0.5):
    """Intersection of two rects, or None if they merely touch within eps."""
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 - x0 > eps and y1 - y0 > eps:
        return (x0, y0, x1, y1)
    return None


def hgap(a, b):
    """Horizontal gap between vertically-overlapping rects; None if not neighbours."""
    if a[3] <= b[1] or b[3] <= a[1]:
        return None
    return b[0] - a[2] if a[2] <= b[0] else a[0] - b[2]


def contains(child, parent, slack: float = 1.5):
    """None if child fits inside parent (+-slack); else the worst escape in px."""
    worst = max(
        parent[0] - child[0], parent[1] - child[1], child[2] - parent[2], child[3] - parent[3]
    )
    return None if worst <= slack else worst


def breathing(child, parent, floor: float = 2.5):
    """Bottom-edge clearance; None if >= floor, else the measured clearance."""
    clear = parent[3] - child[3]
    return None if clear >= floor else clear


def gap_law_violations(gaps, equal_frac: float = 0.06, equal_px: float = 1.0, ratio: float = 1.45):
    """The forbidden zone (LAYOUT-MATH G-1): every pair of same-neighbourhood
    gaps must be equal (within max(equal_frac*larger, equal_px)) or differ by
    >= ratio. Returns [(g_small, g_large), ...] for pairs inside the zone.
    Callers must pre-filter gaps to same-kind, interposition-free neighbours —
    similarity gates proximity."""
    bad = []
    for i in range(len(gaps)):
        for j in range(i + 1, len(gaps)):
            g1, g2 = sorted((gaps[i], gaps[j]))
            if g2 - g1 <= max(equal_frac * g2, equal_px):
                continue
            if g1 > 0 and g2 / g1 >= ratio:
                continue
            bad.append((g1, g2))
    return bad
