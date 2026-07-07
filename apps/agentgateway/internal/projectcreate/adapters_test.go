package projectcreate_test

import (
	"context"
	"testing"
	"time"

	edenerrors "github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/forge"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/gitrepository/gitrepositorytest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/projectcreate"
)

// This file unit-tests the composition adapters that bind the saga's ports to the REAL libraries: the
// Seeder over the gitrepositorytest in-memory Backend (the SAME fake the gitrepository conformance
// suite drives), proving the real Clone -> Flatten -> SetRemote -> Push sequence + the idempotent
// already-seeded skip; and the ForgeAdapter over a fake forge.Forge, proving the mapping. The REAL
// system-git + real GitHub arm is the //go:build integration test (the orchestrator runs it).

const (
	templateURL = "https://github.com/gophersys/template.git"
	newRepoURL  = "https://github.com/MateoSegura/pay-backend-aabbccdd.git"
	ghTokenRef  = "gh://token"
)

type seedClock struct{}

func (seedClock) Now() time.Time { return time.Date(2026, time.June, 22, 12, 0, 0, 0, time.UTC) }

// newSeeder builds a Seeder over a fresh gitrepositorytest Backend whose template REMOTE is pre-seeded
// with content (so Clone has something to copy), plus a secretstest provider that resolves the gh token.
func newSeeder(t *testing.T) (*projectcreate.Seeder, *gitrepositorytest.Backend) {
	t.Helper()
	backend := gitrepositorytest.New()
	// Register the template remote with a seed commit so Clone copies it into the checkout.
	backend.AdvanceRemote(templateURL, "main", "template-readme")
	provider := secretstest.New(map[string]string{ghTokenRef: "FAKE-GH-PAT-do-not-leak"}) //nolint:gosec // G101: a deliberately FAKE token (never a real credential) for the in-memory fake backend.

	seeder, err := projectcreate.NewSeeder(
		projectcreate.SeederConfig{CheckoutRoot: t.TempDir()},
		projectcreate.SeederDeps{Backend: backend, Secrets: provider, Clock: seedClock{}},
	)
	if err != nil {
		t.Fatalf("NewSeeder: %v", err)
	}
	return seeder, backend
}

func TestSeeder_ClonesFlattensRepointsAndPushes(t *testing.T) {
	t.Parallel()
	seeder, backend := newSeeder(t)

	result, err := seeder.SeedRepository(context.Background(), projectcreate.SeedInput{
		ProjectID:     "project-aabbccddeeff001122",
		TemplateURL:   templateURL,
		RepositoryURL: newRepoURL,
		Credential:    secrets.Ref(ghTokenRef),
	})
	if err != nil {
		t.Fatalf("SeedRepository: %v", err)
	}
	if result.DefaultBranch != "main" {
		t.Errorf("default branch = %q, want main", result.DefaultBranch)
	}
	if result.CommitID == "" {
		t.Errorf("seed commit id empty, want the flatten commit")
	}

	// The push targeted the NEW repository (origin re-pointed), not the template — exactly one push,
	// to origin/main.
	if len(backend.Pushed) != 1 {
		t.Fatalf("pushes = %d, want 1", len(backend.Pushed))
	}
	if got := backend.Pushed[0].DestRef.String(); got != "main" {
		t.Errorf("pushed dest ref = %q, want main", got)
	}
	// The credential canary never reached an argument surface (the no-leak guarantee).
	backend.AssertCredentialNeverInArgs(t, "FAKE-GH-PAT-do-not-leak")
}

func TestSeeder_AlreadySeeded_IsIdempotentSkip(t *testing.T) {
	t.Parallel()
	seeder, backend := newSeeder(t)
	// The new repository ALREADY has content on main (a prior seed run) — diverged from the local seed,
	// so the ff-only push is rejected as non-fast-forward → the idempotent skip path.
	backend.AdvanceRemote(newRepoURL, "main", "already-seeded-content")

	result, err := seeder.SeedRepository(context.Background(), projectcreate.SeedInput{
		ProjectID:     "project-replaycase00112233",
		TemplateURL:   templateURL,
		RepositoryURL: newRepoURL,
		Credential:    secrets.Ref(ghTokenRef),
	})
	if err != nil {
		t.Fatalf("SeedRepository (already seeded) returned an error, want a clean idempotent skip: %v", err)
	}
	if result.DefaultBranch != "main" {
		t.Errorf("idempotent skip default branch = %q, want main", result.DefaultBranch)
	}
}

func TestSeeder_PropagatesRealFaults(t *testing.T) {
	t.Parallel()
	seeder, backend := newSeeder(t)
	// A transport-class push fault (NOT a non-ff) must surface, never be swallowed as idempotent.
	backend.FailNextPush(&gitrepository.AuthError{Reference: secrets.Ref(ghTokenRef), Remote: "origin"})

	_, err := seeder.SeedRepository(context.Background(), projectcreate.SeedInput{
		ProjectID:     "project-faultcase0011223344",
		TemplateURL:   templateURL,
		RepositoryURL: newRepoURL,
		Credential:    secrets.Ref(ghTokenRef),
	})
	if err == nil {
		t.Fatal("SeedRepository swallowed a push auth fault, want it surfaced")
	}
	if edenerrors.KindOf(err) != edenerrors.KindUnauthenticated {
		t.Errorf("error kind = %v, want unauthenticated", edenerrors.KindOf(err))
	}
}

func TestNewSeeder_RejectsBadConfig(t *testing.T) {
	t.Parallel()
	backend := gitrepositorytest.New()
	provider := secretstest.New(nil)
	seederDeps := projectcreate.SeederDeps{Backend: backend, Secrets: provider, Clock: seedClock{}}

	if _, err := projectcreate.NewSeeder(projectcreate.SeederConfig{CheckoutRoot: ""}, seederDeps); edenerrors.KindOf(err) != edenerrors.KindInvalid {
		t.Errorf("empty checkout root: kind = %v, want invalid", edenerrors.KindOf(err))
	}
	if _, err := projectcreate.NewSeeder(projectcreate.SeederConfig{CheckoutRoot: "relative/path"}, seederDeps); edenerrors.KindOf(err) != edenerrors.KindInvalid {
		t.Errorf("relative checkout root: kind = %v, want invalid", edenerrors.KindOf(err))
	}
}

// ── ForgeAdapter ───────────────────────────────────────────────────────────────────────────────.

// scriptForge is a fake forge.Forge that records the request and returns a scripted repository.
type scriptForge struct {
	request       forge.CreateRepositoryRequest
	deleteRequest forge.DeleteRepositoryRequest
	repository    forge.Repository
	err           error
}

//nolint:gocritic // matches forge.Forge (CreateRepository takes the request by value).
func (f *scriptForge) CreateRepository(_ context.Context, request forge.CreateRepositoryRequest) (forge.Repository, error) {
	f.request = request
	if f.err != nil {
		return forge.Repository{}, f.err
	}
	return f.repository, nil
}

// deleteRequest records the last DeleteRepository call so a test can assert the saga never deletes
// (the saga is create-only; the production path has no delete).
//
//nolint:gocritic // matches forge.Forge (DeleteRepository takes the request by value).
func (f *scriptForge) DeleteRepository(_ context.Context, request forge.DeleteRepositoryRequest) error {
	f.deleteRequest = request
	return f.err
}

func TestForgeAdapter_MapsRequestAndResult(t *testing.T) {
	t.Parallel()
	script := &scriptForge{repository: forge.Repository{
		Owner: "MateoSegura", Name: "pay-backend-aabbccdd",
		CloneURL: newRepoURL, DefaultBranch: "main",
	}}
	adapter, err := projectcreate.NewForgeAdapter(script)
	if err != nil {
		t.Fatalf("NewForgeAdapter: %v", err)
	}

	coordinates, err := adapter.CreateRepository(context.Background(), projectcreate.CreateRepositoryInput{
		Owner: "MateoSegura", Name: "pay-backend-aabbccdd", Private: true,
		Description: "Eden-built service: pay backend", Credential: secrets.Ref(ghTokenRef),
	})
	if err != nil {
		t.Fatalf("CreateRepository: %v", err)
	}
	// The request mapped through verbatim (owner/name/private/credential).
	if script.request.Owner != "MateoSegura" || script.request.Name != "pay-backend-aabbccdd" || !script.request.Private {
		t.Errorf("request not mapped: %+v", script.request)
	}
	if script.request.Credential.String() != ghTokenRef {
		t.Errorf("credential ref = %q, want %q", script.request.Credential.String(), ghTokenRef)
	}
	// The result mapped onto coordinates.
	if coordinates.CloneURL != newRepoURL || coordinates.DefaultBranch != "main" {
		t.Errorf("coordinates not mapped: %+v", coordinates)
	}
}

func TestForgeAdapter_PropagatesError(t *testing.T) {
	t.Parallel()
	script := &scriptForge{err: edenerrors.New(edenerrors.KindUnauthenticated, "bad token")}
	adapter, newErr := projectcreate.NewForgeAdapter(script)
	if newErr != nil {
		t.Fatalf("NewForgeAdapter: %v", newErr)
	}
	_, err := adapter.CreateRepository(context.Background(), projectcreate.CreateRepositoryInput{
		Owner: "MateoSegura", Name: "x", Credential: secrets.Ref(ghTokenRef),
	})
	if edenerrors.KindOf(err) != edenerrors.KindUnauthenticated {
		t.Errorf("error kind = %v, want unauthenticated", edenerrors.KindOf(err))
	}
}

func TestNewForgeAdapter_RejectsNil(t *testing.T) {
	t.Parallel()
	if _, err := projectcreate.NewForgeAdapter(nil); edenerrors.KindOf(err) != edenerrors.KindInvalid {
		t.Errorf("nil forge: kind = %v, want invalid", edenerrors.KindOf(err))
	}
}

// ── Materializer ───────────────────────────────────────────────────────────────────────────────.

func TestNewMaterializer_RejectsBadConfig(t *testing.T) {
	t.Parallel()
	manualDir := t.TempDir() // a real, existing dir so only the field under test is invalid.
	dependencies := projectcreate.MaterializerDeps{Backend: gitrepositorytest.New(), Secrets: secretstest.New(nil), Clock: seedClock{}}

	cases := []struct {
		name          string
		configuration projectcreate.MaterializerConfig
	}{
		{"relative workspace root", projectcreate.MaterializerConfig{WorkspaceRoot: "relative", ManualSourceDir: manualDir}},
		{"empty workspace root", projectcreate.MaterializerConfig{WorkspaceRoot: "", ManualSourceDir: manualDir}},
		{"relative manual source", projectcreate.MaterializerConfig{WorkspaceRoot: t.TempDir(), ManualSourceDir: "relative"}},
		{"manual source does not exist", projectcreate.MaterializerConfig{WorkspaceRoot: t.TempDir(), ManualSourceDir: "/nonexistent/eden/manual"}},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			if _, err := projectcreate.NewMaterializer(testCase.configuration, dependencies); edenerrors.KindOf(err) != edenerrors.KindInvalid {
				t.Errorf("%s: kind = %v, want invalid", testCase.name, edenerrors.KindOf(err))
			}
		})
	}

	// A complete configuration + a real manual dir constructs cleanly.
	if _, err := projectcreate.NewMaterializer(projectcreate.MaterializerConfig{WorkspaceRoot: t.TempDir(), ManualSourceDir: manualDir}, dependencies); err != nil {
		t.Errorf("valid materializer configuration rejected: %v", err)
	}
}
