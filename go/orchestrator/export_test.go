package orchestrator

import (
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// export_test.go is the white-box seam: it re-exports a PURE unexported helper so the external
// _test package exercises it WITHOUT widening the public surface.

// ToWorkspaceSpecForTest drives the FULL fold (toWorkspaceSpec) so a test asserts the in-pod vs
// host-side branch DIVERGENCE at the WorkspaceSpec level: an in-pod workload (non-empty Entrypoint)
// folds the WorkdirRepo into Sandbox.Env and takes NO host Bind mount; a classic host-side workspace
// (empty Entrypoint) keeps the host Bind and folds NO repo env. It builds the Agent the fold reads
// (the tenancy + template-name labels) from the template so the test drives the real production fold,
// not a re-spelled copy.
//
//nolint:gocritic // Tenancy is the small frozen tenancy key taken by value (the production fold reads it by value); template is a pointer to mirror toWorkspaceSpec's production signature.
func ToWorkspaceSpecForTest(tenant Tenancy, template *AgentTemplate) workspaceprovider.WorkspaceSpec {
	// toWorkspaceSpec reads agent.Tenant (the ownership-domain labels) and agent.Template.Name (the
	// template-name label); the production Spawn sets agent.Template to the resolved template's Ref.
	agent := &Agent{ID: "agent-1", Tenant: tenant, Template: template.Ref}
	return toWorkspaceSpec(agent, template)
}

// EffectiveWorkDirForTest exercises the per-spawn host-CWD override precedence: the SpawnRequest
// .Workspace override wins, else the provisioned WorkDir, else the default.
func EffectiveWorkDirForTest(override, provisioned string) string {
	inputs := spawnInputs{workspace: override}
	return inputs.effectiveWorkDir(provisioned)
}

// DefaultWorkDirForTest re-exports the repo-less harness CWD constant for the precedence test.
func DefaultWorkDirForTest() string { return defaultWorkDir }

// WorkdirRepoEnvForTest exercises the in-pod WorkdirRepo env-fold (the additive in-pod branch): it
// folds a RepoMount into the env COPY exactly as toWorkspaceSpec does for an in-pod workload, so the
// test asserts the URL/Ref/credential-reference land in the Sandbox.Env (the producer side of the env
// contract the agent-runtime PID-1 binary consumes), without re-spelling the env keys.
func WorkdirRepoEnvForTest(base map[string]string, repository RepoMount) map[string]string {
	return withWorkdirRepoEnv(base, repository)
}

// IsInPodWorkloadForTest re-exports the workload-shape predicate so the test pins the additive branch
// selector: an empty Entrypoint is the classic host-Bind path; a non-empty one is the in-pod env-fold.
func IsInPodWorkloadForTest(entrypoint []string) bool { return isInPodWorkload(entrypoint) }

// EffectiveHostToolNamesForTest exercises the per-spawn-host-tools-over-template-Hosts precedence by
// the tool NAMES (the Handler closures are not comparable): a non-empty per-spawn set REPLACES the
// template's declared Hosts, else the template's Hosts apply.
func EffectiveHostToolNamesForTest(perSpawn, templateHosts []string) []string {
	asTools := func(names []string) []agentsession.HostTool {
		if names == nil {
			return nil
		}
		out := make([]agentsession.HostTool, len(names))
		for i, n := range names {
			out[i] = agentsession.HostTool{Name: n}
		}
		return out
	}
	inputs := spawnInputs{hostTools: asTools(perSpawn), template: AgentTemplate{Hosts: asTools(templateHosts)}}
	effective := inputs.effectiveHostTools()
	names := make([]string, len(effective))
	for i, tool := range effective {
		names[i] = tool.Name
	}
	return names
}
