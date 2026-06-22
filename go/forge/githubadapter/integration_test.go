//go:build integration

// This is the DEFERRED real-substrate integration lane (test-taxonomy dimension d,
// ADR-0020). It is authored now and run in the integration pass, NOT in the fast
// unit suite. It hits the REAL github.com REST API over a real *http.Client, creates
// a throwaway repository, asserts the idempotent re-create reads it back, and
// DELETES it on cleanup (under a unique name namespace) so it leaves no residue.
//
// It is gated TWICE: the `integration` build tag AND a real GitHub PAT in the
// environment (EDEN_FORGE_GITHUB_TOKEN, with the `repo` + `delete_repo` scopes) plus
// the target owner (EDEN_FORGE_GITHUB_OWNER). With the tag set but the token absent,
// the test SKIPS with a precise message (a real PAT cannot be synthesized) — it never
// silently passes. The token is fed through a real secrets path: an env-backed
// secrets.Provider resolves the reference; the value never enters argv or a log.
//
// NOTE FOR THE INTEGRATION PASS: deleting a repository needs the `delete_repo` scope,
// which is BROADER than the `repo` scope Wave 1's CreateRepo needs. The throwaway PAT
// used by this lane must carry it; document that in the CI secret provisioning. The
// `DeleteRepo` call below is a TEST-ONLY teardown helper issued directly against the
// API (forge.Forge does not expose delete in Wave 1) — when a delete verb is added to
// the port, replace the inline teardown with it.

package githubadapter_test

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/forge"
	"github.com/gophersys/libs/go/forge/githubadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

const (
	envIntegrationToken = "EDEN_FORGE_GITHUB_TOKEN" //nolint:gosec // env var NAME, not a credential.
	envIntegrationOwner = "EDEN_FORGE_GITHUB_OWNER"
	integrationRefName  = "eden-forge-integration-token"
)

// TestIntegration_CreateRepo_RealGitHub creates a throwaway repository on the real
// github.com, re-creates it to prove the idempotent 422->GET read-back, then deletes
// it on cleanup. SKIPS (never fails) when the PAT/owner are absent.
func TestIntegration_CreateRepo_RealGitHub(t *testing.T) {
	token := os.Getenv(envIntegrationToken)
	owner := os.Getenv(envIntegrationOwner)
	if token == "" || owner == "" {
		t.Skipf("integration lane needs %s and %s in the environment; a real PAT cannot be synthesized", envIntegrationToken, envIntegrationOwner)
	}

	// Resolve the PAT through a real secrets path: an env-seeded provider hands the
	// adapter the value only via secrets.Secret.Use; the test never holds it in argv.
	provider := secretstest.New(map[string]string{integrationRefName: token})
	connector, err := githubadapter.New(
		githubadapter.Config{UserAgent: "eden-forge-integration"},
		githubadapter.Deps{HTTP: &http.Client{Timeout: 30 * time.Second}, Secrets: provider},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	// Unique, time-namespaced name so concurrent/retried runs never collide and a
	// leaked repository is identifiable as a forge integration artifact.
	name := fmt.Sprintf("eden-it-forge-%d", time.Now().UnixNano())
	request := forge.CreateRepoRequest{
		Owner:       owner,
		Name:        name,
		Private:     true,
		Description: "eden forge integration test — safe to delete",
		Credential:  secrets.Ref(integrationRefName),
	}

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	// ALWAYS reap the repository, even on a mid-test failure, under the unique name.
	t.Cleanup(func() {
		if delErr := deleteRepoForTeardown(context.Background(), token, owner, name); delErr != nil {
			t.Errorf("teardown: failed to delete throwaway repo %s/%s: %v", owner, name, delErr)
		}
	})

	created, err := connector.CreateRepo(ctx, request)
	if err != nil {
		t.Fatalf("CreateRepo (first): %v", err)
	}
	if created.CloneURL == "" || created.DefaultBranch == "" {
		t.Errorf("created repository is under-populated: %+v", created)
	}
	if created.Owner != owner || created.Name != name {
		t.Errorf("identity drift: got %s/%s, want %s/%s", created.Owner, created.Name, owner, name)
	}

	// Idempotency on the REAL substrate: a second create must 422 then read the same
	// repository back, not error.
	again, err := connector.CreateRepo(ctx, request)
	if err != nil {
		t.Fatalf("CreateRepo (idempotent re-create): %v", err)
	}
	if again.CloneURL != created.CloneURL {
		t.Errorf("idempotent re-create drifted: got %q, want %q", again.CloneURL, created.CloneURL)
	}
}

// TestIntegration_CreateRepo_BadTokenIsUnauthenticated proves a real 401 from
// github.com classifies as KindUnauthenticated end-to-end. SKIPS without an owner.
func TestIntegration_CreateRepo_BadTokenIsUnauthenticated(t *testing.T) {
	owner := os.Getenv(envIntegrationOwner)
	if owner == "" {
		t.Skipf("integration lane needs %s in the environment", envIntegrationOwner)
	}
	provider := secretstest.New(map[string]string{integrationRefName: "ghp_obviously_invalid_token"})
	connector, err := githubadapter.New(
		githubadapter.Config{},
		githubadapter.Deps{HTTP: &http.Client{Timeout: 30 * time.Second}, Secrets: provider},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	_, err = connector.CreateRepo(ctx, forge.CreateRepoRequest{
		Owner:      owner,
		Name:       fmt.Sprintf("eden-it-forgenoauth-%d", time.Now().UnixNano()),
		Credential: secrets.Ref(integrationRefName),
	})
	if err == nil {
		t.Fatal("expected an authentication error from github.com with a bad token")
	}
	if got := errors.KindOf(err); got != errors.KindUnauthenticated {
		t.Errorf("Kind: got %v, want KindUnauthenticated", got)
	}
}

// deleteRepoForTeardown issues DELETE /repos/{owner}/{name} directly against the API
// to reap the throwaway repository. It is a TEST-ONLY teardown (the forge.Forge port
// does not expose delete in Wave 1); when a delete verb lands on the port, replace
// this with it. Needs the `delete_repo` scope on the integration PAT.
func deleteRepoForTeardown(ctx context.Context, token, owner, name string) error {
	// Belt-and-suspenders: even this raw teardown is fenced by the same guard as forge.DeleteRepo —
	// it refuses to delete anything that is not an ephemeral eden-it-* repository off the protected
	// denylist, so a bad name can never reap a real repository.
	if err := forge.GuardDelete(owner, name); err != nil {
		return err
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodDelete,
		"https://api.github.com/repos/"+owner+"/"+name, nil)
	if err != nil {
		return err
	}
	request.Header.Set("Accept", "application/vnd.github+json")
	request.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	request.Header.Set("Authorization", "Bearer "+token)
	response, err := (&http.Client{Timeout: 30 * time.Second}).Do(request)
	if err != nil {
		return err
	}
	defer func() { _ = response.Body.Close() }()
	// 204 No Content is success; 404 means it was never created (already reaped) — both fine.
	if response.StatusCode != http.StatusNoContent && response.StatusCode != http.StatusNotFound {
		return fmt.Errorf("unexpected delete status %d", response.StatusCode)
	}
	return nil
}
