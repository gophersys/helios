# agentsession-peer-plane

phase:    red
repo:     gophersys/libs
branch:   feat/agentsession-peer-plane
worktree: ~/code/.worktrees/libs-agentsession-peer-plane
pr:       -
attempt:  0/2

## Goal
PR-1c/S4 — THE feature the program is named for. On a base that now has both
adapters ready (claude native cross-session messaging pin 2.1.234; omp one
long-lived rpc process able to host a library-owned message plane), add the peer
plane + the subagent channel to agentsession:
- PeerPlane/PeerLink port (VISIBLE types, ~31 additive .apibaseline lines — NOT
  methods on the unexported session, which apidiff cannot see); orchestrator-root
  TREE topology, msg_id reconciliation, roster.
- claudeadapter rides native cross-session messaging (peer.go); ompadapter exposes
  eden_peer_send/eden_peer_list host tools (peer.go).
- The SUBAGENT channel as a DISTINCT function (two payload types, two capabilities;
  a subagent NEVER appears in the peer roster — the non-conflation asserts).
- Spec.Name/Parent, Deps.Peer, Event.Peer/.Subagent, CapPeerMessaging/CapSubagentMessaging.
- The harness lane: skip sites → t.Fatalf; two real programs in ONE container exchange
  a message (msg_id correlation both ways — bidirectional registration, not one-way
  receipt); N-agent + orchestrator concurrent mesh. Real agents, gated, never mocks.

## Plan
plan: SELF-APPROVED (--auto). SPLIT ADOPTED (planner's recommendation, the design's own
named seam §7.3): THIS is PR-1c-i = the peerplane package + the whole contract (Spec.Name/
Parent, Deps.Peer, Event.Peer/.Subagent, 3 EventKinds, 2 Capabilities, peer.go port,
controlframe peer codec) + fake-driven conformance + the real-UDS/real-process proof +
the harness lane authored under -tags harness. PR-1c-ii (deferred) = claudeadapter/
peer.go (native + --name/--settings argv, unexported/zero baseline delta) + ompadapter/
peer.go (eden_peer_send/list host tools). Peer+subagent cohesion stays in i; only the
harness-specific bindings defer — and their only live proof was always eden's lane.
Risk weighed: apidiff-record + the docs/architecture R1 contract-revision MUST land in
THIS PR (the ~31-line surface growth is the invisible-change class the whole design
guards) — the plan makes it a same-PR requirement.
Canonical plan = planner report (task ae68d5e195d3fa53c). Load-bearing:
- CORRECTION adopted: controlframe PeerPrefix/EncodePeer/DecodePeer are SCALAR-ONLY
  (from/to/msgID/replyTo/body string + verified bool) — an agentsession.PeerMessage
  param would cycle (identifiers.go imports controlframe).
- Port: PeerPlane (2 methods) + PeerLink (4), VISIBLE exported types (NOT methods on
  *session — apidiff-blind). Deps.Peer accepts the port; peerplane.New→*Orchestrator.
  unixsocket binding lands here; natsbus is the fleet slice, same port no change.
- Tree: orchestrator root, msg_id ledger + reconciler; SILENT-HOLD (a held peer msg is
  invisible both sides — proven) ⇒ root-side reconciliation with a DeliveryDeadline
  bounce recording UndeliveredError, NEVER a timeout guess.
- Non-conflation: subagent NEVER in Roster(); the plane API has no overload accepting a
  SubagentMessage (compile-enforced) + a fake-driven test; live proof = eden.
- Open validation: Deps.Peer!=nil && Name=="" ⇒ ConfigError (a session that believes
  it is reachable and is not).
- Harness lane obligations A/B/C authored under -tags harness (t.Fatalf, no skip); run
  in eden's harness-conformance at PR-2, NOT libs CI (no credential/harness). libs CI
  proves the plane over real UDS + real OS processes, credential-free.
- SO_PEERCRED Linux-only: Listen fails CLOSED + named on unsupported platform.
- Gates: phase-gate all + apidiff-record same PR; _ctl/lib.sh harness verb additive
  (shared by 16 libs — care). Tests 1-8 per plan, each with its falsification.

## Proven
-

## Blocked
-

## Next
Phase 2: dev-test-author writes tests 1-8 + the -tags harness obligations red (the
apidiff red is the surface-not-yet-added; the property/reconciler/socket reds need the
port symbols — controlframe precedent: compile-dep reds in their own commit, bite proven
against a naive scratch reference). Big slice — expect multiple red commits.
