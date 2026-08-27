package orchestrator

import (
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// The fold is the heart of Spawn+reconcile: it composes the immutable AgentTemplate +
// the per-spawn material into the two downstream artifacts the lower ports consume — a
// workspaceprovider.WorkspaceSpec (the sandbox demand, compiled with tenancy + cluster)
// and an agentsession.Spec (the session demand, threading the opaque credential). The
// template is the ceiling; the request only tightens. The orchestrator never executes a
// template — it folds it.

// toWorkspaceSpec compiles a template's SandboxSpec + the agent's tenancy + cluster into
// the frozen workspaceprovider.WorkspaceSpec. Tenancy rides the ownership-domain labels
// (the workspaceprovider tenancy keys); SandboxSpec.EgressAllow → []EgressRule;
// substrate + image + resources map 1:1. Provision is idempotent on Name within a
// tenancy, so the Name is derived deterministically from the AgentID (a retried pass
// re-adopts rather than duplicates).
func toWorkspaceSpec(agent *Agent, template *AgentTemplate, workdirRepo RepoMount) workspaceprovider.WorkspaceSpec {
	labels := map[string]string{
		workspaceprovider.LabelOrganization: agent.Tenant.OrganizationID,
		workspaceprovider.LabelProject:      agent.Tenant.ProjectID,
		labelAgentID:                        string(agent.ID),
		labelTemplateName:                   agent.Template.Name,
	}
	for k, v := range template.Labels {
		labels[k] = v
	}

	// The EFFECTIVE WorkdirRepo (workdirRepo) is the per-spawn SpawnRequest.WorkdirRepo when supplied —
	// e.g. the project-creation saga's per-project repo, which the STATIC template cannot carry — else
	// the template's own Sandbox.WorkdirRepo (spawnInputs.effectiveWorkdirRepo). It is realized one of
	// two ways, selected by the workload shape (additive, ADR-0022 §4): an IN-POD workload (a non-empty
	// Entrypoint — the workspace's PID-1 IS the agent-runtime binary, which clones the repo itself;
	// apps/agent-runtime workdir.go) folds the repo into the child-process Env (URL + Ref + the OPAQUE
	// credential reference) so the in-pod cloner resolves the credential server-side and clones locally;
	// a CLASSIC Ready-then-Run workspace (empty Entrypoint — the existing host-side path) keeps the host
	// Bind mount behavior verbatim. The in-pod path is the only one that threads .Ref + .Credential (the
	// host Bind dropped them; they had no realization).
	env := template.Sandbox.Env
	if isInPodWorkload(template.Sandbox.Entrypoint) {
		env = withWorkdirRepoEnv(env, workdirRepo)
	}

	spec := workspaceprovider.WorkspaceSpec{
		Name:             workspaceName(agent.ID),
		Substrate:        substrateToProvider(template.Sandbox.Substrate),
		Image:            template.Sandbox.Image,
		Resources:        resourcesToProvider(template.Sandbox.Resources),
		Egress:           egressToProvider(template.Sandbox.EgressAllow),
		Labels:           labels,
		Env:              envToProvider(env),
		Entrypoint:       entrypointToProvider(template.Sandbox.Entrypoint),
		ProvisionTimeout: 0, // not the per-spec deadline: reconcile bounds the Provision CALL via Config.ProvisionTimeout (provisionContext), so the ctx governs the wait
	}
	// The host Bind mount is the CLASSIC Ready-then-Run path only: an in-pod workload clones the repo
	// itself from the folded Env, so it takes no host Bind (the .URL is a remote, not a host path).
	if !isInPodWorkload(template.Sandbox.Entrypoint) {
		if mount, ok := repoMount(workdirRepo); ok {
			spec.Mounts = append(spec.Mounts, mount)
		}
	}
	return spec
}

// foldSession composes the immutable AgentTemplate + the per-spawn material + the
// provisioned workspace into the frozen agentsession.Spec — the one place orchestration
// meets the F4 session contract. The credential is threaded OPAQUELY (agentsession.Open
// resolves it server-side); the budget is the tightened effective budget; the routing,
// grants, and host tools are the frozen agentsession types verbatim (no translation
// layer). resumeFrom re-attaches an existing harness session (Resume); "" spawns fresh.
func foldSession(workDir string, inputs *spawnInputs, resumeFrom SessionRef) agentsession.Spec {
	return agentsession.Spec{
		Workspace:    workDir,
		Routing:      inputs.template.Routing,
		Grants:       inputs.template.Grants,
		HostTools:    inputs.effectiveHostTools(),
		Credential:   inputs.credential, // OPAQUE ref; agentsession.Open resolves it server-side
		Budget:       inputs.budget,
		ResumeFrom:   string(resumeFrom),
		SystemHints:  inputs.systemHints,
		OnPermission: inputs.onPermission,
	}
}

// substrateToProvider maps the orchestrator Substrate enum onto the frozen
// workspaceprovider.Substrate string.
func substrateToProvider(s Substrate) workspaceprovider.Substrate {
	if s == SubstrateDocker {
		return workspaceprovider.SubstrateDocker
	}
	return workspaceprovider.SubstrateKubernetes
}

// resourcesToProvider maps the ResourceEnvelope (CPU millis / MiB) onto the frozen
// workspaceprovider.Resources (CPU milli / bytes).
func resourcesToProvider(r ResourceEnvelope) workspaceprovider.Resources {
	const mib = 1024 * 1024
	return workspaceprovider.Resources{
		CPUMilli:     r.CPUMillis,
		MemoryBytes:  r.MemoryMiB * mib,
		StorageBytes: r.EphemeralMiB * mib,
	}
}

// egressToProvider maps the declared egress endpoints onto frozen EgressRules
// (default-deny otherwise; the provider derives the NetworkPolicy).
func egressToProvider(allow []string) []workspaceprovider.EgressRule {
	if len(allow) == 0 {
		return nil
	}
	rules := make([]workspaceprovider.EgressRule, 0, len(allow))
	for _, host := range allow {
		rules = append(rules, workspaceprovider.EgressRule{Host: host, Note: "template egress-allow"})
	}
	return rules
}

// envToProvider maps the non-secret child-process env onto frozen EnvVars (a credential
// never travels here — that is the secrets seam).
func envToProvider(env map[string]string) []workspaceprovider.EnvVar {
	if len(env) == 0 {
		return nil
	}
	vars := make([]workspaceprovider.EnvVar, 0, len(env))
	for name, value := range env {
		vars = append(vars, workspaceprovider.EnvVar{Name: name, Value: value})
	}
	return vars
}

// repoMount maps an optional RepoMount onto a frozen Bind mount (the clone is
// gitrepository's concern, threaded through workspaceprovider). The zero RepoMount means
// "empty workspace" and yields no mount.
func repoMount(repository RepoMount) (workspaceprovider.Mount, bool) {
	if repository.URL == "" {
		return workspaceprovider.Mount{}, false
	}
	return workspaceprovider.Mount{
		Kind:   workspaceprovider.MountBind,
		Target: defaultWorkDir,
		Source: repository.URL,
	}, true
}

// entrypointToProvider carries the template's workload-pod Entrypoint (ADR-0022 §4,
// OD-15-a) verbatim onto the frozen WorkspaceSpec.Entrypoint. An empty Entrypoint yields nil
// (a classic Ready-then-Run workspace — the existing behavior); a non-empty one makes the
// workspace's PID-1 the workload, so the supervised pod IS the session.
func entrypointToProvider(entrypoint []string) []string {
	if len(entrypoint) == 0 {
		return nil
	}
	return append([]string(nil), entrypoint...)
}

// isInPodWorkload reports whether the template is an in-pod workload (a non-empty Entrypoint: the
// workspace's PID-1 IS the agent-runtime binary, ADR-0022 §4). Only an in-pod workload folds the
// WorkdirRepo into the child Env (the binary clones it itself); a classic Ready-then-Run workspace
// keeps the host Bind. Empty == the existing behavior, so the existing host-side path is byte-unchanged.
func isInPodWorkload(entrypoint []string) bool { return len(entrypoint) > 0 }

// The in-pod workdir-clone env keys (the producer side of the env contract the agent-runtime PID-1
// binary consumes in apps/agent-runtime workdir.go). They are NON-secret: EnvWorkdirRepoCredential
// carries the OPAQUE secrets.Reference STRING (RepoMount.Credential.String()), resolved server-side by
// the in-pod cloner's secrets Mediator — never the value. The agent-runtime app reads these by name at
// boot (the env boundary between the orchestrator producer and the in-pod consumer).
const (
	// EnvWorkdirRepo names the env var carrying the clone URL of the repo the in-pod binary clones.
	EnvWorkdirRepo = "EDEN_WORKDIR_REPO"
	// EnvWorkdirRepoRef names the env var carrying the optional branch/tag/sha to check out.
	EnvWorkdirRepoRef = "EDEN_WORKDIR_REPO_REF"
	// EnvWorkdirRepoCredential names the env var carrying the OPAQUE clone-credential reference STRING.
	EnvWorkdirRepoCredential = "EDEN_WORKDIR_REPO_CRED" //nolint:gosec // G101 false positive: this is an env-var KEY NAME, not a credential value (the value is an opaque secrets.Reference resolved server-side).
)

// withWorkdirRepoEnv folds a non-zero WorkdirRepo into a COPY of env (the in-pod workload path): the
// URL, the optional Ref, and the OPAQUE Credential reference STRING (RepoMount.Credential is never a
// VALUE — its String() is a loggable reference the in-pod cloner resolves server-side). A zero
// WorkdirRepo (no URL) returns env unchanged (an empty in-pod workspace). It NEVER mutates the
// template's map (the template is immutable; the fold copies).
func withWorkdirRepoEnv(env map[string]string, repository RepoMount) map[string]string {
	if repository.URL == "" {
		return env
	}
	merged := make(map[string]string, len(env)+3)
	for k, v := range env {
		merged[k] = v
	}
	merged[EnvWorkdirRepo] = repository.URL
	if repository.Ref != "" {
		merged[EnvWorkdirRepoRef] = repository.Ref
	}
	if !repository.Credential.IsZero() {
		merged[EnvWorkdirRepoCredential] = repository.Credential.String()
	}
	return merged
}

// workspaceName derives the deterministic, tenancy-scoped workspace name from the
// AgentID (the Provision idempotency key, so a retried pass re-adopts).
func workspaceName(id AgentID) string { return "ws-" + string(id) }

// defaultWorkDir is the harness CWD a repo-less or repo-bind sandbox uses.
const defaultWorkDir = "/workspace"

// The orchestration-plane label keys stamped onto a provisioned workspace so List/Probe
// find exactly the agents this Pool authored.
const (
	labelAgentID      = "eden.agent"
	labelTemplateName = "eden.template"
)
