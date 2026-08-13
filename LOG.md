# LOG — append-only loop journal

Newest entries at the bottom. Format: `## <UTC ISO> — <task>` then 2-6 lines.

## 2026-08-14T07:40Z — P0 bootstrap
Repo created from the working session: framework + research corpus imported,
densui package extracted with 9 passing tests, operator demo (solver-laid-out,
gate-proven) imported, CI + loop installed. Everything after this entry is the
loop's own work.

## 2026-08-13T21:01Z — P1 densui.probe
Extracted the DOM measurement probe into the package: `probe.js` (standalone-
valid, node --check gated; glyph-ink text boxes via Range + measureText) and
`densui.probe.collect()` (cross-platform Chrome discovery, fail-loud on missing
chrome/root/output). 4 new tests incl. an ink-vs-embox proof; mutant run shown
red before green. Surprise: the JS header comment contained the output
sentinel literally and the regex matched the comment — sentinel strings must
never appear in injected source; fixed by rewording + taking the last match.
Next: P1 densui.audit consumes probe output.

## 2026-08-13T21:09Z — P1 densui.audit (sub-step 1 of 2)
The proof battery is now library code: `densui.audit` — overlap with declared
legal-overlap callables (`knob_value_graze` factory encodes the measured Live
tolerance), crowding floor, similarity-gated + interposition-aware gap law,
containment with declared spills, breathing floor, level + cross-container
alignment, and `run_battery` composing them. 8 tests, each check proven to
fail on a bad fixture (and one genuinely went red on my own fixture arithmetic
— gap 83 is hierarchical, not sloppy; the law was right and the test was
wrong). HANDOFF: sub-step 2 = rewrite demos/operator/build/overlap_audit.py
as a thin wrapper over densui.probe + densui.audit and re-run the demo gates;
the box stays ⏳ until then.

## 2026-08-13T21:19Z — P1 densui.audit (sub-step 2 of 2) ✓
demos/operator/build/overlap_audit.py is now 81 lines of declarations (parts,
graze, spill, sweep values, column key) over densui.probe + densui.audit; the
260-line bespoke original is gone. assemble.py runs it via uv --project so the
package resolves. The gate immediately caught a real wrapper bug: the global
row's LEDs carry osc.*.on owners and my alignment key read four side-by-side
LEDs as one 57px-misaligned column — key restricted to dial/checkbox. Full
demo chain green (solver, ratio, audit, sweep, params). Assembled
operator.html added to .gitignore: it embeds licensed Ableton fonts and must
never be committed. Box ticked.

## 2026-08-13T21:29Z — P1 densui.solve
The solver is now generic library code: `densui.solve.solve(spec)` takes a
dict or TOML path (tomllib, stdlib) with font + flow_rows (sequential anchored
boxes, trailing element, value-ink clearance) + knob_rows (two-line, separate
line-1/line-2 floors, centred labels, tucked values, rhythm equalisation by
construction with corrections reported). Returns pure position data — CSS
emission stays with callers. 6 tests: rhythm, floor violation, value
clearance, insertion-order determinism, flow margins/trailing, missing-font
fail-loud. Operator still runs its local solve_layout.py by design — P2's
panel.toml box migrates it onto this API with a byte-identical CSS proof.

## 2026-08-13T21:39Z — P1 densui.measure
Reference forensics as a library: exact sampling, dark-run scans, quantised
level bands (the plate/title finder), region stats (darkest/lightest/dominant
with positions), and gridline-labelled NEAREST zooms — the exact toolkit that
replaced eyeballing in the founding session, now reusable. Pillow behind a
[measure] extra with a fail-loud import message; dev extra carries it for
tests. 5 tests against a synthetic bitmap with known truth, incl. a negative
(clean row scans empty). 32 total green.

## 2026-08-13T21:47Z — P1 densui compare
A/B composites as a library: side_by_side() stacks reference over build per
region with a divider (NEAREST, no smoothing — pixels must stay honest) and
find_color_row() locates a device edge in a page screenshot. Tests verify the
layout arithmetic, that each half really shows its own source, the divider
colour, and the absent-colour negative. 34 green. P1 remaining: the CLI.

## 2026-08-13T21:49Z — P1 CLI ✓ — PHASE 1 COMPLETE
`uv run densui <solve|audit|zoom|compare>`: solve prints positions JSON from a
TOML spec; audit runs probe + battery from a [probe]/[rules] config with
optional sweep JS and exits 1 on violations; zoom and compare wrap the
forensics tools. 4 CLI tests incl. an end-to-end audit on a deliberately
overlapping fixture page (exit 1 proven) and a fail-loud bad-spec case.
38 tests green. P1 done: probe, audit, solve, measure, compare, CLI — the
whole calculus is now importable and shell-usable. Next: P2 panel.toml.

## 2026-08-13T21:54Z — P2 panel.toml schema
docs/spec.md defines the one-file panel format: [panel]/[font]/[census]/
[tracks]/[solve]/[probe]/[rules]/[ratio], each section by design the exact
input shape of its consumer, with the LAYOUT-MATH invariants stated (measured
anchors, two legal size sources, reported corrections, cited exceptions).
The canonical example is EXECUTABLE: a test extracts it from the doc, parses
it, and solves it with a real font — and on first run it caught my example
being geometrically impossible (gamma's widest value escaped the plate).
Fixed with numbers that solve. 40 tests green.

## 2026-08-13T21:59Z — P2 operator panel.toml ✓ (byte-identical proof)
Every solver number the demo owned now lives in panel.toml (anchors with
their measurement provenance in comments, floors, widest strings, static
line-2 positions, emit order); build/solve_layout.py shrank to an emitter
mapping densui.solve output onto the demo's selectors. Migration proven by
diff: old output == new output, byte for byte, after two emitter fixes
(float margin formatting; corrections precede the row, matching the old
order). The golden is committed as expected_positions.css and assemble now
FAILS on any drift from it — intended changes must regenerate the
expectation deliberately. Full demo chain green.

## 2026-08-13T22:04Z — P2 spec validation ✓ — PHASE 2 COMPLETE
densui.spec.load_panel(): every problem reported at once with its full path
and difflib did-you-mean ("units[0]: unknown key 'widst' (did you mean
'widest'?)"), plus existence checks (font path) and shape checks (ratio rows
are [want, tol]). Wired into the operator emitter before solving; docs/spec.md
updated. 4 tests: docs example validates; typo suggestion; multi-error
accumulation; missing font named. 44 green; demo chain green (drift guard
doubles as proof the emitter is untouched). P2 done: a panel is a validated
data file end to end. Next: P3 gates in CI.

## 2026-08-13T22:14Z — gophersys standards + multi-agent hardening (Mateo directive)
Adopted the house standards: ctl.sh single entry point (test/vet/fmt/build),
ci.yml now runs `./ctl.sh test` on the arc-org ARC fleet (eden/infrastructure
owns the controller). P3's remaining boxes reworded for the fleet + the cictl
review standard. LOOP.md hardened for the second agent working here: foreign
⏳ untouchable under 40 min, lock-push rejection = task taken, pull --rebase
before every push, never force-push. Two catches: `ruff format --check` was
failing on 20 never-formatted files while my pipe read tail's exit code as
the gate's (the exact swallowed-status trap) — formatted, target honest now;
and ctl.sh's params gate needed its own loud failure message.

## 2026-08-13T22:16Z — P3 fleet geometry gates (sub-step 1: wiring + local proof)
ratio_audit.py now discovers Chrome via densui.probe.find_chrome (DENSUI_CHROME
honoured) and runs inside the densui project env; ctl.sh gained a `geometry`
target with honest font selection (Ableton fidelity locally, DejaVu on
runners, DENSUI_FONT override, loud failure when none); ci.yml gained a
`geometry` job on arc-org installing chromium via playwright at job time —
if the fleet forbids that, the job fails loudly and becomes a BLOCKED.md
coordination item, per the box's own instruction. Local `ctl.sh geometry`
green end to end. HANDOFF: verify the fleet run's outcome next loop run
(gh run list) before ticking the box.

## 2026-08-13T22:27Z — P3 fleet geometry (sub-step 2: repo transferred, fleet diagnosed, model fixed)
The eternally-queued runs were structural: arc-org is the gophersys org fleet
and dense-ui lived on the personal account — transferred to gophersys/dense-ui
per Mateo's directive; first post-transfer push picked up in seconds. That run
then failed HONESTLY twice: (1) test job — no browser on the fleet image, the
probe tests refuse to pass without measuring (correct); chromium-via-playwright
step added to the test job too. (2) geometry job — the solver refused DejaVu:
"rackL/c-level: reserved boxes collide (margin -1)". Real model flaw: labels
are INK, not boxes — one may overhang empty face; the flow model now shrinks
the reserved track and reports a correction (control-box overflow stays a hard
error), with the glyph-ink audit as downstream truth. Two new tests (overflow
corrects / control box still refuses); 46 green; fidelity + Arial geometry
chains green locally. Also relearned: patch against source you have READ —
ruff format had rewritten solve.py and my first patch died on a stale match.
Box stays ⏳ pending a green fleet verdict.

## 2026-08-13T22:34Z — UI CI image + devcontainer (Mateo directive) + font-portable solver
Fleet round 2 failed on honest solver inequalities under DejaVu (value ink
crowding the next dial by <1.5px). Two fixes landed together:
(1) solver font-portability — a crowded neighbour nudges right within a
declared anchor_tolerance (default 4px), reported as a correction; beyond it,
refusal. Fidelity build produces zero nudges, golden untouched. New test.
(2) The per-job chromium install is gone as an approach: ci/Dockerfile bakes
chromium (playwright, build-time), DejaVu fonts, uv, node into
ghcr.io/gophersys/dense-ui-ci with in-image proof (densui-chromium --version)
before any tag moves; build-ci-image.yml mirrors hardware's; and the
DEVCONTAINER builds FROM the CI image, so dev and CI cannot drift — Mateo's
"develop in the same devcontainer" made structural. Sequencing: this push
builds the image; the ci.yml/on-pr.yml flip to `container:` happens once the
image is published (next run, on evidence).
