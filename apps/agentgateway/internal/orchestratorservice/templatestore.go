package orchestratorservice

import (
	"context"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
)

// supervisorTemplateRef pins the supervisor AgentTemplate this service resolves — the
// immutable Name+Version the create-saga names on a Spawn (libs/plugins/supervisor's 0.1.0
// recipe). It is the ONE template the v0 store knows; a TemplateRef naming anything else is a
// TemplateNotFoundError.
var supervisorTemplateRef = orchestrator.TemplateRef{Name: "supervisor", Version: "0.1.0"}

// supervisorTemplateStore is the in-memory orchestrator.TemplateStore the docker-first service
// resolves the supervisor AgentTemplate through. It is hand-authored (a small static store) for
// the v0 single-instance posture: the real template authoring/publishing plane (the engine's
// governed template registry) lands later behind this SAME read-only Resolve seam with no
// surface change. It defines NO new types — it returns the existing orchestrator.AgentTemplate
// value the supervisor AGENT-TEMPLATE.md specifies, compiled to the requested substrate.
//
// Its zero value is unusable; construct it with newSupervisorTemplateStore so the substrate is
// frozen at the edge (the docker-first composition passes SubstrateDocker; the kubernetes
// composition passes SubstrateKubernetes — the only difference between the two deployments).
type supervisorTemplateStore struct {
	substrate orchestrator.Substrate
}

// static assertion: the store binds the frozen orchestrator.TemplateStore port (Resolve only).
var _ orchestrator.TemplateStore = supervisorTemplateStore{}

// newSupervisorTemplateStore freezes the substrate the supervisor template's sandbox compiles
// to. The docker-first service passes orchestrator.SubstrateDocker (the local single instance);
// the kubernetes deployment passes SubstrateKubernetes — the AGENT-TEMPLATE.md ceiling otherwise
// identical (ADR-0012: substrate selects mechanism only).
func newSupervisorTemplateStore(substrate orchestrator.Substrate) supervisorTemplateStore {
	return supervisorTemplateStore{substrate: substrate}
}

// Resolve returns the immutable supervisor AgentTemplate for the supervisor ref, or a wrapped
// TemplateNotFoundError (KindNotFound) for any other ref. It binds orchestrator.TemplateStore
// verbatim; the orchestrator FOLDS the returned value (it never executes it).
//
//nolint:gocritic // contract: TemplateStore.Resolve takes the TemplateRef by value (the frozen port surface).
func (s supervisorTemplateStore) Resolve(_ context.Context, ref orchestrator.TemplateRef) (orchestrator.AgentTemplate, error) {
	if ref != supervisorTemplateRef {
		return orchestrator.AgentTemplate{}, errors.Wrap(errors.KindNotFound,
			"orchestratorservice: resolve template",
			&orchestrator.TemplateNotFoundError{Ref: ref})
	}
	return s.supervisorTemplate(), nil
}

// supervisorTemplate builds the supervisor AgentTemplate value the AGENT-TEMPLATE.md specifies,
// with the sandbox compiled to this store's frozen substrate. Every field is data the
// orchestrator folds; nothing here is a live handle or a secret value (the per-spawn credential
// rides the SpawnRequest as an opaque secrets.Reference, never this template).
func (s supervisorTemplateStore) supervisorTemplate() orchestrator.AgentTemplate {
	return orchestrator.AgentTemplate{
		Ref:         supervisorTemplateRef,
		Description: "Deterministic project-manager: drives a project init lifecycle (charter -> product -> decisions -> plan -> build) as a git-derived FSM, acting only through typed slash-commands.",

		Skills: []orchestrator.SkillRef{
			{Name: "supervisor-operating-manual", Version: "0.1.0"},
		},
		Rules: []orchestrator.RuleRef{
			{Name: "supervisor-identity", Version: "0.1.0"},
			{Name: "supervisor-state-machine", Version: "0.1.0"},
			{Name: "supervisor-git-protocol", Version: "0.1.0"},
			{Name: "supervisor-hard-interfaces", Version: "0.1.0"},
			{Name: "supervisor-artifact-schemas", Version: "0.1.0"},
		},

		// BROAD-but-CLAMPED: read the whole project + the typed command scripts + read-only git. The
		// supervisor's breadth is in WHAT it decides, not WHAT it touches. The orchestrator folds these
		// verbatim into agentsession.Spec.Grants — this auto-allow set MUST stay in sync with the
		// template's .claude/commands/*.sh (the FSM transitions); a missing grant stalls the supervisor.
		Grants: []agentsession.ToolGrant{
			{ID: "read", Tool: "Read", ReadOnly: true},
			{ID: "glob", Tool: "Glob", ReadOnly: true},
			{ID: "grep", Tool: "Grep", ReadOnly: true},
			{ID: "git-ro", Tool: "Bash", Scopes: []string{"git status *", "git ls-files *", "git log *", "git diff *", "git show *"}, ReadOnly: true},
			{ID: "cmd-state-show", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/state-show.sh *"}},
			{ID: "cmd-propose-questionnaire", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/propose-questionnaire.sh *"}},
			{ID: "cmd-record-answer", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/record-answer.sh *"}},
			{ID: "cmd-propose-charter", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/propose-charter.sh *"}},
			{ID: "cmd-ratify-charter", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/ratify-charter.sh *"}},
			{ID: "cmd-propose-work-item", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/propose-work-item.sh *"}},
			{ID: "cmd-open-decision", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/open-decision.sh *"}},
			{ID: "cmd-rule-decision", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/rule-decision.sh *"}},
			{ID: "cmd-plan", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/plan.sh *"}},
			{ID: "cmd-advance", Tool: "Bash", Scopes: []string{"bash ./.claude/commands/advance.sh *"}},
		},

		// No Eden host-callback tools at v0 (the supervisor reads the repo directly).
		Hosts: nil,

		// Role=supervisor -> agentconfiguration resolves {claude-code, opus} (the standing
		// Opus directive). The orchestrator carries this key and never decides the model.
		Routing: supervisorRouteKey, // cite the one canonical key (service.go); the pool routes it to claude-code

		Sandbox: orchestrator.SandboxSpec{
			Substrate:   s.substrate,
			Image:       "ghcr.io/gophersys/base",
			Resources:   orchestrator.ResourceEnvelope{CPUMillis: 1000, MemoryMiB: 2048, EphemeralMiB: 4096},
			EgressAllow: nil, // model provider only (default-deny, 07 §3); git is local to the workspace
			Env:         map[string]string{"EDEN_AGENT_ROLE": "supervisor"},
			// Entrypoint empty == the classic Ready-then-Run workspace (the supervisor is
			// interactive/looped, not a one-shot workload pod).
		},

		// A LONG budget: a supervisor session spans the whole init lifecycle. 0 == unbounded
		// HERE; the engine still enforces the project TokenBudget (02 §2). One supervisor per
		// (Tenant, Template) — a project has one PM.
		Limits: orchestrator.Limits{
			MaxConcurrent: 1,
			Budget:        agentsession.Budget{MaxCostMicros: 0, MaxTurns: 0, MaxWall: 0},
		},

		Labels: map[string]string{"eden.role": "supervisor", "eden.lifecycle": "init"},
	}
}
