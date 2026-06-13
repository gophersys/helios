package gitrepositorytest

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

// initRealRepo inits a REAL empty git repository on disk in t.TempDir() (the substitutability
// suite's real arm), returning its absolute root. It pins a deterministic identity and an
// isolated environment so the suite's stage/commit cases run against an actual worktree.
// Cleanup is t.TempDir()'s own (the directory is reaped by the testing framework).
func initRealRepo(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	mustGit(t, root, "init", "-q", "-b", "main")
	mustGit(t, root, "config", "user.name", "Eden Seed")
	mustGit(t, root, "config", "user.email", "seed@eden.dev")
	return root
}

// mustGit runs a git command in dir for the suite's real arm, failing the test on error.
func mustGit(t *testing.T, dir string, args ...string) {
	t.Helper()
	command := exec.Command("git", args...) //nolint:gosec // suite args are test-literal; never user input.
	command.Dir = dir
	command.Env = seedEnv()
	if out, err := command.CombinedOutput(); err != nil {
		t.Fatalf("git %v: %v: %s", args, err, out)
	}
}

// writeRealFile writes content to an absolute path on disk, creating parent dirs, failing the
// test on error.
func writeRealFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir %s: %v", filepath.Dir(path), err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil { //nolint:gosec // suite fixtures are test data, 0644 is intentional.
		t.Fatalf("write %s: %v", path, err)
	}
}
