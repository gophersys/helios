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

	"github.com/gophersys/libs/go/edenhttp"
	ederrors "github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/platformgateway/internal/server"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// signingKey is the dev-JWT HMAC key the test mints tokens with — the SAME value seeded under
// jwtSecretRef in newDeps, so a token this test signs verifies through the server's spine.
const signingKey = "test-signing-key-32-bytes-minimum!!"

// fakeStore is the in-memory users.Store the route-level test wires into the assembled server: it
// satisfies every users route's single-method port (Get/List) so the real handler tree runs end to
// end without a database. The unit lane proves logic against it; the integration lane proves the SAME
// contract on real postgres (ADR-0016 §2).
type fakeStore struct {
	row persistence.User
	err error
}

func (f *fakeStore) Get(_ context.Context, id uuid.UUID) (persistence.User, error) {
	if f.err != nil {
		return persistence.User{}, f.err
	}
	row := f.row
	row.ID = id
	return row, nil
}

func (f *fakeStore) List(_ context.Context, _, _ int32) ([]persistence.User, error) {
	if f.err != nil {
		return nil, f.err
	}
	return []persistence.User{f.row}, nil
}

func (f *fakeStore) Default(_ context.Context) (persistence.User, error) {
	if f.err != nil {
		return persistence.User{}, f.err
	}
	return f.row, nil
}

// newUsersServer assembles the gateway with a fake users store wired through the REAL server.New (the
// same constructor the composition root calls), so the persisted `users` routes are mounted behind
// the auth spine and the public login bootstrap reads the same fake.
func newUsersServer(t *testing.T, userStore *fakeStore) *server.Server {
	t.Helper()
	dependencies := newDeps(t)
	dependencies.Users = userStore
	dependencies.DefaultUser = userStore
	srv, err := server.New(server.Config{JWTSecretRef: secrets.Ref(jwtSecretRef)}, dependencies)
	if err != nil {
		t.Fatalf("server.New: %v", err)
	}
	return srv
}

// token mints a signed dev-JWT for a FRESH test user id and REGISTERS the given grants for that user in
// the fake DB-driven resolver — so the spine authenticates the token (subject only) and then authorizes
// against the resolver's grants, NOT the token's. This is the DB-driven model: the token carries identity,
// the grants come from the (fake) database. The test drives the authorized happy path and the 403
// (wrong/missing grant) path through the real spine + verifier, just keyed off the resolver now.
func token(t *testing.T, grants ...string) string {
	t.Helper()
	parsed := make([]edenhttp.Grant, 0, len(grants))
	for _, g := range grants {
		grant, perr := edenhttp.ParseGrant(g)
		if perr != nil {
			t.Fatalf("parse grant %q: %v", g, perr)
		}
		parsed = append(parsed, grant)
	}
	subject := registerGrants(uuid.NewString(), parsed)
	return tokenForSubject(t, subject) // a uuid subject; grants live in the resolver, not the token.
}

// do issues a request through the assembled server and returns the recorder.
func do(srv *server.Server, method, target, bearer string, body []byte) *httptest.ResponseRecorder {
	reader := bytes.NewReader(body)
	request := httptest.NewRequest(method, target, reader)
	if bearer != "" {
		request.Header.Set("Authorization", "Bearer "+bearer)
	}
	recorder := httptest.NewRecorder()
	srv.Handler().ServeHTTP(recorder, request)
	return recorder
}

// TestUsers_ListHappyPath drives GET /v1/users end to end with the users:read grant: the real spine
// authenticates + authorizes, the route's five stages run, and the 200 success Envelope carries the
// page of users.
func TestUsers_ListHappyPath(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 12, 0, 0, 0, time.UTC)
	row := persistence.User{ID: uuid.New(), Email: "ann@eden.local", Name: "Ann", IsDefault: true, CreatedAt: stamp, UpdatedAt: stamp}
	srv := newUsersServer(t, &fakeStore{row: row})

	recorder := do(srv, http.MethodGet, "/v1/users", token(t, "users:read"), nil)
	if recorder.Code != http.StatusOK {
		t.Fatalf("GET /v1/users status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
	var envelope struct {
		Data struct {
			Items []struct {
				Email     string `json:"email"`
				IsDefault bool   `json:"isDefault"`
			} `json:"items"`
		} `json:"data"`
	}
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode envelope: %v", err)
	}
	if len(envelope.Data.Items) != 1 || envelope.Data.Items[0].Email != "ann@eden.local" || !envelope.Data.Items[0].IsDefault {
		t.Fatalf("envelope items = %+v, want one default user ann@eden.local", envelope.Data.Items)
	}
}

// TestUsers_GetHappyPath drives GET /v1/users/{id} with users:read and asserts the 200 envelope
// carries the user at the requested id.
func TestUsers_GetHappyPath(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 12, 0, 0, 0, time.UTC)
	srv := newUsersServer(t, &fakeStore{row: persistence.User{Email: "ann@eden.local", Name: "Ann", CreatedAt: stamp, UpdatedAt: stamp}})

	id := uuid.New()
	recorder := do(srv, http.MethodGet, "/v1/users/"+id.String(), token(t, "users:read"), nil)
	if recorder.Code != http.StatusOK {
		t.Fatalf("GET /v1/users/{id} status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
	var envelope struct {
		Data struct {
			ID   string `json:"id"`
			Name string `json:"name"`
		} `json:"data"`
	}
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode envelope: %v", err)
	}
	if envelope.Data.ID != id.String() || envelope.Data.Name != "Ann" {
		t.Fatalf("envelope data = %+v, want id %s name Ann", envelope.Data, id)
	}
}

// TestUsers_RejectsUnauthenticated proves the users routes sit behind the auth spine: no token → 401,
// before any stage runs.
func TestUsers_RejectsUnauthenticated(t *testing.T) {
	t.Parallel()
	srv := newUsersServer(t, &fakeStore{})
	recorder := do(srv, http.MethodGet, "/v1/users", "", nil)
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("GET /v1/users (no token) status = %d, want 401", recorder.Code)
	}
}

// TestUsers_RejectsMissingGrant proves authorization is the route's declarative Required grant: a
// token WITHOUT users:read is 403 on the list route (authenticated, but not authorized).
func TestUsers_RejectsMissingGrant(t *testing.T) {
	t.Parallel()
	srv := newUsersServer(t, &fakeStore{})
	recorder := do(srv, http.MethodGet, "/v1/users", token(t, "users:write"), nil)
	if recorder.Code != http.StatusForbidden {
		t.Fatalf("GET /v1/users (wrong grant) status = %d, want 403", recorder.Code)
	}
}

// TestUsers_GetNotFound proves the persistence not-found maps to a 404 through the route's execute
// stage (the Kind→status mapping holds end to end).
func TestUsers_GetNotFound(t *testing.T) {
	t.Parallel()
	srv := newUsersServer(t, &fakeStore{err: ederrors.New(ederrors.KindNotFound, "user not found")})
	recorder := do(srv, http.MethodGet, "/v1/users/"+uuid.New().String(), token(t, "users:read"), nil)
	if recorder.Code != http.StatusNotFound {
		t.Fatalf("GET /v1/users/{id} (absent) status = %d, want 404", recorder.Code)
	}
}

// TestUsers_GetRejectsMalformedID proves the parse stage runs in the assembled pipeline: a non-uuid
// path id is a 400 before execute touches the store.
func TestUsers_GetRejectsMalformedID(t *testing.T) {
	t.Parallel()
	srv := newUsersServer(t, &fakeStore{})
	recorder := do(srv, http.MethodGet, "/v1/users/not-a-uuid", token(t, "users:read"), nil)
	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("GET /v1/users/not-a-uuid status = %d, want 400", recorder.Code)
	}
}

// TestBootstrap_DefaultUserIsPublic proves the login bootstrap is PRE-IDENTITY: GET
// /bootstrap/default-user with NO token answers 200 (like the health probes) and returns the seeded
// default user. This is the login target — a basic login reads it without first being authenticated.
func TestBootstrap_DefaultUserIsPublic(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 12, 0, 0, 0, time.UTC)
	row := persistence.User{ID: uuid.New(), Email: "boss@eden.local", Name: "Boss", IsDefault: true, CreatedAt: stamp, UpdatedAt: stamp}
	srv := newUsersServer(t, &fakeStore{row: row})

	recorder := do(srv, http.MethodGet, "/bootstrap/default-user", "", nil)
	if recorder.Code != http.StatusOK {
		t.Fatalf("GET /bootstrap/default-user (no token) status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
	var envelope struct {
		Data struct {
			Email     string `json:"email"`
			IsDefault bool   `json:"isDefault"`
		} `json:"data"`
	}
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode envelope: %v", err)
	}
	if envelope.Data.Email != "boss@eden.local" || !envelope.Data.IsDefault {
		t.Fatalf("bootstrap returned %+v, want the default user boss@eden.local", envelope.Data)
	}
}
