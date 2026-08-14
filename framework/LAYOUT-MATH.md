# LAYOUT-MATH — the blind layout calculus of Dense-UI

An LLM cannot see. Screenshots into its context are lossy, and every judged
pixel is a guess that failed this project three times (a chord read as a
diameter; 63:37 read for 151:160; a text *top* placed with no line-box model).
Therefore: **layout is computed, never judged; correctness is proved, never
seen.** This document is the calculus. Synthesized from `research/typo-math.md`,
`research/constraint-math.md`, `research/psycho-math.md` — all constants there
are measured or cited from primary sources, and each file lists what could NOT
be verified rather than inventing it.

## Axioms

- **A-1. Two legal sources of size.** Every element dimension comes from
  (a) font metrics computed from the TTF (`px = units/upm × size`), or
  (b) a declared token. A guessed number is a defect.
- **A-2. No coordinate is a function of any text width.** Packed flex has
  `∂x_k/∂w_i = 1` for all i<k — every label edit moves every later control;
  `space-between` makes every text move ALL controls. Text renders INTO a
  reserved box sized from the widest enumerated string (tabular figures for
  digits); it never sizes one. Fixed tracks have derivative 0.
- **A-3. The baseline is the only vertical anchor for text.**
  `baselineY = boxTop + lineHeight/2 + (A′−D′)/2`. Centre by cap, not by box:
  `baselineY = (H + cap_px)/2`; the box-centring error is `(cap − A′ + D′)/2`
  and is font-specific — compute it, never nudge it.
- **A-4. Three text boxes, three jobs.** Layout box (h = lineHeight,
  w = Σadvances) for reservation; em box for line stacking; **glyph ink box**
  (`actualBoundingBoxAscent/Descent` per string) for collision. Em boxes of
  stacked lines may legally overlap; ink boxes may not.
- **A-5. Integers only.** Snap every edge to whole px and every text to a
  4-px rhythm where possible. Vernier acuity detects misalignment at
  `0.007 × separation` — 1 px reads as broken up to S ≈ 143 px, and sub-pixel
  offsets do not average away (the eye reads the luminance centroid).

## The gap laws (why panels read as sloppy or natural)

- **G-1. Forbidden zone.** Within one neighbourhood, any two gaps are either
  **equal (±3%, the detection JND)** or differ by **≥ 1.5×**. Ratios inside
  (1.03, 1.5) are visibly unequal yet not hierarchical — that interval IS the
  computable definition of "sloppy". (Grouping needs ≈5× the detection JND.)
- **G-2. Grouping is a ratio.** `gap_between_groups ≥ 1.5 × gap_within_group`
  (2× when the group must read pre-attentively).
- **G-3. Floors.** 3 px foveal crowding gap between ink; 2 px hairline;
  24 px hit-target pitch (WCAG 2.5.8 circle test); line-height ≥ 1.36× for
  running text (UI single-line labels may go tighter — the em box guards them).

## The solve procedure (deterministic, no solver dependency)

1. **Tokens**: spacing scale on a 4-px unit; 3–4 type sizes, ratio 1.125–1.2;
   the grid outranks the ratio (quantise line-heights to the unit).
2. **Tracks first**: columns/rows are fixed tracks solved from the container:
   `(W − 2M − (n−1)G) mod n == 0` — make it integral by moving the margin,
   never the tracks. A zone is a subtree; a track is never content-sized (A-2).
3. **Reserve text boxes** from the widest formatted string of each parameter
   (the failure string included), using TTF advances at the chosen size.
4. **Anchor** each part as `(target, side, offset, self-align)`; label
   candidate order follows cartography: UR, UL, LL, LR, R, T, L, B — at most
   two candidates per label (four is already NP-hard).
5. **Priorities** (Auto Layout's constants verbatim): required=1000,
   compression-resistance 750 > content-hugging 250 — whitespace collapses
   before text ever truncates.
6. **Non-overlap is a disjunction** — no linear pass can state it. Choose the
   separation axis per pair by smaller penetration
   (`olap_x = (w_u+w_v)/2 − |x_u−x_v|` vs `olap_y`), then the constraint is
   linear: `right(u) + gap ≤ left(v)`.
7. **Declared legal overlaps** only: text tucked into a knob ring is legal in
   the annulus dead sector (the arc's open bottom: sweep 270° ⇒ θ∈[135°,225°]
   measured from 12 o'clock; strict form `r_i ≤ |p−c| ≤ r_o ∧ θ in sector`).
   Everything undeclared that intersects is a defect.

## The proof battery (run, never assert)

| Check | Predicate | Catches |
|---|---|---|
| Overlap | pairwise AABB on glyph-ink/border boxes; declared exceptions only | things on top of each other |
| Crowding | min-gap matrix, floors from G-3 | touching parts |
| Gap law | all same-neighbourhood gap pairs: equal ±3% or ≥1.5× | the "sloppy" interval |
| Containment | child ⊆ parent content box (±1.5 px; declared spills only) | escapes |
| Alignment | same-role edges/centres equal ±0.5 px within a rack; snapped to ints | 1-px "broken" reads |
| Ratio table | rendered boxes vs the measured reference table ±5% | drift toward library defaults |
| Content sweep | re-validate with every enum at its widest string | value-dependent breakage |
| Determinism | solve twice in reversed element order; identical output | order-dependent layout |

A check that cannot run is a failure, not a pass. Every check names both parts
and the numbers when it fails.

## Psychophysics constants the layout consumes

(Every constant below is verified or [derived]; the research file's §9 now
carries a DISPOSITION for each former unknown — nothing here rests on an
unresolved citation.)

- px↔arcmin bridge: `K = 3437.75·(25.4/PPI)/D_mm`; reference K=1.34 (45 px/deg).
- Fitts: `ID = log2(A/W + 1)` is scale-invariant — densify uniformly for free;
  halving W at fixed A costs ~233 ms per acquisition. Cut travel (re-zone)
  before cutting target size.
- Peripheral clearance to be identified without a saccade:
  `clear ≥ b·r_px`, b = .184 right / .237 left / .300 lower / .381 upper —
  dense panels can never afford it, so optimise saccade TARGETING (plate
  luminance/colour landmarks), not peripheral identification. Alarms right/below.
- Type sets viewing distance: `D_max = 3437.75 · cap_mm / 16`.
- Light-on-dark strokes run one weight lighter (1/7–1/8 cap vs 1/6–1/7).

## How the blind engine works end to end

REASON gives the census (strings, widest strings, kinds). This calculus turns
it into rectangles: tracks → reserved boxes → anchors → separations, all in
integers, all from metrics and tokens. The proof battery then replaces eyes:
overlap, crowding, gap law, containment, alignment, content sweep. What a
sighted reviewer calls "it looks off" decomposes into a failed predicate with
two names and a number — which is the only critique a blind system can act on,
and the only one it can be sure of.
