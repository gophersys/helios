# CONTRACT — the bench demo (stage 3, EXECUTED)

The telemetry console's backend, run for real: `densui.tree.Tree` is the
framework's stage-3 reference implementation and `densui.fakes.FakeSerial`
is the fake backend Gate 3 demands. The drills are tests in
`tools/densui/tests/test_bench_contract.py` — they run on every `ctl.sh
test`, locally and on the fleet, so the contract stage can never regress
into prose.

Drills executed (each maps to a DENSE-UI stage-3 clause):
- echo suppression by TOKEN with device coercion adopted (§7)
- unsolicited disagreement adopted and repainted (§7)
- undo keyed to source=user only (§4)
- streams refuse set(); stale-not-zero incl. the never-seen case (§10)
- disconnect honesty: unacked stays pending; reconnect report resolves (§12)
- unknown address throws from every entry point (§4)

Remaining (handoff): rate/coalescing at the seam (§5), never-move-under-the-
cursor queueing (§8), readAll() resync after reconnect, and a minimal bench
UI over this tree once the drills all stand.
