package orchestrator_test

import (
	"testing"

	"github.com/gophersys/libs/go/orchestrator"
)

// TestEffectiveWorkDir_OverridePrecedence proves the SpawnRequest.Workspace override seam: an
// externally-materialized host CWD wins over the provisioned WorkDir, which wins over the default.
// This is the load-bearing rule that lets a caller (the project-creation saga) provision a real
// working tree — a clone + the agent's overlaid operating files — and point the harness session at
// it instead of the empty container-derived "/workspace".
func TestEffectiveWorkDir_OverridePrecedence(t *testing.T) {
	t.Parallel()
	def := orchestrator.DefaultWorkDirForTest()
	cases := []struct {
		name        string
		override    string
		provisioned string
		want        string
	}{
		{"override wins over provisioned", "/host/materialized", "/workspace", "/host/materialized"},
		{"override wins over empty provisioned", "/host/materialized", "", "/host/materialized"},
		{"no override falls back to provisioned", "", "/workspace", "/workspace"},
		{"no override, no provisioned falls back to default", "", "", def},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			if got := orchestrator.EffectiveWorkDirForTest(testCase.override, testCase.provisioned); got != testCase.want {
				t.Errorf("effectiveWorkDir(%q, %q) = %q, want %q", testCase.override, testCase.provisioned, got, testCase.want)
			}
		})
	}
}
