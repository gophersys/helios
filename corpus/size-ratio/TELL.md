# size-ratio — the seeded defect

The label is 9px type against a 28px dial. Every absolute size on this page is
plausible on its own; the RELATION between them is the tell — 9/28 = 0.32 in
type-size terms, which is where generated panels land. The drawn reference
measures ~0.44 in ink terms; type-size ratios differ, and the two must never be
compared across bases (see DENSE-UI §Ratios).

`densui.audit.check_ratios` measures glyph ink, not type size, so the numbers it
reports are on that basis: an all-caps label's ink is its cap height, 0.72em on
both gate faces, so the correct 16px label would measure `16 x 0.72 / 28 = 0.41`
and this page measures **0.23**. The declared row wants 0.41 ±0.06, and the
failure names the row, the measured value, the want and the tolerance.

Everything else here is clean: one knob unit, so no gap pair and no crowding
pair exists; the label ink clears the plate bottom by ~70px; the dial and the
label do not intersect; the `dial` row (28 ±1) passes, which is what makes the
failing row evidence rather than a page that fails everything.
