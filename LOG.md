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
