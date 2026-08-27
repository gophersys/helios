# fleet-contracts

phase:    intake
repo:     gophersys/eden
branch:   docs/fleet-contracts
worktree: ~/code/.worktrees/eden-fleet-contracts
pr:       -
attempt:  0/2

## Goal

Author the four DRAFT contract documents that turn the locked 2026-08-18 agent-fleet
architecture into API agreements parallel implementation lanes can build against:
`fleetenvelope` (the message spine), `fleetbus` (NATS JetStream subject/stream/consumer
contracts), `agentpod` (the CRD schema + lifecycle state machine) and `fleetcheckpoint`
(the turn-boundary checkpoint format, bound to the FROZEN `objectstorage` port and NOT to
MinIO). Status stays **DRAFT for negotiation**; freezing is Mateo's §5 gate and no agent
exercises it.

## Authority

- Mateo, 2026-08-26, verbatim: *"we can kick off a lot of these things in parallel if we do
  api agreements up front"* and *"i want u to make bigger code changes and test locally
  before submitting a pr, avoid submitting smaller code, and try to implement features
  completely"*.
- The blueprint's fleet-leg ledger row (`docs/plans/eden-rework-blueprint.md:1918`) defers
  the fleet leg with the trigger **"Mateo schedules the fleet program"**, and states in the
  same cell: *"The architecture is already decided (agent-fleet rulings, 2026-08-18:
  role-pods, JetStream planes, frozen envelope, CRD controller); what is deferred is
  building it, not designing it."* The trigger has fired; this change is the designing
  half the row already blesses.
- Three further rulings, Mateo 2026-08-26 (decision prompt, interactive session f9c810a8):
  TASK = TRACE across the whole tree · telemetry taps at a BUS CONSUMER, not in-process ·
  instrumentation = a central agentprofile schema + renderer with a commit-time drift gate.

## Lane

FEATURE lane (`.claude/rules/git-process.md` §4 — "any contract change"). Phase 2's
red-test obligation has **no subject in this repository**: the change adds no executable
surface, and eden's affected gates select nothing outside an Nx project. That is stated,
never waived — no agent may waive §4/phase 2 for itself. The executable proof of the
`fleetenvelope` agreement is the sibling `gophersys/libs` pull request, whose conformance
suite is red-first and whose `phase-gate qa` runs in the devcontainer.

## Plan

SELF-APPROVED. Risk weighed: authoring four contracts at once risks one of them drifting
from the locked rulings. Mitigation — every normative statement carries its source (a
2026-08-18 ruling id, a blueprint `file:line`, or a frozen contract section), and an
independent adversarial refutation runs claims-vs-sources before the PR opens.

## Proven

(populated only with commands run and output read)

## Blocked

Empty.

## Next

Extract the locked design facts from the fleet design artifacts, then author
`fleetenvelope` first — it is the spine the other three cite.
