# EYES — when looking is allowed, and when it may never decide

The founding premise of this repository: the engine laying out these panels
cannot see, and — the part that took eight fleet rounds to fully accept —
when it *tries* to see, it misreads. This doctrine is not a preference; it
is the incident record generalized.

## The incident record (why this doctrine exists)

| What eyes said | What measurement said | Cost |
|---|---|---|
| Knob Ø ≈ 20 (scanline read) | Ø 27 — the scan crossed a chord, not the diameter | one full geometry rebuild |
| Display split ≈ 63:37 | 151:160 — misread of a crop | grid clipped for three rounds |
| Values "tuck into the ring" | ink sits clear, below-right — a misread legalized as an audit exception | "text on knobs", user-visible |
| Arial ≈ DejaVu (proxy testing) | different advances broke four fleet rounds | four rounds |
| "The fidelity grid fits" | it overflowed 13px behind a spill allowance, always | a hidden lie in every prior green |

Every one of these passed visual inspection. Every one fell to arithmetic.

## The rules

1. **Eyes are for DISCOVERY, never for verdicts.** Zoomed anatomy reads
   (8×, gridline-labelled — `ui.measure.zoom`) and reference-vs-built
   composites (`ui.compare`) exist to generate HYPOTHESES: "the needle
   looks dark", "the row seems two-line". Every hypothesis then becomes a
   measurement (`ui.measure`), a spec entry, or it dies.
2. **A gate may never pass because something "looks right".** Pass criteria
   are: the solver's inequalities, the ratio table, the glyph-ink battery,
   the sweep, the drills, and gesture behaviour via `ui.drive` — all
   numeric, all named, all bare-exit-code. A screenshot is not an argument.
3. **A gate may FAIL from looking** — a human (or a model) seeing something
   wrong is a valid *bug report*. The fix path is mandatory: decompose the
   observation into a failed predicate (two names and a number), add or
   tighten the predicate, prove it red, then fix. "Looks off" that cannot
   be decomposed goes to the census as an open question, not into CSS.
4. **When eyes and math disagree, measure again — do not average.** Each
   disagreement in the record above was resolved by a second measurement
   with a better instrument, never by splitting the difference.
5. **Proxies are eyes at one remove.** Testing with a stand-in font,
   viewport or renderer "close to" the target is visual judgement wearing a
   lab coat; the fleet's real environment is the referee (Arial vs DejaVu,
   four rounds). Local proxies may develop, never certify.
6. **The one legitimate pure-taste zone**: hue families and prose (bench
   NOTES §2, telemetry NOTES §5). The framework constrains colour ROLES and
   state semantics; it does not claim taste. Name taste as taste.

## The toolchain mapping

| Purpose | Tool | May decide a gate? |
|---|---|---|
| anatomy discovery | measure.zoom / compare.side_by_side | no |
| geometry truth | solve + audit battery + ratio + sweep | YES |
| face identity | audit.check_font_identity (sentinel advance at 16px vs solved face) | YES |
| behaviour truth | drive scenarios, contract drills | YES |
| bug reporting | any pair of eyes | fail only, via a new predicate |

Rule 5's four lost rounds are now a predicate. A substituted face is invisible
to every other row of this table — parts carry glyph INK, and ink is where the
glyphs are, never which face drew it — so "Arial ≈ DejaVu" could only be
refuted by the fleet, one round at a time. It is now measured per text kind, on
the page, against the face the boxes were solved from, and it fails the gate
instead of the round.
