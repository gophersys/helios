# agentsession-peer-plane

phase:    intake
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
(pending phase 1 — canonical design design-artifacts/synthesis-1.json sliceBoundaries
[S4/PR-1c] + the execution-proven claude contract memory claude-cross-session-headless-
contract; PeerPlane = two-binding port, unixsocket now / natsbus at the fleet slice.
Program approval: Mateo 2026-08-18. FULL MESH v1 decided.)

## Proven
-

## Blocked
-

## Next
Phase 1: dev-planner.
