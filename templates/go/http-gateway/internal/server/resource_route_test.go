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

	"github.com/gophersys/libs/templates/go/http-gateway/internal/server"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// signingKey is the dev-JWT HMAC key the test mints tokens with — the SAME value seeded under
// jwtSecretRef in newDeps, so a token this test signs verifies through the server's spine.
const signingKey = "test-signing-key-32-bytes-minimum!!"

// fakeStore is the in-memory resource.Store the route-level test wires into the assembled server: it
// satisfies every route's single-method port (Create/Get/List/Update/Delete) so the real handler
// tree runs end to end without a database. The unit lane proves logic against it; the integration
// lane proves the SAME contract on real postgres (ADR-0016 §2).
type fakeStore struct {
	row persistence.Resource
	err error
}

func (f *fakeStore) Create(_ context.Context, id uuid.UUID, name string) (persistence.Resource, error) {
	if f.err != nil {
		return persistence.Resource{}, f.err
	}
	return persistence.Resource{ID: id, Name: name, CreatedAt: f.row.CreatedAt, UpdatedAt: f.row.UpdatedAt}, nil
}

func (f *fakeStore) Get(_ context.Context, id uuid.UUID) (persistence.Resource, error) {
	if f.err != nil {
		return persistence.Resource{}, f.err
	}
	row := f.row
	row.ID = id
	return row, nil
}

func (f *fakeStore) List(_ context.Context, _, _ int32) ([]persistence.Resource, error) {
	if f.err != nil {
		return nil, f.err
	}
	return []persistence.Resource{f.row}, nil
}

func (f *fakeStore) Update(_ context.Context, id uuid.UUID, name string) (persistence.Resource, error) {
	if f.err != nil {
		return persistence.Resource{}, f.err
	}
	return persistence.Resource{ID: id, Name: name, CreatedAt: f.row.CreatedAt, UpdatedAt: f.row.UpdatedAt}, nil
}

func (f *fakeStore) Delete(_ context.Context, _ uuid.UUID) error { return f.err }

// newResourceServer assembles the gateway with a fake resource store wired through the REAL
// server.New (the same constructor the composition root calls), so the persisted `resource` routes
// are mounted behind the auth spine.
func newResourceServer(t *testing.T, resourceStore *fakeStore) *server.Server {
	t.Helper()
	dependencies := newDeps(t)
	dependencies.Resources = resourceStore
	srv, err := server.New(server.Config{JWTSecretRef: secrets.Ref(jwtSecretRef)}, dependencies)
	if err != nil {
		t.Fatalf("server.New: %v", err)
	}
	return srv
}

// token mints a signed dev-JWT carrying the given grants, so the test can drive the authenticated +
// authorized happy path and the 403 (wrong grant) path through the real spine.
func token(t *testing.T, grants ...string) string {
	t.Helper()
	verifier, err := edenhttp.NewHMACVerifier(signingKey)
	if err != nil {
		t.Fatalf("new verifier: %v", err)
	}
	parsed := make([]edenhttp.Grant, 0, len(grants))
	for _, g := range grants {
		grant, perr := edenhttp.ParseGrant(g)
		if perr != nil {
			t.Fatalf("parse grant %q: %v", g, perr)
		}
		parsed = append(parsed, grant)
	}
	signed, err := verifier.Sign("tester", parsed, time.Now().Add(time.Hour))
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}
	return signed
}

// do issues a request through the assembled server and returns the recorder.
func do(srv *server.Server, method, target, bearer string, body []byte) *httptest.ResponseRecorder {
	var reader *bytes.Reader
	if body != nil {
		reader = bytes.NewReader(body)
	} else {
		reader = bytes.NewReader(nil)
	}
	request := httptest.NewRequest(method, target, reader)
	if bearer != "" {
		request.Header.Set("Authorization", "Bearer "+bearer)
	}
	recorder := httptest.NewRecorder()
	srv.Handler().ServeHTTP(recorder, request)
	return recorder
}

// TestResource_CreateHappyPath drives POST /v1/resources end to end with the resource:create grant:
// the real spine authenticates + authorizes, the route's five stages run, and the 201 success
// Envelope carries the persisted resource.
func TestResource_CreateHappyPath(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 12, 0, 0, 0, time.UTC)
	srv := newResourceServer(t, &fakeStore{row: persistence.Resource{CreatedAt: stamp, UpdatedAt: stamp}})

	recorder := do(srv, http.MethodPost, "/v1/resources", token(t, "resource:create"), []byte(`{"name":"widget"}`))
	if recorder.Code != http.StatusCreated {
		t.Fatalf("POST /v1/resources status = %d, want 201; body=%s", recorder.Code, recorder.Body.String())
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
	if envelope.Data.Name != "widget" || envelope.Data.ID == "" {
		t.Fatalf("envelope data = %+v, want a minted id + name widget", envelope.Data)
	}
}

// TestResource_RejectsUnauthenticated proves the resource routes sit behind the auth spine: no token
// → 401, before any stage runs.
func TestResource_RejectsUnauthenticated(t *testing.T) {
	t.Parallel()
	srv := newResourceServer(t, &fakeStore{})
	recorder := do(srv, http.MethodGet, "/v1/resources", "", nil)
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("GET /v1/resources (no token) status = %d, want 401", recorder.Code)
	}
}

// TestResource_RejectsMissingGrant proves authorization is the route's declarative Required grant: a
// token WITHOUT resource:read is 403 on the list route (authenticated, but not authorized).
func TestResource_RejectsMissingGrant(t *testing.T) {
	t.Parallel()
	srv := newResourceServer(t, &fakeStore{})
	recorder := do(srv, http.MethodGet, "/v1/resources", token(t, "resource:create"), nil)
	if recorder.Code != http.StatusForbidden {
		t.Fatalf("GET /v1/resources (wrong grant) status = %d, want 403", recorder.Code)
	}
}

// TestResource_GetNotFound proves the persistence not-found maps to a 404 through the route's execute
// stage (the Kind→status mapping holds end to end).
func TestResource_GetNotFound(t *testing.T) {
	t.Parallel()
	srv := newResourceServer(t, &fakeStore{err: ederrors.New(ederrors.KindNotFound, "resource not found")})
	recorder := do(srv, http.MethodGet, "/v1/resources/"+uuid.New().String(), token(t, "resource:read"), nil)
	if recorder.Code != http.StatusNotFound {
		t.Fatalf("GET /v1/resources/{id} (absent) status = %d, want 404", recorder.Code)
	}
}

// TestResource_CreateRejectsBlankName proves the validate stage runs in the assembled pipeline: a
// blank name is a 400 before execute touches the store.
func TestResource_CreateRejectsBlankName(t *testing.T) {
	t.Parallel()
	srv := newResourceServer(t, &fakeStore{})
	recorder := do(srv, http.MethodPost, "/v1/resources", token(t, "resource:create"), []byte(`{"name":"  "}`))
	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("POST /v1/resources (blank name) status = %d, want 400", recorder.Code)
	}
}

// TestResource_DeleteHappyPath drives DELETE /v1/resources/{id} with the resource:delete grant and
// asserts the 200 acknowledgement envelope.
func TestResource_DeleteHappyPath(t *testing.T) {
	t.Parallel()
	srv := newResourceServer(t, &fakeStore{})
	id := uuid.New()
	recorder := do(srv, http.MethodDelete, "/v1/resources/"+id.String(), token(t, "resource:delete"), nil)
	if recorder.Code != http.StatusOK {
		t.Fatalf("DELETE /v1/resources/{id} status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
}
