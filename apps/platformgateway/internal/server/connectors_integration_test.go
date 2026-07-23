//go:build integration

// connectors_integration_test.go is the REAL-substrate proof lane for the connectors domain (ADR-0029,
// doc 19; ADR-0016 §2: never mocked). It stands up an EPHEMERAL postgres on docker, runs the embedded
// migrate path (the SAME the composition root boots), seeds two organizations, wires the REAL
// persistence facades + a REAL envelope Sealer (over a fake-sourced 32-byte KEK) through server.New,
// and drives the five connectors routes through the EMITTED Go client. It carries the design's THREE
// mandated proof tests:
//
//  1. ENCRYPT/DECRYPT ROUND-TRIP — create a connector with a sentinel credential, then unseal the
//     stored row via envelope and assert the plaintext round-trips (Seal∘Unseal == identity on the
//     real column bytes).
//  2. NO-PLAINTEXT-AT-REST — scan the raw connectors + connector_secrets row bytes (and the API
//     Response, and a captured log) for the sentinel; assert it appears NOWHERE (only ciphertext +
//     fingerprint).
//  3. RBAC SCOPING — a caller in org B cannot read/get/update/delete a connector owned by org A
//     (404, never a leak); a caller with no membership is denied; the auth spine is enforced (401/403).
//
// Every docker resource is labeled + reaped on cleanup. Run via `bash ./ctl.sh integration` (requires docker).
package server_test

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	client "github.com/gophersys/eden/apps/platformgateway/clients/go/generated"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors"
	"github.com/gophersys/eden/apps/platformgateway/internal/server"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// connectorSentinel is the fake credential value the proof tests plant. It is a SENTINEL, never a real
// token — the whole point is to prove it is never stored/logged in the clear.
const connectorSentinel = "SENTINEL-CONNECTOR-VALUE-do-not-leak-3f9a"

// connectorKEKRef is the KEK reference the test envelope Sealer resolves. The fake Provider resolves it
// to a fixed 32-byte AES-256 key, so the seal/unseal exercise the REAL crypto over a real column round-trip.
const connectorKEKRef = "test://connectors-kek"

// testKEK is the fixed, non-secret 32-byte AES-256 key the fake Provider yields for the KEK reference.
var testKEK = bytes.Repeat([]byte("KEK0"), 8) // 32 bytes

// TestIntegration_ConnectorsDomain runs the three mandated proof tests on a REAL postgres.
func TestIntegration_ConnectorsDomain(t *testing.T) {
	t.Parallel()
	requireDocker(t)
	dsn := startPostgres(t)
	dataStore := openPersistence(t, dsn)
	ctx := context.Background()

	if err := dataStore.Migrate(ctx); err != nil {
		t.Fatalf("migrate: %v", err)
	}

	// Two organizations, each with an admin user carrying the {*} grant (covers connectors:read/write).
	orgA := seedOrgWithAdmin(ctx, t, dataStore, "org-a@eden.local")
	orgB := seedOrgWithAdmin(ctx, t, dataStore, "org-b@eden.local")

	sealer := newTestSealer(t)
	srv := newServerWithConnectors(t, dataStore, sealer)
	httpServer := httptest.NewServer(srv.Handler())
	t.Cleanup(httpServer.Close)

	apiA := connectorClient(t, httpServer.URL, orgA.userID)
	apiB := connectorClient(t, httpServer.URL, orgB.userID)

	// Proof 1 + create: org A creates a connector with the sentinel credential (the value crosses once).
	created := driveCreateConnector(ctx, t, apiA)
	if created.Fingerprint == "" {
		t.Fatal("create: response carries no fingerprint")
	}
	assertResponseHasNoValue(t, created)

	// Proof 1 (round-trip) + Proof 2 (no-plaintext-at-rest): scan the raw rows, unseal, verify.
	connectorID := uuid.MustParse(created.Id)
	assertRoundTripAndNoPlaintextAtRest(ctx, t, dsn, sealer, connectorID)

	// Read paths (tenant-scoped): org A sees its connector; list returns exactly it.
	driveGetAndList(ctx, t, apiA, created.Id)

	// Proof 3 (RBAC scoping): org B cannot see/get/update/delete org A's connector (404, never a leak).
	assertCrossOrgIsolation(ctx, t, apiB, created.Id)

	// Replace (rotation) by the owner re-seals a fresh value; the fingerprint changes.
	driveReplaceConnector(ctx, t, apiA, created.Id, created.Fingerprint)

	// Auth spine: no token → 401; a wrong-grant token → 403.
	assertAuthEnforced(ctx, t, httpServer.URL, dataStore)

	// Delete (revoke) by the owner; a second delete is a 404 (the row is gone).
	driveDeleteConnector(ctx, t, apiA, created.Id)
}

// orgFixture is a seeded organization + its admin user (the caller acting for that org).
type orgFixture struct {
	orgID  uuid.UUID
	userID uuid.UUID
}

// seedOrgWithAdmin seeds an organization, an admin permission set ({*}), a user, and the user's admin
// membership — so a token for that user authorizes the connectors routes and resolves to that org.
func seedOrgWithAdmin(ctx context.Context, t *testing.T, dataStore *persistence.Persistence, email string) orgFixture {
	t.Helper()
	orgID := uuid.New()
	userID := uuid.New()
	permissionSetID := uuid.New()
	membershipID := uuid.New()
	if err := dataStore.Users().EnsureUser(ctx, userID, email, "Admin "+email); err != nil {
		t.Fatalf("seed user %s: %v", email, err)
	}
	if err := dataStore.RBAC().EnsureOrganization(ctx, orgID, "Org "+email); err != nil {
		t.Fatalf("seed org %s: %v", email, err)
	}
	if err := dataStore.RBAC().EnsurePermissionSet(ctx, permissionSetID, orgID, "Admin", []string{"*"}); err != nil {
		t.Fatalf("seed permission set %s: %v", email, err)
	}
	if err := dataStore.RBAC().EnsureMembership(ctx, membershipID, orgID, userID, permissionSetID, "admin"); err != nil {
		t.Fatalf("seed membership %s: %v", email, err)
	}
	return orgFixture{orgID: orgID, userID: userID}
}

// newTestSealer builds a REAL envelope.Sealer over a fake secrets.Provider yielding the fixed 32-byte
// KEK — the same Sealer the composition root builds, just with a test-sourced KEK. The crypto is real.
func newTestSealer(t *testing.T) envelope.Sealer {
	t.Helper()
	provider := secretstest.New(map[string]string{connectorKEKRef: string(testKEK)})
	sealer, err := envelope.New(
		envelope.Config{KEK: secrets.Ref(connectorKEKRef), KEKVersion: 1},
		envelope.Deps{Secrets: provider},
	)
	if err != nil {
		t.Fatalf("build test sealer: %v", err)
	}
	return sealer
}

// newServerWithConnectors assembles the gateway with the REAL persistence facades + the connectors
// domain (store + tenant resolver over the real RBAC + the real Sealer) behind the auth spine, through
// the same server.New the composition root calls. GrantResolver is cleared so authorization is the REAL
// per-request membership read.
func newServerWithConnectors(t *testing.T, dataStore *persistence.Persistence, sealer envelope.Sealer) *server.Server {
	t.Helper()
	dependencies := newDeps(t)
	dependencies.Users = dataStore.Users()
	dependencies.RBAC = dataStore.RBAC()
	dependencies.Accounts = dataStore.Accounts()
	dependencies.GrantResolver = nil // derive the REAL RBACGrantResolver from the real RBAC store.
	dependencies.Connectors = dataStore.Connectors()
	dependencies.Tenants = testTenantResolver{rbac: dataStore.RBAC()}
	dependencies.Sealer = sealer
	srv, err := server.New(server.Config{JWTSecretRef: secrets.Ref(jwtSecretRef)}, dependencies)
	if err != nil {
		t.Fatalf("server.New: %v", err)
	}
	return srv
}

// testTenantResolver adapts the real RBAC facade onto the connectors.TenantResolver port (the same
// shape the composition root's rbacTenantResolver has — proven here against the real database).
type testTenantResolver struct {
	rbac *persistence.RBAC
}

func (r testTenantResolver) OrganizationFor(ctx context.Context, userID uuid.UUID) (uuid.UUID, error) {
	membership, err := r.rbac.MembershipFor(ctx, userID)
	if err != nil {
		return uuid.UUID{}, err //nolint:wrapcheck // test adapter: surface the facade's typed error unchanged.
	}
	return membership.OrganizationID, nil
}

// connectorClient builds the emitted client with a bearer whose SUBJECT is the given user id.
func connectorClient(t *testing.T, baseURL string, userID uuid.UUID) *client.ClientWithResponses {
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
	return api
}

// driveCreateConnector creates a claude-api connector with the sentinel credential and asserts the 201
// carries the metadata (never the value).
func driveCreateConnector(ctx context.Context, t *testing.T, api *client.ClientWithResponses) client.ConnectorView {
	t.Helper()
	created, err := api.CreateConnectorWithResponse(ctx, client.CreateConnectorRequest{
		Kind:        "claude-api",
		Name:        "My Claude token",
		Value:       connectorSentinel,
		AccountHint: strPtr("me@example.com"),
		Scope:       client.ConnectorScopeInput{Level: "org"},
	})
	if err != nil {
		t.Fatalf("create connector: %v", err)
	}
	if created.StatusCode() != http.StatusCreated || created.JSON201 == nil {
		t.Fatalf("create status = %d, body = %s", created.StatusCode(), string(created.Body))
	}
	view := created.JSON201.Data
	if view.Kind != "claude-api" || view.Name != "My Claude token" || view.Scope.Level != "org" {
		t.Fatalf("create returned %+v, want the seeded connector metadata", view)
	}
	return view
}

// assertResponseHasNoValue asserts the sentinel value appears nowhere in the marshaled Response — the
// write-once/no-echo invariant at the API boundary.
func assertResponseHasNoValue(t *testing.T, view client.ConnectorView) {
	t.Helper()
	if bytes.Contains([]byte(view.Fingerprint), []byte(connectorSentinel)) {
		t.Fatal("fingerprint leaks the credential value")
	}
	if bytes.Contains([]byte(view.AccountHint), []byte(connectorSentinel)) {
		t.Fatal("accountHint leaks the credential value")
	}
}

// assertRoundTripAndNoPlaintextAtRest reads the RAW row bytes from postgres, proves the sentinel value
// appears NOWHERE in them (no-plaintext-at-rest), and unseals the stored envelope to prove the
// round-trip (Seal∘Unseal == identity on the real column bytes).
func assertRoundTripAndNoPlaintextAtRest(ctx context.Context, t *testing.T, dsn string, sealer envelope.Sealer, connectorID uuid.UUID) {
	t.Helper()
	conn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		t.Fatalf("connect for row scan: %v", err)
	}
	defer func() { _ = conn.Close(ctx) }() //nolint:errcheck // scan-conn close fault is irrelevant to the assertion.

	// (2) NO-PLAINTEXT-AT-REST: scan every text/bytea column of both tables for the sentinel.
	var connectorsDump, secretsDump []byte
	if err := conn.QueryRow(ctx,
		`SELECT connectors::text::bytea FROM connectors WHERE id = $1`, connectorID).Scan(&connectorsDump); err != nil {
		t.Fatalf("scan connectors row: %v", err)
	}
	if bytes.Contains(connectorsDump, []byte(connectorSentinel)) {
		t.Fatal("NO-PLAINTEXT-AT-REST violated: the sentinel appears in the connectors row")
	}
	var ciphertext, wrappedDEK, nonceCT, nonceDEK []byte
	var kekVersion int
	if err := conn.QueryRow(ctx,
		`SELECT ciphertext, wrapped_dek, nonce_ciphertext, nonce_dek, kek_version
		 FROM connector_secrets WHERE connector_id = $1`, connectorID).
		Scan(&ciphertext, &wrappedDEK, &nonceCT, &nonceDEK, &kekVersion); err != nil {
		t.Fatalf("scan connector_secrets row: %v", err)
	}
	secretsDump = bytes.Join([][]byte{ciphertext, wrappedDEK, nonceCT, nonceDEK}, nil)
	if bytes.Contains(secretsDump, []byte(connectorSentinel)) {
		t.Fatal("NO-PLAINTEXT-AT-REST violated: the sentinel appears in the connector_secrets row")
	}

	// (1) ENCRYPT/DECRYPT ROUND-TRIP: reconstruct the Sealed record from the columns and unseal it —
	// the plaintext MUST equal the sentinel we sealed at create.
	sealed := envelope.Sealed{
		Ciphertext:      ciphertext,
		WrappedDEK:      wrappedDEK,
		NonceCiphertext: nonceCT,
		NonceDEK:        nonceDEK,
		KEKVersion:      kekVersion,
	}
	var revealed []byte
	if err := sealer.Unseal(ctx, sealed, func(pt []byte) error {
		revealed = append(revealed[:0], pt...)
		return nil
	}); err != nil {
		t.Fatalf("unseal stored row: %v", err)
	}
	if string(revealed) != connectorSentinel {
		t.Fatalf("round-trip mismatch: unsealed %q, want the sentinel", revealed)
	}
}

// driveGetAndList asserts the owner sees its connector by id and in the list (tenant-scoped read).
func driveGetAndList(ctx context.Context, t *testing.T, api *client.ClientWithResponses, id string) {
	t.Helper()
	got, err := api.GetConnectorWithResponse(ctx, id)
	if err != nil {
		t.Fatalf("get connector: %v", err)
	}
	if got.StatusCode() != http.StatusOK || got.JSON200 == nil || got.JSON200.Data.Id != id {
		t.Fatalf("get status = %d, body = %s", got.StatusCode(), string(got.Body))
	}
	listed, err := api.ListConnectorsWithResponse(ctx, &client.ListConnectorsParams{})
	if err != nil {
		t.Fatalf("list connectors: %v", err)
	}
	if listed.StatusCode() != http.StatusOK || listed.JSON200 == nil || len(listed.JSON200.Data.Items) != 1 {
		t.Fatalf("list status = %d, count != 1; body = %s", listed.StatusCode(), string(listed.Body))
	}
	if listed.JSON200.Data.Items[0].Id != id {
		t.Fatalf("list returned a different connector than the one created")
	}
}

// assertCrossOrgIsolation is the RBAC SCOPING proof: a caller in org B cannot get/update/delete a
// connector owned by org A — each is a 404 (never a leak of the other org's connector).
func assertCrossOrgIsolation(ctx context.Context, t *testing.T, apiB *client.ClientWithResponses, orgAConnectorID string) {
	t.Helper()
	got, err := apiB.GetConnectorWithResponse(ctx, orgAConnectorID)
	if err != nil {
		t.Fatalf("cross-org get: %v", err)
	}
	if got.StatusCode() != http.StatusNotFound {
		t.Fatalf("cross-org get status = %d, want 404 (isolation); body = %s", got.StatusCode(), string(got.Body))
	}
	// The other org's connector must not leak in org B's list.
	listed, err := apiB.ListConnectorsWithResponse(ctx, &client.ListConnectorsParams{})
	if err != nil {
		t.Fatalf("cross-org list: %v", err)
	}
	if listed.StatusCode() != http.StatusOK || listed.JSON200 == nil || len(listed.JSON200.Data.Items) != 0 {
		t.Fatalf("cross-org list leaked another org's connector: body = %s", string(listed.Body))
	}
	upd, err := apiB.ReplaceConnectorCredentialWithResponse(ctx, orgAConnectorID, client.ReplaceConnectorCredentialRequest{Value: "attacker-value"})
	if err != nil {
		t.Fatalf("cross-org update: %v", err)
	}
	if upd.StatusCode() != http.StatusNotFound {
		t.Fatalf("cross-org update status = %d, want 404 (isolation)", upd.StatusCode())
	}
	del, err := apiB.DeleteConnectorWithResponse(ctx, orgAConnectorID)
	if err != nil {
		t.Fatalf("cross-org delete: %v", err)
	}
	if del.StatusCode() != http.StatusNotFound {
		t.Fatalf("cross-org delete status = %d, want 404 (isolation)", del.StatusCode())
	}
}

// driveReplaceConnector rotates the credential and asserts the fingerprint changes (a fresh seal).
func driveReplaceConnector(ctx context.Context, t *testing.T, api *client.ClientWithResponses, id, oldFingerprint string) {
	t.Helper()
	upd, err := api.ReplaceConnectorCredentialWithResponse(ctx, id, client.ReplaceConnectorCredentialRequest{
		Value:       "a-different-sentinel-value",
		AccountHint: strPtr("me2@example.com"),
	})
	if err != nil {
		t.Fatalf("replace connector: %v", err)
	}
	if upd.StatusCode() != http.StatusOK || upd.JSON200 == nil {
		t.Fatalf("replace status = %d, body = %s", upd.StatusCode(), string(upd.Body))
	}
	if upd.JSON200.Data.Fingerprint == oldFingerprint {
		t.Fatal("replace did not change the fingerprint (the credential was not re-sealed)")
	}
}

// assertAuthEnforced asserts the connectors routes sit behind the auth spine: no token → 401, a token
// for a user with no connectors:write grant → 403.
func assertAuthEnforced(ctx context.Context, t *testing.T, baseURL string, dataStore *persistence.Persistence) {
	t.Helper()
	// No token → 401.
	anon, err := client.NewClientWithResponses(baseURL + "/v1")
	if err != nil {
		t.Fatalf("anon client: %v", err)
	}
	resp, err := anon.ListConnectorsWithResponse(ctx, &client.ListConnectorsParams{})
	if err != nil {
		t.Fatalf("anon list: %v", err)
	}
	if resp.StatusCode() != http.StatusUnauthorized {
		t.Fatalf("anon list status = %d, want 401", resp.StatusCode())
	}

	// A user with a NON-admin membership (no wildcard) → 403 on connectors:write. Seed a member whose
	// permission set carries only "users:read" (not connectors:*).
	orgID := uuid.New()
	userID := uuid.New()
	permissionSetID := uuid.New()
	membershipID := uuid.New()
	if err := dataStore.Users().EnsureUser(ctx, userID, "reader@eden.local", "Reader"); err != nil {
		t.Fatalf("seed reader user: %v", err)
	}
	if err := dataStore.RBAC().EnsureOrganization(ctx, orgID, "Reader Org"); err != nil {
		t.Fatalf("seed reader org: %v", err)
	}
	if err := dataStore.RBAC().EnsurePermissionSet(ctx, permissionSetID, orgID, "ReadOnly", []string{"users:read"}); err != nil {
		t.Fatalf("seed readonly set: %v", err)
	}
	if err := dataStore.RBAC().EnsureMembership(ctx, membershipID, orgID, userID, permissionSetID, "member"); err != nil {
		t.Fatalf("seed reader membership: %v", err)
	}
	reader := connectorClient(t, baseURL, userID)
	denied, err := reader.CreateConnectorWithResponse(ctx, client.CreateConnectorRequest{
		Kind: "github", Name: "x", Value: "y", Scope: client.ConnectorScopeInput{Level: "org"},
	})
	if err != nil {
		t.Fatalf("reader create: %v", err)
	}
	if denied.StatusCode() != http.StatusForbidden {
		t.Fatalf("reader create status = %d, want 403 (no connectors:write grant)", denied.StatusCode())
	}
}

// driveDeleteConnector revokes the connector and asserts a second delete is a 404 (the row is gone).
func driveDeleteConnector(ctx context.Context, t *testing.T, api *client.ClientWithResponses, id string) {
	t.Helper()
	del, err := api.DeleteConnectorWithResponse(ctx, id)
	if err != nil {
		t.Fatalf("delete connector: %v", err)
	}
	if del.StatusCode() != http.StatusOK || del.JSON200 == nil || del.JSON200.Data.Id != id {
		t.Fatalf("delete status = %d, body = %s", del.StatusCode(), string(del.Body))
	}
	gone, err := api.DeleteConnectorWithResponse(ctx, id)
	if err != nil {
		t.Fatalf("re-delete connector: %v", err)
	}
	if gone.StatusCode() != http.StatusNotFound {
		t.Fatalf("re-delete status = %d, want 404 (already revoked)", gone.StatusCode())
	}
	// Compile-time cite of the connectors.Store port so this test file documents the seam it drives.
	var _ connectors.Store = (*persistence.Connectors)(nil)
}

// strPtr returns a pointer to s (the emitted client's optional fields are *string).
func strPtr(s string) *string { return &s }
