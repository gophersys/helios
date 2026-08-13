"""densui — the Dense-UI layout calculus as a library.

Layout is computed, never judged; correctness is proved, never seen.
See framework/LAYOUT-MATH.md for the axioms these functions implement.
"""

from densui.fontmetrics import Face
from densui.geometry import breathing, contains, gap_law_violations, hgap, inter

__all__ = ["Face", "breathing", "contains", "gap_law_violations", "hgap", "inter"]
