package orchestrator

import "github.com/gophersys/libs/go/agentsession"

// export_test.go is the white-box seam: it re-exports a PURE unexported helper so the external
// _test package exercises it WITHOUT widening the public surface.

// EffectiveWorkDirForTest exercises the per-spawn host-CWD override precedence: the SpawnRequest
// .Workspace override wins, else the provisioned WorkDir, else the default.
func EffectiveWorkDirForTest(override, provisioned string) string {
	inputs := spawnInputs{workspace: override}
	return inputs.effectiveWorkDir(provisioned)
}

// DefaultWorkDirForTest re-exports the repo-less harness CWD constant for the precedence test.
func DefaultWorkDirForTest() string { return defaultWorkDir }

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
