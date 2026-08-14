# breathing — the seeded defect

`value(one)` ends at y=59 inside a plate that ends at y=60: 1.0px of bottom
clearance, under the 2.5px floor in default `Rules()`. The value reads as
resting on the plate edge instead of sitting in it.

The escape is 0px, so containment stays silent — this seed is the pressed-but-
still-inside case that only `densui.audit.check_breathing` can see.
