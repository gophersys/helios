package composition_test

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/gitrepository/gitrepositorytest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agent-runtime/internal/composition"
)

// TestPrepareWorkdir_EmptyRepoIsNoOp pins the ADDITIVE GUARD: when EDEN_WORKDIR_REPO is empty (the
// existing assistant/probe boot, and the live host-side demo whose supervisor template leaves
// WorkdirRepo unset), prepareWorkdir is a NO-OP that returns environment.Workspace VERBATIM. This is
// the byte-unchanged contract for the existing boot — the in-pod clone never runs unless explicitly
// requested.
func TestPrepareWorkdir_EmptyRepoIsNoOp(t *testing.T) {
	t.Parallel()
	env := composition.Environment{
		AgentID:   "smoke",
		Workspace: "/some/provisioned/workspace",
		// WorkdirRepo deliberately empty.
	}
	got, err := composition.PrepareWorkdirForTest(context.Background(), env, secretstest.New(nil))
	if err != nil {
		t.Fatalf("PrepareWorkdir(empty repo) error = %v, want nil (no-op)", err)
	}
	if got != "/some/provisioned/workspace" {
		t.Fatalf("PrepareWorkdir(empty repo) = %q, want the Workspace verbatim", got)
	}
}

// TestPrepareWorkdir_ClonesOverlaysCommits proves the REAL clone+overlay+commit structure against a
// LOCAL git remote driven by the REAL system git binary (no mock, no network — the in-pod analog of
// the host-side Materializer, exercised at the unit level). It asserts: the returned dir is the cloned
// CWD; the seeded file is present; the supervisor .claude manual is overlaid (execute bit preserved on
// a hook script); and the working tree is CLEAN (the overlay was committed) so the supervisor starts
// without a dirty tree. The credential is the zero Reference (a public/local clone), so the secrets
// provider is never consulted.
func TestPrepareWorkdir_ClonesOverlaysCommits(t *testing.T) {
	// No t.Parallel(): this test sets EDEN_SUPERVISOR_MANUAL_DIR via t.Setenv (forbidden under parallel).
	if _, err := exec.LookPath("git"); err != nil {
		t.Skipf("system git unavailable: %v", err) // FAIL-NOT-SKIP holds in the devcontainer; local hosts without git skip the binding.
	}

	root := t.TempDir()
	originURL := makeSeedRemote(t, root) // a real git repo seeded with one file; the clone source.
	manualDir := makeManualFixture(t, root)
	workspaceRoot := filepath.Join(root, "pod-workspace")

	env := composition.Environment{
		AgentID:     "agent-xyz",
		Workspace:   workspaceRoot,
		WorkdirRepo: originURL,
		// WorkdirRepoCred empty == a public/local clone (the zero credential Reference).
	}
	t.Setenv("EDEN_SUPERVISOR_MANUAL_DIR", manualDir) // point the overlay at the fixture, not the baked image path.

	workDir, err := composition.PrepareWorkdirForTest(context.Background(), env, secretstest.New(nil))
	if err != nil {
		t.Fatalf("PrepareWorkdir(local clone) error = %v", err)
	}

	// 1) The CWD is a fresh per-agent clone dir under the workspace root.
	wantDir := filepath.Join(workspaceRoot, "supervisor-agent-xyz")
	if workDir != wantDir {
		t.Fatalf("workDir = %q, want %q", workDir, wantDir)
	}

	// 2) The seeded file landed (the repo was actually cloned).
	if _, statErr := os.Stat(filepath.Join(workDir, "README.md")); statErr != nil {
		t.Fatalf("seeded README.md absent in clone: %v", statErr)
	}

	// 3) The supervisor .claude manual was overlaid, execute bit preserved on the hook script.
	hookPath := filepath.Join(workDir, ".claude", "hooks", "session-start.sh")
	info, statErr := os.Stat(hookPath)
	if statErr != nil {
		t.Fatalf("overlaid .claude hook absent: %v", statErr)
	}
	if info.Mode().Perm()&0o100 == 0 {
		t.Fatalf("overlay dropped the execute bit on the hook: mode = %v", info.Mode())
	}

	// 4) The working tree is CLEAN — the overlay was staged+committed (the supervisor refuses a dirty
	//    tree). `git status --porcelain` empty proves the commit.
	porcelain := gitPorcelain(t, workDir)
	if porcelain != "" {
		t.Fatalf("working tree dirty after materialize (overlay not committed):\n%s", porcelain)
	}
}

// workdirManualCredRef is the OPAQUE clone-credential reference the in-pod cloner threads to Clone (the
// per-spawn EDEN_WORKDIR_REPO_CRED the orchestrator folds into the in-pod env from the SpawnRequest).
const workdirManualCredRef = "vault://eden/projects/acme#gh-token" //nolint:gosec // G101 false positive: this is an opaque secrets.Reference STRING (a vault PATH resolved server-side), never a credential value.

// workdirCredCanary is the FAKE resolved credential VALUE the secrets provider hands back for
// workdirManualCredRef. The no-leak guarantee: it must NEVER appear on a process-argument surface.
const workdirCredCanary = "FAKE-GH-PAT-do-not-leak" //nolint:gosec // G101: a deliberately FAKE token (never a real credential) for the in-memory fake backend.

// TestPrepareWorkdir_FakeBackend_ResolvesAndThreadsCredential proves the cloner's PURE clone-credential
// wiring against an INJECTED in-memory fake gitrepository.Backend (the SAME fake the gitrepository
// conformance suite and projectcreate's Seeder test drive — no real git binary, no real clone): when
// EDEN_WORKDIR_REPO AND EDEN_WORKDIR_REPO_CRED are set, the cloner (1) RESOLVES the opaque credential
// reference through the injected secrets Mediator server-side (the Resolved log carries the exact
// reference), and (2) the resolved credential VALUE never reaches a process-argument surface (the
// no-leak guarantee). This mirrors projectcreate/adapters_test.go's Seeder credential-confinement
// assertions for the in-pod analog.
//
// SCOPE (honest): the in-memory fake clones into an IN-MEMORY git model, so the subsequent .claude
// overlay (os.CopyFS, an on-DISK write) is invisible to the fake's staged index — its Stage(All) sees
// no change and the overlay Commit is "nothing to commit". The credential is resolved BY Clone, BEFORE
// the overlay/commit, so this test asserts the credential half precisely (Resolved + no-leak) and
// treats the in-memory empty-overlay-commit as the documented limitation of an in-memory backend. The
// on-disk overlay+execute-bit+clean-tree half is the REAL-system-git test
// (TestPrepareWorkdir_ClonesOverlaysCommits) — one behavior, two complementary substrates.
func TestPrepareWorkdir_FakeBackend_ResolvesAndThreadsCredential(t *testing.T) {
	// No t.Parallel(): this test sets EDEN_SUPERVISOR_MANUAL_DIR via t.Setenv (forbidden under parallel).
	root := t.TempDir()
	manualDir := makeManualFixture(t, root)
	workspaceRoot := filepath.Join(root, "pod-workspace")
	originURL := "https://github.com/acme/seeded-project.git"

	// The injected fake backend with the seeded project REMOTE registered, so the in-memory Clone has
	// content to copy (AdvanceRemote registers the remote model the fake's clone reads from).
	backend := gitrepositorytest.New()
	backend.AdvanceRemote(originURL, "main", "seeded-readme")
	// The secrets Mediator resolves the workdir credential reference to the canary VALUE; the cloner
	// threads the OPAQUE reference to Clone, which resolves it server-side before handing the Backend
	// the short-lived Secret (the value confined to Secret.Use, never argv).
	provider := secretstest.New(map[string]string{workdirManualCredRef: workdirCredCanary})

	env := composition.Environment{
		AgentID:         "agent-xyz",
		Workspace:       workspaceRoot,
		WorkdirRepo:     originURL,
		WorkdirRepoCred: workdirManualCredRef, // the OPAQUE reference the in-pod env carries (EDEN_WORKDIR_REPO_CRED).
	}
	t.Setenv("EDEN_SUPERVISOR_MANUAL_DIR", manualDir)

	// The clone — and the credential resolution it drives — happens BEFORE the overlay/commit; the only
	// acceptable error is the in-memory backend's "nothing to commit" on the on-disk overlay (the
	// documented limitation). Any OTHER error (a Clone-time credential failure, a missing remote) would
	// mean the credential path itself faulted, so it must fail the test — the credential assertions
	// below are then genuinely load-bearing, not vacuously passed by an early Clone error.
	_, err := composition.PrepareWorkdirWithBackendForTest(context.Background(), env, provider, backend)
	if err != nil && !errors.IsType[*gitrepository.NothingToCommitError](err) {
		t.Fatalf("PrepareWorkdir(fake backend) error = %v, want nil or the in-memory NothingToCommitError", err)
	}

	// 1) The opaque credential REFERENCE was resolved server-side by the injected Mediator — the Clone
	//    threaded EDEN_WORKDIR_REPO_CRED through, never cloning anonymously when a credential is set.
	if !resolvedContains(provider.Resolved, workdirManualCredRef) {
		t.Fatalf("the workdir credential reference %q was never resolved (Clone did not thread the credential); resolved = %v", workdirManualCredRef, provider.Resolved)
	}

	// 2) The resolved credential VALUE never reached a process-argument surface (the no-leak guarantee:
	//    the value lives only inside Secret.Use, never on argv/URL/log).
	backend.AssertCredentialNeverInArgs(t, workdirCredCanary)
}

// TestPrepareWorkdir_FakeBackend_EmptyRepoSkipsClone reasserts the additive GUARD against the fake
// backend (the substrate-injected analog of TestPrepareWorkdir_EmptyRepoIsNoOp): an EMPTY
// EDEN_WORKDIR_REPO is a NO-OP that returns Workspace verbatim and NEVER touches the backend or the
// secrets Mediator — the existing assistant/probe boot is byte-unchanged even with a backend wired.
func TestPrepareWorkdir_FakeBackend_EmptyRepoSkipsClone(t *testing.T) {
	t.Parallel()
	backend := gitrepositorytest.New()
	provider := secretstest.New(nil)

	env := composition.Environment{
		AgentID:   "smoke",
		Workspace: "/some/provisioned/workspace",
		// WorkdirRepo deliberately empty: the existing boot, byte-unchanged.
	}

	got, err := composition.PrepareWorkdirWithBackendForTest(context.Background(), env, provider, backend)
	if err != nil {
		t.Fatalf("PrepareWorkdir(empty repo, fake backend) error = %v, want nil (no-op)", err)
	}
	if got != "/some/provisioned/workspace" {
		t.Fatalf("PrepareWorkdir(empty repo) = %q, want the Workspace verbatim", got)
	}
	// The no-op never resolved a credential (the secrets Mediator was untouched) and never pushed.
	if len(provider.Resolved) != 0 {
		t.Fatalf("empty-repo no-op resolved a credential = %v, want none (the backend/secrets are untouched)", provider.Resolved)
	}
	if len(backend.Pushed) != 0 {
		t.Fatalf("empty-repo no-op issued a backend op = %v, want none", backend.Pushed)
	}
}

// resolvedContains reports whether the secrets provider's Resolved log carries the named reference.
func resolvedContains(resolved []secrets.Reference, name string) bool {
	for _, ref := range resolved {
		if ref.String() == name {
			return true
		}
	}
	return false
}

// makeSeedRemote initializes a real git repository under root with a single committed file and returns
// its clone URL (a local filesystem path — git clones it without network). Real system git, no mock.
func makeSeedRemote(t *testing.T, root string) string {
	t.Helper()
	origin := filepath.Join(root, "seed-origin")
	if err := os.MkdirAll(origin, 0o750); err != nil {
		t.Fatalf("mkdir seed origin: %v", err)
	}
	runGit(t, origin, "init", "-q", "-b", "main")
	runGit(t, origin, "config", "user.name", "Seed")
	runGit(t, origin, "config", "user.email", "seed@eden.dev")
	if err := os.WriteFile(filepath.Join(origin, "README.md"), []byte("# seeded project\n"), 0o600); err != nil {
		t.Fatalf("write seed file: %v", err)
	}
	runGit(t, origin, "add", "-A")
	runGit(t, origin, "commit", "-q", "-m", "seed")
	return origin
}

// makeManualFixture writes a tiny supervisor .claude manual fixture (an executable hook) under root and
// returns its path — the EDEN_SUPERVISOR_MANUAL_DIR the overlay copies from (standing in for the baked
// image path so the clone-on-boot path is provable without the image layer).
func makeManualFixture(t *testing.T, root string) string {
	t.Helper()
	manual := filepath.Join(root, "supervisor-manual")
	hooks := filepath.Join(manual, "hooks")
	if err := os.MkdirAll(hooks, 0o750); err != nil {
		t.Fatalf("mkdir manual fixture: %v", err)
	}
	if err := os.WriteFile(filepath.Join(manual, "settings.json"), []byte("{}\n"), 0o600); err != nil {
		t.Fatalf("write manual settings.json: %v", err)
	}
	hook := filepath.Join(hooks, "session-start.sh")
	if err := os.WriteFile(hook, []byte("#!/usr/bin/env bash\n"), 0o600); err != nil {
		t.Fatalf("write manual hook: %v", err)
	}
	// Set the execute bit deliberately: the overlay (os.CopyFS) MUST preserve it (the supervisor's
	// command/hook scripts are run), so the fixture carries an executable hook the test asserts survives.
	if err := os.Chmod(hook, 0o700); err != nil { //nolint:gosec // an executable hook fixture is the explicit intent — the test asserts os.CopyFS preserves the execute bit.
		t.Fatalf("chmod manual hook executable: %v", err)
	}
	return manual
}

// runGit runs a git subcommand in dir, failing the test on a non-zero exit.
func runGit(t *testing.T, dir string, args ...string) {
	t.Helper()
	cmd := exec.Command("git", args...) // #nosec G204 -- args are test-literal, dir is t.TempDir().
	cmd.Dir = dir
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("git %v in %s: %v\n%s", args, dir, err, out)
	}
}

// gitPorcelain returns `git status --porcelain` output for dir (empty == a clean tree).
func gitPorcelain(t *testing.T, dir string) string {
	t.Helper()
	cmd := exec.Command("git", "status", "--porcelain") // #nosec G204 -- literal args, t.TempDir() cwd.
	cmd.Dir = dir
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("git status in %s: %v\n%s", dir, err, out)
	}
	return string(out)
}
