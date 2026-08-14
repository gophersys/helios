# containment — the seeded defect

The plate ends at x=200 and `blk(one)` runs from x=180 to x=220, so the control
hangs 20px outside the container it belongs to — far past the 1.5px slack in
default `Rules()`. `densui.audit.check_containment` must report the escape.

It is the only part on the page, so no pair-wise class (overlap, crowding,
gap-law) has anything to compare.
