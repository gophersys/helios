# fractional-edges — the seeded defect

Four dials in one column. `dial(d2)` is at `top: 60.5px`, so its top edge
measures 60.5 and its bottom 88.5. `ui.audit.check_integer_edges` names the
part, the edge and the value at scale 1 (LAYOUT-MATH A-5, psycho-math R6.2):
hyperacuity reads a luminance centroid, so an antialiased half pixel is SEEN as
half a pixel — it does not average away, and no amount of antialiasing hides it.

The defect is vertical on purpose. Half a pixel of LEFT would also move the
column's alignment class, so the page would carry two defects; moving it down
the page leaves the axis census untouched — 4 controls on 1 x-axis, 4.00 against
A1's floor.

Everything else is clean: the column pitch is 40 / 39.5 / 40 px, well past the
24px WCAG circle and far too far apart for any crowding or gap-law pair; the
dials never share a line, so nothing is compared for level; there is no text on
the page. Rendered at any scale other than 1 this page is legitimate, which is
why the predicate takes the scale as an argument.
