# NOTES — what the framework could NOT decide (the honest remainder)

The PLAN requires each demo to say where the method ran out. For the blind
telemetry console:

1. **Interaction and the contract stage are unexercised.** This demo is a
   static render (Gate 2's own form). Stage 3 — the parameter tree, a fake
   serial backend, staleness timers actually firing, the ilimit
   hold-to-engage — is the bench demo's job (next box), where CONTRACT is the
   point. The framework decided the *shape* of all of it (census directions,
   staleness deadlines, degraded renders); it has not yet run.
2. **Stream-cell placement is derived but not solver-owned.** The V/I cells
   hang off each rail's solved centre with hand-derived offsets from
   layers.md's arithmetic. The grid_rows model should absorb them; until
   then the audit (which passes) is the only guard on that geometry.
3. **The alarm rail is a placeholder** ("FAULTS / (none)"). The census's
   derived over-limit flags and tele.fault.last have no rendered life yet —
   they need the contract stage's fake backend to mean anything.
4. **No cold-read test.** The framework's Gate-3 drill needs a stranger; a
   blind demo built and audited by the same agent cannot supply one. UNRUN,
   recorded, not waived.
5. **Aesthetics were decided by exactly one taste call**: the neutral
   slate/green palette. Everything geometric came from the calculus; the hue
   family did not — the framework constrains colour ROLES, not colour taste,
   and says so (A4). This is the honest edge of "blind".
