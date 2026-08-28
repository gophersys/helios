# breathing — the seeded defect

The plate ends at y=60 and the GLYPH INK of `value(one)` bottoms out at y=60.2
under this host's `monospace` (Menlo): a clearance of -0.2px against the 2.5px
floor in default `Rules()`. The value does not sit in the plate, it sits on the
plate's bottom edge — and only ink measurement can see it, since the element
box says nothing about where the glyphs actually land.

## Why the numbers are built the way they are

The ink bottom is `box top + line-height/2 + (ascent - descent)/2 + the
string's descent`, so it moves with whatever font the host resolves. Two
choices keep the seed inside its band on any face:

- **The line box carries the position**, not the ascent alone: half-leading
  moves the text up by exactly half of what a taller ascent adds, so only half
  of a face's metric spread ever reaches the clearance.
- **The string has no descender** (`-12.0 dB`). Old-style figures (Georgia)
  drop a `3` a further 2.0px; digits that sit on the baseline do not.

Measured on this page across 13 faces a Mac resolves — monospace/Menlo, Courier
New, Andale Mono, JetBrains Mono, Arial, Helvetica, Verdana, Georgia, Times New
Roman, Inter, sans-serif, serif — the clearance spans **-0.23 .. +0.81px**, and
breathing fires on every one of them while containment stays silent on every
one. Under the CI image's only faces (DejaVu Sans Mono and DejaVu Sans, from
`fonts-dejavu-core`, inlined as data URIs to measure them here) it is -0.17px,
the same as Menlo.

## The band is bounded by two classes, not one

Breathing fires below 2.5px of clearance; containment fires once the ink
escapes its container by more than 1.5px. A breathing-only seed therefore lives
in `(-1.5, 2.5)`, and this one sits near the middle of it: at the worst face
measured it is still 1.69px clear of the breathing floor and 1.27px clear of
the containment slack. Pressing harder into the edge would not make the seed
stronger — it would make it a containment seed.

Nothing else on the page has anything to say: one part, so no pair-wise class
(overlap, crowding, gap-law) has a comparison to make, and `value` is not a
rhythm kind.
