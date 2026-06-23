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
	// inPod selects the IN-POD supervisor variant (ADR-0022 §4): when true the template's sandbox is a
	// WORKLOAD POD (Entrypoint = the agent-runtime binary as PID-1) that clones the project repo itself
	// and runs the supervisor session in-pod, instead of the host-side Materializer + Ready-then-Run
	// workspace. Default FALSE — the existing host-side template is byte-IDENTICAL when off (the live
	// demo path), so this variant is purely additive and flag-gated.
	inPod bool
	// inPodNATSURL is the bus URL the in-pod agent-runtime binary dials (folded into the in-pod
	// Sandbox.Env as EDEN_NATS_URL). Read only when inPod is true; "" lets the pod default to
	// nats.DefaultURL. The repo URL + credential are per-SPAWN (the orchestrator folds them into the
	// in-pod env from the SpawnRequest's WorkdirRepo), never static template values.
	inPodNATSURL string
}

// static assertion: the store binds the frozen orchestrator.TemplateStore port (Resolve only).
var _ orchestrator.TemplateStore = supervisorTemplateStore{}

// newSupervisorTemplateStore freezes the substrate the supervisor template's sandbox compiles
// to. The docker-first service passes orchestrator.SubstrateDocker (the local single instance);
// the kubernetes deployment passes SubstrateKubernetes — the AGENT-TEMPLATE.md ceiling otherwise
// identical (ADR-0012: substrate selects mechanism only). inPod selects the in-pod workload variant
// (default false: the existing host-side Ready-then-Run template).
func newSupervisorTemplateStore(substrate orchestrator.Substrate, inPod bool, inPodNATSURL string) supervisorTemplateStore {
	return supervisorTemplateStore{substrate: substrate, inPod: inPod, inPodNATSURL: inPodNATSURL}
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
			// The supervisor invokes each typed transition as a SLASH-COMMAND, which Claude Code runs
			// through the Skill tool ({"skill":"propose-questionnaire", ...}). The adapter folds the
			// invoked name into the permission tool string ("Skill(propose-questionnaire)"), so these
			// Skill-scoped grants are the auto-allow surface for the supervisor's closed command set —
			// each command's UNDERLYING bash stays double-walled by the template settings.json + the
			// gate-tool hook. The Bash command-script grants below cover a direct (non-Skill) run.
			{ID: "skill-commands", Tool: "Skill", Scopes: []string{
				"state-show", "propose-questionnaire", "record-answer", "propose-charter",
				"ratify-charter", "propose-work-item", "open-decision", "rule-decision", "plan", "advance",
			}},
			{ID: "slash-commands", Tool: "SlashCommand", Scopes: []string{
				"state-show", "propose-questionnaire", "record-answer", "propose-charter",
				"ratify-charter", "propose-work-item", "open-decision", "rule-decision", "plan", "advance",
			}},
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
			// The eden_commit_transition controller host-tool (injected per-spawn via
			// SpawnRequest.HostTools at the composition root): the supervisor calls it to COMMIT+push a
			// transition it staged and project the FSM state to Postgres. Claude surfaces an Eden SDK-MCP
			// host-tool as mcp__<server>__<name> (server "eden", claudeadapter hostToolServerName), so the
			// grant key is the MCP-qualified name. The handler re-validates the transition server-side.
			{ID: "host-commit-transition", Tool: "mcp__eden__eden_commit_transition"},
		},

		// No Eden host-callback tools at v0 (the supervisor reads the repo directly).
		Hosts: nil,

		// Role=supervisor -> agentconfiguration resolves {claude-code, opus} (the standing
		// Opus directive). The orchestrator carries this key and never decides the model.
		Routing: supervisorRouteKey, // cite the one canonical key (service.go); the pool routes it to claude-code

		Sandbox: s.supervisorSandbox(),

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

// inPodSupervisorEntrypoint is the workload-pod PID-1 command of the in-pod supervisor variant: the
// agent-runtime binary baked into ghcr.io/gophersys/base-derived image (deploy/image/agent-runtime
// .Dockerfile installs it at /usr/local/bin/agent-runtime; the image's own ENTRYPOINT names it, so the
// Entrypoint here is the explicit ADR-0022 §4 workload declaration the provider folds onto the pod).
var inPodSupervisorEntrypoint = []string{"agent-runtime"}

// inPod env keys folded into the in-pod supervisor Sandbox.Env (the agent-runtime binary reads them at
// boot). EDEN_ROLE selects the supervisor route (opus) in the pod's own composition root; EDEN_NATS_URL
// is the bus the in-pod sidecar dials. The per-spawn EDEN_WORKDIR_REPO / EDEN_WORKDIR_REPO_CRED are
// folded by the ORCHESTRATOR from the SpawnRequest's WorkdirRepo (orchestrator.withWorkdirRepoEnv), NOT
// here — the template carries only the static knobs.
const (
	inPodEnvRole    = "EDEN_ROLE"
	inPodRoleValue  = "supervisor"
	inPodEnvNATSURL = "EDEN_NATS_URL"
)

// supervisorSandbox builds the supervisor template's SandboxSpec. The DEFAULT (inPod false) is the
// existing host-side Ready-then-Run workspace — BYTE-IDENTICAL to the prior inline literal (the live
// demo path). The IN-POD variant (inPod true) makes the workspace a WORKLOAD POD: a non-empty
// Entrypoint (agent-runtime as PID-1, ADR-0022 §4) + the in-pod Env (EDEN_ROLE=supervisor +
// EDEN_NATS_URL). The orchestrator's fold (libs/go/orchestrator/fold.go) detects the non-empty
// Entrypoint and folds the per-spawn WorkdirRepo (URL + credential reference) into the in-pod Env so
// the pod's agent-runtime binary clones the project repo + overlays the baked supervisor .claude
// manual itself (apps/agent-runtime workdir.go), the in-pod analog of the host-side Materializer.
func (s supervisorTemplateStore) supervisorSandbox() orchestrator.SandboxSpec {
	if !s.inPod {
		return orchestrator.SandboxSpec{
			Substrate:   s.substrate,
			Image:       "ghcr.io/gophersys/base",
			Resources:   orchestrator.ResourceEnvelope{CPUMillis: 1000, MemoryMiB: 2048, EphemeralMiB: 4096},
			EgressAllow: nil, // model provider only (default-deny, 07 §3); git is local to the workspace
			Env:         map[string]string{"EDEN_AGENT_ROLE": "supervisor"},
			// Entrypoint empty == the classic Ready-then-Run workspace (the supervisor is
			// interactive/looped, not a one-shot workload pod).
		}
	}
	env := map[string]string{
		"EDEN_AGENT_ROLE": "supervisor", // preserved for parity with the host-side variant (observability)
		inPodEnvRole:      inPodRoleValue,
	}
	if s.inPodNATSURL != "" {
		env[inPodEnvNATSURL] = s.inPodNATSURL
	}
	return orchestrator.SandboxSpec{
		Substrate:   s.substrate,
		Image:       "ghcr.io/gophersys/agent-runtime", // the in-pod image (base + the baked agent-runtime binary + supervisor manual)
		Resources:   orchestrator.ResourceEnvelope{CPUMillis: 1000, MemoryMiB: 2048, EphemeralMiB: 4096},
		EgressAllow: nil,
		Env:         env,
		// The non-empty Entrypoint IS the in-pod selector: the orchestrator folds the per-spawn
		// WorkdirRepo into the Env (URL + credential reference) on this branch, and provisions a
		// workload pod whose PID-1 is the agent-runtime binary (ADR-0022 §4). The credential reference
		// rides the SpawnRequest per-project; the template declares the workload shape, not the secret.
		Entrypoint:  append([]string(nil), inPodSupervisorEntrypoint...),
		WorkdirRepo: orchestrator.RepoMount{}, // the per-spawn repo URL + credential are threaded by the saga into the SpawnRequest; the orchestrator folds them into the in-pod Env.
	}
}
