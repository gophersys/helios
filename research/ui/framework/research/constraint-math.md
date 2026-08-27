# Constraint-Based Layout Systems — executable rules for a blind layout engine

Scope: what a constraint *is* mathematically, why our flex "gap packing" drifts with label width, what the minimum
solver for a sightless agent must contain, and how to *prove* a layout is legal with geometry instead of eyes. Every
rule below is a formula, a number with units, or a decision procedure. Sources at the end; inline `[n]` refs.

## 1. What a constraint is (Cassowary / Auto Layout)

**R1.1 — A constraint is a linear (in)equality over real coordinate variables.** Form: `a₁x₁ + … + aₙxₙ {=, ≤, ≥} c`. UI
example straight from the paper: "figure1 is to the left of figure2" is `figure1.rightSide ≤ figure2.leftSide` [1
p.1-2]. Auto Layout's serialised form is the same object with a multiplier: `item1.attr1 = multiplier × item2.attr2 +
constant`, relation ∈ {=, ≤, ≥} [4]. WHY: linear arithmetic is the largest class that a simplex solver decides exactly,
in polynomial time, with no floating-point search.

**R1.2 — Strengths are a hierarchy, not weights.** `required` is special and must hold; all other strengths are
preferences, and "a constraint of a given strength completely dominates any constraint with a weaker strength" [1 §1.1].
Cassowary uses `required, strong, weak` in its examples but permits any finite number of levels [1 §1.1].

**R1.3 — Error function (metric comparator), exact.** For `l = 0`: `e(cθ) = |lθ|`. For `l ≤ 0`: `e(cθ) = lθ if lθ > 0,
else 0` [1 §1.1]. A predicate comparator is *wrong* for inequalities; use the metric one [1 §1.1].

**R1.4 — Comparator = weighted-sum-better on a lexicographic error tuple.** θ maps to `[Σ_{c∈H₁} e(cθ), …, Σ_{c∈Hₙ}
e(cθ)]`; θ beats σ iff its tuple is lexicographically smaller [1 §1.1]. Paper's example: `required 2xₘ = x_l + x_r;
strong x_r = 90; weak x_l = 50; weak x_r = xₘ + 10` → tuples `[20,0]` vs `[0,10]`, the second wins. Consequence: **no
number of weak preferences can outvote one strong one.**

**R1.5 — Symbolic weights, not big constants.** Cassowary rejects "make strong 1000× weak" because "for sufficiently
large values for the constrained variables, we might nevertheless end up in a situation in which weak constraints were
satisfied in preference to strong ones" [1 §2.3]. Objective: `[1,0,…,0]·Σ_{δ∈Δ₁}δ + [0,1,…,0]·Σ_{δ∈Δ₂}δ + … +
[0,…,1]·Σ_{δ∈Δₙ}δ` [1 §2.3]. Kiwi *does* collapse to floats: `create(a,b,c)=a·10⁶+b·10³+c`, so `weak=1`, `medium=1 000`,
`strong=1 000 000`, `required=create(1000,1000,1000)=1 001 001 000`, and it warns that "a large number of weak
constraints may outweigh a medium constraint" [3]. **Rule: < 1000 weak constraints per medium, or use symbolic
ordering.**

**R1.6 — Non-required constraints compile to error variables.** `strength l = 0` ⇒ `required l = e_l ∧ strength e_l =
0`; `strength l ≥ 0` ⇒ `required l − e_l ≥ 0 ∧ required e_l ≥ 0 ∧ strength e_l = 0` [1 §1.1]. Edits/stays become `v = α
+ δ⁺_v − δ⁻_v`, δ ≥ 0, with δ⁺,δ⁻ in the objective [1 §2.3].

**R1.7 — Auto Layout's numbers.** Priority ∈ [1, 1000]; 1000 = required. An intrinsic content size of `{100, 30}` with
compression resistance 750 and content hugging 250 generates exactly four constraints: `H:[label(<=100@250)]
H:[label(>=100@750)] V:[label(<=30@250)] V:[label(>=30@750)]` [4]. WHY: "resist shrinking below content" (750) must beat
"resist growing past content" (250), otherwise text truncates before whitespace collapses. **Adopt these two numbers
verbatim.**

**R1.8 — Determinism comes from tie-breaking, not from the solver.** Cassowary breaks pivot ties with Bland's rule: "we
number the variables… we choose the lowest numbered variable" [1 §2.2]. **Any layout solver we ship must define a total
order on elements (stable IDs) or two runs can differ.**

**R1.9 — What Cassowary CANNOT do: non-overlap.** Non-overlap is a *disjunction* of linear constraints, and simplex
solves conjunctions only. This is the single most important negative result for us — see §2.

## 2. Non-overlap by construction (the axis-choice theorem)

**R2.1 — The exact non-overlap condition** for boxes u, v with centres (x,y) and size (w,h):

```
x_v − x_u ≥ ½(w_v+w_u)  ∨  x_u − x_v ≥ ½(w_v+w_u)
∨ y_v − y_u ≥ ½(h_v+h_u)  ∨  y_u − y_v ≥ ½(h_v+h_u)          [5 §2]
```

**R2.2 — Collapse the disjunction by picking one disjunct.** Dwyer/Marriott/Stuckey: "the first [idea] is to approximate
each non-overlap constraint by one of its disjuncts. The second is to split it into two separate optimization problems,
one for the x dimension and one for the y" [5 §2]. Once the disjunct is chosen the problem is linear/convex again.

**R2.3 — Choose the disjunct by penetration depth.** Their selection functions:

```
olap_x(u,v) = (w_u+w_v)/2 − |x⁰_u − x⁰_v|
olap_y(u,v) = (h_u+h_v)/2 − |y⁰_u − y⁰_v|        [5 §3]
```
Separate on the axis with the **smaller** overlap (least movement). Overlap exists iff both are > 0 — this is also the
AABB test in centre form (see R6.1).

**R2.4 — Separation constraint canonical form:** `u + a ≤ v`, `a ≥ 0` the minimum gap [5 §4]. Everything a dense panel
needs (min gutters, alignment, ordering) is expressible here.

**R2.5 — The placement problem (VPSC):** minimize `Σᵢ wᵢ(vᵢ − dᵢ)²` subject to the separation constraints, `dᵢ` =
desired value, `wᵢ ≥ 0` = importance [5 §4]. Quadratic keeps everything as close to its *designed* position as possible
while making overlap impossible — exactly the repair semantics wanted after a label grows.

**R2.6 — Cost bounds.** Scan-line generation is `O(|V|·k(log|V|+k))` producing `O(k|V|)` horizontal constraints (k = max
nodes overlapping one node); the vertical pass emits **≤ 2|V|** constraints [5 Thms 1, 3], and both guarantee "no nodes
will overlap in any solution" [5 Thms 2, 4]. Microseconds for a 200-control panel.

**R2.7 — Tabstops make overlap impossible without any solver.** ALM (Auckland Layout Model) "switches focus from the
cells of the grid to the tabstops between cells"; elements attach to shared horizontal/vertical tabstop lines and an
algorithm generates the constraints that keep the layout non-overlapping [6]. **Rule: a dense panel is a set of
x-tabstops and y-tabstops; a control owns a rectangle between four of them. Two controls that share no tabstop cell
cannot overlap — proved structurally, not tested.**

## 3. Why our flex "gap packing" drifts (the exact bug)

**R3.1 — Packing is a prefix sum, so drift is structural.** With items laid main-start to main-end at gap g, the left
edge of item k is `x_k = p + Σ_{i<k}(wᵢ + g)`, hence `∂x_k/∂wᵢ = 1 for every i < k`. One glyph wider on label 2 moves
labels 3…n by the same amount. Flexbox sizes each item from its content: the hypothetical main size comes from
`flex-basis`/`width`/content [7 §9.3], and `max-content` is "the narrowest width that fits content if no soft wrap
opportunities are used" [8].

**R3.2 — `justify-content: space-between` makes the drift NON-LOCAL.** Spec: first subject flush with start edge, last
flush with end, "the spacing between any two adjacent alignment subjects is the same" [9]. So with container inner main
size C and n items:

```
s = (C − Σᵢ wᵢ) / (n − 1)
x_k = p + Σ_{i<k} wᵢ + k·s
∂x_k/∂w_j = [j < k] − k/(n−1)        ∈ [−1, +1]
```

**Every control's position depends on every label's text.** That is our bug in one line: changing the string "Res" to
"Resonance" moves controls that come *before* it too.

**R3.3 — The flex resolution loop.** §9.7 [7]: (1) pick grow or shrink by comparing Σ hypothetical sizes to the
container; (2) freeze zero-flex items; (3) initial free space; (4) loop {remaining free space; distribute ∝ flex factors
— for shrink use the **scaled flex shrink factor** `flex-shrink × inner flex base size`; clamp to min/max; `total
violation = Σ(clamped − unclamped)`; positive → freeze min-violators, negative → freeze max-violators, zero → freeze
all}. Terminates in ≤ n passes (each freezes ≥ 1 item). And `min-width: auto` on a flex item = its **content-based
minimum size** [7 §4.5] — an invisible floor made of text.

**R3.4 — The fix, as a formula.** A fixed track (`px`) is resolved from the container size alone, without reference to
content [10 §11.4]. Therefore in a fixed track grid or a tabstop model `∂x_k/∂w_j = 0 ∀ j`. **Rule: in a dense
fixed-size panel, no position may be a function of any text width. Text is placed *into* a reserved box; it never sizes
one.**

**R3.5 — Corollary for numeric readouts.** Reserve the box from the widest *possible* value, not the current one:
`w_reserved = max over the enumerated value set of measured width`, and render digits with the OpenType `tnum` (Tabular
Figures) feature so glyph advances are uniform [11] ⇒ `∂w/∂value = 0`.

## 4. Intrinsic size without eyes (font + asset metrics)

**R4.1 — Text advance width.** `width_px = (Σ advanceᵢ + Σ kernᵢ) × fontSize_px / unitsPerEm`, advances in font design
units from `hmtx`, `unitsPerEm` from `head`. Never estimate from character count.

**R4.2 — Line box height.** When `fsSelection` bit 7 (USE_TYPO_METRICS) is set, the spec's own recommendation is
`lineHeight = (sTypoAscender − sTypoDescender + sTypoLineGap) × size / unitsPerEm` [12]. `usWinAscent`/`usWinDescent`
are a **clipping** rectangle — using them for line spacing is "strongly discouraged" [12].

**R4.3 — Optical alignment metrics.** `sCapHeight` = baseline→cap top, `sxHeight` = baseline→x-height, both in design
units [12]. To centre a label optically against a control of height H, align the **cap band**, not the em box:
`baseline_y = cy + (sCapHeight × size / unitsPerEm)/2`.

**R4.4 — Two legal sources of an element's size, and only two.** (a) measured font/asset metrics; (b) a declared
constant in the design token file. A guessed number is a defect. This is the blind-agent version of Auto Layout's
`intrinsicContentSize` → four constraints (R1.7).

**R4.5 — Intrinsic-size vocabulary to copy.** `min-content` = smallest size with no avoidable overflow (all soft wraps
taken); `max-content` = ideal size given infinite space; and the exact clamp `fit-content = max(min-content,
min(max-content, stretch-fit))` [8].

## 5. Anchor model (what the agent actually writes)

**R5.1 — An anchored box is `(anchor element, anchor side, offset, self-alignment)`.** CSS anchor positioning resolves
`anchor(--name side)` to the length that aligns the positioned box's inset-modified containing-block edge with that edge
of the anchor's box; `center` / `<percentage>` interpolate between the anchor's start (0%) and end (100%) [13].

**R5.2 — The 3×3 region grid is the right coarse vocabulary.** `position-area` builds four lines per axis
(containing-block start, anchor start, anchor end, containing-block end) → nine regions plus `span-*` [13]. Our "above /
below / left / right / tucked" tokens should map 1:1 onto these nine, so the model is closed and finite.

**R5.3 — Fallback is an ordered list, first-fit wins.** Spec: a box that overflows its inset-modified containing block
tries its position options in order, skipping the currently-active one first for stability, and keeps current styles if
none fit [13]. **Rule: every label declares an ordered candidate list; take the first candidate whose rect passes §6; if
none pass, FAIL LOUDLY rather than pick the least-bad.**

**R5.4 — Use cartography's canonical ranking as the default order.** Christensen/Marks/Shieber's standard 8 candidate
positions with desirability (lower = better) [2 Fig. 1]:

```
2 | 1        upper-left = 2, upper-right = 1
--•--        lower-left = 3, lower-right = 4
3 | 4        top = 6, right = 5, left = 7, bottom = 8
```
So the default order is: **UR, UL, LL, LR, R, T, L, B**.

**R5.5 — Keep the candidate set tiny, on purpose.** PFLP with 4 equally-favoured positions is already NP-hard [2 §2];
but "a placement model that allows only two potential positions for each label results in a problem that is solved
easily in polynomial time (Formann and Wagner, 1991)" [2 §2]. **Rule: ≤ 2 candidate positions per label in the default
policy; more only where a validator proves the local sub-problem is conflict-free.**

**R5.6 — Continuous polar placement is prior art.** Hirsch's model gives each point feature an infinite set of positions
on a circle centred on it, with the label sliding around the circle and pinned at the four cardinal tangency points [2
§3.4]. That is exactly the "tucked at an angle around a knob" model, 1982.

## 6. Validation geometry (the blind agent's eyes)

**R6.1 — AABB intersection.** Rects overlap iff `a.x0 < b.x1 ∧ b.x0 < a.x1 ∧ a.y0 < b.y1 ∧ b.y0 < a.y1`. Signed
clearance:

```
sx = max(a.x0 − b.x1, b.x0 − a.x1)
sy = max(a.y0 − b.y1, b.y0 − a.y1)
clearance(a,b) = max(sx, sy)          # separation on EITHER axis suffices (R2.1)
```

**R6.2 — Minimum-gap matrix.** `G[type_a][type_b]` in px, symmetric, from the spacing scale. Check `clearance(a,b) ≥
G[ta][tb]`, else report `(a, b, clearance, required)`. Populate from a 4 px base scale {4, 8, 12, 16, 24, 32}: label↔own
control 4, control↔control 8, group↔group 16, plate↔plate 24. A matrix, not one number: a readout tucked to *its own*
knob is a different relation from two unrelated knobs.

**R6.3 — Touch/aim floor, citable.** WCAG 2.2 SC 2.5.8: targets ≥ **24 × 24 CSS px**, or for undersized targets "if a 24
CSS pixel diameter circle is centered on the bounding box of each, the circles do not intersect another target or the
circle for another undersized target" [14] ⇒ executable: `dist(centre_a, centre_b) ≥ 24 px`.

**R6.4 — Sector-based legal overlap (text tucked into a knob's open ring).** Real knobs have a dead sector. JUCE's
default rotary parameters are `startAngleRadians = π·1.2` (216°) and `endAngleRadians = π·2.8` (504° ≡ 144°), measured
**clockwise from 12 o'clock** [15] ⇒ a **288° active sweep and a 72° dead sector spanning 144°→216°, centred exactly on
180° (bottom)**. Procedure, with knob centre c, ring radii `[r_i, r_o]`, dead sector `[θ₀, θ₁]`:

```
for each sample point p of the label rect (4 corners + edge midpoints + the point of
the rect closest to c):
    r = |p − c|
    θ = (atan2(p.x − c.x, c.y − p.y) mod 2π)          # clockwise from up
    if r_i ≤ r ≤ r_o and θ ∉ [θ₀, θ₁]:  VIOLATION
```
Cheap pre-filter: skip if `d_min(rect, c) > r_o` or `d_max(rect, c) < r_i`. **Rule: legal overlap is declared per
control as an (r_i, r_o, θ₀, θ₁) annulus-sector exclusion, never as "looks fine".** Default for a 288°-sweep knob:
`θ₀=144°, θ₁=216°`, and shrink to `[152°, 208°]` (a 4° guard each side) before allowing a tucked label.

**R6.5 — Containment.** For every element e with plate P: `P.x0 ≤ e.x0 ∧ e.x1 ≤ P.x1 ∧ P.y0 ≤ e.y0 ∧ e.y1 ≤ P.y1`. This
is ReDeCheck's *element protrusion* — an element that was a child at one width becomes a sibling because it overflowed
its parent [16 RLF 2].

**R6.6 — Adopt ReDeCheck's failure taxonomy, retargeted.** Its five failures (element collision, element protrusion,
viewport protrusion, small-range layout, wrapping) are detected from a graph of relations — contained / child / sibling,
alignment attributes L, R, CJ, LJ, above, overlap — not from pixels [16 §3]. For a fixed-size panel the sweep axis
becomes **content length, not viewport width**:

| ReDeCheck | Dense-UI analogue | Check |
|---|---|---|
| element collision | control/label overlap | R6.1 + R6.2 |
| element protrusion | escapes its plate | R6.5 |
| viewport protrusion | escapes the panel | R6.5 against panel rect |
| small-range layout | legal only for one string length | sweep shortest→longest value in the enum, assert the relation set is constant |
| wrapping elements | a row silently gains a line | assert row cardinality and y-tabstop count are invariant |

**R6.7 — Ambiguity check (underconstrained ⇒ non-reproducible).** Auto Layout ships `hasAmbiguousLayout` and
`exerciseAmbiguityInLayout`, which perturbs the solution to reveal that more than one satisfies the constraints [4].
Mandatory analogue: **solve twice — once in declaration order, once reversed — and assert byte-identical integer
geometry.** A difference means the spec is ambiguous, not that the second run is bad.

**R6.8 — Integers only.** Blink lays out in `LayoutUnit` = fixed point **1/64 px** (chosen over Gecko's 1/60 app units
so conversions are shifts, not divisions) and snaps to device pixels at paint [17]. **Rule: compute in whole px or
1/64-px integers, never floats; a non-integer final coordinate is a bug, not a rounding detail.**

**R6.9 — Declarative assertions are prior art and they scale.** Cornipickle expresses "desirable properties of a web
application as a set of human-readable assertions on the page's HTML and CSS data", checked live; its authors classified
90+ real layout bugs across 35 sites [18]. Layout correctness is an assertion-language problem, not a screenshot
problem.

## 7. The minimal solver for a blind agent

**R7.1 — Five inputs, nothing else.**
1. `intrinsic(e) → (w, h)` from font/asset metrics or a declared token (R4.4).
2. `anchor(e) = (target, side, offset, self-align)` (R5.1), offsets drawn from the token scale.
3. spacing tokens: one base unit u (4 px) and the set {1,2,3,4,6,8}·u.
4. container constraints: panel rect, plate rects, tabstop lines (R2.7).
5. a deterministic solve order.

**R7.2 — Solve order = topological sort of the anchor DAG.** Edge `u → v` iff v's position references u; then one `O(n)`
pass. **Cycles are a hard error.** Cassowary tolerates cycles ("a solver that can handle cycles of both equality and
inequality constraints is thus highly desirable" [1 §1]) only because it is a global simplex; a blind agent should
refuse them so that every coordinate has a single readable derivation.

**R7.3 — Parent proposes, child answers, parent places.** SwiftUI's `Layout` protocol is the cleanest two-phase shape:
`sizeThatFits(proposal:subviews:)` then `placeSubviews(in:proposal:subviews:)` [19]. Phase 1 = pure function of
intrinsic sizes, phase 2 = pure function of phase 1. No phase may read a later phase's result.

**R7.4 — Overflow recovery, in this fixed order** (flexbox §9.7 [7], proven terminating): freeze inflexible → free space
→ distribute ∝ flex factor → clamp to min/max → freeze violators → repeat. Prepend step 0: *before* shrinking anything,
try the next anchor candidate (R5.3). Shrinking text is last because compression resistance (750) outranks hugging (250)
(R1.7).

**R7.5 — When a real solver is warranted.** `kiwisolver` (maintained Cassowary, matplotlib's layout backend) is a pip
install away and exposes exactly R1.1–R1.6 [3]. Use it only when tabstops + DAG cannot express the intent; prefer the
DAG, because then every coordinate has a one-line explanation the agent can print.

**R7.6 — Report, never repair silently.** Every validator returns `(rule_id, element_a, element_b, measured, required,
unit)`; a failing layout fails the build. A check that could not run (missing font metrics, unmeasurable glyph) is a
FAILURE, not a pass — the discipline that let ReDeCheck's authors drop the oracle image [16].

## Sources

1. Badros, Borning, Stuckey — *The Cassowary Linear Arithmetic Constraint Solving Algorithm*, ACM TOCHI 8(4), 2002. https://constraints.cs.washington.edu/solvers/cassowary-tochi.pdf
2. Christensen, Marks, Shieber — *An Empirical Study of Algorithms for Point-Feature Label Placement*, MERL TR94-12 / ACM TOG 14(3):203-232, 1995. https://merl.com/publications/docs/TR94-12.pdf
3. kiwisolver docs — *Solver internals and tips* (strengths, `create_strength`, float caveat). https://kiwisolver.readthedocs.io/en/latest/basis/solver_internals.html
4. objc.io — *Advanced Auto Layout Toolbox* (intrinsic content size → 4 constraints; alignment rect; `hasAmbiguousLayout`, `exerciseAmbiguityInLayout`). https://www.objc.io/issues/3-views/advanced-auto-layout-toolbox/
5. Dwyer, Marriott, Stuckey — *Fast Node Overlap Removal*, GD'05, LNCS 3842:153-164. https://people.eng.unimelb.edu.au/pstuckey/papers/gd2005b.pdf
6. Auckland Layout Model (Lutteroth/Weber) — tabstop-based GUI layout, non-overlap constraint generation. https://aucklandlayout.sourceforge.net/
7. W3C — *CSS Flexible Box Layout Module Level 1*, §4.5 automatic minimum size, §9.5 main-axis alignment, §9.7 resolving flexible lengths. https://www.w3.org/TR/css-flexbox-1/
8. W3C — *CSS Box Sizing Level 3* (min-content, max-content, fit-content clamp). https://www.w3.org/TR/css-sizing-3/
9. W3C — *CSS Box Alignment Level 3* (`space-between` normative definition). https://www.w3.org/TR/css-align-3/
10. W3C — *CSS Grid Layout Level 1*, §11 track sizing algorithm (fixed tracks resolved without content). https://drafts.csswg.org/css-grid-1/
11. Microsoft — OpenType feature tag `tnum` (Tabular Figures). https://learn.microsoft.com/en-us/typography/opentype/spec/features_pt
12. Microsoft — OpenType `OS/2` table: sTypoAscender/Descender/LineGap, usWin*, sxHeight, sCapHeight, USE_TYPO_METRICS. https://learn.microsoft.com/en-us/typography/opentype/spec/os2
13. W3C/CSSWG — *CSS Anchor Positioning Level 1*: `anchor()`, `position-area`, `position-try-fallbacks`, overflow-driven fallback. https://drafts.csswg.org/css-anchor-position-1/
14. W3C — *Understanding SC 2.5.8 Target Size (Minimum)*, WCAG 2.2 (24×24 px, 24 px circle spacing exception). https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
15. JUCE — `juce_Slider.cpp` default `rotaryParams.startAngleRadians = π·1.2`, `endAngleRadians = π·2.8`. https://github.com/juce-framework/JUCE/blob/master/modules/juce_gui_basics/widgets/juce_Slider.cpp
16. Walsh, Kapfhammer, McMinn — *Automated Layout Failure Detection for Responsive Web Pages without an Explicit Oracle*, ISSTA 2017. https://eprints.whiterose.ac.uk/id/eprint/116989/10/c50-3.pdf
17. WebKit/Chromium — `LayoutUnit` subpixel layout (1/64 px; Gecko app units 1/60; pixel snapping at paint). https://trac.webkit.org/wiki/LayoutUnit
18. Hallé et al. — *Declarative layout constraints for testing web applications* (Cornipickle). https://www.sciencedirect.com/science/article/pii/S2352220816300293
19. Apple — SwiftUI `Layout` protocol: `sizeThatFits(proposal:subviews:cache:)` / `placeSubviews(...)`. https://www.swiftuifieldguide.com/layout/layout/
