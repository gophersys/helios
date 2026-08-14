# Typographic and Grid Mathematics for a Blind Layout Engine

Every rule below is a formula, a number with a unit, or a decision procedure. Nothing is
"looks right". The engine reads font tables, computes rectangles, asserts inequalities.

**T0 — no text is placed by name.** A run enters layout only as
`(family, axisCoords, upm, A, D, G, cap, xh, advances[], size_px)`. Missing field ⇒ fail
loudly, name the font. A font that cannot be measured cannot be laid out.

---

## 1. Ground truth from the font file

**R1.1 Read the tables; the ratios are only a sanity band.**
```python
f=TTFont(p); upm=f["head"].unitsPerEm; A=f["hhea"].ascent; D=abs(f["hhea"].descent)
G=f["hhea"].lineGap; cap=f["OS/2"].sCapHeight; xh=f["OS/2"].sxHeight   # OS/2 v2+
px(metric) = metric_units / upm * size_px          # the only unit conversion in the system
```
UPM is 1000 (CFF) or 2048 (TrueType) — never assume. [OpenType hmtx](https://learn.microsoft.com/en-us/typography/opentype/spec/hmtx) · [OS/2 fields](https://fonttools.readthedocs.io/en/latest/ttLib/tables/O_S_2f_2.html) · [metrics reference](https://font-converters.com/technical/font-metrics)

Assert `0.60 ≤ cap/upm ≤ 0.78` and `0.40 ≤ xh/upm ≤ 0.60`, else reject. The folk value
cap ≈ 0.70 em is real as a *centre* — the observed range across typefaces is 0.62–0.72 em ([cap height](https://grokipedia.com/page/cap_height)) — but it is never the value.

**R1.2 Measured constants** (fontTools, local fonts, 2026‑08‑13):

| Font | upm | A | D | G | win A/D | cap (÷upm) | xh (÷upm) | avgW | USE_TYPO |
|---|---|---|---|---|---|---|---|---|---|
| Inter var | 2048 | 1984 | 494 | 0 | 2269/660 | 1490 (**0.7275**) | 1118 (**0.5459**) | 0.6401 | yes |
| JetBrains Mono var | 1000 | 1020 | 300 | 0 | 1020/300 | 730 (**0.7300**) | 550 (**0.5500**) | 0.6020 | yes |
| Fraunces var | 2000 | 1956 | 510 | 0 | 2340/609 | 1400 (**0.7000**) | 964 (**0.4820**) | 0.6325 | yes |

**R1.3 Platform fork — compute it, never inherit it.**
```
normal_mac        = (hheaA + |hheaD| + hheaG) / upm
normal_win_typo   = (typoA + |typoD| + typoG) / upm     # fsSelection bit 7 (0x80) set
normal_win_legacy = (winA + winD) / upm                 # bit 7 clear
```
Without bit 7 the same font renders up to ~40% taller on Windows than macOS ([Google Fonts metrics guide](https://googlefonts.github.io/gf-guide/metrics.html) · [gf-docs](http://googlefonts.github.io/gf-docs/VerticalMetrics/)).
Measured `normal`: Inter **1.2100**, JetBrains Mono **1.3200**, Fraunces **1.2330** — same
nominal size, 9% different box height. **Rule: never use `line-height: normal` in a fixed
panel; always an explicit integer px. Fail if bit 7 is clear.**

**R1.4 Variable-font traps** (both verified in Inter):
- `MVAR` varies `xhgt` ⇒ x‑height is a function of the axis coordinates, not of the family.
- `HVAR` varies advances: `"Resonance"` at 11 px = **57.77 px @ wght 400**, **59.79 px @
  wght 700** (+3.5%).

Metrics are keyed by `(family, axisCoords)`. Emphasising a label re-runs the width proof,
or budget **+4%** width while the instance is unfrozen.

---

## 2. The line-box model — where glyphs actually sit

**R2.1 Content area** (glyph box before leading):
`contentArea_px = (A + D)/upm * size_px`. Inter @11 px = **13.31 px**. ([De Oliveira, CSS font metrics](https://iamvdo.me/en/blog/css-font-metrics-line-height-and-vertical-align))

**R2.2 Leading (normative).** With `A' = A/upm·size`, `D' = D/upm·size`:
```
L = lineHeight_px − (A' + D');   halfLead = L/2;   A_eff = A' + L/2;   D_eff = D' + L/2
```
> "Calculate the leading L as L = line-height − (A + D). Half the leading … is added above
> A of the first available font, and the other half below D."
> — [CSS Inline Layout L3](https://www.w3.org/TR/css-inline-3/)

`L` may be negative; glyphs then overflow the line box, so collision must then use §3.

**R2.3 Baseline offset — the most-used number in the system:**
```
baselineY = boxTop + lineHeight_px/2 + (A' − D')/2
```
Inter, size 11, lh 16: A'=10.656, D'=2.653, L=2.690 ⇒ baselineY = **12.00 px** from top.
Every alignment axis is stated against `baselineY`, never against a box top: the space
above the caps is `A' − cap' + L/2` and is font-specific. This is precisely what
`text-box-trim` exists to remove ([Chrome](https://developer.chrome.com/blog/css-text-box-trim) · [leading-trim](https://medium.com/microsoft-design/leading-trim-the-future-of-digital-typesetting-d082d84b202)).

**R2.4 Cap-trim (capsize algorithm, verbatim arithmetic).**
```
capHeightTrim = −(A/upm − cap/upm + (G/upm)/2)          # em
baselineTrim  = −(D/upm + (G/upm)/2)                     # em
fontSize_for_target_cap = cap_target_px / (cap/upm)
```
([capsize `precomputeValues`](https://github.com/seek-oss/capsize))
Inter, target cap 8 px ⇒ size = 8/0.7275 = **10.996 → 11 px**. At lh 16 both trims are
**−4.00 px** (they coincide because Inter satisfies `A − cap − D = 1984−1490−494 = 0`).

**Rule: size text by cap height whenever two families must look the same size.** Nominal
font-size is not a visual quantity; cap height is.

---

## 3. The true occupied rectangle (the non-overlap proof)

**R3.1 Layout box — conservative, used for collision.**
```
w  = Σ advance(gᵢ)/upm·size + Σ kern(gᵢ,gᵢ₊₁)/upm·size
y0 = baselineY − A_eff ;  y1 = baselineY + D_eff ;  h = lineHeight_px
```

**R3.2 Ink box — tight, used for optical alignment and edge padding.**
```
ink.x0 = min(penᵢ + xMin(gᵢ)) ; ink.x1 = max(penᵢ + xMax(gᵢ))
ink.y0 = min yMin(gᵢ) ; ink.y1 = max yMax(gᵢ)      (relative to baseline)
rsb = advance − lsb − (xMax − xMin)
```
([FreeType glyph metrics](https://freetype.org/freetype2/docs/glyphs/glyphs-3.html))
Measured, Inter 11 px (BoundsPen):

| string | advance sum | ink w | ink y0 | ink y1 | ink h |
|---|---|---|---|---|---|
| `CUTOFF` | 44.72 | 43.38 | −0.13 | 8.11 | 8.24 |
| `Resonance` | 57.77 | 56.26 | −0.14 | 8.00 | 8.14 |
| `gjpqy` | 29.06 | 28.21 | −2.37 | 8.27 | **10.64** |
| `0.00` | 23.99 | 22.68 | −0.11 | 8.11 | 8.22 |

`ink ⊆ layoutBox` holds in every case (worst ink 10.64 px vs 13.31 px content area).
**Prove non-overlap on the layout box — it is conservative by construction.** Browser
equivalents: `TextMetrics.actualBoundingBox*` = ink, `fontBoundingBox*` = layout ([MDN TextMetrics](https://developer.mozilla.org/en-US/docs/Web/API/TextMetrics)).

**R3.3 Predicate.**
```
disjoint(a,b) ⟺ a.x1+pad ≤ b.x0 ∨ b.x1+pad ≤ a.x0 ∨ a.y1+pad ≤ b.y0 ∨ b.y1+pad ≤ a.y0
```
Run over every pair in a zone. O(n²) is free at panel scale.

**R3.4 Width bounds when the string is unknown.**
- Monospace: `w = n · adv/upm · size` **exactly**. JetBrains Mono adv = 600/1000 = **0.6 em**
  for every glyph (verified) ⇒ 6.60 px/char @11 px.
- Proportional: `w ≤ n · max(adv over the permitted charset)`. Do **not** use
  `hhea.advanceWidthMax` — Inter's is 5492 u = 2.68 em (a decorative glyph). Charset-bounded:
  uppercase Latin in Inter maxes at `W` = 0.9854 em.
- Kerning lives in GPOS (Inter has GPOS, no legacy `kern`), so advance sums carry error:
  reserve **+2%** on proportional runs, or shape with HarfBuzz and skip the reserve
  ([advance ≠ sum of advances](https://freetype.org/freetype2/docs/glyphs/glyphs-3.html)).

**R3.5 Numerals: tabular, or the layout is a lie.** Inter's default figures are
proportional — advances 833…1323 u, `'1'` is 0.63× the width of `'4'`, so `1.11`→`4.44`
changes width by up to 59%. Inter's `tnum` glyphs are **1328 u = 0.6484 em, uniform**
(verified). Any value that changes at runtime uses `tnum` or a mono family; then
```
readout_w = maxDigits·digitAdv_em·size + w(sign) + w('.') + w(' ') + w(unit)
```
is exact and the field right-aligns on a fixed axis.

---

## 4. Optical vs geometric centring

**R4.1 Why box-centring reads low.** The layout box is vertically asymmetric (`A' = 0.969 em`
above baseline vs `D' = 0.241 em` below) while visible uppercase ink occupies `0…cap`. The
signed correction, positive = move text down:
```
Δy = (cap − A' + D') / 2        [em·size]
```
Inter: `(0.7275 − 0.9688 + 0.2412)/2 = 0` exactly — box-centring *is* cap-centring.
Fraunces: `(0.700 − 0.978 + 0.255)/2 = −0.0115 em` ⇒ text sits **0.13 px low @11 px,
0.35 px low @30 px**; move it up. JetBrains Mono: `+0.005 em`. **Font-dependent: compute it.**
(Same term as the `vertical-align` correction in [De Oliveira](https://iamvdo.me/en/blog/css-font-metrics-line-height-and-vertical-align).)

**R4.2 Cap-centring for buttons, cells, chips, badges** — box of height `H`:
```
baselineY = (H + cap_px)/2                      cap_px = cap/upm · size
```
Inter 11 px in a 20 px row: cap_px = 8.00 ⇒ baselineY = **14.00 px** from box top.
For mixed case where descenders should look balanced: `baselineY = (H + cap_px − inkDesc)/2`.

**R4.3 Overshoot is measured, not corrected.** Inter: `H` yMax 1490 vs `O` yMax **1510**
(+20 u = +0.98% em = +1.34% of cap), `O` yMin −20; `x` 1118 vs `o` **1132** (+1.25% of x‑h).
Typical 1–3% ([overshoot](https://en.wikipedia.org/wiki/Overshoot_(typography))).
The designer already applied this correction — the engine aligns on cap/xh/baseline and
adds no nudge, but budgets **+0.015 em** of ink above cap for tight top clearances.

**R4.4 Panel optical centre ≈ 46% from the top** (offset −0.04·H vs geometric) ([visual centre](https://blog.thepapermillstore.com/designing-using-visual-center/) · [sign design](https://www.thesignchef.com/article/how-to-a-design-a-sign-finding-the-optical-center-of-your-sign-design)).
Apply **only** to a lone dominant element in a large empty field. Never inside a grid — it
destroys the rhythm equality of §5.

---

## 5. Baseline grid and vertical rhythm

**R5.1 Unit `u ∈ {4, 8}` px** — 4 for dense instrument panels, 8 for outer chrome; every
vertical quantity is `k·u`. ([8‑pt grid](https://spec.fm/specifics/8-pt-grid) · [4 px baseline grid](https://uxdesign.cc/the-4px-baseline-grid-89485012dea6) · [Material 8dp baseline grid](https://m2.material.io/design/layout/responsive-ui.html) · [Carbon spacing = multiples of 2/4/8](https://carbondesignsystem.com/elements/spacing/overview/))

**R5.2 Snap line-height:** `lineHeight = ceil(ratio · size / u) · u`.
> "line box heights are rounded *up* to the closest multiple of the unit … the additional
> space is distributed to over-side and under-side equally"
> — [CSS Rhythmic Sizing L1](https://www.w3.org/TR/css-rhythm-1/)

11 px @1.4, u=4 ⇒ ceil(15.4/4)·4 = **16**. 12 px @1.4 ⇒ **20** (effective ratio 1.667 —
accept: the grid outranks the ratio).

**R5.3 Land baselines on grid lines:**
```
baselineY_abs = boxTop + lineHeight/2 + (A' − D')/2
snapOffset    = (u − (baselineY_abs mod u)) mod u      # push the box down by this
```
Then assert `baselineY_abs mod u == 0` for every run. Vertical rhythm becomes an `==`.

**R5.4 Row heights.** Dense: **24 / 28 / 32 px** (Carbon ships a 24 px data-table row; AG
Grid default 42; MUI X default 52 — comfortable, not dense). Below 28 px, pointer targets
degrade; 24 px is fine for read-only telemetry. ([Carbon](https://github.com/carbon-design-system/carbon/issues/8875) · [AG Grid](https://www.ag-grid.com/javascript-data-grid/row-height/) · [MUI X](https://mui.com/x/react-data-grid/row-height/))
Constraint: `rowH ≥ lineHeight + 2·padY` and `rowH mod u == 0`.

---

## 6. Modular scale, quantised

**R6.1** `size(n) = snap(base · rⁿ)`. Ratios professionals use *for UI*: **1.125** (major
second) and **1.2** (minor third) for dense/compact; 1.25–1.333 only for editorial surfaces.
Dense dashboards live at the tight end. ([type-scale types](https://cieden.com/book/sub-atomic/typography/different-type-scale-types) · [modular scale](https://imperavi.com/books/ui-typography/principles/modular-scale/))

**R6.2 Quantise then dedupe.** base 11, r 1.125 → 11, 12.4, 13.9, 15.7 ⇒ **11, 12, 14, 16**.
If two steps land within 1 px, drop one — a 1 px difference carries no hierarchy. A dense
panel needs **3–4 sizes total**: `{11 unit/caption, 12 label, 14 value, 16 section title}`.

**R6.3 Tracking is a function of size.** SF varies tracking continuously and tightens as
size grows (the old Text/Display split at 20 pt is now a smooth ramp between 17 and 28 pt) ([WWDC20, details of UI typography](https://wwdcnotes.com/documentation/wwdc20-10175-the-details-of-ui-typography/)).
Executable approximation ([D'Amato](https://blog.damato.design/posts/two-typographic-tricks/)):
```
tracking_em = (25 − size_px) / 3000            # +0.0047 em @11 px, 0 @25 px, negative above
allCaps: tracking_em += 0.04 … 0.06
```
Tracking changes width — recompute R3.1 after applying it.

---

## 7. Column / gutter mathematics (Müller‑Brockmann, made integer)

**R7.1 Identity and integrality.**
```
W = 2M + n·C + (n−1)·G      ⇒      C = (W − 2M − (n−1)G) / n
```
([grid arithmetic](https://www.numberanalytics.com/blog/ultimate-guide-to-grid-in-typography-theory);
Müller-Brockmann derives column width, gutter and margin from page format and type size — [Grid Systems in Graphic Design](https://ia803105.us.archive.org/29/items/GridSystemsInGraphicDesignJosefMullerBrockmann/Grid%20systems%20in%20graphic%20design%20-%20Josef%20Muller-Brockmann.pdf))

Fixed-size panels require `C ∈ ℤ`. Procedure: iterate `G ∈ {8,12,16,24}`, `M ∈ {8,16,24,32}`;
take the first pair with `(W − 2M − (n−1)G) mod n == 0`. If none, adjust `M` by ±1 px —
**margins absorb the remainder, never the columns** (unequal columns void every alignment
proof). Worked: W=960, n=12, G=16 → M=24 gives 61.33 ✗; M=32 gives 720/12 = **60 ✓**.

**R7.2 Gutter band** `G ∈ [C/4, C/2]`
([editorial grids](https://www.numberanalytics.com/blog/mastering-grids-in-editorial-design));
dense panels take the low end, and always `G mod u == 0`.

**R7.3 The vertical module derives from the text.** Müller-Brockmann: field depth = an
integer number of text lines; space between fields = one or more full lines ([construction](https://www.neugraphic.com/muller-brockmann/muller-brockmann-text2.html)):
```
moduleH = k · lineHeight ;  vGutter = m · lineHeight    (k,m ∈ ℤ⁺, m usually 1)
```
This is what makes a panel's horizontal rules land on baselines automatically.

---

## 8. Label-above-control and value-beside-control (pro-audio panel math)

**R8.1 Proximity, as an inequality.** Related items **4–8 px**, unrelated **24–32+ px** ([NN/g proximity](https://www.nngroup.com/articles/gestalt-proximity/) · [spacing systems](https://uxdesign.cc/gestalt-in-ux-or-why-designers-are-so-annoying-about-spacing-a4f06a6e255e)):
```
gap_between_groups ≥ 2 · gap_within_group          (3× is safer below 12 px type)
```
The classic failure is a 12 px label→field gap beside a 16 px field→field gap: halve the
inner, double the outer.

**R8.2 The collision-free stack.** Label size `s_L`, snapped `LH_L`, `gap_in = 4 px` (u=4):
```
labelBaseline = groupTop + LH_L/2 + (A'_L − D'_L)/2
controlTop    = labelBaseline + D'_L + gap_in
valueBaseline = controlTop + controlH + gap_in + A'_V
groupH        = ceil((valueBaseline + D'_V − groupTop)/u)·u
assert controlTop − (labelBaseline + D'_L) ≥ 4
```
Use layout `D'`, not ink descent, so an unforeseen `g`/`y` can never touch the control.

Shipping reference numbers (Teragon plugin GUI kit): large-knob label **15 pt**, generic
labels **12 pt**, unit labels **9 pt @50% white**; labels sit *below* the button inside the
same clickable frame; buttons occupy 24 px of a 40 px frame; grouping = 3 px-radius rounded
rect ([TeragonGuiComponents](http://teragonaudio.com/TeragonGuiComponents.html)). Ableton's
device guidance: whole-pixel geometry, snap to a 1×1 px grid, symmetric L/R margins ([M4L production guidelines](https://github.com/Ableton/maxdevtools/blob/main/m4l-production-guidelines/m4l-production-guidelines.md)).

Cell width, with label and value centred on the control's vertical axis:
```
cellW = ceil( max(knobW, labelW, valueW) / u ) · u
```
If `labelW > knobW + G`, abbreviate or widen the cell — never bleed into the gutter, because
the gutter is the only evidence that two controls are separate groups.

**R8.3 Value beside a control: reserve, then right-align.**
```
valueW_reserved = maxDigits·digitAdv_em·size + w(sign) + w('.') + w(' ') + w(unit)
xLeft_of_control ≤ (cellRight − padR) − valueW_reserved − gap_in
```
Verified, Inter 11 px with `tnum`, `−99.9 dB` = 8686 u = 4.2412 em = **46.65 px** ⇒ reserve
**48 px** (a multiple of u) and right-align. Proportional figures give 43.23 px for
`-12.3 dB` but jitter with the digits — hence R3.5.

**R8.4 Truncation is computed before geometry is emitted.**
```
fits(text) ⟺ layoutBox.w ≤ availW
else: keep the longest prefix with advanceSum ≤ availW − w('…')
```
An overflowing string silently invalidates every horizontal proof in its row.

---

## 9. Legibility floor (a gate, not a preference)

**R9.1 Visual angle.** `θ_arcmin ≈ 3438 · h_mm / d_mm`, `h_mm = θ · d / 3438`.
Thresholds: **≥16′ minimum**, **≥22′ for comfortable sustained reading**, **≤30′** (larger
reduces characters per fixation and slows reading) ([Kolbe et al. 2023, *Ophthalmic & Physiological Optics*, reviewing ANSI/HFES 100](https://onlinelibrary.wiley.com/doi/full/10.1111/opo.13170)).
At d = 600 mm, 110 ppi (0.231 mm/px): 16′ ⇒ 2.79 mm = **12.1 px of x-height**; 22′ ⇒ 3.84 mm
= **16.6 px**. For Inter (x‑h 0.5459 em) 12.1 px of x-height means a **22 px** font — far
above dense-UI practice, so use the arcmin bound for *body copy* and the practice floor for
glanceable labels.

**R9.2 Practice floor.** Absolute minimum **11 px** (units/captions only); 12 px labels,
13–14 px values, 16 px section titles. Under 12 px trips Google's small-font warning; dense
data apps test 13 px nav / 12 px table / 11 px timestamps ([Walter](https://stephaniewalter.design/blog/what-minimum-font-size-for-a-high-density-data-web-app-do-you-suggest/) · [small-text fonts](https://www.designyourway.net/blog/best-fonts-for-small-text/)).

**R9.3 Normalise families by x-height, not nominal size:**
`size_B = size_A · (xh_A/upm_A) / (xh_B/upm_B)`. Inter 11 px ↔ Fraunces 12.45 → **12 px**.

---

## 10. The validator — assertions run before any pixel is emitted

1. `upm, A, D, G, cap, xh` present for every family; ratios inside the bands (R1.1–R1.2).
2. `fsSelection & 0x80 ≠ 0` for every family (R1.3).
3. No run uses `line-height: normal`; every `lineHeight mod u == 0` (R5.2).
4. `baselineY_abs mod u == 0` for every run (R5.3).
5. `ink ⊆ layoutBox` for every run (R3.2) — catches a bad metric parse.
6. Pairwise `disjoint()` per zone on layout boxes with `pad ≥ 4 px` (R3.3).
7. `fits(text)` for every static string at final size **and weight**, +2% kerning reserve on
   proportional runs, +4% if the variable instance is unfrozen (R1.4, R3.4, R8.4).
8. Every runtime numeric field uses tabular figures, is right-aligned on a fixed axis, and
   its reserved width is computed from `maxDigits` (R3.5, R8.3).
9. `gap_between_groups ≥ 2 · gap_within_group` in every group (R8.1).
10. `(W − 2M − (n−1)G) mod n == 0`; all module heights are integer multiples of `lineHeight`
    (R7.1, R7.3).
11. Distinct type sizes ≤ 4, each ≥ 2 px apart after grid rounding (R6.2).
12. Smallest size ≥ 11 px; anything smaller fails and names the element (R9.2).

Any failure is an error, never a warning. A layout that "mostly" proves has not been proved.


---

## Appendix (2026-08-14): per-face cap tables for the faces in actual use

Measured by `densui.Face.metrics(16)` and REGENERATED AS A GATE on every
machine (`test_metrics_table_sane_for_every_available_face` — the fleet
validates DejaVu, a Mac validates Arial and Ableton Sans Small; a face
drifting outside the R1 sanity bands fails by name, so this table cannot
rot).

| face | upm | cap/em | xh/em | asc px@16 | desc px@16 | cap px@16 | centring dy px@16 |
|---|---|---|---|---|---|---|---|
| AbletonSansSmall-Regular | 1000 | 0.710 | 0.517 | 12.00 | −4.00 | 11.36 | **1.68** |
| Arial | 2048 | 0.716 | 0.519 | 11.65 | −3.37 | 11.46 | **1.59** |
| DejaVuSans (fleet-validated) | — | in-band per the gate | | | | | |

The load-bearing column is **centring dy** (R4: `(cap − A′ + D′)/2`): text
box-centred over a dial sits ~1.6–1.7 px above true cap-centre in BOTH our
primary faces at 16 px — nearly identical, which is why the operator's
box-centred labels read correctly across the font swap. A face with dy near
0 (e.g. Inter, per the original R4 measurement) would need the correction
applied the OTHER way; the gate's ±2 px band flags any newcomer whose dy
demands per-face treatment.
