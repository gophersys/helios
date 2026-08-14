# hit-pitch — the seeded defect

Nine 12px targets on a 60 x 40 grid, except `checkbox(b2)`, which sits 20px
below `checkbox(b1)` instead of 40. WCAG 2.2 SC 2.5.8 (psycho-math R3.4) draws
a 24px circle on each target's bounding box and forbids the circles from
intersecting, so 20px of centre pitch fails and
`densui.audit.check_hit_pitch` names the pair and the 20.0px it measured.

The edge gap between b1 and b2 is 8px — comfortably above every crowding floor
in the battery, which is the point: the edge gap is the common misreading of
this SC, and it says nothing useful about targets this size.

Exactly one pair is inside the circle. b2 keeps its column, so the panel still
holds 9 controls on 3 x-axes (3.00, at A1's floor) and the alignment predicate
has nothing to say; the next nearest pairs are 60px apart in a row and 63px
diagonally; every edge is a whole pixel; there is no text on the page.
