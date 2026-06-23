package composition_test

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/gophersys/eden/apps/agent-runtime/internal/composition"
	"github.com/gophersys/libs/go/secrets/secretstest"
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
