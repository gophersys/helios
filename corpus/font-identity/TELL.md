# font-identity — the seeded defect

The panel declares a sans face and the page draws a mono one. Nothing on the
rendered page says so: parts carry glyph INK, and ink is where the glyphs are,
never which face drew them. Every reserved width in this system is
`Face.adv()` of the widest string, so a substituted face means every box on a
panel like this one reserves room for text that is not there — and the rest of
the battery keeps passing, because it measures where the ink landed.

`ui.audit.check_font_identity` measures the ADVANCE of a pinned 73-glyph
sentinel, which is the quantity the boxes were computed from, with kerning off
(canvas kerns; `Face.adv()` sums glyph advances, and on this sentinel the two
differ by 3.55–5.05px with kerning left on — the whole band, spent on nothing).

The margin on both gate hosts, at the declared 16px:

| host | declared resolves to | page renders | sentinel advance | apart |
|---|---|---|---|---|
| macOS | Arial (fallback; the DejaVu path is a container path) | Courier New | 660.68 → 700.91px | **40.23px** |
| CI image | DejaVu Sans (declared) | DejaVu Sans Mono | | **5.27px** |

The band is 0.5px, so the smaller of the two margins is ten times it. Both are
far above the 0.0000px that chrome and fontTools agree to on this string.

Everything else here is clean, which is what makes the failure evidence rather
than a page that fails everything: one part, so no gap pair, no crowding pair
and no overlap exists; no rhythm kind, so the axis budget is silent; no hit
target and no token-sized box, so pitch and integer edges have nothing to
judge; the label ink clears the plate bottom by ~68px; and no `[ratio]` table
is declared.

The failure names the kind, the face the page resolved to, both advances and
the signed delta — enough to decide whether the CSS, a webfont or the spec is
at fault before touching anything.
