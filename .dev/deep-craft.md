# deep-craft

phase:    plan
repo:     gophersys/dense-ui
branch:   feat/deep-craft
worktree: ~/code/.worktrees/dense-ui-deep-craft
pr:       -
attempt:  0/2

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
(dev-planner, 2026-08-14; pending Mateo's approval)

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

## Blocked
Nothing.

## Next
dev-planner returns a plan; STOP and show Mateo.
