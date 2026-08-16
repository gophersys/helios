# crowding — the seeded defect

`blk(one)` ends at x=60 and `blk(two)` starts at x=61 while their vertical
bands overlap: a 1.0px gap between two differently-owned controls, under the
2.0px floor `ui.audit.check_crowding` enforces at default `Rules()`.

The two blocks do not intersect, so the overlap class stays silent here — this
seed is the near-miss that overlap cannot see.
