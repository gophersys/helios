package orchestrator_test

import (
	"reflect"
	"testing"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
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

// TestEffectiveWorkdirRepo_OverridePrecedence pins the per-spawn repo override: a SpawnRequest
// .WorkdirRepo with a non-empty URL (e.g. the saga's per-project repo, which the static template
// cannot carry) wins over the template's Sandbox.WorkdirRepo; a zero override (empty URL) falls back
// to the template's own. This is the seam that makes the in-pod supervisor clone the RIGHT project.
func TestEffectiveWorkdirRepo_OverridePrecedence(t *testing.T) {
	t.Parallel()
	perSpawn := orchestrator.RepoMount{URL: "https://github.com/acme/project.git", Ref: "main", Credential: secrets.Ref("vault://eden/development#gh-token")}
	templateRepo := orchestrator.RepoMount{URL: "https://github.com/acme/template-default.git"}
	cases := []struct {
		name     string
		override orchestrator.RepoMount
		template orchestrator.RepoMount
		wantURL  string
	}{
		{"per-spawn override wins over template", perSpawn, templateRepo, perSpawn.URL},
		{"per-spawn override wins over zero template", perSpawn, orchestrator.RepoMount{}, perSpawn.URL},
		{"zero override falls back to template", orchestrator.RepoMount{}, templateRepo, templateRepo.URL},
		{"both zero stays zero", orchestrator.RepoMount{}, orchestrator.RepoMount{}, ""},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			got := orchestrator.EffectiveWorkdirRepoForTest(testCase.override, testCase.template)
			if got.URL != testCase.wantURL {
				t.Errorf("effectiveWorkdirRepo URL = %q, want %q", got.URL, testCase.wantURL)
			}
			// When the per-spawn override wins, its Ref + Credential ride through too (not just the URL).
			if testCase.override.URL != "" && (got.Ref != testCase.override.Ref || got.Credential != testCase.override.Credential) {
				t.Errorf("override must thread Ref+Credential: got {%q,%v}", got.Ref, got.Credential)
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

// TestToWorkspaceSpec_InPodFoldsEnvNoBind drives the FULL fold (toWorkspaceSpec) end-to-end to prove
// the BRANCH DIVERGENCE the increment turns on: an IN-POD workload (a non-empty Entrypoint) folds the
// per-spawn WorkdirRepo into the WorkspaceSpec.Env (URL + Ref + the OPAQUE credential reference) and
// takes NO host Bind mount — the in-pod binary clones the repo itself from the folded env. This is the
// additive in-pod path: the .Ref + .Credential thread through (the host Bind dropped them).
func TestToWorkspaceSpec_InPodFoldsEnvNoBind(t *testing.T) {
	t.Parallel()
	tenant := orchestrator.Tenancy{OrganizationID: "acme", ProjectID: "alpha"}
	template := orchestrator.AgentTemplate{
		Ref: orchestrator.TemplateRef{Name: "supervisor", Version: "0.1.0"},
		Sandbox: orchestrator.SandboxSpec{
			Substrate:  orchestrator.SubstrateDocker,
			Image:      "ghcr.io/gophersys/agent-runtime",
			Entrypoint: []string{"agent-runtime"}, // the in-pod selector (a non-empty Entrypoint)
			Env:        map[string]string{"EDEN_ROLE": "supervisor"},
			WorkdirRepo: orchestrator.RepoMount{
				URL:        "https://github.com/acme/seeded-project.git",
				Ref:        "main",
				Credential: secrets.Ref("vault://eden/projects/acme#gh-token"),
			},
		},
	}

	spec := orchestrator.ToWorkspaceSpecForTest(tenant, &template)

	// The in-pod path takes NO host Bind mount: the binary clones the remote itself.
	for _, mount := range spec.Mounts {
		if mount.Kind == workspaceprovider.MountBind {
			t.Fatalf("in-pod workload must take NO host Bind mount (the binary clones the repo), got %+v", mount)
		}
	}
	// The WorkdirRepo folded into Sandbox.Env: URL + Ref + the OPAQUE credential REFERENCE STRING.
	env := envByName(spec.Env)
	if env[orchestrator.EnvWorkdirRepo] != "https://github.com/acme/seeded-project.git" {
		t.Errorf("in-pod %s = %q, want the clone URL folded into Env", orchestrator.EnvWorkdirRepo, env[orchestrator.EnvWorkdirRepo])
	}
	if env[orchestrator.EnvWorkdirRepoRef] != "main" {
		t.Errorf("in-pod %s = %q, want the branch ref threaded (the host Bind dropped it)", orchestrator.EnvWorkdirRepoRef, env[orchestrator.EnvWorkdirRepoRef])
	}
	if env[orchestrator.EnvWorkdirRepoCredential] != "vault://eden/projects/acme#gh-token" {
		t.Errorf("in-pod %s = %q, want the OPAQUE credential reference threaded (the host Bind dropped it)", orchestrator.EnvWorkdirRepoCredential, env[orchestrator.EnvWorkdirRepoCredential])
	}
	// The base env is preserved alongside the folded repo env.
	if env["EDEN_ROLE"] != "supervisor" {
		t.Error("the in-pod fold must preserve the template's base Sandbox.Env")
	}
}

// TestToWorkspaceSpec_HostSideKeepsBindNoEnvFold drives the FULL fold for the CLASSIC host-side path
// (an EMPTY Entrypoint): the existing behavior is byte-unchanged — a host Bind mount IS produced from
// the WorkdirRepo.URL and the repo URL is NOT folded into Sandbox.Env. This is the guard that the
// additive in-pod branch leaves the live host-side demo path untouched.
func TestToWorkspaceSpec_HostSideKeepsBindNoEnvFold(t *testing.T) {
	t.Parallel()
	tenant := orchestrator.Tenancy{OrganizationID: "acme", ProjectID: "alpha"}
	template := orchestrator.AgentTemplate{
		Ref: orchestrator.TemplateRef{Name: "supervisor", Version: "0.1.0"},
		Sandbox: orchestrator.SandboxSpec{
			Substrate: orchestrator.SubstrateDocker,
			Image:     "ghcr.io/gophersys/base",
			// Entrypoint EMPTY == the classic Ready-then-Run host-side workspace (the existing behavior).
			Env: map[string]string{"EDEN_AGENT_ROLE": "supervisor"},
			WorkdirRepo: orchestrator.RepoMount{
				URL:        "https://github.com/acme/seeded-project.git",
				Ref:        "main",
				Credential: secrets.Ref("vault://eden/projects/acme#gh-token"),
			},
		},
	}

	spec := orchestrator.ToWorkspaceSpecForTest(tenant, &template)

	// The host-side path keeps the host Bind mount derived from the WorkdirRepo.URL (the existing behavior).
	var bind *workspaceprovider.Mount
	for i := range spec.Mounts {
		if spec.Mounts[i].Kind == workspaceprovider.MountBind {
			bind = &spec.Mounts[i]
		}
	}
	if bind == nil {
		t.Fatal("host-side workspace must keep the host Bind mount (the existing behavior, byte-unchanged)")
	}
	if bind.Source != "https://github.com/acme/seeded-project.git" {
		t.Errorf("host-side Bind source = %q, want the WorkdirRepo URL", bind.Source)
	}
	// The host-side path does NOT fold the repo into Sandbox.Env (only the in-pod branch does).
	env := envByName(spec.Env)
	if _, present := env[orchestrator.EnvWorkdirRepo]; present {
		t.Error("host-side path must NOT fold the repo URL into Sandbox.Env (that is the in-pod branch only)")
	}
}

// envByName indexes a WorkspaceSpec's []EnvVar by name for assertion convenience.
func envByName(vars []workspaceprovider.EnvVar) map[string]string {
	out := make(map[string]string, len(vars))
	for _, v := range vars {
		out[v.Name] = v.Value
	}
	return out
}
