# ADR-0025: The agent permission system — grants, human, advisor, and the risk-class wall

- **Status:** Accepted (the model ratified by the founder, 2026-06-15; realized in `libs/go/agentsession`
  + `libs/go/agentruntime` across slices — see Implementation status)
- **Date:** 2026-06-15
- **Deciders:** Mateo (ratified the resolution chain + the advisor authority bound, 2026-06-15)

## Context

`agentsession` (the harness-agnostic session port) already models tool permission as a round-trip:
a tool request outside the standing `Spec.Grants` allowlist surfaces as an `EventPermissionRequest`,
resolved either by an out-of-band human `session.Resolve(requestID, Decision)` or by the synchronous
`Spec.OnPermission` policy; the normalized answer is an internal `eden:permission:<id>:<verdict>:<by>`
control frame (cited, not redefined — `agentsession.go`/`session.go`/`pump.go`). `HostTool`s are
Eden-provided tools the agent calls back into (`host_tool_call → Handler → host_tool_result`).

The ADR-0020 crown-jewel audit surfaced that this whole surface was **fake-only on the live path**:
the real claude/omp adapters never translated the normalized frame into the CLI's native
permission-response, so a live decision leaked to the CLI **as a stdin user prompt** (a message the
model ignores), and `HostTool.Handler`/`Schema` were never registered with the live CLI. The fake
adapter parsed the frame, hiding the gap. Separately, the only out-of-grant auto-resolver was a static
`OnPermission` (default-deny) — fine for safety, but it gives an unattended/autonomous session no
intelligent way to proceed.

This ADR rules the **complete permission system**: the resolution model, the **advisor** (an agent
that adjudicates another agent's request), the **risk-class wall** that bounds the advisor, and the
**native-protocol** obligation on every adapter.

## Decision

### 1. The resolution model

`Spec.Grants` (the allowlist **as data**, config-as-code; mirrors claude `--allowedTools` / omp
`SyncTools`) is checked first → auto-allow, no prompt. An out-of-grant request runs a **per-session
resolution chain** (a `Spec` setting):

- **Chat:** `EventPermissionRequest` → out-of-band human `Resolve` → on **timeout** → the **advisor**
  → default-deny.
- **Autonomous (no human):** the **advisor** → default-deny.

The terminal fallback is **always default-deny** (fail-safe). With no advisor injected, the chain
degrades to the existing `OnPermission`/default-deny — no regression.

### 2. `Decision = {Verdict, Scope, By, Rationale}`

`Scope ∈ {once, session}`. `Scope:session` dynamically widens **this running session's** grant set so
the same tool is not re-asked this session — **never** persisted to the config-as-code grants. The
chat UI offers *allow-once / allow-for-session / deny* (a different tool still escalates).

### 3. The advisor — an agent adjudicating an agent

A `PermissionAdvisor` **port** in the agentsession contract (agentsession stays pure — it does **not**
spawn agents). The **implementation lives in the runtime** (`agentruntime`, which can spawn agents),
injected as a dependency. It spawns a **bounded, max-thinking reasoning session** — *no out-of-grant
tools* (it reasons, it does not act, so no recursive permission), a wall-clock + token budget (no hang
/ runaway, default-deny on error) — given the request (tool+args+reason) and a **context bundle**: the
session goal/role/phase, the higher-level product/task intent, the standing grants, a recent-transcript
snippet, and the security posture (never a secret value). It returns a `Decision` + a **`Rationale`
that is audit-logged** — every AI-made permission decision is explainable.

### 4. The risk-class wall — the prompt-injection boundary

The advisor's authority is bounded by a **risk class derived from the tool + scope (DATA), never the
agent's prose**: a pure `riskClass(tool, scopes) → {low, medium, high}` over a documented table
(read-scoped/reversible → low/medium; destructive/irreversible/egress/credential/write-outside-workspace
→ **high**). The **clamp** is applied to the advisor's verdict **inside agentsession**, so it holds for
*any* advisor implementation: `riskClass == high ∧ advisor said allow ⇒ override to deny` (or escalate
to a human if a human path exists). Prompt-injection can argue all it wants in the tool args; it can
**never talk the advisor past the high-risk wall**, because the wall reads data, not words. The strict
sandbox (ADR-0022) remains the containment behind every decision.

### 5. Native protocol — no decision ever leaks as a prompt

Every harness adapter MUST translate the normalized permission/host-tool model onto the CLI's **native
control protocol**, never a stdin user turn:

- **claude** (stream-json control channel): a `control_request{subtype:can_use_tool}` is the ask
  (→ `EventPermissionRequest`); the answer is a `control_response` carrying the `PermissionResult`
  (`{behavior:allow, updatedInput}` / `{behavior:deny, message}`), correlated by `request_id`;
  `--permission-prompt-tool stdio` is load-bearing (without it headless claude silently auto-allows).
  Host tools are in-process **SDK-MCP servers** (the `initialize` control_request advertises
  `sdkMcpServers`; `mcp_message` JSON-RPC routes `tools/list` from `HostTool.Schema` and `tools/call`
  into `HostTool.Handler`).
- **omp**: the `--approval-mode` approval-request/response frames + the host-tool channel (the
  symmetric translation).

## Consequences

- The human round-trip works for real on a live agent (the chat: *agent asks → you approve/deny → it
  proceeds or is blocked*).
- Unattended/autonomous sessions get an **intelligent** permission decider that is still hard-bounded
  by the risk wall — safe autonomy, not all-or-nothing default-deny.
- The platform dogfoods itself: an agent adjudicates an agent, with an explainable, audited rationale.
- Adapters carry a real protocol obligation; a fake-only permission round-trip is now a known
  anti-pattern (the enforcement is the live-harness gated test, never the fake alone — ADR-0016 §2).

## Implementation status

- **Slice 1 — claude native control-channel (done, live-verified):** `can_use_tool → EventPermissionRequest`,
  `Resolve → control_response`, SDK-MCP host-tool registration; the human round-trip PASSES on live
  claude (allow→tool runs, deny→blocked). `CapHostTools=CapPartial` (honest — the live `tools/call`
  completion is a documented follow-up).
- **Slice 2 — the advisor + risk-class wall + Decision.Scope + the resolution chain:** the agentsession
  contract + the agentruntime advisor impl.
- **Pending:** the omp native protocol (gated on omp being baked into the devcontainer image, ADR-0021);
  the claude host-tool live-`tools/call` completion.
