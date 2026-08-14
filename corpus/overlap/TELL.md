# overlap — the seeded defect

`blk(one)` (10,10,60,40) and `blk(two)` (40,20,90,50) share a 20x20px region,
so two controls print over each other. `densui.audit.check_overlaps` must name
both parts and the intersection size at default `Rules()`.

Everything else on this page is clean: the two blocks are the only parts, and
neither is a text or rhythm kind, so no other class has anything to say.
