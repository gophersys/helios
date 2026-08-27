# instrumentation-contracts

phase:    intake
repo:     gophersys/eden
branch:   docs/instrumentation-contracts
worktree: ~/code/.worktrees/eden-instrumentation-contracts
pr:       -
attempt:  0/2

## Goal

Author the two DRAFT contract documents that let the observability + agent-instrumentation
program run as parallel lanes against written API agreements instead of against each other:

- **`agentprofile`** — the central schema (role × harness matrix) that is the single source of
  truth for agent instrumentation, the renderer that emits each harness's native files, the
  determinism guarantee, the commit-time drift-gate semantics, and how a rendered profile is
  addressed by a pod (artifact + digest, which the AgentPod CRD's `profileRef` points at).
- **`fleettelemetry`** — the message-kind → OTel mapping table, task-as-trace semantics, the
  durable-consumer read pattern that never competes with delivery consumers, and the UI
  streaming read model that platformgateway serves from the same consumer.

Status stays **DRAFT for negotiation**. Freezing is Mateo's §5 gate and no agent exercises it.
Each document ends with the exact freeze question Mateo must answer.

## Authority

Mateo's four design rulings, 2026-08-26, decision prompt, interactive session f9c810a8:

1. Instrumentation source of truth = **central schema + renderer** — one agentprofile schema
   (role × harness matrix: claude/omp/codex) in eden; a renderer emits each harness's native
   files (CLAUDE.md, .claude/rules, skills, settings; omp/codex equivalents).
2. **Commit-time rendering + drift gate** — rendered files are committed; CI fails on drift,
   following the estate's existing generated-file pattern.
3. Telemetry = **bus consumer** — one service consumes the fleet's JetStream messages → OTel;
   the same consumer feeds UI streaming (platformgateway SSE). No in-process exporters in
   agentsession.
4. **Task = trace across the whole tree** — the message header carries a task id and a W3C
   traceparent.

Plus the standing program directives of the same day: *"we can kick off a lot of these things
in parallel if we do api agreements up front"* and *"i want u to make bigger code changes and
test locally before submitting a pr, avoid submitting smaller code, and try to implement
features completely"*.

## Lane

FEATURE lane (`.claude/rules/git-process.md` §4 — "any contract change"). Phase 2's red-test
obligation has **no subject in this repository**: this change adds no executable surface, and
eden's affected gates select nothing outside an Nx project. That is STATED, never waived — no
agent may waive §4/phase 2 for itself. The executable proof of the `agentprofile` agreement is
the sibling `gophersys/libs` pull request (`feat/agentprofile`), whose conformance suite is
red-first and whose `phase-gate qa` runs in the devcontainer.

## Plan

(to be written after research lands)

## Proven

(populated only with commands run and output read)

## Blocked

Empty.

## Next

Read the research findings, then author `agentprofile` first — the libs lane builds against it.
