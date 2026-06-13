//go:build integration

// Package gitrepositorytest_test's integration suite runs against the REAL system git binary
// (ADR-0016: conformance is never a mock). It is gated behind the `integration` build tag so
// the default `go test` (and the pre-commit hook) stays fast; run it explicitly with
//
//	go test -tags integration ./...
//
// Every test spins ACTUAL git repositories and worktrees in t.TempDir() and reaps EVERYTHING
// on t.Cleanup (the framework reaps TempDir on failure too), so parallel or abandoned runs
// never collide and never leak. A push/fetch test targets a REAL LOCAL BARE REMOTE
// (git init --bare in a temp dir as origin) — no network, no cluster.
package gitrepositorytest_test

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/gitrepository/gitrepositorytest"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// TestSystemGit_Conforms runs THE one conformance suite over the REAL system-git Backend
// (ADR-0016: the same suite the in-memory fake passes, now against an actual git binary). This
// is the proof shape the brief asks for — the system-git binding of the two (fake + real git).
func TestSystemGit_Conforms(t *testing.T) {
	t.Parallel()
	gitrepositorytest.Run(t, gitrepository.SystemGit)
}

// TestSystemGit_NewRealRepo_StageCommitWithAuthor drives the FULL author plane against a REAL
// repo end-to-end: seed → working-tree edit → Stage → Commit with a real ActorAgent Author →
// assert the new commit resolves AND its Eden-* audit trailers are queryable via real
// `git log` (the audit-trail invariant, 02 §1 / 07 §7).
func TestSystemGit_NewRealRepo_StageCommitWithAuthor(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	dir, repository := gitrepositorytest.NewRealRepo(t, gitrepositorytest.RepoSeed{
		DefaultBranch: "main",
		Commits: []gitrepositorytest.SeedCommit{
			{Files: map[string]string{"README.md": "v1\n"}, Message: "init"},
		},
	})
	if repository == nil {
		t.Fatal("NewRealRepo returned a nil repository")
	}

	writeFile(t, filepath.Join(dir, "feature.go"), "package main\n")
	if _, err := repository.Stage(ctx, dir, gitrepository.StageOptions{Paths: []string{"feature.go"}}); err != nil {
		t.Fatalf("Stage: %v", err)
	}

	agent := gitrepository.Identity{
		Name: "Eden Agent (implement)", Email: "agent+run42@eden.dev", Kind: gitrepository.ActorAgent,
		RunID: "run42", SessionID: "sess7", Phase: "implement",
	}
	id, err := repository.Commit(ctx, dir, "feat: add feature", agent, gitrepository.CommitOptions{})
	if err != nil {
		t.Fatalf("Commit(agent): %v", err)
	}
	if id.IsZero() {
		t.Fatal("agent Commit returned a zero CommitID")
	}

	// The new commit is HEAD and resolves on disk.
	if head := gitOutput(t, dir, "rev-parse", "HEAD"); head != id.String() {
		t.Errorf("HEAD = %s, want the committed id %s", head, id.String())
	}

	// The Eden-* audit trailers are queryable via real git (the audit trail IS the git history).
	trailers := gitOutput(t, dir, "log", "-1", "--format=%(trailers:only,unfold)")
	for _, want := range []string{"Eden-Run-ID: run42", "Eden-Session-ID: sess7", "Eden-Phase: implement"} {
		if !strings.Contains(trailers, want) {
			t.Errorf("commit trailers missing %q; got:\n%s", want, trailers)
		}
	}

	// Author AND committer are the agent identity (attribution, both halves).
	authorLine := gitOutput(t, dir, "log", "-1", "--format=%an <%ae> / %cn <%ce>")
	if !strings.Contains(authorLine, "agent+run42@eden.dev") {
		t.Errorf("author/committer not stamped from Identity: %s", authorLine)
	}

	// A human commit carries NONE of the Eden-* trailers.
	writeFile(t, filepath.Join(dir, "human.txt"), "by a person\n")
	if _, err := repository.Stage(ctx, dir, gitrepository.StageOptions{Paths: []string{"human.txt"}}); err != nil {
		t.Fatalf("Stage(human): %v", err)
	}
	if _, err := repository.Commit(ctx, dir, "docs: human note",
		gitrepository.Identity{Name: "Mateo", Email: "mateo@eden.dev", Kind: gitrepository.ActorHuman},
		gitrepository.CommitOptions{}); err != nil {
		t.Fatalf("Commit(human): %v", err)
	}
	humanTrailers := gitOutput(t, dir, "log", "-1", "--format=%(trailers:only,unfold)")
	if strings.Contains(humanTrailers, "Eden-Run-ID") {
		t.Errorf("a human commit must carry NO Eden-Run-ID trailer; got:\n%s", humanTrailers)
	}
}

// TestSystemGit_RealWorktreeIsolation creates/removes REAL linked worktrees and proves the
// swarm-isolation primitive on disk: two worktrees over disjoint paths commit independently;
// RemoveWorktree prunes the .git/worktrees metadata (not a bare rm); the main tree is never
// removable.
func TestSystemGit_RealWorktreeIsolation(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	dir, repository := gitrepositorytest.NewRealRepo(t, gitrepositorytest.RepoSeed{
		Commits: []gitrepositorytest.SeedCommit{
			{Files: map[string]string{"base.txt": "base\n"}, Message: "base"},
		},
	})

	pathA := filepath.Join(dir, "wt-a")
	pathB := filepath.Join(dir, "wt-b")

	idA := seedWorktree(t, repository, pathA, "feature/a", "a.txt", "from A\n", "runA")
	idB := seedWorktree(t, repository, pathB, "feature/b", "b.txt", "from B\n", "runB")

	// Two real directories exist with their own .git link files.
	if !isDir(pathA) || !isDir(pathB) {
		t.Fatalf("linked worktree directories must exist on disk")
	}
	if idA == idB {
		t.Errorf("independent worktrees must produce distinct commits")
	}

	// Worktrees lists three live trees (main + A + B).
	worktrees, err := repository.Worktrees(ctx)
	if err != nil {
		t.Fatalf("Worktrees: %v", err)
	}
	if len(worktrees) != 3 {
		t.Errorf("expected 3 worktrees (main + A + B), got %d: %+v", len(worktrees), worktrees)
	}

	// RemoveWorktree prunes A's metadata (a real `git worktree remove`); B and main survive.
	if err := repository.RemoveWorktree(ctx, pathA, gitrepository.RemoveOptions{DeleteBranch: true}); err != nil {
		t.Fatalf("RemoveWorktree A: %v", err)
	}
	if isDir(pathA) {
		t.Errorf("RemoveWorktree must remove the worktree directory")
	}
	// The metadata is pruned, not a stale entry.
	list := gitOutput(t, dir, "worktree", "list", "--porcelain")
	if strings.Contains(list, pathA) {
		t.Errorf("RemoveWorktree must prune the .git/worktrees metadata; still listed:\n%s", list)
	}
	// Idempotent second removal.
	if err := repository.RemoveWorktree(ctx, pathA, gitrepository.RemoveOptions{}); err != nil {
		t.Errorf("second RemoveWorktree must be an idempotent no-op, got %v", err)
	}
	// The main tree is never removable.
	if err := repository.RemoveWorktree(ctx, dir, gitrepository.RemoveOptions{Force: true}); err == nil {
		t.Errorf("RemoveWorktree(main) must be rejected")
	} else if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("RemoveWorktree(main) must be KindInvalid, got %v", errors.KindOf(err))
	}
}

// seedWorktree adds a linked worktree at path on a fresh branch, writes a file, stages and
// commits it as an agent, and returns the new commit id — the per-worktree setup the isolation
// test repeats for two disjoint worktrees.
func seedWorktree(t *testing.T, repository *gitrepository.Repository, path, branchName, file, content, runID string) gitrepository.CommitID {
	t.Helper()
	ctx := context.Background()
	branch := mustBranchName(t, branchName)
	wt, err := repository.AddWorktree(ctx, gitrepository.WorktreeOptions{Path: path, Branch: branch, Start: "main"})
	if err != nil {
		t.Fatalf("AddWorktree %s: %v", branchName, err)
	}
	writeFile(t, filepath.Join(path, file), content)
	if _, err := wt.Stage(ctx, path, gitrepository.StageOptions{Paths: []string{file}}); err != nil {
		t.Fatalf("Stage %s: %v", branchName, err)
	}
	id, err := wt.Commit(ctx, path, "commit "+runID, agentIdent(runID), gitrepository.CommitOptions{})
	if err != nil {
		t.Fatalf("Commit %s: %v", branchName, err)
	}
	return id
}

// TestSystemGit_RealBareRemote_PushFetchFastForwardOnly drives Push/Fetch against a REAL LOCAL
// BARE REMOTE (git init --bare) and proves: a first push succeeds; a fetch reads the tip; a
// concurrent writer advances origin; and a DIVERGENT push is rejected NonFastForward carrying
// BOTH tips, with the remote ref left unchanged.
func TestSystemGit_RealBareRemote_PushFetchFastForwardOnly(t *testing.T) {
	t.Parallel()
	ctx := context.Background()

	bare := t.TempDir()
	mustRunGit(t, bare, "init", "-q", "--bare", "-b", "main")

	dir, _ := gitrepositorytest.NewRealRepo(t, gitrepositorytest.RepoSeed{
		Commits: []gitrepositorytest.SeedCommit{
			{Files: map[string]string{"base.txt": "base\n"}, Message: "base"},
		},
	})
	provider := secretstest.New(map[string]string{"vault://eden/git#token": "ignored-for-local-file-remote"})
	repository := buildRealRepository(t, dir, map[string]string{"origin": bare}, provider)
	branch := mustBranchName(t, "main")

	// First push to the bare remote (a clean fast-forward from empty).
	if _, err := repository.Push(ctx, gitrepository.PushOptions{Remote: "origin", LocalRef: branch}); err != nil {
		t.Fatalf("initial Push: %v", err)
	}
	// The bare remote now carries main.
	if got := gitOutput(t, bare, "rev-parse", "main"); got == "" {
		t.Fatalf("bare remote must carry main after push")
	}

	// Fetch reads the tip back.
	tips, err := repository.Fetch(ctx, gitrepository.FetchOptions{Remote: "origin", Refs: []gitrepository.Ref{{Remote: "origin", Branch: branch}}})
	if err != nil {
		t.Fatalf("Fetch: %v", err)
	}
	if tip := tips[gitrepository.Ref{Remote: "origin", Branch: branch}]; tip.IsZero() {
		t.Errorf("Fetch must report the remote's main tip")
	}

	// A concurrent writer advances origin/main; capture the new remote tip.
	remoteTipAfterAdvance := advanceBareRemote(t, bare)

	// Our repository now makes a DIVERGENT commit on main and pushes — rejected NonFastForward.
	writeFile(t, filepath.Join(dir, "diverge.txt"), "from us\n")
	if _, err := repository.Stage(ctx, dir, gitrepository.StageOptions{Paths: []string{"diverge.txt"}}); err != nil {
		t.Fatalf("Stage(diverge): %v", err)
	}
	if _, err := repository.Commit(ctx, dir, "diverge", agentIdent("runX"), gitrepository.CommitOptions{}); err != nil {
		t.Fatalf("Commit(diverge): %v", err)
	}
	_, pushErr := repository.Push(ctx, gitrepository.PushOptions{Remote: "origin", LocalRef: branch})
	nff, ok := errors.AsType[*gitrepository.NonFastForwardError](pushErr)
	if !ok || nff == nil {
		t.Fatalf("divergent Push must be NonFastForwardError, got %v (%T)", pushErr, pushErr)
	}
	if nff.Local.IsZero() || nff.Remote.IsZero() || nff.Local == nff.Remote {
		t.Errorf("NonFastForwardError must carry distinct local+remote tips: local=%s remote=%s", nff.Local, nff.Remote)
	}
	if nff.Remote.String() != remoteTipAfterAdvance {
		t.Errorf("NonFastForwardError.Remote = %s, want the advanced remote tip %s", nff.Remote, remoteTipAfterAdvance)
	}
	if errors.KindOf(pushErr) != errors.KindConflict {
		t.Errorf("NonFastForward must classify KindConflict, got %v", errors.KindOf(pushErr))
	}

	// The remote ref was NOT advanced by the rejected push (it still points at the writer's tip).
	if got := gitOutput(t, bare, "rev-parse", "main"); got != remoteTipAfterAdvance {
		t.Errorf("rejected push must NOT advance the remote ref: got %s, want %s", got, remoteTipAfterAdvance)
	}
}

// TestSystemGit_NewIsPure asserts New runs no git: it constructs over a path that has NO .git
// and never creates one (the pure-spine invariant — the first git op is the first verb).
func TestSystemGit_NewIsPure(t *testing.T) {
	t.Parallel()
	dir := t.TempDir() // an empty dir, NOT a git repo
	repository, err := gitrepository.New(
		gitrepository.Config{Root: dir},
		gitrepository.Deps{Backend: gitrepository.SystemGit(), Clock: fixedTestClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if repository == nil {
		t.Fatal("New returned nil")
	}
	if _, statErr := os.Stat(filepath.Join(dir, ".git")); !os.IsNotExist(statErr) {
		t.Errorf("New must not create a .git directory (it must run no git)")
	}
}

// TestSystemGit_New_RejectsNilClock proves the constructor validates Deps against the real
// backend: a nil Clock is rejected (the pure spine still requires its dependencies).
func TestSystemGit_New_RejectsNilClock(t *testing.T) {
	t.Parallel()
	dir := t.TempDir()
	_, err := gitrepository.New(
		gitrepository.Config{Root: dir},
		gitrepository.Deps{Backend: gitrepository.SystemGit(), Clock: nil},
	)
	if err == nil {
		t.Fatal("New must reject a nil Clock")
	}
	if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("nil-Clock New must be KindInvalid, got %v", errors.KindOf(err))
	}
}

// Integration helpers.

// fixedTestClock is a deterministic gitrepository.Clock for the integration constructors.
type fixedTestClock struct{}

func (fixedTestClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// buildRealRepository constructs a *gitrepository.Repository over the real system git backend
// for an on-disk dir, with the given remotes and secrets provider.
func buildRealRepository(t *testing.T, dir string, remotes map[string]string, provider *secretstest.Provider) *gitrepository.Repository {
	t.Helper()
	repository, err := gitrepository.New(
		gitrepository.Config{Root: dir, Remotes: remotes},
		gitrepository.Deps{Backend: gitrepository.SystemGit(), Secrets: provider, Clock: fixedTestClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return repository
}

// advanceBareRemote clones the bare remote, commits a file, and pushes — a genuine concurrent
// writer moving origin/main ahead — and returns the remote's new tip.
func advanceBareRemote(t *testing.T, bare string) string {
	t.Helper()
	other := t.TempDir()
	mustRunGit(t, "", "clone", "-q", bare, other)
	writeFile(t, filepath.Join(other, "other.txt"), "concurrent\n")
	mustRunGit(t, other, "add", "-A")
	mustRunGit(t, other, "-c", "user.name=Other", "-c", "user.email=other@eden.dev", "commit", "-q", "-m", "advance")
	mustRunGit(t, other, "push", "-q", "origin", "main")
	return gitOutput(t, bare, "rev-parse", "main")
}

// agentIdent builds an ActorAgent identity for a run id.
func agentIdent(runID string) gitrepository.Identity {
	return gitrepository.Identity{
		Name: "Eden Agent", Email: "agent+" + runID + "@eden.dev", Kind: gitrepository.ActorAgent,
		RunID: runID, SessionID: "sess-" + runID, Phase: "implement",
	}
}

// mustBranchName parses a branch name in a test.
func mustBranchName(t *testing.T, name string) gitrepository.BranchName {
	t.Helper()
	parsed, err := gitrepository.ParseBranchName(name)
	if err != nil {
		t.Fatalf("ParseBranchName(%q): %v", name, err)
	}
	return parsed
}

// writeFile writes content to an absolute path, creating parents, failing on error.
func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir %s: %v", filepath.Dir(path), err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

// isDir reports whether path is an existing directory.
func isDir(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

// gitOutput runs a git command in dir and returns its trimmed stdout, failing on error.
func gitOutput(t *testing.T, dir string, args ...string) string {
	t.Helper()
	command := exec.Command("git", args...)
	command.Dir = dir
	command.Env = integrationEnv()
	out, err := command.Output()
	if err != nil {
		t.Fatalf("git %v: %v", args, err)
	}
	return strings.TrimSpace(string(out))
}

// mustRunGit runs a git command in dir (or cwd-less for a clone), failing on error.
func mustRunGit(t *testing.T, dir string, args ...string) {
	t.Helper()
	command := exec.Command("git", args...)
	if dir != "" {
		command.Dir = dir
	}
	command.Env = integrationEnv()
	if out, err := command.CombinedOutput(); err != nil {
		t.Fatalf("git %v: %v: %s", args, err, out)
	}
}

// integrationEnv pins a deterministic, isolated git environment for the integration harness.
func integrationEnv() []string {
	env := []string{
		"GIT_TERMINAL_PROMPT=0", "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null", "LC_ALL=C",
	}
	if path := os.Getenv("PATH"); path != "" {
		env = append(env, "PATH="+path)
	}
	if home := os.Getenv("HOME"); home != "" {
		env = append(env, "HOME="+home)
	}
	return env
}
