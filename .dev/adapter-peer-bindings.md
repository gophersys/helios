# adapter-peer-bindings

phase:    intake
repo:     gophersys/libs
branch:   feat/adapter-peer-bindings
worktree: ~/code/.worktrees/libs-adapter-peer-bindings
pr:       -
attempt:  0/2

## Goal
PR-1c-ii — the deferred half of the peer slice: bind the merged peer plane to the two
real harnesses so a running agent can actually send and receive.
- claudeadapter/peer.go: ride NATIVE cross-session messaging (the execution-proven
  contract: --name <id>, --settings '{"crossSessionInbound":"accept"}', the receiver's
  delivery-triggered result event carries origin{msg_id,name,body,...}, sender's
  SendMessage tool result carries the same msg_id). Normalize inbound to
  EventPeerMessage / outbound acceptance to EventPeerSent.
- ompadapter/peer.go: eden_peer_send / eden_peer_list host tools on the merged rpc
  host-tool router; the library-owned plane carries the traffic.
- Both bindings: ZERO .apibaseline delta (unexported); CapPeerMessaging claude=Partial
  (cross-harness send from a claude model is v1-out-of-scope), omp per its plane role.
Live proof is eden's harness lane at PR-2 (libs CI has no credential/harness).

## Plan
(pending phase 1 — inputs: the MERGED peerplane + peer port (b54976d); the claude
contract memory claude-cross-session-headless-contract.md; the committed probe fixtures
design-artifacts/claude-peer-receive*.stream.jsonl incl. the HELD pair + claude-peer-send.json;
the merged ompadapter rpc host-tool router as the omp-side model; synthesis-1.json S4.)

## Proven
-

## Blocked
-

## Next
Phase 1: dev-planner.
