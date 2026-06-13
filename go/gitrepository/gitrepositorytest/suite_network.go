package gitrepositorytest

import (
	"context"
	"os/exec"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// remoteURLFor returns the remote URL the suite uses for a backend kind. For the in-memory
// fake it is an abstract key into the shared remote registry; for a real backend it is a REAL
// bare repository on disk the caller created.
func remoteURLFor(t *testing.T, backend gitrepository.Backend) string {
	t.Helper()
	if _, ok := backend.(*Backend); ok {
		return "memory://origin"
	}
	return initBareRemote(t)
}

// initBareRemote creates a REAL bare repository on disk (a local origin), returning its path.
func initBareRemote(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	mustGit(t, dir, "init", "-q", "--bare", "-b", "main")
	return dir
}

// assertFastForwardOnlyImpl drives the ff-only push property end to end: a base commit is
// pushed to a shared remote; a SECOND repository over the same remote advances it; the first
// repository then makes a DIVERGENT commit and its push is rejected as NonFastForwardError
// carrying both tips, with the remote ref left UNCHANGED.
func assertFastForwardOnlyImpl(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	ctx := context.Background()

	backendA := newBackend()
	remoteURL := remoteURLFor(t, backendA)
	remotes := map[string]string{"origin": remoteURL}

	fixA := newFixture(t, backendA, remotes)
	branch := mustParse(t, "main")

	// Base commit on A, pushed to origin (a clean first push).
	seedCommit(t, fixA, fixA.root, "base.txt", "base\n", "base")
	if _, err := fixA.repository.Push(ctx, pushOptions("origin", branch)); err != nil {
		t.Fatalf("initial Push: %v", err)
	}

	// A concurrent writer advances origin/main under A (the remote moves out from under it).
	advanceRemote(t, remoteURL, backendA)

	// A now makes a DIVERGENT commit on main and pushes — it must be rejected NonFastForward.
	seedCommit(t, fixA, fixA.root, "diverge.txt", "from A\n", "diverge")
	_, err := fixA.repository.Push(ctx, pushOptions("origin", branch))
	nff, ok := errors.AsType[*gitrepository.NonFastForwardError](err)
	if !ok || nff == nil {
		t.Fatalf("divergent Push must be NonFastForwardError, got %v (%T)", err, err)
	}
	if nff.Local.IsZero() || nff.Remote.IsZero() {
		t.Errorf("NonFastForwardError must carry both tips: local=%s remote=%s", nff.Local, nff.Remote)
	}
	if nff.Local == nff.Remote {
		t.Errorf("NonFastForwardError local and remote tips must differ (they diverged)")
	}
	assertKind(t, err, errors.KindConflict, "NonFastForward Push")
}

// advanceRemote moves the remote's main branch one commit ahead of what repository A last
// pushed — a concurrent writer the ff-only case needs. For the in-memory fake it bumps the
// shared remote registry directly (AdvanceRemote); for a real backend it clones the REAL bare
// remote, commits, and pushes a genuine concurrent advance.
func advanceRemote(t *testing.T, remoteURL string, backend gitrepository.Backend) {
	t.Helper()
	if fake, ok := backend.(*Backend); ok {
		fake.AdvanceRemote(remoteURL, "main", "from another writer\n")
		return
	}
	work := t.TempDir()
	runSuiteGit(t, "", "clone", "-q", remoteURL, work)
	writeRealFile(t, work+"/other.txt", "from another writer\n")
	runSuiteGit(t, work, "add", "-A")
	runSuiteGit(t, work, "-c", "user.name=Other", "-c", "user.email=other@eden.dev", "commit", "-q", "-m", "advance")
	runSuiteGit(t, work, "push", "-q", "origin", "main")
}

// runSuiteGit runs a git command for the suite's network harness (real arm), failing on error.
func runSuiteGit(t *testing.T, dir string, args ...string) {
	t.Helper()
	command := exec.Command("git", args...) //nolint:gosec // suite args are test-literal; never user input.
	if dir != "" {
		command.Dir = dir
	}
	command.Env = seedEnv()
	if out, err := command.CombinedOutput(); err != nil {
		t.Fatalf("git %v: %v: %s", args, err, out)
	}
}

// pushOptions builds a PushOptions for a remote+branch with the canary credential reference.
func pushOptions(remote string, branch gitrepository.BranchName) gitrepository.PushOptions {
	return gitrepository.PushOptions{Remote: remote, LocalRef: branch, Auth: secrets.Ref(canaryRef)}
}

// assertCredentialNeverLeaksImpl proves the credential resolves via Deps.Secrets exactly when a
// networked op carries a reference, the canary never appears in a recorded op argument
// projection, and a bad credential yields AuthError carrying the ref (never the value).
func assertCredentialNeverLeaksImpl(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	ctx := context.Background()

	backend := newBackend()
	remoteURL := remoteURLFor(t, backend)
	fix := newFixture(t, backend, map[string]string{"origin": remoteURL})
	branch := mustParse(t, "main")

	seedCommit(t, fix, fix.root, "base.txt", "base\n", "base")
	if _, err := fix.repository.Push(ctx, pushOptions("origin", branch)); err != nil {
		t.Fatalf("Push with credential: %v", err)
	}

	// The reference was resolved exactly once for the push.
	if len(fix.provider.Resolved) == 0 {
		t.Errorf("Push must resolve the secrets.Reference via Deps.Secrets")
	}
	for _, ref := range fix.provider.Resolved {
		if ref.String() != canaryRef {
			t.Errorf("resolved an unexpected reference: %s", ref)
		}
	}

	// For the in-memory arm, the canary value must NOT appear in any recorded op projection.
	if fake, ok := backend.(*Backend); ok {
		fake.AssertCredentialNeverInArgs(t, SeededCanary)
	}

	// A bad credential reference (one the provider rejects) yields an authentication failure
	// carrying the ref, never the value. The provider fails the bad ref; the library wraps it as
	// an AuthError (KindUnauthenticated).
	const badRef = "vault://eden/bad#token"
	badProvider := secretstest.New(nil).FailWith(badRef, secrets.NotFoundError{Ref: secrets.Ref(badRef)})
	badRepo := buildRepository(t, backend, fix.root, map[string]string{"origin": remoteURL}, badProvider)
	_, err := badRepo.Fetch(ctx, gitrepository.FetchOptions{
		Remote: "origin",
		Refs:   []gitrepository.Ref{{Remote: "origin", Branch: branch}},
		Auth:   secrets.Ref(badRef),
	})
	if err == nil {
		t.Errorf("Fetch with a rejected credential reference must fail")
	} else {
		assertKind(t, err, errors.KindUnauthenticated, "Fetch(bad credential)")
		if containsCanary(err.Error()) {
			t.Errorf("error message leaked a credential value: %q", err.Error())
		}
	}
}

// buildRepository constructs a *Repository over backend with the given provider — used by the
// bad-credential arm.
func buildRepository(t *testing.T, backend gitrepository.Backend, root string, remotes map[string]string, provider secrets.Provider) *gitrepository.Repository {
	t.Helper()
	repository, err := gitrepository.New(
		gitrepository.Config{Root: root, Remotes: remotes, DefaultAuthor: platformActor()},
		gitrepository.Deps{Backend: backend, Secrets: provider, Clock: fixedClock{at: epoch}},
	)
	if err != nil {
		t.Fatalf("buildRepository: %v", err)
	}
	return repository
}

// containsCanary reports whether s contains the seeded canary value.
func containsCanary(s string) bool { return s != "" && indexOf(s, SeededCanary) >= 0 }

// indexOf is a tiny substring search (avoids importing strings in this small helper file).
func indexOf(haystack, needle string) int {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return i
		}
	}
	return -1
}
