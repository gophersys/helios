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
