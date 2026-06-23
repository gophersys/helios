package orchestrator_test

import (
	"reflect"
	"testing"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/secrets"
)

// TestEffectiveHostTools_PerSpawnReplacesTemplate proves the per-spawn host-tools override: a caller's
// closure-bearing host-tools (the controller's powers, built at the composition root) REPLACE the
// static template's declared Hosts; an empty per-spawn set falls back to the template's Hosts.
func TestEffectiveHostTools_PerSpawnReplacesTemplate(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name          string
		perSpawn      []string
		templateHosts []string
		want          []string
	}{
		{"per-spawn replaces template", []string{"eden_commit_transition", "eden_spawn_subagent"}, []string{"old"}, []string{"eden_commit_transition", "eden_spawn_subagent"}},
		{"empty per-spawn falls back to template", nil, []string{"templated"}, []string{"templated"}},
		{"both empty yields none", nil, nil, []string{}},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			if got := orchestrator.EffectiveHostToolNamesForTest(testCase.perSpawn, testCase.templateHosts); !reflect.DeepEqual(got, testCase.want) {
				t.Errorf("effectiveHostTools(%v, %v) = %v, want %v", testCase.perSpawn, testCase.templateHosts, got, testCase.want)
			}
		})
	}
}

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

// TestIsInPodWorkload_SelectsByEntrypoint pins the additive branch selector: an EMPTY Entrypoint is
// the classic host-Bind path (the existing behavior, byte-unchanged); a NON-EMPTY one is the in-pod
// env-fold. This is the guard that keeps the existing host-side supervisor template's fold identical.
func TestIsInPodWorkload_SelectsByEntrypoint(t *testing.T) {
	t.Parallel()
	if orchestrator.IsInPodWorkloadForTest(nil) {
		t.Error("empty Entrypoint must be the classic host-Bind path (the existing behavior)")
	}
	if orchestrator.IsInPodWorkloadForTest([]string{}) {
		t.Error("empty-slice Entrypoint must be the classic host-Bind path")
	}
	if !orchestrator.IsInPodWorkloadForTest([]string{"agent-runtime"}) {
		t.Error("non-empty Entrypoint must select the in-pod env-fold")
	}
}

// TestWorkdirRepoEnvFold_ThreadsRefAndCredential proves the in-pod env-fold THREADS .Ref + .Credential
// — the fields the host Bind path DROPPED. It asserts the URL, the branch ref, and the OPAQUE
// credential REFERENCE STRING (never a value) land in the env COPY, the base env is preserved, the
// template's base map is NOT mutated (immutability), and a zero WorkdirRepo is a pass-through.
func TestWorkdirRepoEnvFold_ThreadsRefAndCredential(t *testing.T) {
	t.Parallel()

	base := map[string]string{"EDEN_AGENT_ROLE": "supervisor"}
	repository := orchestrator.RepoMount{
		URL:        "https://github.com/acme/seeded-project.git",
		Ref:        "main",
		Credential: secrets.Ref("vault://eden/projects/acme#gh-token"),
	}

	got := orchestrator.WorkdirRepoEnvForTest(base, repository)

	if got[orchestrator.EnvWorkdirRepo] != repository.URL {
		t.Errorf("%s = %q, want %q", orchestrator.EnvWorkdirRepo, got[orchestrator.EnvWorkdirRepo], repository.URL)
	}
	if got[orchestrator.EnvWorkdirRepoRef] != "main" {
		t.Errorf("%s = %q, want %q", orchestrator.EnvWorkdirRepoRef, got[orchestrator.EnvWorkdirRepoRef], "main")
	}
	// The credential is the loggable REFERENCE STRING, never a value (redaction-safe).
	if got[orchestrator.EnvWorkdirRepoCredential] != "vault://eden/projects/acme#gh-token" {
		t.Errorf("%s = %q, want the opaque reference string", orchestrator.EnvWorkdirRepoCredential, got[orchestrator.EnvWorkdirRepoCredential])
	}
	if got["EDEN_AGENT_ROLE"] != "supervisor" {
		t.Error("the base env must be preserved through the fold")
	}
	// Immutability: the fold copies; the template's base map is untouched.
	if _, mutated := base[orchestrator.EnvWorkdirRepo]; mutated {
		t.Error("the fold mutated the base env map (the template is immutable; the fold must copy)")
	}

	// A zero WorkdirRepo (no URL) is a pass-through — an empty in-pod workspace folds no repo env.
	passthrough := orchestrator.WorkdirRepoEnvForTest(base, orchestrator.RepoMount{})
	if _, present := passthrough[orchestrator.EnvWorkdirRepo]; present {
		t.Error("a zero WorkdirRepo must fold NO repo env (the empty in-pod workspace)")
	}
}
