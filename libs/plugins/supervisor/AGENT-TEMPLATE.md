# Supervisor AgentTemplate

This document specifies the `supervisor` **AgentTemplate** — the immutable, data-only recipe the
orchestrator's `TemplateStore` resolves to spawn a supervisor session. It binds **verbatim** to the
frozen `orchestrator` contract (`docs/architecture/contracts/orchestrator.md`, `.apibaseline` at
`libs/go/orchestrator/.apibaseline`); it defines **no new types** — one concept, one home. The
orchestrator *folds* this template (the ceiling) plus a per-spawn `SpawnRequest` (the floor) into an
`agentsession.Spec` + a `workspaceprovider.WorkspaceSpec` and never executes its contents.

## The bound contract (cited, never redefined)

`AgentTemplate` is defined in `github.com/gophersys/libs/go/orchestrator`:

```go
type AgentTemplate struct {
	Ref         TemplateRef              // identity: Name + Version (immutable pin)
	Description string                   // operator-facing summary; never a secret
	Skills      []SkillRef               // named skill modules agentconfiguration resolves to harness files
	Rules       []RuleRef                // named rule/system-prompt fragments (standing instructions)
	Grants      []agentsession.ToolGrant // the standing allowlist AS DATA (07 §3)
	Hosts       []agentsession.HostTool  // Eden-provided callback tools
	Routing     agentsession.RouteKey    // selects harness+model per phase/role; orchestrator is TOLD, never decides
	Sandbox     SandboxSpec              // substrate + resource envelope + egress
	Limits      Limits                   // max-concurrent class ceiling + per-session token budget
	Labels      map[string]string        // free-form selectors for fleet/rollout grouping
}
```

with `SandboxSpec`, `Limits`, `TemplateRef`, `SkillRef`, `RuleRef`, `Substrate` from the same
package, and `agentsession.{ToolGrant,HostTool,RouteKey,Budget}` from
`github.com/gophersys/libs/go/agentsession`. The `TemplateStore.Resolve(ctx, TemplateRef) →
(AgentTemplate, error)` seam (orchestrator `Deps.Templates`) returns this value.

## The supervisor template value

```
AgentTemplate{
  Ref:         TemplateRef{ Name: "supervisor", Version: "0.1.0" },
  Description: "Deterministic project-manager: drives a project init lifecycle (charter → product → decisions → plan → build) as a git-derived FSM, acting only through typed slash-commands.",

  // ── Capability surface ───────────────────────────────────────────────────────────
  // The operating manual itself (instructions/ + the typed commands) is mounted as the
  // supervisor's rules+skills. agentconfiguration resolves these refs to the harness-native
  // files — which, for claude-code, is exactly the rendered template/.claude/ this plugin ships.
  Skills: []SkillRef{
    { Name: "supervisor-operating-manual", Version: "0.1.0" }, // the .claude commands + FSM driver
  },
  Rules: []RuleRef{
    { Name: "supervisor-identity",       Version: "0.1.0" },   // instructions/00-identity.md
    { Name: "supervisor-state-machine",  Version: "0.1.0" },   // instructions/10-state-machine.md
    { Name: "supervisor-git-protocol",   Version: "0.1.0" },   // instructions/20-git-protocol.md
    { Name: "supervisor-hard-interfaces",Version: "0.1.0" },   // instructions/30-hard-interfaces.md
    { Name: "supervisor-artifact-schemas",Version: "0.1.0" },  // instructions/40-artifact-schemas.md
  },

  // ── Grants: BROAD-but-CLAMPED (the supervisor reasons widely but ACTS only through commands) ──
  // The grant set is intentionally NARROW at the tool level even though the role is broad: the
  // supervisor's breadth is in WHAT it decides, not in WHAT it touches. It may read the whole
  // project and run ONLY the typed command scripts + read-only git. Every grant is data; the
  // orchestrator folds these verbatim into agentsession.Spec.Grants. The strict sandbox + the
  // ADR-0025 risk-class wall (high-risk tools can never be advisor-auto-allowed) are the clamp.
  Grants: []agentsession.ToolGrant{
    { ID: "read",      Tool: "Read",  ReadOnly: true },
    { ID: "glob",      Tool: "Glob",  ReadOnly: true },
    { ID: "grep",      Tool: "Grep",  ReadOnly: true },
    { ID: "git-ro",    Tool: "Bash",  Scopes: []string{"git status *","git ls-files *","git log *","git diff *","git show *"}, ReadOnly: true },
    // The ONLY write-capable grants are the eight typed command scripts — the hard interface.
    { ID: "cmd-state-show",            Tool: "Bash", Scopes: []string{"bash ./.claude/commands/state-show.sh *"} },
    { ID: "cmd-propose-charter",       Tool: "Bash", Scopes: []string{"bash ./.claude/commands/propose-charter.sh *"} },
    { ID: "cmd-ratify-charter",        Tool: "Bash", Scopes: []string{"bash ./.claude/commands/ratify-charter.sh *"} },
    { ID: "cmd-propose-questionnaire", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/propose-questionnaire.sh *"} },
    { ID: "cmd-open-decision",         Tool: "Bash", Scopes: []string{"bash ./.claude/commands/open-decision.sh *"} },
    { ID: "cmd-rule-decision",         Tool: "Bash", Scopes: []string{"bash ./.claude/commands/rule-decision.sh *"} },
    { ID: "cmd-plan",                  Tool: "Bash", Scopes: []string{"bash ./.claude/commands/plan.sh *"} },
    { ID: "cmd-advance",               Tool: "Bash", Scopes: []string{"bash ./.claude/commands/advance.sh *"} },
  },

  // No Eden host-callback tools at v0 (the supervisor reads the repo directly; project-data host
  // tools are an AssistantSession concern, 07 §3). Hosts is empty.
  Hosts: nil,

  // ── Routing: Role=supervisor → resolved to {claude-code, opus-4.8} by agentconfiguration ──
  // The template names the RouteKey; agentconfiguration (02 §5, C22) owns the RouteKey→Route table
  // that binds it to Harness "claude-code" + Model "opus-4.8" (the standing directive: subagents
  // and fleets run on Opus). The orchestrator carries this key and never decides the model.
  Routing: agentsession.RouteKey{ Phase: "supervise", Role: "supervisor" },

  // ── Sandbox: the strict, long-lived workspace the FSM runs in ───────────────────────────────
  Sandbox: SandboxSpec{
    Substrate:   SubstrateKubernetes, // ADR-0012 default; docker for local dogfooding via ClusterRef at Spawn
    Image:       "ghcr.io/gophersys/base", // the devcontainer base: claude pinned (ADR-0021), jq baked
    Resources:   ResourceEnvelope{ CPUMillis: 1000, MemoryMiB: 2048, EphemeralMiB: 4096 },
    EgressAllow: []string{ /* model provider only (default-deny, 07 §3); the supervisor needs no extra egress — git is local to the workspace */ },
    Env:         map[string]string{ "EDEN_AGENT_ROLE": "supervisor" }, // non-secret; never a credential
    // The project repo IS the supervisor's memory; it is cloned into the workspace by gitrepository
    // (passed through WorkdirRepo; the per-spawn RepoMount.Auth is an OPAQUE secrets.Reference).
    // Entrypoint empty == the classic Ready-then-Run workspace (the supervisor is interactive/looped,
    // not a one-shot workload pod).
  },

  // ── Limits: a LONG budget (a supervisor session spans the whole init lifecycle) ──────────────
  Limits: Limits{
    MaxConcurrent: 1,                          // one supervisor per (Tenant, Template) — a project has one PM
    Budget: agentsession.Budget{
      MaxCostMicros: 0,                         // 0 == unbounded HERE; the engine still enforces the project TokenBudget (02 §2)
      MaxTurns:      0,                         // 0 == harness default (the FSM bounds progress, not a turn cap)
      MaxWall:       0,                         // 0 == ctx bounds it; a supervisor is long-lived across many transitions
    },
  },

  Labels: map[string]string{ "eden.role": "supervisor", "eden.lifecycle": "init" },
}
```

## How the orchestrator resolves + folds it

1. **Resolve.** A consumer (the engine, or a control-plane "start the project manager" action) calls
   `Manager.Spawn(ctx, SpawnRequest{ Template: TemplateRef{"supervisor","0.1.0"}, Tenant: …,
   Credential: <opaque secrets.Reference>, By: …, RunID: … })`. Reconcile calls
   `Deps.Templates.Resolve` to obtain this `AgentTemplate`.
2. **Fold (template = ceiling, request = floor).** The orchestrator compiles `Sandbox` →
   `workspaceprovider.WorkspaceSpec`, folds `Grants`/`Hosts`/`Routing`/`Budget`/`Rules`/`Skills`
   into the `agentsession.Spec`, threads the opaque `Credential` through to
   `agentsession.Spec.Credential` (resolved server-side at `Open`, never the value), and applies any
   per-spawn tightening (`BudgetOverride`, a narrower grant subset). A request may only **tighten**;
   widening is an `InvalidRequestError`.
3. **Spawn & track.** `workspaceprovider.Provision` brings up the strict sandbox, the agentsession
   adapter launches claude-code inside it with the rendered `.claude/` operating manual, and the
   `Pool` tracks the agent (`StatusPending → Provisioning → Running`) and emits `PlaneAgent`
   observability the whole way. The supervisor then drives the FSM transition-by-transition; the
   chat surface tails `agentsession.Session.Events` off `Agent.Session` directly.

## Permission posture (ADR-0025)

The supervisor is broad-but-clamped: its grants are narrow (read + the eight command scripts), and an
out-of-grant request runs the ratified resolution chain — chat human → advisor → default-deny, or,
autonomous, advisor → default-deny — with the verdict **clamped by the risk class** computed from the
tool+scope DATA. A destructive/egress/credential tool is `riskClass==high` and can never be
advisor-auto-allowed, regardless of any prose in the args. The strict sandbox (ADR-0022) is the
containment behind every decision. The supervisor never needs a high-risk grant: its only writes are
through the typed commands, which stage canonical artifacts and let the orchestrator commit.

## Provenance

Like an `Archetype` (02 §2), this AgentTemplate is **data with provenance**, immutable once published
(editing == publishing a new `Version` — a governed act), and never hand-edited at the use site. The
`0.1.0` recipe corresponds to the operating manual rendered under `template/.claude/` in this plugin
directory; a change to the manual (new command, new state, new schema) is a new template version.
