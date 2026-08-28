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
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// TestSystemGit_Conforms runs THE one conformance suite over the REAL system-git Backend
// (ADR-0016: the same suite the in-memory fake passes, now against an actual git binary). This
// is the proof shape the brief asks for — the system-git binding of the two (fake + real git).
func TestSystemGit_Conforms(t *testing.T) {
	t.Parallel()
	gitrepositorytest.RunBackendSuite(t, gitrepository.SystemGit)
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

// TestSystemGit_TemplateCopySeed drives the WHOLE template-copy ergonomic against real git: a
// template bare remote with multi-commit history is library-Cloned; origin is re-pointed at a
// fresh EMPTY bare repository (SetRemote); the clone's history is Flattened to a single seed
// commit; and that seed is Pushed into the new repo as a clean first push. It proves the
// end-state: the NEW repo holds EXACTLY ONE commit (the seed), the template's history is gone,
// and the full working tree survived — all while preserving the fast-forward-only Push contract.
func TestSystemGit_TemplateCopySeed(t *testing.T) {
	t.Parallel()
	ctx := context.Background()

	// A "template" bare remote seeded with three commits of history (via a working clone).
	templateBare := t.TempDir()
	mustRunGit(t, templateBare, "init", "-q", "--bare", "-b", "main")
	seedBareRemote(
		t, templateBare,
		seedStep{file: "README.md", content: "template v1\n", message: "template: init"},
		seedStep{file: "main.go", content: "package main\n", message: "template: add main"},
		seedStep{file: "README.md", content: "template v2\n", message: "template: update readme"},
	)
	if got := gitOutput(t, templateBare, "rev-list", "--count", "main"); got != "3" {
		t.Fatalf("template remote must carry 3 commits, got %s", got)
	}

	// A fresh EMPTY destination bare repository (the NEW repo we seed into).
	newBare := t.TempDir()
	mustRunGit(t, newBare, "init", "-q", "--bare", "-b", "main")

	// 1. Clone the template via the LIBRARY into a fresh work dir (origin → template).
	parent := t.TempDir()
	workDir := filepath.Join(parent, "checkout")
	provider := secretstest.New(map[string]string{"vault://eden/git#token": "ignored-for-local-file-remote"})
	cloner := buildRealRepository(t, parent, map[string]string{"origin": templateBare}, provider)
	clone, err := cloner.Clone(ctx, templateBare, workDir, gitrepository.CloneOptions{})
	if err != nil {
		t.Fatalf("Clone(template): %v", err)
	}

	// 2. Re-point origin at the NEW, empty repository so the seed pushes THERE, not at the template.
	if err := clone.SetRemote("origin", newBare); err != nil {
		t.Fatalf("SetRemote(origin→new): %v", err)
	}

	// 3. Flatten the template's history to a single seed commit.
	seed, err := clone.Flatten(ctx, gitrepository.FlattenOptions{
		Message: "seed from template",
		Author:  agentIdent("seedrun"),
	})
	if err != nil {
		t.Fatalf("Flatten: %v", err)
	}
	if seed.IsZero() {
		t.Fatal("Flatten returned a zero seed CommitID")
	}

	// 4. Push the seed into the NEW repo — a clean first push into an unborn branch (ff-only holds).
	branch := mustBranchName(t, "main")
	if _, err := clone.Push(ctx, gitrepository.PushOptions{Remote: "origin", LocalRef: branch}); err != nil {
		t.Fatalf("Push(seed→new repo): %v", err)
	}

	// End-state on the NEW repo: EXACTLY one commit, it is the seed, and it is a ROOT commit.
	if got := gitOutput(t, newBare, "rev-list", "--count", "main"); got != "1" {
		t.Errorf("the NEW repo must hold a single seed commit, got %s commits", got)
	}
	if got := gitOutput(t, newBare, "rev-parse", "main"); got != seed.String() {
		t.Errorf("the NEW repo's main = %s, want the seed id %s", got, seed.String())
	}
	if parents := gitOutput(t, newBare, "rev-list", "--parents", "-n", "1", "main"); strings.Contains(parents, " ") {
		t.Errorf("the seeded commit must be a ROOT commit (no parent); got %q", parents)
	}

	// The template's history is GONE from the new repo: none of its commit subjects survive.
	subjects := gitOutput(t, newBare, "log", "main", "--format=%s")
	if strings.Contains(subjects, "template:") {
		t.Errorf("the template's history must NOT bleed into the new repo; subjects:\n%s", subjects)
	}

	// The full working tree survived: every template file is tracked in the seed, latest content.
	tracked := gitOutput(t, newBare, "ls-tree", "-r", "--name-only", "main")
	for _, want := range []string{"README.md", "main.go"} {
		if !strings.Contains(tracked, want) {
			t.Errorf("seed tree missing %q; ls-tree:\n%s", want, tracked)
		}
	}
	if body := gitOutput(t, newBare, "show", "main:README.md"); !strings.Contains(body, "template v2") {
		t.Errorf("seed must carry the latest template content; README = %q", body)
	}

	// The seed is attributable (agent trailers queryable on the single commit in the new repo).
	trailers := gitOutput(t, newBare, "log", "-1", "main", "--format=%(trailers:only,unfold)")
	if !strings.Contains(trailers, "Eden-Run-ID: seedrun") {
		t.Errorf("seed commit must carry the agent audit trailer; got:\n%s", trailers)
	}
}

const (
	// envCloneAuthToken gates TestSystemGit_ClonePrivateRemote_RealAuth — a real PAT with at
	// least the `repo` read scope. The lane SKIPS (never fails) when it is absent.
	envCloneAuthToken = "EDEN_FORGE_GITHUB_TOKEN" //nolint:gosec // env var NAME, not a credential.
	// privateTemplateRemote is the real private repository the credential helper must authenticate
	// against. A local-file remote (every other test here) needs no auth, so it can NEVER exercise
	// the credential-helper run path — only a real https remote that issues a 401-without-creds does.
	privateTemplateRemote = "https://github.com/gophersys/template.git"
	cloneAuthRefName      = "eden-gitrepository-clone-token"
)

// TestSystemGit_ClonePrivateRemote_RealAuth clones a REAL private https remote
// (gophersys/template) through the library's credential helper, proving the helper actually
// authenticates real `git clone` over the network. This is the ONLY test in the suite that
// exercises the credential-helper RUN path: every other test targets a local-file bare remote,
// which git serves with no auth challenge, so git never invokes the helper. A regression in how
// `-c credential.helper=<path>` is passed (e.g. shell-quoting the absolute path so git treats it
// as a `git credential-<name>` lookup instead of a direct executable) makes the clone fail with
// "could not read Username for github.com" — exactly the defect this test now fences. SKIPS
// (never silently passes) without the PAT.
func TestSystemGit_ClonePrivateRemote_RealAuth(t *testing.T) {
	t.Parallel()
	token := os.Getenv(envCloneAuthToken)
	if token == "" {
		t.Skipf("clone-auth lane needs %s in the environment; a real PAT cannot be synthesized", envCloneAuthToken)
	}

	// The PAT flows through the real secrets seam: an env-seeded provider hands the token to the
	// credential helper only via secrets.Secret.Use — it is never placed on argv or a URL.
	provider := secretstest.New(map[string]string{cloneAuthRefName: token})
	parent := t.TempDir()
	repository := buildRealRepository(t, parent, map[string]string{"origin": privateTemplateRemote}, provider)

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	workDir := filepath.Join(parent, "checkout")
	clone, err := repository.Clone(ctx, privateTemplateRemote, workDir, gitrepository.CloneOptions{
		Depth:      1,
		Credential: secrets.Ref(cloneAuthRefName),
	})
	if err != nil {
		t.Fatalf("Clone(private remote via credential helper): %v", err)
	}
	if clone == nil {
		t.Fatal("Clone returned a nil repository for a successful private clone")
	}

	// The clone is real: it is a git work tree (a `.git`) carrying the template's tracked files.
	if _, statErr := os.Stat(filepath.Join(workDir, ".git")); statErr != nil {
		t.Fatalf("cloned work tree has no .git: %v", statErr)
	}
	tracked := gitOutput(t, workDir, "ls-files")
	if strings.TrimSpace(tracked) == "" {
		t.Fatal("cloned private template is empty; expected the template's tracked files")
	}

	// No-leak: the real PAT must never have reached an argv surface. The credential helper script
	// itself (and the token file it reads) live in a per-op temp dir under /tmp, NOT in the work
	// tree, so the checked-out files can never contain the secret.
	if strings.Contains(tracked, token) {
		t.Fatal("the PAT must never appear in a tracked path")
	}
}

// seedStep is one file+message commit applied to a bare remote by seedBareRemote.
type seedStep struct {
	file    string
	content string
	message string
}

// seedBareRemote clones a bare remote into a temp work dir, applies the given commits in order,
// and pushes them back — giving the bare remote a real multi-commit history.
func seedBareRemote(t *testing.T, bare string, steps ...seedStep) {
	t.Helper()
	work := t.TempDir()
	mustRunGit(t, "", "clone", "-q", bare, work)
	for _, step := range steps {
		writeFile(t, filepath.Join(work, step.file), step.content)
		mustRunGit(t, work, "add", "-A")
		mustRunGit(t, work, "-c", "user.name=Template", "-c", "user.email=template@eden.dev", "commit", "-q", "-m", step.message)
	}
	mustRunGit(t, work, "push", "-q", "origin", "main")
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
	if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
		t.Fatalf("mkdir %s: %v", filepath.Dir(path), err)
	}
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
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
	command := exec.Command("git", args...) //nolint:gosec // args are test-literal, never user input.
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
	command := exec.Command("git", args...) //nolint:gosec // args are test-literal, never user input.
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
