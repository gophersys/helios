# deep-craft

phase:    green
repo:     gophersys/dense-ui
branch:   feat/deep-craft
worktree: ~/code/.worktrees/dense-ui-deep-craft
pr:       -
attempt:  1/2

## Goal
A full-depth improvement pass over the dense-ui system — tooling, accuracy,
and process — aimed at one outcome: panels generated through this framework
stop reading as AI-generated. The system can now PROVE things (solver +
proof battery + CDP measurement + fleet certification), so the improvement
is done as research-backed, executable rules: programmatic (solver/audit
coverage), mathematical (ratios, spacing calculus, optical corrections),
psychological (perception constants with sources), and LLM-aware (what a
blind model gets wrong by default and which constraints prevent it).

## Plan
(dev-planner 2026-08-14; APPROVED by Mateo with one amendment, recorded here)

MATEO'S AMENDMENT (2026-08-14): build the scorecard FIRST — "so that we can
test as we go based on metrics." Adopted as W0, with the eyes-doctrine
constraint: the scorecard reports COVERAGE and FAILURES (measured classes,
violations, seeded-defect catch rate) and can never issue a pass on
"not-AI-looking"; an absent predicate reports UNMEASURED, never clean.

W0 — The craft scorecard (defect-class registry + seeded corpus + CLI)
- tools/densui/src/densui/score.py: REGISTRY of named defect classes (from
  Mateo's actual callouts: size-ratio, padding-rhythm, axis-sprawl,
  hit-pitch, fractional-edges, font-identity, component-anatomy, colour,
  plus the already-measured battery classes overlap/crowding/gap-law/
  containment/breathing/alignment). Each row: class -> predicate symbol in
  densui, or UNMEASURED. A registry row naming a symbol that does not exist
  is itself a failure.
- corpus/<class>/: one minimal page+panel.toml per class, seeded with
  exactly one deliberate defect, TELL.md naming it. Nothing Ableton.
- densui score: runs every registered predicate over the corpus and the
  demos; per-class table (measured?, violations, seed caught?); rc!=0 when
  a should-pass target fails OR a predicate misses its own seeded defect
  (a check that cannot fail is the defect). UNMEASURED rows are reported,
  not scored.
- ctl.sh score target; wired into CI alongside geometry.
Then W1 -> W2 -> W3 as planned; each must flip its class to measured, catch
its seed, and keep the demos green — the needle Mateo watches.

FINDING that sets the order: demos/telemetry/panel.toml declares [ratio]
rows that NOTHING executes — spec.py validates their shape, cli audit never
reads cfg["ratio"], run_battery has no ratio check, and ui-verifier.md
claims the ratio table runs in ctl.sh geometry (true only for operator's
hand-written ratio_audit.py). A believed check that checks nothing, on the
#1 named defect class (wrong size ratios).

W1 — Ratio rows become a general, executed predicate (START HERE)
- audit.check_ratios(probe_out, rows): rows measure "<kind>.<dim>" (h|w|cx|cy)
  or ratio = ["label.h","dial.h"], want/tol; multi-instance kinds reduce by
  MEDIAN and fail on spread > tol (spread is its own failure).
- spec.py: typed [ratio] rows; untyped pair form -> named migration error.
- probe.js: emit root rect (additive) so panel_w/panel_h are measurable.
- cli audit runs [ratio], rc!=0 on any row.
- Migrate telemetry + bench + operator specs; operator's ratio_audit.py keeps
  its Ableton rows but calls the general predicate.
- docs/spec.md + LAYOUT-MATH.md battery row names the symbol.

W2 — Axes A1/A7/A8 stop being prose
- audit.axis_census(parts): distinct left/right/centre/width/height classes,
  omega = -N*sum(p*log2 p) (psycho-math R6.3); check_axis_budget fails when
  controls / distinct axes < 3.0 (per-panel override declared in [rules]
  with a NOTES reason); check_hit_pitch (WCAG 2.5.8 circle, centre pitch
  not edge gap); check_integer_edges (A-5) on solver output always, probe
  rects only when scale == 1.
- spec [rules] keys; run_battery composition; psycho-math §8 rows marked
  with their consuming symbol; DENSE-UI A1; ui-layout skill Gate-2; and
  ui-verifier.md's ratio claim becomes true.

W3 — The rendered face is the solved face
- probe.js: per text kind report resolved family + measured advance of a
  sentinel string; audit.check_font_identity fails when it differs from
  Face.adv() by > 0.5px. Silent font fallback is a named AI tell AND
  invalidates every reserved box.

Nine tests, each with its stated fails-if (see planner output, recorded in
PR body later): ratio row got/want/tol; instance-spread own failure; cli
executes declared rows (rc 1 today would be rc 0); untyped row named
migration error; axis census counts + omega; hit pitch centre-not-edge;
integer edges scale-guarded; research constants name a live consumer
(doc-extraction idiom); font identity catches substitution (computed
advance, never getComputedStyle's declared list).

Gate: ./ctl.sh test + ./ctl.sh geometry (all three demos, telemetry's
dormant rows now live). Fleet referee: on-pr.yml on arc-org.

Risks: telemetry rows may fail the moment they execute (that is the feature
working; legal fixes are spec row or geometry, never tolerance); axis
budget may fail operator (per-panel declaration with cited reason allowed);
probe.js is on the measurement path of all demos (additive fields only);
skills/ui-verifier must move in the same commit as what they teach.

Out of scope (named next features): component-anatomy assay (needs
Page.captureScreenshot + bitmap predicates), colour/contrast/greyscale
predicates, peripheral clearance A13/A14, optical corrections in the
solver, the composed "reads as generated" discriminator (it is the
composition of these predicates; built first it is a scorecard, not a
check).

## Proven
- `git worktree add -b feat/deep-craft ... origin/main` → HEAD at 0dbf676.
- RED (W0): `uv run --extra dev pytest tests/test_scorecard.py -v` → EXIT=1,
  `12 failed, 1 passed in 0.20s`; every failure is the feature's absence
  (ModuleNotFoundError: densui.score / ImportError / argparse invalid
  choice 'score'). Whole suite `12 failed, 78 passed`, zero collection
  errors, zero regressions vs 77-passed baseline.
- Assertions BITE: scratchpad harness ran the real test functions against
  11 deliberately wrong stub implementations — 11/11 caught at red time.
  (Verifier note: re-run after implementation the harness reports 10/11 —
  stub 1's premise expired because corpus/overlap now exists; the verifier
  proved that assertion still bites independently via its BREAK 6, a class
  flipped to measured with no seed -> pytest red naming the missing dir.)
- Corpus fixture pair verified through REAL chrome on the existing audit
  path: seeded rc=1 with the overlap named; clean rc=0.
- One deliberately-green test (fixture guard) pins that CLEAN/SEEDED
  fixtures are what the battery actually sees — declared, not smuggled.

## Pinned interface (implementer builds to exactly this)
- densui.score.UNMEASURED — sentinel object, not a string.
- densui.score.REGISTRY: dict[str, Row]; Row.predicate = dotted string or
  UNMEASURED. 14 kebab-case classes; battery six map to densui.audit.
- densui.score.Target(name=..., probe_out=..., seeds=None) — kw-constructible.
- run_scorecard(targets) -> {"classes": {cls: {measured, violations,
  seed_caught}}, "failures": [str]} — top-level keys exactly those two.
- CLI: densui score --corpus <dir> — scores seed dirs PRESENT, prints
  report JSON, rc follows failures.
- corpus/<class>/{page.html, panel.toml, TELL.md} at repo root; panel.toml
  carries [probe].root; TELL.md is documentation, not parsed.

## Blocked
Nothing.

## Verify (W0) — verdicts
Verifier (read-only + reversible breaks, all restored, tree byte-identical
to 645cd3b after): breathing and gap-law seeds each went red TWO ways
(defect un-planted; probe blinded); dangling registry symbol -> pytest red
naming the row; injected "passes" key -> eyes-doctrine test red; measured-
without-seed guard bites (BREAK 6); CI steps unconditional (no continue-on-
error/if); zero test-file edits (diff 0 bytes); no masking constructs; no
[rules] overrides; no Ableton content in corpus; TELL numbers match
measured output; flake not reproduced in 3 full runs (90 passed each).
FINDINGS: F1 (medium) score CLI has no should-pass targets — demos not
wired, half the W0 sentence missing -> back to phase 3. F2 (low-med)
breathing seed catchable only under element-box probing that no production
panel uses; under production ink config the seed is NOT caught (verifier
reproduced) -> back to phase 3. F3 (low) stale 11/11 quote -> fixed above.
Pre-existing, out of scope, recorded for the PR body: ctl.sh:10 lets
grep -q decide the params gate under pipefail (SIGPIPE 141 hazard).

## Green (W0) — proven
- Orchestrator re-ran, bare rcs: `uv run --extra dev pytest -q` -> 90
  passed rc=0; `./ctl.sh score` -> rc=0, all six battery seeds caught
  (alignment, breathing, containment, crowding, gap-law, overlap),
  failures=[]. Implementer's own evidence: ruff rc=0 (+format on its two
  files), ./ctl.sh test rc=0, ./ctl.sh geometry rc=0 (demos run through the
  extracted _collect/_rules path, so the refactor is proven by that green),
  break-test on a scratch COPY of the corpus (worktree untouched):
  un-planted overlap seed -> rc=1 with "seeded overlap defect not caught".
- Count correction accepted: 90 not 91 (the 78 baseline already included
  the deliberately-green fixture guard; 77+13=90).
- Flake recorded, not claimed fixed: test_drive pointer-timing failed once
  post-change, passed 5 subsequent runs; nothing on its path touched.
- Scope note: implementer added `./ctl.sh score` to ci.yml + on-pr.yml (2
  lines) — kept: W0 says wired into CI; an unwired verb is a gate that
  does not exist.
- Breathing seed design choice documented in its TELL.md/panel.toml: value
  measured as element box (not glyph ink) so the 1.0px seed clearance is
  CSS-px stable across host fonts instead of flipping inside a 4px
  macOS-vs-CI metrics window.

## Fix round (W0 findings) — proven
- F1 fixed: score takes positional should-pass targets through the same
  _collect/_rules path (seeds=None); ctl.sh score builds the demos (shared
  build_demos() with geometry) then scores corpus + all three; unprobeable
  should-pass target rc=2 named, never skipped. Break-test: planted gap-law
  in a scratch COPY of bench -> rc=1 naming the demo target and class.
  Fleet path proven: DENSUI_FONT=DejaVu ./ctl.sh score rc=0, nine targets.
- F2 fixed: breathing seed reworked under production config
  (text_kinds=["value"]); ink clearance MEASURED across 13 mac faces
  (-0.23..+0.81px, fires on all) AND the CI image's DejaVu faces inlined as
  data URIs (-0.17px, fires); bounded band: >=1.69px to the breathing floor,
  >=1.27px to containment slack, vs 1.04px face spread. Un-planted variant
  rc=1.
- Fix 3 (drift twin, flagged by implementer, approved): operator's
  [probe]/[rules] live ONLY in panel.toml; overlap_audit.py consumes it via
  the CLI's _collect/_rules (-24 lines, dead PAGE assignment gone). Proof
  the twin is dead: one edit (remove led) moved BOTH paths 128->124 parts
  identically; before, only the score path would have moved.
- Orchestrator re-ran bare: ./ctl.sh score rc=0 (3 should-pass rows),
  pytest 90 passed rc=0. Implementer: geometry rc=0 (128 parts both paths),
  ./ctl.sh test rc=0, ruff+format rc=0, zero test-file edits.
- Follow-up noted for W1 (touches cli.py anyway): promote _collect/_rules
  to a public densui API — three consumers now (audit, score, operator gate).

## Red (W1) — proven
- 16 tests in tests/test_ratios.py, all red for the feature's absence:
  AttributeError check_ratios (6); SpecError not raised on the legacy pair
  form quoted verbatim from telemetry's panel.toml (5, incl. docs+demo
  migration demands); the dormant check CAUGHT IN THE ACT via real chrome —
  blocks 30px vs spec 45, densui audit rc=0, failures:[] (2); probe KeyError
  'root' (1); registry size-ratio UNMEASURED + missing corpus seed (2).
- Suite: 16 failed, 90 passed; collect rc=0, 106 tests, zero errors.
- Bite harnesses (scratchpad, repo untouched): reference implementation
  satisfies all 6 predicate tests; 7 wrong implementations each caught
  (dormant, always-fails, mean-not-median, no-spread, message-without-
  numbers, absent-kind-clean, inverted quotient). Corpus-completeness
  auto-bite PROVEN by execution: registry flip alone turns
  test_corpus_has_a_seed_for_every_measured_class red.
- Named in advance: two existing green tests (docs example validates,
  telemetry panel validates) MUST be migrated in the same implementation
  change; telemetry's woken rows may legitimately fail — legal fix is the
  spec row or the geometry, never the tolerance.

## Green (W1) — proven
- Orchestrator re-ran bare: ./ctl.sh score rc=0 (size-ratio measured=True
  seed_caught=True, failures=[]), pytest 106 passed rc=0. Implementer:
  ruff+format rc=0, node --check rc=0, ./ctl.sh test rc=0, ./ctl.sh
  geometry rc=0 with telemetry executing "ratios": 3 on every gate — the
  months-dormant rows now live, passing against real geometry, no want or
  tolerance touched. Break-test: un-planted seed on a scratch copy rc=1.
  Zero test-file edits. _collect/_rules promoted to public
  densui.probe_config (three consumers migrated, no behavior change,
  proven by the gates).
- Operator's hand-written ratio_audit rows deliberately NOT converted,
  with measured evidence: label ink spread 3.25px over 22 labels -> 0.12
  quotient units, would false-fire at the +-0.06 band; most rows (font
  sizes, colours, scrollHeights) have no part-kind vocabulary.
- OPEN, decided by orchestrator: telemetry's row=[72,4] has no expression
  in the pinned vocabulary (implementer measured every candidate: spanning
  parts overlap by construction, cy rows blocked by cross-row spread). The
  claim IS font-independent as a difference of ink centres (value.cy -
  label.cy = 50.00 measured = 20+2+28 derived). DECISION: a span row form
  (span = ["label.cy","value.cy"], want, tol) goes into W2's red scope;
  the un-migrated row stays as an in-file comment naming this.
- Process note: one consolidated verifier pass runs after W3 (W0 got a
  full verify; W1's evidence includes its own break-tests) — recorded so
  the PR body states it plainly.

## Red (W2) — proven
- 27 tests in tests/test_axes.py, all red for the feature's absence
  (AttributeError axis_census/check_axis_budget/check_hit_pitch/
  check_integer_edges; Rules TypeError; SpecError unknown keys; span
  KeyError at audit.py:245; telemetry lacks its row; registry UNMEASURED;
  corpus seeds absent; psycho-math §8 unmarked both directions).
- Suite 27 failed/106 passed; 133 collected, zero errors; zero regressions.
- Bite: reference implementation 18/18 green; 25 wrong predicate
  implementations all caught; doc-sweep mutations 8/8 caught (incl. the
  ASCII-arrow imposter and marks-on-wrong-axioms) against md5-verified
  untouched research file.
- Six design calls pinned and recorded (x_axes = min over left/right/cx —
  sum makes A1 unenforceable; controls = rhythm_kinds; span rows exempt
  from spread; ink exemption lives in run_battery; reason enforced on BOTH
  spec paths; census families exactly left/right/cx/w/h).
- Declined for now: extending the marker sweep to LAYOUT-MATH's axiom list
  (§8 is the scoped home; follow-up if wanted).

## W2 green attempt 1 — implementation complete, contract defects found
Implementer built everything pinned (27/27 axes tests green) and STOPPED on
three measured findings instead of papering over:
1. Test-vs-test conflict: budget composed at floor 3.0 unconditionally
   fails any <3-control panel by construction; three existing clean
   fixtures (1 dial + 1 value) went red.
2. The census population is wrong for the budget: ink centres never
   coincide, so telemetry = 6 controls / 23 axes = 0.26; operator 0.69;
   EVERY panel would need an override below 1.0 — the rule dying in config.
3. Integer edges vs reality: telemetry/bench = 10 genuine .5 dial edges
   (28px dials margin-auto centred in odd solved boxes — a REAL parity
   defect, the feature working); operator = 110 fractional edges incl. 54
   dial edges + line-height/autoscale-derived tops — needs measured
   investigation of parity semantics (odd box at .5 centre IS
   integer-edged), not blanket assertions.
Also: three older corpus seeds now carry a second (axis) violation; §8
A5/A9 left unmarked because their constants DIFFER from the research text
(3px vs 2.0 min_sibling_gap; 1.50 vs 1.45) — an honest refusal worth its
own look later.
PHASE-2 RETURN directives (orchestrator): (a) budget numerator AND
denominator over rules.rhythm_kinds — controls per control-axis; Ω may
stay whole-panel as report; (b) budget silent when controls < floor
(ratio uninformative), discriminating cases re-pinned at >=3 controls;
(c) probe-side integer-edge check scoped by a declared population
(rules.snap_kinds default ⊆ authored/solver-emitted kinds), parity-aware
semantics investigated by MEASUREMENT on operator before pinning;
telemetry/bench dial parity stays caught (geometry fix expected there).

## Next
Test author revises the W2 pins per the three directives; implementer
follows; then W3.
