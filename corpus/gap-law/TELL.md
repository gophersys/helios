# gap-law — the seeded defect

Three same-kind dials on one line leave gaps of 12px and 16px. That pair sits
inside the forbidden zone (LAYOUT-MATH G-1): too far apart to read as equal,
too close to read as a deliberate group break (16/12 = 1.33 < 1.45).

Both gaps clear the 2.0px crowding floor and the dial centres are level, so
`ui.audit.check_gap_law` is the only predicate with anything to say.
