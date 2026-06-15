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
func toWorkspaceSpec(agent *Agent, template *AgentTemplate) workspaceprovider.WorkspaceSpec {
	labels := map[string]string{
		workspaceprovider.LabelOrganization: agent.Tenant.OrganizationID,
		workspaceprovider.LabelProject:      agent.Tenant.ProjectID,
		labelAgentID:                        string(agent.ID),
		labelTemplateName:                   agent.Template.Name,
	}
	for k, v := range template.Labels {
		labels[k] = v
	}

	spec := workspaceprovider.WorkspaceSpec{
		Name:             workspaceName(agent.ID),
		Substrate:        substrateToProvider(template.Sandbox.Substrate),
		Image:            template.Sandbox.Image,
		Resources:        resourcesToProvider(template.Sandbox.Resources),
		Egress:           egressToProvider(template.Sandbox.EgressAllow),
		Labels:           labels,
		Env:              envToProvider(template.Sandbox.Env),
		Entrypoint:       entrypointToProvider(template.Sandbox.Entrypoint),
		ProvisionTimeout: 0, // ctx (bounded by ProvisionTimeout in reconcile) governs the wait
	}
	if mount, ok := repoMount(template.Sandbox.WorkdirRepo); ok {
		spec.Mounts = append(spec.Mounts, mount)
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
		HostTools:    inputs.template.Hosts,
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
