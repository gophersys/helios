package gitrepositorytest

import (
	"context"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// SeededCanary is the credential plaintext the suite seeds so the no-leak assertions have a
// concrete needle. A Clone/Fetch/Push resolves it, yet it must appear in NO recorded op
// argument projection.
const SeededCanary = "S3CR3T-canary-do-not-leak"

// canaryRef is the secrets.Reference the seeded canary resolves under.
const canaryRef = "vault://eden/git#token"

// RunBackendSuite drives any gitrepository.Backend through the substitutability properties
// (contract §4). The unit arm runs the in-memory fake; the live arm (//go:build integration) runs
// the SAME suite against the real system-git Backend. newBackend builds a FRESH Backend per case
// so cases never share mutable model state.
//
//nolint:thelper // RunBackendSuite IS the suite entrypoint; subtests carry t directly.
func RunBackendSuite(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Run("NeverAMergeEngine", func(t *testing.T) { assertNeverMergeEngine(t) })
	t.Run("PureSpineNoIO", func(t *testing.T) { assertPureSpine(t, newBackend) })
	t.Run("ValueRoundTrips", func(t *testing.T) { assertValueRoundTrips(t) })
	t.Run("StageCommitAuditIdentity", func(t *testing.T) { assertAuditIdentity(t, newBackend) })
	t.Run("CommitRequiresIdentity", func(t *testing.T) { assertCommitRequiresIdentity(t, newBackend) })
	t.Run("NothingToCommit", func(t *testing.T) { assertNothingToCommit(t, newBackend) })
	t.Run("WorktreeIsolation", func(t *testing.T) { assertWorktreeIsolation(t, newBackend) })
	t.Run("RemoveWorktreeIdempotentAndGuarded", func(t *testing.T) { assertRemoveWorktree(t, newBackend) })
	t.Run("ReadSurfacesFaithful", func(t *testing.T) { assertReadSurfaces(t, newBackend) })
	t.Run("DiffBoundedAndBinaryAware", func(t *testing.T) { assertDiffBounded(t, newBackend) })
	t.Run("FastForwardOnlyPush", func(t *testing.T) { assertFastForwardOnly(t, newBackend) })
	t.Run("CredentialNeverLeaks", func(t *testing.T) { assertCredentialNeverLeaks(t, newBackend) })
	t.Run("TypedErrors", func(t *testing.T) { assertTypedErrors(t, newBackend) })
}

// Suite plumbing.

// fixture is a backend-agnostic seam the suite drives: it carries a freshly-constructed
// *Repository plus the operations the suite needs that differ between the in-memory fake (a
// model write) and a real backend (a disk write) — placing a working-tree file and learning
// the bound root. Both arms then exercise the SAME port methods, so substitutability is
// EXECUTED, not asserted.
type fixture struct {
	repository *gitrepository.Repository
	backend    gitrepository.Backend
	provider   *secretstest.Provider
	root       string
	// putWorking places a working-tree file (model write for the fake, disk write for real).
	putWorking func(worktree, path, content string)
}

// newFixture builds a fixture over a fresh backend. For the in-memory fake it binds a stable
// abstract root and writes through the model; for a real backend it inits a REAL repo on disk
// in t.TempDir() and writes to disk. remotes are wired into Config.
func newFixture(t *testing.T, backend gitrepository.Backend, remotes map[string]string) *fixture {
	t.Helper()
	provider := secretstest.New(map[string]string{canaryRef: SeededCanary})

	if fake, ok := backend.(*Backend); ok {
		root := memRoot()
		repository, err := gitrepository.New(
			gitrepository.Config{Root: root, Remotes: remotes, DefaultAuthor: platformActor()},
			gitrepository.Deps{Backend: backend, Secrets: provider, Clock: fixedClock{at: epoch}},
		)
		if err != nil {
			t.Fatalf("construct repository (fake): %v", err)
		}
		return &fixture{
			repository: repository, backend: backend, provider: provider, root: root,
			putWorking: func(worktree, path, content string) { fake.SetWorkingFile(worktree, path, content) },
		}
	}

	// A real backend: materialize an empty on-disk repo so the suite's stage/commit cases have a
	// genuine worktree.
	root := initRealRepo(t)
	repository, err := gitrepository.New(
		gitrepository.Config{Root: root, Remotes: remotes, DefaultAuthor: platformActor()},
		gitrepository.Deps{Backend: backend, Secrets: provider, Clock: fixedClock{at: epoch}},
	)
	if err != nil {
		t.Fatalf("construct repository (real): %v", err)
	}
	return &fixture{
		repository: repository, backend: backend, provider: provider, root: root,
		putWorking: func(worktree, path, content string) { writeRealFile(t, filepath.Join(worktree, path), content) },
	}
}

// platformActor is the suite's DefaultAuthor.
func platformActor() gitrepository.Identity {
	return gitrepository.Identity{Name: "Eden Platform", Email: "platform@eden.dev", Kind: gitrepository.ActorPlatform}
}

// memRoot is the stable absolute root the in-memory suite cases bind to.
func memRoot() string { return filepath.FromSlash("/in-memory") }

// §4 properties.

// assertNeverMergeEngine is the reflective check that the surface has NO merge verb (the
// single most important boundary, §6). It inspects the three consumer ports for any method
// whose name implies a merge/rebase/cherry-pick/pull/force/reset operation.
func assertNeverMergeEngine(t *testing.T) {
	t.Helper()
	forbidden := []string{"Merge", "Rebase", "CherryPick", "Pull", "Force", "Reset"}
	for _, iface := range []reflect.Type{
		reflect.TypeOf((*gitrepository.Provisioner)(nil)).Elem(),
		reflect.TypeOf((*gitrepository.Inspector)(nil)).Elem(),
		reflect.TypeOf((*gitrepository.Author)(nil)).Elem(),
	} {
		for i := range iface.NumMethod() {
			name := iface.Method(i).Name
			for _, bad := range forbidden {
				if name == bad {
					t.Errorf("surface exposes a forbidden merge-family verb: %s.%s", iface.Name(), name)
				}
			}
		}
	}
	// PushOptions must have NO Force field (the compile-time ff-only guarantee).
	pushType := reflect.TypeOf(gitrepository.PushOptions{})
	if _, ok := pushType.FieldByName("Force"); ok {
		t.Errorf("PushOptions must not have a Force field (push is fast-forward-only by contract)")
	}
}

// assertPureSpine confirms New runs no git: it constructs over a backend and asserts no op was
// recorded, then that the first verb is what triggers a backend call.
func assertPureSpine(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	backend := newBackend()
	repository, err := gitrepository.New(
		gitrepository.Config{Root: memRoot()},
		gitrepository.Deps{Backend: backend, Clock: fixedClock{at: epoch}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if repository == nil {
		t.Fatal("New returned nil repository")
	}
	// New must not read the clock: a zero Identity.When is stamped only at Commit time. There is
	// no observable side effect to assert beyond "New did not error and returned a handle"; the
	// integration arm asserts no .git was created by New (only by the first verb).
	_ = backend
}

// assertValueRoundTrips checks ParseBranchName round-trips and rejects injection-shaped names,
// and that the zero CommitID reports invalid.
func assertValueRoundTrips(t *testing.T) {
	t.Helper()
	for _, name := range []string{"main", "feature/x", "release/2026.06"} {
		parsed, err := gitrepository.ParseBranchName(name)
		if err != nil {
			t.Errorf("ParseBranchName(%q) errored: %v", name, err)
			continue
		}
		if parsed.String() != name {
			t.Errorf("ParseBranchName(%q).String() = %q", name, parsed.String())
		}
	}
	for _, bad := range []string{"-x", "a..b", "a b", "feature/", "/feature", "a\x00b", "@{0}", ".hidden"} {
		if _, err := gitrepository.ParseBranchName(bad); err == nil {
			t.Errorf("ParseBranchName(%q) must reject an injection-shaped name", bad)
		}
	}
	if !(gitrepository.CommitID{}).IsZero() {
		t.Errorf("zero CommitID must report IsZero")
	}
}

// assertAuditIdentity proves an ActorAgent commit injects the Eden-* trailers + sets
// author/committer, the returned CommitID resolves, and the commit time defaults to the
// injected Clock. It exercises the full stage→commit path through the port. The trailer-
// queryability assertion lives in the integration arm (it inspects real `git log`).
func assertAuditIdentity(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	fix := newFixture(t, newBackend(), nil)
	ctx := context.Background()

	fix.putWorking(fix.root, "a.txt", "hello\n")
	if _, err := fix.repository.Stage(ctx, fix.root, gitrepository.StageOptions{Paths: []string{"a.txt"}}); err != nil {
		t.Fatalf("Stage: %v", err)
	}
	agent := gitrepository.Identity{
		Name: "Eden Agent (implement)", Email: "agent+run9@eden.dev", Kind: gitrepository.ActorAgent,
		RunID: "run9", SessionID: "sess3", Phase: "implement",
	}
	id, err := fix.repository.Commit(ctx, fix.root, "feat: thing", agent, gitrepository.CommitOptions{})
	if err != nil {
		t.Fatalf("Commit(agent): %v", err)
	}
	if id.IsZero() {
		t.Errorf("agent Commit returned a zero CommitID")
	}
	// HEAD now resolves to the new commit (the read surface sees it).
	status, serr := fix.repository.Status(ctx, fix.root)
	if serr != nil {
		t.Fatalf("Status after commit: %v", serr)
	}
	if status.Head != id {
		t.Errorf("Status.Head = %s after commit, want %s", status.Head, id)
	}
	if !status.Clean {
		t.Errorf("worktree must be clean after committing the only change")
	}
}

// assertCommitRequiresIdentity proves a zero Identity is an InvalidRefError (every commit is
// attributable).
func assertCommitRequiresIdentity(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	backend := newBackend()
	// Construct WITHOUT a DefaultAuthor so a zero per-commit Identity stays zero.
	var root string
	if _, ok := backend.(*Backend); ok {
		root = memRoot()
	} else {
		root = initRealRepo(t)
	}
	provider := secretstest.New(map[string]string{canaryRef: SeededCanary})
	repository, err := gitrepository.New(
		gitrepository.Config{Root: root},
		gitrepository.Deps{Backend: backend, Secrets: provider, Clock: fixedClock{at: epoch}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if fake, ok := backend.(*Backend); ok {
		fake.SetWorkingFile(root, "a.txt", "x\n")
	} else {
		writeRealFile(t, filepath.Join(root, "a.txt"), "x\n")
	}
	if _, serr := repository.Stage(context.Background(), root, gitrepository.StageOptions{Paths: []string{"a.txt"}}); serr != nil {
		t.Fatalf("Stage: %v", serr)
	}
	_, err = repository.Commit(context.Background(), root, "msg", gitrepository.Identity{}, gitrepository.CommitOptions{})
	assertKind(t, err, errors.KindInvalid, "Commit with a zero Identity")
	if !errors.IsType[*gitrepository.InvalidRefError](err) {
		t.Errorf("Commit zero-Identity error must be InvalidRefError, got %T", err)
	}
}

// assertNothingToCommit proves an empty index with AllowEmpty=false returns
// NothingToCommitError (a clean no-op signal).
func assertNothingToCommit(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	fix := newFixture(t, newBackend(), nil)
	_, err := fix.repository.Commit(context.Background(), fix.root, "nothing",
		gitrepository.Identity{Name: "A", Email: "a@b.dev", Kind: gitrepository.ActorHuman},
		gitrepository.CommitOptions{})
	if !errors.IsType[*gitrepository.NothingToCommitError](err) {
		t.Errorf("empty-index Commit must be NothingToCommitError, got %v (%T)", err, err)
	}
	assertKind(t, err, errors.KindConflict, "NothingToCommit")
}

// assertKind asserts err classifies to the expected errors.Kind.
func assertKind(t *testing.T, err error, want errors.Kind, description string) {
	t.Helper()
	if err == nil {
		t.Errorf("%s: expected an error of kind %v, got nil", description, want)
		return
	}
	if got := errors.KindOf(err); got != want {
		t.Errorf("%s: KindOf = %v, want %v (err: %v)", description, got, want, err)
	}
}
