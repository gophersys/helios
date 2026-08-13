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

All nine drills now stand: the three above landed with the seam (§5/§9 —
last-write-wins per address, queue bounded by construction), under-cursor
queueing (§8), and readAll() resync (§12) — where the drill itself surfaced
the lost-write semantic: a pending address absent from the reconnect report
REVERTS to confirmed truth, because the panel must never show a setpoint the
hardware does not hold. Remaining (handoff): a minimal bench UI over this
tree — the panel part of the box.
