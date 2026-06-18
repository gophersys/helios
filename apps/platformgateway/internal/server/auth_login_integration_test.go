//go:build integration

// auth_login_integration_test.go is the REAL-substrate integration lane for the full auth + DB-driven
// authorize slice (ADR-0016 §2: never mocked). On an EPHEMERAL postgres it runs the EMBEDDED startup
// migrate path (incl. 0003_create_accounts), seeds the default user + the IOTEA RBAC (org + admin
// permission set {*} + admin membership) + the default user's "password" account (a bcrypt digest of the
// dev password, the SAME way the composition root seeds it), then drives the REAL flow end to end through
// the running server: POST /auth/login with the right password mints a token + returns the profile; that
// token authorizes BOTH /v1/me AND /v1/users (the admin "*" grant, loaded from the DB per request, covers
// users:read); a wrong password is 401; no token is 401. So the accounts schema, bcrypt verify, the mint,
// and the DB-driven authorize are proven to AGREE on a real database. Run via `bash ./ctl.sh integration`.
package server_test

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/google/uuid"

	"github.com/gophersys/eden/apps/platformgateway/internal/server/credential"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/login"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// devLoginPassword is the plaintext the lane seeds the default user's password account with (bcrypt
// hashed at seed) and posts to /auth/login. It mirrors the composition root's dev default ("eden").
const devLoginPassword = "eden"

// TestIntegration_AuthLoginAndDBAuthorize proves real authentication + DB-driven authorize on a REAL
// postgres: seed the user + RBAC + a bcrypt password account, log in, and use the minted token on the
// authenticated API.
func TestIntegration_AuthLoginAndDBAuthorize(t *testing.T) {
	t.Parallel()
	dsn := startPostgres(t)

	dataStore := openPersistence(t, dsn)
	ctx := context.Background()

	if err := dataStore.Migrate(ctx); err != nil {
		t.Fatalf("migrate: %v", err)
	}

	// Seed the user + the IOTEA RBAC (admin member, permission set {*}) + the default user's password
	// account (a bcrypt digest of devLoginPassword) — the SAME seed the composition root runs on boot.
	userID := uuid.New()
	orgID := uuid.New()
	seedRBAC(ctx, t, dataStore, userID, orgID, uuid.New(), uuid.New())
	hash, err := credential.Hash(devLoginPassword)
	if err != nil {
		t.Fatalf("hash password: %v", err)
	}
	email := "default@eden.local"
	if err := dataStore.Accounts().EnsureAccount(ctx, uuid.New(), userID,
		persistence.ProviderPassword, login.NormalizeEmail(email), hash); err != nil {
		t.Fatalf("seed password account: %v", err)
	}

	srv := newServerWithRBAC(t, dataStore)
	httpServer := httptest.NewServer(srv.Handler())
	t.Cleanup(httpServer.Close)

	// (a) Wrong password → 401, never revealing which factor was wrong.
	if status := postLogin(t, httpServer.URL, email, "not-the-password"); status != http.StatusUnauthorized {
		t.Fatalf("login (wrong password) status = %d, want 401", status)
	}

	// (b) Right password → 200 with a token + the profile (org/role/permissions).
	token, profile := driveLogin(t, httpServer.URL, email, devLoginPassword, userID, orgID)
	if profile.Role != "admin" || len(profile.Permissions) != 1 || profile.Permissions[0] != "*" {
		t.Fatalf("login profile role/permissions = %q/%v, want admin/[*]", profile.Role, profile.Permissions)
	}

	// (c) The minted token authorizes BOTH /v1/me AND /v1/users — the admin "*" grant, loaded from the DB
	// per request (NOT embedded in the token), covers the zero-grant /me and the users:read /users routes.
	assertAuthorized(t, httpServer.URL+"/v1/me", token)
	assertAuthorized(t, httpServer.URL+"/v1/users", token)

	// (d) No token → 401 on the authenticated API (the spine authenticates before the route runs).
	assertStatus(t, httpServer.URL+"/v1/users", "", http.StatusUnauthorized)
}

// loginProfile mirrors the /auth/login success payload's profile shape (the fields the test asserts).
type loginProfile struct {
	ID           string `json:"id"`
	Email        string `json:"email"`
	Organization struct {
		ID   string `json:"id"`
		Name string `json:"name"`
	} `json:"organization"`
	Role        string   `json:"role"`
	Permissions []string `json:"permissions"`
}

// loginBody marshals a credentials body, panicking on the impossible static-map marshal error.
func loginBody(email, password string) []byte {
	raw, err := json.Marshal(map[string]string{"email": email, "password": password})
	if err != nil {
		panic(err)
	}
	return raw
}

// driveLogin posts valid credentials, asserts 200, and returns the minted token + the decoded profile.
func driveLogin(t *testing.T, baseURL, email, password string, wantUserID, wantOrgID uuid.UUID) (string, loginProfile) {
	t.Helper()
	resp, err := http.Post(baseURL+"/auth/login", "application/json", bytes.NewReader(loginBody(email, password))) //nolint:noctx // test probe of a local httptest server.
	if err != nil {
		t.Fatalf("login POST: %v", err)
	}
	defer func() { _ = resp.Body.Close() }() //nolint:errcheck // probe response close fault is irrelevant.
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("login status = %d, want 200; body = %s", resp.StatusCode, string(raw))
	}
	var envelope struct {
		Data struct {
			Token   string       `json:"token"`
			Profile loginProfile `json:"profile"`
		} `json:"data"`
	}
	if err := json.Unmarshal(raw, &envelope); err != nil {
		t.Fatalf("login decode: %v; body = %s", err, string(raw))
	}
	if envelope.Data.Token == "" {
		t.Fatalf("login returned an empty token; body = %s", string(raw))
	}
	profile := envelope.Data.Profile
	if profile.ID != wantUserID.String() || profile.Email != email {
		t.Fatalf("login profile user = %+v, want id %s email %s", profile, wantUserID, email)
	}
	if profile.Organization.ID != wantOrgID.String() || profile.Organization.Name != "Eden" {
		t.Fatalf("login profile organization = %+v, want id %s name Eden", profile.Organization, wantOrgID)
	}
	return envelope.Data.Token, profile
}

// postLogin posts credentials and returns only the status (for the wrong-password assertion).
func postLogin(t *testing.T, baseURL, email, password string) int {
	t.Helper()
	resp, err := http.Post(baseURL+"/auth/login", "application/json", bytes.NewReader(loginBody(email, password))) //nolint:noctx // test probe of a local httptest server.
	if err != nil {
		t.Fatalf("login POST: %v", err)
	}
	defer func() { _ = resp.Body.Close() }() //nolint:errcheck // probe response close fault is irrelevant.
	return resp.StatusCode
}

// assertAuthorized asserts a GET to target with the bearer is 200 — the minted token authorizes the route.
func assertAuthorized(t *testing.T, target, bearer string) {
	t.Helper()
	assertStatus(t, target, bearer, http.StatusOK)
}

// assertStatus drives a GET (with an optional bearer) and asserts the status.
func assertStatus(t *testing.T, target, bearer string, want int) {
	t.Helper()
	request, err := http.NewRequestWithContext(context.Background(), http.MethodGet, target, http.NoBody)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	if bearer != "" {
		request.Header.Set("Authorization", "Bearer "+bearer)
	}
	resp, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("GET %s: %v", target, err)
	}
	defer func() { _ = resp.Body.Close() }() //nolint:errcheck // probe response close fault is irrelevant.
	if resp.StatusCode != want {
		raw, _ := io.ReadAll(resp.Body)
		t.Fatalf("GET %s status = %d, want %d; body = %s", target, resp.StatusCode, want, string(raw))
	}
}
