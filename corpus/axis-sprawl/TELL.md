# axis-sprawl — the seeded defect

Five dials, each on its own vertical line: five distinct left edges, five right
edges, five centres. `densui.audit.check_axis_budget` reads 5 controls ÷ 5
x-axes = 1.00 against DENSE-UI A1's floor of ~3, and reports Ω 34.83 with it
(three x families of five singleton classes at N=5: `3 × 5 × log2 5`).

This is the defect A1 names and the one a panel gets wrong while every local
measurement looks fine. Nothing here is crowded, nothing overlaps, no gap pair
exists: the dials are 50px apart horizontally and 40px apart vertically, so no
two share a line for `check_level` or `check_gap_law` to compare, the 64px
centre pitch clears the 24px WCAG circle, every edge is a whole pixel, and the
page carries no text. The fix A1 asks for is to merge axes — put the five on
one or two columns — never to delete a control.
