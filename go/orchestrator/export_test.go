package orchestrator

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
