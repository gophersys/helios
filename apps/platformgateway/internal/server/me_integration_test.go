//go:build integration

// me_integration_test.go is the REAL-substrate integration lane for the IOTEA-style RBAC foundation
// (ADR-0016 §2: never mocked). On an EPHEMERAL postgres it runs the EMBEDDED startup migrate path
// (the SAME path the composition root runs on boot — now including 0002_create_rbac), seeds the
// default user + a default organization + an admin permission set (permissions ["*"]) + the default
// user as an ADMIN member through the persistence facade, wires the typed users + RBAC facades through
// server.New, serves the assembled handler tree, and drives GET /v1/me through the EMITTED Go client
// with a token whose SUBJECT is the seeded user id — asserting the profile's org/role/permissions. It
// also asserts the PUBLIC bootstrap now returns the profile fields alongside the user fields. So the
// migration, the sqlc RBAC queries, the seed, the /me route, and the bootstrap profile are proven to
// AGREE end to end on a real database. Run via `bash ./ctl.sh integration` (requires docker).
package server_test

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/secrets"

	client "github.com/gophersys/eden/apps/platformgateway/clients/go/generated"
	"github.com/gophersys/eden/apps/platformgateway/internal/server"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// TestIntegration_RBACProfile proves the RBAC foundation on a REAL postgres: migrate (incl. the RBAC
// tables) + the idempotent seed (org + admin permission set + admin membership), then GET /v1/me
// through the emitted client (token subject = the seeded user id) returns the profile, and the public
// bootstrap returns the profile fields too.
func TestIntegration_RBACProfile(t *testing.T) {
	t.Parallel()
	dsn := startPostgres(t)

	dataStore := openPersistence(t, dsn)
	ctx := context.Background()

	if err := dataStore.Migrate(ctx); err != nil {
		t.Fatalf("migrate: %v", err)
	}

	// Seed the default user, then the IOTEA RBAC: a default org, an admin permission set (permissions
	// ["*"]), and the default user as an admin member — all idempotent (the second pass is a no-op).
	userID := uuid.New()
	orgID := uuid.New()
	permissionSetID := uuid.New()
	membershipID := uuid.New()
	seedRBAC(ctx, t, dataStore, userID, orgID, permissionSetID, membershipID)
	// Re-seed: every Ensure* is ON CONFLICT DO NOTHING, so the boot seed is safe to run on every start.
	seedRBAC(ctx, t, dataStore, userID, orgID, permissionSetID, membershipID)

	srv := newServerWithRBAC(t, dataStore)
	httpServer := httptest.NewServer(srv.Handler())
	t.Cleanup(httpServer.Close)

	driveMe(ctx, t, httpServer.URL, userID, orgID)
	driveBootstrapProfile(t, httpServer.URL, userID, orgID)
}

// seedRBAC plants the user + the default org + the admin permission set (permissions ["*"]) + the
// default user as an admin member, through the persistence facade (the SAME methods the composition
// root calls on boot).
func seedRBAC(ctx context.Context, t *testing.T, dataStore *persistence.Persistence, userID, orgID, permissionSetID, membershipID uuid.UUID) {
	t.Helper()
	if err := dataStore.Users().EnsureDefault(ctx, userID, "default@eden.local", "Default User"); err != nil {
		t.Fatalf("seed default user: %v", err)
	}
	if err := dataStore.RBAC().EnsureOrganization(ctx, orgID, "Eden"); err != nil {
		t.Fatalf("seed organization: %v", err)
	}
	if err := dataStore.RBAC().EnsurePermissionSet(ctx, permissionSetID, orgID, "Admin", []string{"*"}); err != nil {
		t.Fatalf("seed permission set: %v", err)
	}
	if err := dataStore.RBAC().EnsureMembership(ctx, membershipID, orgID, userID, permissionSetID, "admin"); err != nil {
		t.Fatalf("seed membership: %v", err)
	}
}

// driveMe drives GET /v1/me through the emitted client with a token whose SUBJECT is the seeded user
// id, asserting the 200 profile carries the user, the org (id + name), the admin role, and the
// wildcard permission ["*"] — the RBAC read proven on the real database.
func driveMe(ctx context.Context, t *testing.T, baseURL string, userID, orgID uuid.UUID) {
	t.Helper()
	bearer := tokenForSubject(t, userID.String())
	api, err := client.NewClientWithResponses(baseURL+"/v1", client.WithRequestEditorFn(
		func(_ context.Context, request *http.Request) error {
			request.Header.Set("Authorization", "Bearer "+bearer)
			return nil
		},
	))
	if err != nil {
		t.Fatalf("new client: %v", err)
	}
	got, err := api.GetMeWithResponse(ctx)
	if err != nil {
		t.Fatalf("get /me: %v", err)
	}
	if got.StatusCode() != http.StatusOK || got.JSON200 == nil {
		t.Fatalf("get /me status = %d, body = %s", got.StatusCode(), string(got.Body))
	}
	profile := got.JSON200.Data
	if profile.Id != userID.String() || profile.Email != "default@eden.local" {
		t.Fatalf("/me user = %+v, want id %s email default@eden.local", profile, userID)
	}
	if profile.Organization.Id != orgID.String() || profile.Organization.Name != "Eden" {
		t.Fatalf("/me organization = %+v, want id %s name Eden", profile.Organization, orgID)
	}
	if profile.Role != "admin" || len(profile.Permissions) != 1 || profile.Permissions[0] != "*" {
		t.Fatalf("/me role/permissions = %q/%v, want admin/[*]", profile.Role, profile.Permissions)
	}
	assertSuccessEnvelope(t, "me", got.Body)
}

// driveBootstrapProfile hits the PUBLIC bootstrap (no token) and asserts it now returns the profile
// fields (organization/role/permissions) ALONGSIDE the existing user fields, on the real database.
func driveBootstrapProfile(t *testing.T, baseURL string, userID, orgID uuid.UUID) {
	t.Helper()
	resp, err := http.Get(baseURL + "/bootstrap/default-user") //nolint:noctx // a test probe of a local httptest server.
	if err != nil {
		t.Fatalf("bootstrap GET: %v", err)
	}
	defer func() { _ = resp.Body.Close() }() //nolint:errcheck // probe response close fault is irrelevant to the assertion.
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("bootstrap status = %d, want 200 (public, no token)", resp.StatusCode)
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("bootstrap read body: %v", err)
	}
	var envelope struct {
		Data struct {
			Id           string `json:"id"`
			Email        string `json:"email"`
			IsDefault    bool   `json:"isDefault"`
			Organization struct {
				Id   string `json:"id"`
				Name string `json:"name"`
			} `json:"organization"`
			Role        string   `json:"role"`
			Permissions []string `json:"permissions"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &envelope); err != nil {
		t.Fatalf("bootstrap decode: %v; body = %s", err, string(body))
	}
	data := envelope.Data
	if data.Id != userID.String() || data.Email != "default@eden.local" || !data.IsDefault {
		t.Fatalf("bootstrap user fields = %+v, want the seeded default user (id %s)", data, userID)
	}
	if data.Organization.Id != orgID.String() || data.Organization.Name != "Eden" {
		t.Fatalf("bootstrap organization = %+v, want id %s name Eden", data.Organization, orgID)
	}
	if data.Role != "admin" || len(data.Permissions) != 1 || data.Permissions[0] != "*" {
		t.Fatalf("bootstrap role/permissions = %q/%v, want admin/[*]", data.Role, data.Permissions)
	}
}

// newServerWithRBAC assembles the gateway with the REAL persistence facades wired as the users store,
// the RBAC store, the Accounts store, and the bootstrap providers, through the same server.New the
// composition root calls. It CLEARS the fake GrantResolver so the server derives the persistence-backed
// RBACGrantResolver — the DB-driven authorize is the REAL membership read on the real database.
func newServerWithRBAC(t *testing.T, dataStore *persistence.Persistence) *server.Server {
	t.Helper()
	dependencies := newDeps(t)
	dependencies.Users = dataStore.Users()
	dependencies.RBAC = dataStore.RBAC()
	dependencies.Accounts = dataStore.Accounts()
	dependencies.DefaultUser = dataStore.Users()
	dependencies.DefaultMembership = dataStore.RBAC()
	dependencies.GrantResolver = nil // derive the REAL RBACGrantResolver from the real RBAC store.
	srv, err := server.New(server.Config{JWTSecretRef: secrets.Ref(jwtSecretRef)}, dependencies)
	if err != nil {
		t.Fatalf("server.New: %v", err)
	}
	return srv
}
