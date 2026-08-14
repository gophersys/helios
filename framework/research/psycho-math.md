# Psychophysics of Density — executable numbers for a blind layout engine

Every rule is a formula, a number with units, or a decision procedure. Numbers produced by
composing two sources are marked **[derived]** with the composition shown. §9 lists what I
could not verify, so nothing above it is contaminated by a guess. All arithmetic here was
computed, not recalled.

---

## 1. The reference frame — fix this first

The engine cannot see, so it works in **visual angle** and converts through one declared
constant. Declare the deployment, derive `K`, never guess.

```
AM     = 3437.75                    # arcmin per radian = 60*180/pi
K      = AM * (25.4/PPI) / D_mm     # arcmin per CSS px   (small-angle)
PPD    = 60 / K                     # CSS px per degree
px(a)  = a / K                      # arcmin -> CSS px
ecc(r) = r / PPD                    # px from fixation -> deg eccentricity
```
Small-angle error < 0.1% (checked against exact `2*atan(s/2D)`: agrees to 3 decimals).

| Deployment | CSS PPI | D | **K** arcmin/px | **PPD** |
|---|---|---|---|---|
| 27" 2560×1440 @ 600 mm (= 27" 5K @ 2×) | 108.8 | 600 | **1.338** | 44.9 |
| MacBook Pro 16" @ 2×, 500 mm | 127.0 | 500 | 1.375 | 43.6 |
| W3C CSS reference pixel | 96 | 711 | 1.279 | 46.9 |
| 27" 4K **native, unscaled** @ 600 mm | 163.2 | 600 | **0.892** | 67.3 |

**REFERENCE: `K = 1.34 arcmin/CSS px`, `PPD = 45 CSS px/deg`. Design at K=1.34; validate at
K=0.89** (unscaled 4K) — smaller `K` makes every angular minimum cost more pixels.

*Why:* W3C defines 1 CSS px as ≈0.0213° = 1.279 arcmin at a nominal 28 in arm's length
(96 dpi). A 2× Retina panel keeps CSS PPI ≈109, so authoring in CSS px is already
resolution-independent; the exception is hi-DPI run unscaled.
*Sources:* [W3C CSS Values 4 §absolute-lengths](https://www.w3.org/TR/css-values-4/#absolute-lengths);
[VPixx pixel density & visual angle](https://docs.vpixx.com/labmaestro/monitor-pixel-density-and-degrees-of-visual-angle)
— note their worked formula `PPI*d_cm/2.54` yields pixels **per radian**; divide by 57.2958.

---

## 2. Acuity floors — the smallest anything may be

| Quantity | Angle | **px @ K=1.34** | @ K=0.89 |
|---|---|---|---|
| Resolution acuity (20/20), min separable | 1′ | 0.75 | 1.12 |
| Two edges reliably separate | 2′ | 1.50 | 2.24 |
| Foveal crowding gap floor (§4) | 3.7′ | 2.77 | 4.15 |
| ISO 9241-303 **min** cap height | 16′ | 11.96 | 17.9 |
| ISO 9241-303 **preferred** cap height | 20–22′ | 14.9–16.5 | 22.4–24.7 |
| MIL-STD-1472F coloured char min / pref | 21′ / 30′ | 15.7 / 22.4 | 23.5 / 33.6 |

**R2.1 — Minimum hairline gap = 2 CSS px.** 1 px subtends 1.34′, above the 1′ acuity limit
in theory, but antialiasing and sub-100% contrast erase it. 2 px survives both `K` values.

**R2.2 — Text size.** `font_size = px(cap_arcmin)/0.72` (cap ratio: Inter 0.727, SF ≈0.70,
Helvetica 0.717). ISO min 16′ → cap 11.96 px → **font-size 16.6 px**; preferred 20′ →
cap 14.95 px → **font-size 20.8 px**.

**R2.3 — The inverted rule, which is the useful one.** Dense panels (Ableton-class) run
10–12 px type = 9.6–11.6′ at 600 mm, i.e. **60–72% of the ISO minimum**. Legitimate trade,
but not free: it *redefines the viewing distance*, which is an output, not an input.

```
D_max_mm = AM * cap_mm / 16      # distance at which cap still subtends 16'
```

`D_max` (16′ / 20′), with the angle each subtends at 600 mm:
**10 px** (cap 1.68 mm, 9.6′) → 361 / 289 mm · **11 px** (1.85 mm, 10.6′) → **397** / 318 mm ·
**12 px** (2.02 mm, 11.6′) → 433 / 347 mm · **14 px** (2.35 mm, 13.5′) → 506 / 404 mm ·
**16 px** (2.69 mm, 15.4′) → 578 / 462 mm.

A panel whose smallest label is 11 px is a **40 cm panel**, not a 60 cm one — declare that
or raise the type. Reserve sub-16′ type for *familiar, redundantly-coded* labels (a knob's
name, learned once); never for unfamiliar alphanumerics or critical readouts, since the ISO
minimum is calibrated for first-read legibility.
*Sources:* [ISO 9241-303](https://cdn.standards.iteh.ai/samples/57992/bddfd91165b444f6b9815a6993feadc5/ISO-9241-303-2011.pdf);
MIL-STD-1472F §5.2.1.6.4.1 (4.6 mrad = 16′ min, 5.8 mrad = 20′ pref; colour 6.1/8.7 mrad).

**R2.4 — Stroke width is polarity-dependent** (irradiation: light-on-dark blooms).
MIL-STD-1472F §5.5.5.8–10: dark-on-light **1/6–1/7** of cap; light-on-dark **1/7–1/8**;
transilluminated **1/10**. → **on a dark instrument panel use one weight lighter than on a
light ground** (≈14% thinner stroke).

**R2.5 — Text spacing** (MIL-STD-1472F §5.5.5.11–13): character gap ≥ 1 stroke width; word
gap ≥ 1 character width; **line gap ≥ 0.5 × cap** → with cap = 0.72·F,
**`line-height >= 1.36 * font_size`**. **[derived]**

---

## 3. Fitts's law — and the theorem that matters for density

```
ID = log2(A/W + 1)              # Shannon form (MacKenzie)
MT = a + b*ID                   # b = 1/TP
TP(mouse) = 3.7 .. 4.9 bits/s   # ISO 9241-9 review -> b = 204..270 ms/bit
We = 4.133 * SD_x               # effective width <-> endpoint scatter
```
*Source:* [MacKenzie, Fitts' Law, Wiley Handbook of HCI](https://www.yorku.ca/mack/hhci2018.html).

With `a = 0.10 s`, `TP = 4.3 bits/s` (`b = 233 ms/bit`), `A = 500 px`:
W=48 → ID 3.51, MT 0.917 s · W=24 → 4.45, 1.135 s · W=12 → 5.42, 1.359 s · W=6 → 6.40, 1.588 s.

**R3.1 — Every halving of target width costs exactly 1 bit ≈ 233 ms per acquisition.**

**R3.2 — THE DENSITY THEOREM: Fitts is scale-invariant.** `ID` depends only on `A/W`, so
scaling the whole panel by any factor leaves MT unchanged (verified: `A=500,W=12` and
`A=125,W=12` differ by exactly 2 bits — identical to `A=500,W=48`). Therefore:

> Uniform densification costs **zero** pointing time. What costs time is shrinking `W` while
> holding `A` fixed — cramming controls in without re-zoning. **To add controls at constant
> panel size, first reduce `A` by moving co-used controls adjacent; only then reduce `W`.**
> A re-zoning that halves mean travel buys back one full halving of every control.

This is the most important rule here, because "denser" and "slower" are *not* the same
operation and only the second is avoidable.

**R3.3 — Endpoint scatter** `SD = W/4.133`: W=12 → 2.90 px, W=24 → 5.81 px, W=48 → 11.61 px.
Targets closer than ≈2·SD collect mis-clicks.

**R3.4 — Minimum pitch (a runnable geometric check).** WCAG 2.2 SC 2.5.8: targets ≥ 24×24
CSS px, **or** undersized targets so placed that 24 px-diameter circles centred on each
bounding box **do not intersect** another target or another such circle. Operationally:
**centre-to-centre pitch ≥ 24 CSS px for every adjacent hit-target pair** — a circle
intersection test, no judgement.
*Source:* [Understanding SC 2.5.8](https://www.digitala11y.com/understanding-sc-2-5-8-target-size-minimum/).
Touch baselines for reference only: Apple HIG 44×44 pt, Material 48×48 dp.

---

## 4. Crowding — Bouma's law, and why dense panels are serial devices

```
d = b*phi + w        # critical spacing: LINEAR, not proportional
```
`d` critical target–flanker distance, `phi` eccentricity (deg), `w` intercept.

- Bouma 1970: `b ≈ 0.5` (he later revised to 0.4) with `d` as **empty space** (edge-to-edge);
  modern work uses **centre-to-centre**, which adds ≈ one element width as intercept `w`.
  **The definitions are not interchangeable — the engine must state which.** Only the
  empty-space form passes through the origin.
- `b` varies by task: **0.3–0.7** (Pelli et al. 2004 Table 4), extremes 0.13–0.71. Linearity
  by contrast holds "amazingly well" across visual tasks.
- 50 observers, Sloan font, centre-to-centre: geometric mean **b = 0.23**, intercept
  φ₀ ≈ 0.24°; the two-parameter law explains **82.45%** of variance (93.86% with
  meridian/orientation/font/observer terms).
- **Meridian anisotropy (b):** right **0.184** · left **0.237** · lower **0.300** · upper **0.381**.
- **Radial–tangential:** tangential b ≈ **0.55×** radial (radial ≈1.8× larger).
- **Foveal crowding is real:** at 0° eccentricity critical *gap* ≈ **1′–3.7′**
  (0.75′–1.3′ centre-to-centre by adaptive-optics data).

*Sources:* [Strasburger, Seven Myths on Crowding and Peripheral Vision, i-Perception 11(3) 2020](https://epub.ub.uni-muenchen.de/88027/1/2041669520913052.pdf);
[The Bouma law accounts for crowding in 50 observers (PMC10408772)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10408772/);
[Rosen, Chakravarthi & Pelli, JOV 2014](https://jov.arvojournals.org/article.aspx?articleid=2212997).

**R4.1 — Foveal gap floor.** Two glyph-scale features must be ≥ **3.7′ = 2.8 px → round to
3 CSS px** edge-to-edge, or they crowd *even when directly fixated*. Hard floor below which
sub-features of a control fuse. (4.2 px at K=0.89.)

**R4.2 — THE PERIPHERAL CLEARANCE RULE — and it needs no unit conversion.** Eccentricity in
degrees is `r_px/PPD` and required spacing in px is `d_deg*PPD`, so **`PPD` cancels**:

```
clear_radius_px >= b * r_px       # r_px = distance from the fixation point
```

Required clear radius, by `r` from fixation — right (b=.184) / left (.237) / lower (.300) /
upper (.381) / conservative (.5):
`r=100` → 18/24/30/38/50 px · `r=200` → 37/47/60/76/100 px ·
`r=400` → 74/95/120/152/200 px · `r=700` → 129/166/210/267/350 px.

**R4.3 — Corollary: a dense panel is a foveal-serial device.** A 1440×900 panel at PPD 45
has its corner at 18.9° eccentricity; critical spacing there is 4.35° = **195 px** (b=0.23)
or 424 px (b=0.5). No dense panel can grant 195 px of clear space to a corner control, so
**identification of any control requires a saccade to it.** Consequences:
- Do **not** optimise for peripheral *identification*; optimise for **saccade targeting**,
  driven by the coarse features that survive crowding — plate boundary, plate fill
  luminance, colour channel, gross size. Those must be discriminable at 20° eccentricity.
- **Exempt class:** things that must be noticed *without* looking (alarms, clip lights,
  transport state) are the only elements that must satisfy R4.2. Budget them — each
  consumes `pi*(b*r)^2` of exclusive area, so a panel affords very few.

**R4.4 — Field placement.** Upper-field crowding is **2.07×** worse than right-field
(0.381/0.184). Quadrant rank for peripherally-monitored items: **right > left > lower >
upper.** Put status/alarm indicators right and below the primary fixation zone; never stack
them above it.

**R4.5 — Lay peripheral indicator runs tangentially.** Crowding zones are radially
elongated, so a run **perpendicular to the radius from fixation packs 1.8× tighter** than
the same run laid radially. Centre-fixated panel: a *vertical* strip at the left/right edge
is tangential (good); a *horizontal* row at the same edge is radial (needs 1.8× the pitch).

---

## 5. Gestalt proximity, quantified — the forbidden zone

Two thresholds exist and they are far apart. This is the whole mechanism behind
"deliberate vs sloppy".

**Detection threshold `w_det` — "these gaps are not equal":** spatial-interval/bisection
Weber fraction `Δs/s` ≈ **0.02–0.04** foveal and simultaneous (best case ≈0.01); classic
visual line-length Weber fraction ≈ **0.029** (Teghtsoonian 1971). Sequential or remembered
comparison degrades to ≈10–15% (JND 0.5–0.94 cm on 0.45–11.25 cm baselines).

**Grouping threshold — "these form separate groups":** Gori & Spillmann measured both on one
stimulus (row of 12 equi-spaced dots; widen the gap after every 3rd dot until (a) irregularity
is detected, then (b) triplets are perceived). To be seen as **grouped**, differences had to
be **5.2× larger for spacing** (7.4× size, 6.6× luminance) than for detection. It persisted
with only two gaps and with randomised gap position.
*Source:* [Gori & Spillmann, Vision Research 50(12):1194–1202, 2010](https://pubmed.ncbi.nlm.nih.gov/20363241/).

**[derived] grouping ratio = 1 + 5.2·w_det:** 2% → 1.10× · 3% → 1.16× · 5% → 1.26× · 8% → 1.42×.
The row-of-12 detection task is harder than optimal foveal bisection, so the realistic band
is the upper end: **grouping threshold ≈ 1.2–1.45×.** Corroboration of that magnitude:
dot-lattice studies sweep aspect ratio (ratio of the two shortest inter-dot distances) over
only **1.0, 1.1, 1.2, 1.3** and obtain a full swing of perceived organisation.

**R5.1 — THE FORBIDDEN ZONE (headline rule).**

```
For every pair of gaps compared within one visual neighbourhood:
  ratio == 1.00 (exactly equal, integer px) -> one rhythm         OK
  ratio >= 1.50                             -> a group break      OK
  1.03 < ratio < 1.50    VISIBLY UNEQUAL BUT NOT GROUPING         FAIL
```

*Why:* below ≈1.03 the difference is sub-JND (invisible, harmless); above ≈1.45 it groups;
**in between it is suprathreshold as a difference and subthreshold as a boundary** — the eye
reports "not the same" and receives no compensating structure. That is exactly the percept of
sloppiness, now a computable predicate.

**R5.2 — Spacing scale.** Adjacent tokens differ by **≥1.5×** so every step is simultaneously
suprathreshold *and* group-forming: `4, 6, 9, 14, 20, 30, 46` (1.5×) or `4, 8, 16, 32, 64`
(2×). A √2 scale sits *at* the grouping threshold — usable for tuning, but **√2 steps must
never be the sole carrier of a grouping distinction.**

**R5.3 — Within/between.** `gap_between >= 1.5 * gap_within`; use **2×** when the grouping
must survive at eccentricity, or when the groups are not also fenced by a plate or rule.

**R5.4 — Grouping strength decays exponentially with relative distance** (Kubovy's Pure
Distance Law): `p(v)/p(a) = exp(-alpha*(|v|/|a| - 1))`, depending only on relative inter-element
distance, not angle or global configuration. **The fitted α could not be verified** (§9) —
the form is verified, the constant is not. Use the 1.2–1.45 band above instead.
*Sources:* [Kubovy & Wagemans, Psych Sci 6:225–234, 1995](https://journals.sagepub.com/doi/10.1111/j.1467-9280.1995.tb00597.x);
[Kubovy, Holcombe & Wagemans, Cognitive Psychology 1998](https://www.sciencedirect.com/science/article/abs/pii/S0010028597906733).

**R5.5 — Non-local comparisons are cheap.** Remembered gap comparison has a ~10–15% JND, so
gaps in *different* regions need not match to the pixel. One shared spacing scale makes them
match for free; do not spend layout freedom on it.

---

## 6. Alignment — vernier acuity, and why 1 px is *sometimes* broken

Vernier alignment is a **hyperacuity**: threshold **2–5 arcsec** trained foveal, ≈10 arcsec
untrained — **10–12× finer** than the 1 arcmin resolution limit and *smaller than one foveal
cone* (2.5 µm ≈ 30 arcsec).
*Source:* [The Clinical Use of Vernier Acuity, PMC8523788](https://pmc.ncbi.nlm.nih.gov/articles/PMC8523788/).

The operative number is how threshold scales with **separation between the two things compared**:

```
threshold(S) = sqrt( (S/k1)^2 + k2^2 ),   1/k1 = 0.007 (Weber fraction 0.7%)
                                          k2   = 0.10..0.16 * sigma_edge
```
*Source:* [Whitaker et al., Vision Research 2002, "Isolation of stimulus characteristics
contributing to Weber's law for position"](https://psychology.nottingham.ac.uk/research/vision/papers/Whitaker%20et%20al.VR.2002.pdf)
— verified in the PDF: fits are "Weber fractions of 0.7%", plateau `k2` is "approximately
10–16% of the envelope σ". For crisp UI edges (σ ≈ 0.5 px) `k2` ≈ 0.05–0.08 px, so the linear
term dominates for any `S > 10 px`.

**R6.1 — `detectable_misalignment_px ≈ 0.007 × separation_px`.**

`S=50` → 0.35 px (1 px visible) · `S=100` → 0.70 px (visible) · **`S=143` → 1.00 px
(breakeven)** · `S=300` → 2.10 px (invisible) · `S=1000` → 7.00 px (invisible).

**This is the exact answer to "why does 1 px off-axis read as broken":** only for elements
within **S ≤ 143 px**. Beyond that 1 px is subthreshold. Long-range breakage is **chaining** —
a column of items 100 px apart transmits every pairwise error, and each hop *is* checkable.

**R6.2 — Snap all box edges to integer CSS px.** Sub-pixel positions blur the edge (raising
`k2`, harmless) *and* shift the perceived centroid (not harmless). Hyperacuity reads a
luminance centroid, so an antialiased half-pixel offset is seen as a real half-pixel offset —
it does not average away.

**R6.3 — Tolerance is zero; the *axis budget* is the real constraint.** Exactness is free for
an engine, so spend effort minimising distinct axes. Bonsiepe's layout-complexity measure
(adopted by Tullis) is computable:

```
Omega = -N * sum_i( p_i * log2(p_i) )
```
over the distribution of element coordinate classes (left edges, right edges, top edges,
widths, heights); `N` = element count, `p_i` = frequency of class `i`. **Minimise Ω.** Tullis
found **local density** and **layout complexity** the strongest predictors of search time
across 520 displays; his exact coefficients and local-density kernel are unverified (§9), so
use Ω as an objective, not a threshold.
*Sources:* Tullis, *The Formatting of Alphanumeric Displays*, Human Factors 25(6), 1983;
*A System for Evaluating Screen Formats*, 1986; Bonsiepe 1968.

**R6.4 — The counter-rule.** Collinear layouts were **faster to scan** (RT 1914 ms vs
2046 ms) but produced a far **smaller contextual-cueing effect** (43 ms vs 171 ms); location
recall accuracy was 10.1%, not above chance. **Alignment buys scan speed, not recall.** Buy
recall separately with per-zone landmarks (distinct plate shape, colour, or a unique anchor
control) so a zone is found by identity rather than by counting.
*Source:* [Zelchenko et al., arXiv:2308.12201](https://arxiv.org/pdf/2308.12201).

---

## 7. Density budgets, and hardware anchors

**R7.1 — Data-ink.** `data_ink_ratio = data_ink / total_ink`, equivalently
`1 - (fraction erasable without loss of information)`; `data_density = entries / area`.
Tufte: maximise data-ink, erase non-data-ink and redundant data-ink, "within reason". Panel
form: **ink carrying state (values, positions, active fills) / total non-background pixels.**
Every bevel, gradient, separator and frame is non-data-ink and must justify itself against
R5.3 — a rule that only restates a gap the spacing already encodes is redundant; delete it,
do not restyle it.
*Source:* [Data-Ink Ratio, InfoVis:Wiki](https://infovis-wiki.net/wiki/Data-Ink_Ratio).

**R7.2 — Tullis's four measurable screen properties:** overall density (filled/available
cells), local density (distance-weighted neighbours per element), grouping, layout complexity
(R6.3). Use as objective functions — I found no defensible published cut-off for "maximum
acceptable density" (§9).

**R7.3 — MIL-STD-1472F Table VII**, minimum **edge-to-edge** separation, one hand:
pushbutton↔anything **13 mm**; toggle↔toggle/pushbutton/thumbwheel **13 mm**;
toggle↔rotary **19 mm**; rotary↔thumbwheel **19 mm**; **rotary↔rotary 25 mm**.
Pushbutton (Fig 12): dia. min 10 mm bare fingertip / max 25 mm; separation **min 13 mm,
preferred 50 mm**; displacement 2–6 mm. Keyboard: key min 10 mm, preferred 13 mm; **key-top
separation min 6.4 mm**. Character height (Table XIII, at **710 mm** design distance, scale by
`D/710`): critical fixed markings 2.5–5 mm above 3.5 cd/m², 4–8 mm at or below.
At 108.8 CSS PPI (4.283 px/mm): 6.4 mm = 27 px · 13 mm = 56 px · 19 mm = 81 px · 25 mm =
107 px · 50 mm = 214 px. **These are finger constraints and do not bind a mouse-driven
panel** — for a mouse R3.4 (24 px pitch) governs. Cite them only for touch or 1:1 hardware
replicas.
*Source:* [MIL-STD-1472F](https://www.denix.osd.mil/soh/denix-files/sites/21/2016/03/02_MIL-STD-1472F-Human-Engineering.pdf) §5.4.1.3.7, §5.4.3.1, §5.5.5.

**R7.4 — Geometric stability.** MIL-STD-1472F §5.2.1.6.3: picture-element movement over 1 s
≤ 0.2 mrad = **41 arcsec**. Any element not *meant* to move must not drift more than
**0.5 CSS px** — at hyperacuity that is exactly detectable.

---

## 8. The validator — assertions a program runs, in order

A row that names a symbol after `→` is EXECUTED by that symbol today; the rest are
still prose, and a rule an engine cannot run is a rule it does not have. The marks
are checked from both sides (`tools/densui/tests/test_axes.py`): a named symbol
must resolve, so a rename cannot leave the claim standing.

```
A1  K, PPD, D_mm declared; all angular minima re-evaluated at K_worst = 0.89.
A2  min(font_size) >= 16.6 px, OR D_max_mm = AM*cap_mm/16 is declared as the
      design distance and D_mm <= D_max_mm.
A3  line_height >= 1.36 * font_size.
A4  light-on-dark stroke <= 1/7 cap; dark-on-light <= 1/6 cap.
A5  every edge-to-edge gap between glyph-scale features >= 3 px (foveal crowding).
A6  every hairline/separator gap >= 2 px.
A7  all box edges are integers.  → densui.audit.check_integer_edges
A8  every adjacent hit-target pair: 24 px circles on their bounding boxes do not
      intersect (=> centre-to-centre pitch >= 24 px).  → densui.audit.check_hit_pitch
A9  FORBIDDEN ZONE: for every gap pair in one neighbourhood, ratio == 1.00 exactly
      or ratio >= 1.50. Nothing in (1.03, 1.50).
A10 gap_between_groups >= 1.5 * gap_within_group (2.0 if unfenced or peripheral).
A11 every element pair sharing an alignment axis: |offset| == 0
      (threshold is 0.007*S; 0 is free, so demand 0).
A12 minimise Omega = -N*sum(p_i*log2 p_i) over edge/size classes; report the count
      of distinct left edges and distinct widths per band.
      → densui.audit.axis_census counts and reports it;
      → densui.audit.check_axis_budget spends it (controls per CONTROL x-axis >= 3).
A13 every PERIPHERAL-class element (alarm, state light):
      clear_radius_px >= b * r_px, b by meridian (right .184 / left .237 /
      lower .300 / upper .381; use .5 if unsure); tangential axis may use 0.55*b.
A14 no PERIPHERAL-class element in the upper field while a right or lower slot is
      free (2.07x crowding penalty).
A15 no layout change increases mean A/W over the measured co-use pairs
      (Fitts scale-invariance: densify uniformly or re-zone; never shrink W alone).
```

---

## 9. Dispositions (each former unknown now has a verdict — 2026-08-14 pass)

- **Kubovy's attraction constant — PARTIALLY VERIFIED.** The Pure Distance Law's
  form is confirmed against accessible sources (log-odds linear in relative
  distance (|b|−|a|)/min(|a|,|b|); Cognitive Psychology 35, 71–98, 1998), and
  the secondary literature around it reports a published parameterization of
  the attraction function (k = 150, s = −1; semanticscholar/researchgate
  adaptations of the paper's figures). The constant parameterizes dot-lattice
  phenomenology, not UI gap ratios, so R5.4's operative 1.2–1.45 band is
  UNCHANGED — the band is the design rule; the law is its justification.
- **Tullis's regression coefficients — UNVERIFIABLE via open sources.** Four
  targeted searches (2026-08-14): the four metrics and their predictive power
  confirm repeatedly; the equations live only inside Human Factors 25(6),
  657–682. The equations are used NOWHERE in this framework; if they ever
  are, the paper must be obtained first. Attempt trail recorded here so
  nobody repeats the search thinking it was never tried.
- **"25–30% maximum screen density" — DISCARDED.** No primary source exists
  on any accessible route; the number is folklore. It was never used above
  and is now formally dead: do not reintroduce it without a citation.
- **Gori & Spillmann absolute thresholds — RESOLVED BY METHOD.** The paper
  publishes ratios only (5.2× / 7.4× / 6.6×) by design; composing them with
  the spatial-interval JND literature (2–4%) is the correct permanent form,
  not a workaround. The **[derived]** marking on R5.1 is the final state.
