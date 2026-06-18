package server_test

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/google/uuid"

	ederrors "github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/platformgateway/internal/server"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/credential"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// fakeAccounts is the in-memory login.AccountReader the route-level login test wires through the REAL
// server.New (so the real PasswordAuthenticator runs): it returns a fixed account for the "password"
// provider + a configured provider_account_id (the lowercased email), or a typed not-found. The
// integration lane proves the SAME flow on real postgres (ADR-0016 §2).
type fakeAccounts struct {
	account persistence.Account
	err     error
}

func (f *fakeAccounts) AccountFor(_ context.Context, _, _ string) (persistence.Account, error) {
	if f.err != nil {
		return persistence.Account{}, f.err
	}
	return f.account, nil
}

// newLoginServer assembles the gateway with fake users/RBAC/accounts stores wired through the REAL
// server.New, so the public POST /auth/login route is mounted and runs the real PasswordAuthenticator +
// the real mint. The bearer it mints verifies through the SAME spine (one signing key).
func newLoginServer(t *testing.T, userStore *fakeStore, rbacStore *fakeRBAC, accountStore *fakeAccounts) *server.Server {
	t.Helper()
	dependencies := newDeps(t)
	dependencies.Users = userStore
	dependencies.RBAC = rbacStore
	dependencies.Accounts = accountStore
	dependencies.DefaultUser = userStore
	dependencies.DefaultMembership = rbacStore
	srv, err := server.New(server.Config{JWTSecretRef: secrets.Ref(jwtSecretRef)}, dependencies)
	if err != nil {
		t.Fatalf("server.New: %v", err)
	}
	return srv
}

// postJSON issues a POST with a JSON body and returns the recorder.
func postJSON(srv *server.Server, target string, body any) *httptest.ResponseRecorder {
	raw, err := json.Marshal(body)
	if err != nil {
		panic(err) // a static test struct never fails to marshal.
	}
	request := httptest.NewRequest(http.MethodPost, target, bytes.NewReader(raw))
	request.Header.Set("Content-Type", "application/json")
	recorder := httptest.NewRecorder()
	srv.Handler().ServeHTTP(recorder, request)
	return recorder
}

// TestAuthLogin_HappyPath drives POST /auth/login (PUBLIC, no token) with the right password: the real
// PasswordAuthenticator verifies the bcrypt digest, the server mints a real JWT, and the 200 Envelope
// carries { token, profile }. The minted token is then proven to authenticate through the SAME spine.
func TestAuthLogin_HappyPath(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 12, 0, 0, 0, time.UTC)
	userID := uuid.New()
	hash, err := credential.Hash("eden")
	if err != nil {
		t.Fatalf("hash: %v", err)
	}
	userStore := &fakeStore{row: persistence.User{ID: userID, Email: "ann@eden.local", Name: "Ann", IsDefault: true, CreatedAt: stamp, UpdatedAt: stamp}}
	rbacStore := &fakeRBAC{membership: persistence.Membership{OrganizationName: "Eden", Role: "admin", Permissions: []string{"*"}}}
	accountStore := &fakeAccounts{account: persistence.Account{UserID: userID, Provider: persistence.ProviderPassword, ProviderAccountID: "ann@eden.local", PasswordHash: hash}}
	srv := newLoginServer(t, userStore, rbacStore, accountStore)

	recorder := postJSON(srv, "/auth/login", map[string]string{"email": "Ann@Eden.local", "password": "eden"})
	if recorder.Code != http.StatusOK {
		t.Fatalf("POST /auth/login status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
	var envelope struct {
		Data struct {
			Token   string `json:"token"`
			Profile struct {
				ID          string   `json:"id"`
				Email       string   `json:"email"`
				Role        string   `json:"role"`
				Permissions []string `json:"permissions"`
			} `json:"profile"`
		} `json:"data"`
	}
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode: %v; body=%s", err, recorder.Body.String())
	}
	if envelope.Data.Token == "" {
		t.Fatalf("login returned empty token; body=%s", recorder.Body.String())
	}
	if envelope.Data.Profile.ID != userID.String() || envelope.Data.Profile.Email != "ann@eden.local" {
		t.Fatalf("login profile = %+v, want id %s email ann@eden.local", envelope.Data.Profile, userID)
	}
	if envelope.Data.Profile.Role != "admin" || len(envelope.Data.Profile.Permissions) != 1 {
		t.Fatalf("login profile role/permissions = %q/%v, want admin/[*]", envelope.Data.Profile.Role, envelope.Data.Profile.Permissions)
	}

	// The minted token authenticates through the SAME spine: drive /v1/me (zero-grant) with it → 200.
	// The DB-driven resolver is the fake (registers nothing), but /me requires no grant, so it is 200.
	recorder2 := do(srv, http.MethodGet, "/v1/me", envelope.Data.Token, nil)
	if recorder2.Code != http.StatusOK {
		t.Fatalf("GET /v1/me with minted token status = %d, want 200; body=%s", recorder2.Code, recorder2.Body.String())
	}
}

// TestAuthLogin_WrongPassword proves a bad password is a 401 (KindUnauthenticated), and the response
// never reveals which factor was wrong — the same 401 a missing account yields.
func TestAuthLogin_WrongPassword(t *testing.T) {
	t.Parallel()
	userID := uuid.New()
	hash, err := credential.Hash("the-real-password")
	if err != nil {
		t.Fatalf("hash: %v", err)
	}
	accountStore := &fakeAccounts{account: persistence.Account{UserID: userID, Provider: persistence.ProviderPassword, ProviderAccountID: "ann@eden.local", PasswordHash: hash}}
	srv := newLoginServer(t, &fakeStore{}, &fakeRBAC{}, accountStore)

	recorder := postJSON(srv, "/auth/login", map[string]string{"email": "ann@eden.local", "password": "wrong"})
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("POST /auth/login (wrong password) status = %d, want 401; body=%s", recorder.Code, recorder.Body.String())
	}
}

// TestAuthLogin_UnknownAccount proves a missing account is the SAME 401 as a wrong password (never a 404
// or a "no such email") — the login surface does not leak which of email/password was wrong.
func TestAuthLogin_UnknownAccount(t *testing.T) {
	t.Parallel()
	accountStore := &fakeAccounts{err: ederrors.New(ederrors.KindNotFound, "account not found")}
	srv := newLoginServer(t, &fakeStore{}, &fakeRBAC{}, accountStore)

	recorder := postJSON(srv, "/auth/login", map[string]string{"email": "ghost@eden.local", "password": "whatever"})
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("POST /auth/login (unknown account) status = %d, want 401; body=%s", recorder.Code, recorder.Body.String())
	}
}

// TestAuthLogin_MalformedBody proves a non-JSON / unexpected-field body is a 400 at the parse stage.
func TestAuthLogin_MalformedBody(t *testing.T) {
	t.Parallel()
	srv := newLoginServer(t, &fakeStore{}, &fakeRBAC{}, &fakeAccounts{})

	request := httptest.NewRequest(http.MethodPost, "/auth/login", bytes.NewReader([]byte("not json")))
	recorder := httptest.NewRecorder()
	srv.Handler().ServeHTTP(recorder, request)
	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("POST /auth/login (malformed body) status = %d, want 400; body=%s", recorder.Code, recorder.Body.String())
	}
}

// TestAuthLogin_NeverLeaksCredential proves the success/failure bodies never echo the posted password —
// a redaction property over the login surface (the gosec/secretscan analog at the HTTP boundary).
func TestAuthLogin_NeverLeaksCredential(t *testing.T) {
	t.Parallel()
	const password = "super-secret-canary-pw"
	userID := uuid.New()
	hash, err := credential.Hash(password)
	if err != nil {
		t.Fatalf("hash: %v", err)
	}
	stamp := time.Date(2026, 6, 14, 12, 0, 0, 0, time.UTC)
	userStore := &fakeStore{row: persistence.User{ID: userID, Email: "ann@eden.local", CreatedAt: stamp, UpdatedAt: stamp}}
	rbacStore := &fakeRBAC{membership: persistence.Membership{Role: "admin", Permissions: []string{"*"}}}
	accountStore := &fakeAccounts{account: persistence.Account{UserID: userID, Provider: persistence.ProviderPassword, ProviderAccountID: "ann@eden.local", PasswordHash: hash}}
	srv := newLoginServer(t, userStore, rbacStore, accountStore)

	recorder := postJSON(srv, "/auth/login", map[string]string{"email": "ann@eden.local", "password": password})
	if bytes.Contains(recorder.Body.Bytes(), []byte(password)) {
		t.Fatalf("login response body leaked the plaintext password")
	}
	if bytes.Contains(recorder.Body.Bytes(), []byte(hash)) {
		t.Fatalf("login response body leaked the password hash")
	}
}
