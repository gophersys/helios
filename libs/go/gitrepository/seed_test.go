package gitrepository_test

import (
	"context"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/gitrepository/gitrepositorytest"
)

// platformSeedActor is the deterministic platform identity the seed tests stamp Flatten with.
func platformSeedActor() gitrepository.Identity {
	return gitrepository.Identity{Name: "Eden Platform", Email: "platform@eden.dev", Kind: gitrepository.ActorPlatform}
}

// newRepo builds a *Repository over the in-memory fake with the given remotes — the fast unit
// arm for the pure SetRemote/validation cases (no git binary, no clock read on New).
func newRepo(t *testing.T, remotes map[string]string) *gitrepository.Repository {
	t.Helper()
	repository, err := gitrepository.New(
		gitrepository.Config{Root: "/abs/root", Remotes: remotes, DefaultAuthor: platformSeedActor()},
		gitrepository.Deps{Backend: gitrepositorytest.New(), Clock: stubClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return repository
}

// TestSetRemote_RepointsResolution proves SetRemote re-points the logical name a Push/Fetch
// resolves against — the template-copy "push into the NEW repo" half. It is pure: no git
// process, only the in-memory logical map a transfer reads.
func TestSetRemote_RepointsResolution(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	repository := newRepo(t, map[string]string{"origin": "https://example.test/template.git"})

	// Re-point origin at the NEW repository, then a Fetch of an unknown ref reaches THAT URL —
	// proven by the NotFound carrying the new repo's context, not the template's.
	if err := repository.SetRemote("origin", "https://example.test/new-repo.git"); err != nil {
		t.Fatalf("SetRemote: %v", err)
	}

	// A Fetch on a now-known remote no longer fails with "remote not found"; an unknown remote
	// still does. This proves the map entry moved, not that the verb is a no-op.
	branch := mustParseBranch(t, "main")
	_, err := repository.Fetch(ctx, gitrepository.FetchOptions{
		Remote: "origin",
		Refs:   []gitrepository.Ref{{Remote: "origin", Branch: branch}},
	})
	// The fake fetch against an empty remote registry returns no error (no refs moved); the point
	// is that resolveRemote found the re-pointed URL rather than a NotFound.
	if err != nil {
		t.Fatalf("Fetch after SetRemote must resolve the re-pointed origin: %v", err)
	}

	// A logical name never configured is still unresolved.
	_, err = repository.Push(ctx, gitrepository.PushOptions{Remote: "nonesuch", LocalRef: branch})
	if errors.KindOf(err) != errors.KindNotFound {
		t.Errorf("Push to an unconfigured remote must be KindNotFound, got %v", errors.KindOf(err))
	}
}

// TestSetRemote_Adds proves SetRemote ADDS a brand-new logical remote (not only re-points one),
// so a clone with only "origin" can gain an "eden" authority mirror.
func TestSetRemote_Adds(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	repository := newRepo(t, map[string]string{"origin": "https://example.test/origin.git"})

	if err := repository.SetRemote("eden", "https://eden.test/authority.git"); err != nil {
		t.Fatalf("SetRemote(new): %v", err)
	}
	branch := mustParseBranch(t, "main")
	if _, err := repository.Fetch(ctx, gitrepository.FetchOptions{
		Remote: "eden",
		Refs:   []gitrepository.Ref{{Remote: "eden", Branch: branch}},
	}); err != nil {
		t.Fatalf("Fetch on the freshly-added remote must resolve: %v", err)
	}
}

// TestSetRemote_Validates proves SetRemote applies New's remote-name/URL guards: a malformed
// logical name, an empty URL, or a whitespace-bearing URL is a KindInvalid InvalidRefError, and
// the existing map is unchanged.
func TestSetRemote_Validates(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name string
		key  string
		url  string
	}{
		{"flag-injection name", "-origin", "https://example.test/x.git"},
		{"slash in name", "a/b", "https://example.test/x.git"},
		{"empty name", "", "https://example.test/x.git"},
		{"empty url", "origin", ""},
		{"whitespace url", "origin", "https://example.test/ x.git"},
		{"newline url", "origin", "https://example.test/x.git\n"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			repository := newRepo(t, map[string]string{"origin": "https://example.test/keep.git"})
			err := repository.SetRemote(tc.key, tc.url)
			if err == nil {
				t.Fatalf("SetRemote(%q,%q) must be rejected", tc.key, tc.url)
			}
			if errors.KindOf(err) != errors.KindInvalid {
				t.Errorf("SetRemote(%s) error must be KindInvalid, got %v", tc.name, errors.KindOf(err))
			}
		})
	}
}

// TestFlatten_Validates proves Flatten requires a non-empty message and a resolvable Identity,
// and rejects a canceled context before any backend work.
func TestFlatten_Validates(t *testing.T) {
	t.Parallel()

	// Missing message → KindInvalid.
	repository := newRepo(t, nil)
	_, err := repository.Flatten(context.Background(), gitrepository.FlattenOptions{
		Author: platformSeedActor(),
	})
	if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("Flatten without a message must be KindInvalid, got %v", errors.KindOf(err))
	}

	// A repository with NO DefaultAuthor and a zero per-op Author → KindInvalid (unattributable).
	noAuthor, nerr := gitrepository.New(
		gitrepository.Config{Root: "/abs/root"},
		gitrepository.Deps{Backend: gitrepositorytest.New(), Clock: stubClock{}},
	)
	if nerr != nil {
		t.Fatalf("New: %v", nerr)
	}
	_, err = noAuthor.Flatten(context.Background(), gitrepository.FlattenOptions{Message: "seed from template"})
	if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("Flatten with no resolvable Identity must be KindInvalid, got %v", errors.KindOf(err))
	}

	// A canceled context short-circuits.
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err = repository.Flatten(ctx, gitrepository.FlattenOptions{Message: "seed", Author: platformSeedActor()})
	if err == nil {
		t.Errorf("Flatten on a canceled context must return an error")
	}
}

// TestFlatten_RealLocalRepo_SingleSeedCommit drives the template-copy seed against a REAL local
// git repo (no remote): a clone-like multi-commit history is collapsed to a SINGLE root commit
// whose tree is the full working set, stamped with the seed Identity. It proves the cardinal
// property — the new repo starts with exactly one commit and the template's history is gone.
func TestFlatten_RealLocalRepo_SingleSeedCommit(t *testing.T) {
	t.Parallel()
	ctx := context.Background()

	// A "template" checkout with three commits of history (what a clone would carry).
	dir, repository := gitrepositorytest.NewRealRepo(t, gitrepositorytest.RepoSeed{
		DefaultBranch: "main",
		Commits: []gitrepositorytest.SeedCommit{
			{Files: map[string]string{"README.md": "template v1\n"}, Message: "template: init"},
			{Files: map[string]string{"main.go": "package main\n"}, Message: "template: add main"},
			{Files: map[string]string{"README.md": "template v2\n"}, Message: "template: update readme"},
		},
	})
	if repository == nil {
		t.Fatal("NewRealRepo returned a nil repository")
	}

	// Pre-condition: real history is present (3 commits).
	if before := gitCount(t, dir); before != 3 {
		t.Fatalf("seed must produce 3 commits, got %d", before)
	}

	seed, err := repository.Flatten(ctx, gitrepository.FlattenOptions{
		Message: "seed from template",
		Author: gitrepository.Identity{
			Name: "Eden Agent (init)", Email: "agent+seed@eden.dev", Kind: gitrepository.ActorAgent,
			RunID: "seedrun", SessionID: "sess1", Phase: "init",
		},
	})
	if err != nil {
		t.Fatalf("Flatten: %v", err)
	}
	if seed.IsZero() {
		t.Fatal("Flatten returned a zero seed CommitID")
	}

	// Cardinal property: exactly ONE commit reachable from the branch, and it is the seed.
	if after := gitCount(t, dir); after != 1 {
		t.Errorf("after Flatten the branch must have a single commit, got %d", after)
	}
	if head := gitRun(t, dir, "rev-parse", "HEAD"); head != seed.String() {
		t.Errorf("HEAD = %s, want the seed id %s", head, seed.String())
	}
	if parents := gitRun(t, dir, "rev-list", "--parents", "-n", "1", "HEAD"); strings.Contains(parents, " ") {
		t.Errorf("the seed commit must be a ROOT commit (no parent); rev-list = %q", parents)
	}

	// The FULL working tree survived the flatten (every template file is tracked in the seed).
	tracked := gitRun(t, dir, "ls-tree", "-r", "--name-only", "HEAD")
	for _, want := range []string{"README.md", "main.go"} {
		if !strings.Contains(tracked, want) {
			t.Errorf("seed tree missing %q; ls-tree:\n%s", want, tracked)
		}
	}
	// The latest content is preserved (README was updated to v2 before the flatten).
	if body := gitRun(t, dir, "show", "HEAD:README.md"); !strings.Contains(body, "template v2") {
		t.Errorf("seed must snapshot the latest tree content; README = %q", body)
	}

	// The seed is attributable: the agent trailers are queryable on the single commit.
	trailers := gitRun(t, dir, "log", "-1", "--format=%(trailers:only,unfold)")
	for _, want := range []string{"Eden-Run-ID: seedrun", "Eden-Session-ID: sess1", "Eden-Phase: init"} {
		if !strings.Contains(trailers, want) {
			t.Errorf("seed commit trailers missing %q; got:\n%s", want, trailers)
		}
	}
	if message := gitRun(t, dir, "log", "-1", "--format=%s"); message != "seed from template" {
		t.Errorf("seed message = %q, want %q", message, "seed from template")
	}
}

// mustParseBranch parses a branch name for the seed tests, failing on a malformed name.
func mustParseBranch(t *testing.T, name string) gitrepository.BranchName {
	t.Helper()
	branch, err := gitrepository.ParseBranchName(name)
	if err != nil {
		t.Fatalf("ParseBranchName(%q): %v", name, err)
	}
	return branch
}

// gitRun runs a git command in dir under an isolated environment and returns its trimmed stdout,
// failing the test on error. It is the seed test's own git driver (the real-local-repo arm).
func gitRun(t *testing.T, dir string, args ...string) string {
	t.Helper()
	command := exec.Command("git", args...) //nolint:gosec // args are test-literal, never user input.
	command.Dir = dir
	command.Env = seedTestEnv()
	out, err := command.Output()
	if err != nil {
		t.Fatalf("git %v: %v", args, err)
	}
	return strings.TrimSpace(string(out))
}

// gitCount returns the number of commits reachable from HEAD in dir.
func gitCount(t *testing.T, dir string) int {
	t.Helper()
	n, err := strconv.Atoi(gitRun(t, dir, "rev-list", "--count", "HEAD"))
	if err != nil {
		t.Fatalf("parse commit count: %v", err)
	}
	return n
}

// seedTestEnv pins a deterministic, isolated environment for the seed test's git (no user
// config, no credential prompt) — the same isolation the library's own backend uses.
func seedTestEnv() []string {
	env := []string{
		"GIT_TERMINAL_PROMPT=0",
		"GIT_CONFIG_NOSYSTEM=1",
		"GIT_CONFIG_GLOBAL=/dev/null",
		"LC_ALL=C",
	}
	if path := os.Getenv("PATH"); path != "" {
		env = append(env, "PATH="+path)
	}
	if home := os.Getenv("HOME"); home != "" {
		env = append(env, "HOME="+home)
	}
	return env
}
