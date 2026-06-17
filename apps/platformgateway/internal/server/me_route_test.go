package server_test

import (
	"context"
	"encoding/json"
	"net/http"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/platformgateway/internal/server"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// fakeRBAC is the in-memory me.MembershipReader / loginbootstrap.MembershipProvider the route-level
// test wires into the assembled server: it returns a fixed membership (or an error) so the /v1/me
// route + the bootstrap profile run end to end without a database. The integration lane proves the
// SAME contract on real postgres (ADR-0016 §2).
type fakeRBAC struct {
	membership persistence.Membership
	err        error
}

func (f *fakeRBAC) MembershipFor(_ context.Context, _ uuid.UUID) (persistence.Membership, error) {
	if f.err != nil {
		return persistence.Membership{}, f.err
	}
	return f.membership, nil
}

// newProfileServer assembles the gateway with a fake users store + a fake RBAC store wired through the
// REAL server.New (the same constructor the composition root calls), so the /v1/me route is mounted
// behind the auth spine and the public bootstrap renders the same fakes' profile.
func newProfileServer(t *testing.T, userStore *fakeStore, rbacStore *fakeRBAC) *server.Server {
	t.Helper()
	dependencies := newDeps(t)
	dependencies.Users = userStore
	dependencies.RBAC = rbacStore
	dependencies.DefaultUser = userStore
	dependencies.DefaultMembership = rbacStore
	srv, err := server.New(server.Config{JWTSecretRef: secrets.Ref(jwtSecretRef)}, dependencies)
	if err != nil {
		t.Fatalf("server.New: %v", err)
	}
	return srv
}

// tokenForSubject mints a signed dev-JWT whose SUBJECT is the given user id (not the "tester" subject
// the bare token helper uses), so the /v1/me route — which reads the caller from the verified token's
// subject — resolves to a specific seeded user. The grants are carried verbatim.
func tokenForSubject(t *testing.T, subject string, grants ...string) string {
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
	signed, err := verifier.Sign(subject, parsed, time.Now().Add(time.Hour))
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}
	return signed
}

// TestMe_HappyPath drives GET /v1/me with a token whose subject is the seeded user id: the real spine
// authenticates (the route requires NO grant — authenticated-only), execute loads the user + their
// membership, and the 200 success Envelope carries the profile (user fields + org name, role "admin",
// permissions ["*"]).
func TestMe_HappyPath(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 12, 0, 0, 0, time.UTC)
	userID := uuid.New()
	orgID := uuid.New()
	userStore := &fakeStore{row: persistence.User{ID: userID, Email: "ann@eden.local", Name: "Ann", IsDefault: true, CreatedAt: stamp, UpdatedAt: stamp}}
	rbacStore := &fakeRBAC{membership: persistence.Membership{
		OrganizationID:    orgID,
		OrganizationName:  "Eden",
		Role:              "admin",
		PermissionSetName: "Admin",
		Permissions:       []string{"*"},
	}}
	srv := newProfileServer(t, userStore, rbacStore)

	recorder := do(srv, http.MethodGet, "/v1/me", tokenForSubject(t, userID.String()), nil)
	if recorder.Code != http.StatusOK {
		t.Fatalf("GET /v1/me status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
	var envelope struct {
		Data struct {
			ID           string `json:"id"`
			Email        string `json:"email"`
			Organization struct {
				ID   string `json:"id"`
				Name string `json:"name"`
			} `json:"organization"`
			Role        string   `json:"role"`
			Permissions []string `json:"permissions"`
		} `json:"data"`
	}
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode envelope: %v", err)
	}
	data := envelope.Data
	if data.ID != userID.String() || data.Email != "ann@eden.local" {
		t.Fatalf("profile user = %+v, want id %s email ann@eden.local", data, userID)
	}
	if data.Organization.ID != orgID.String() || data.Organization.Name != "Eden" {
		t.Fatalf("profile organization = %+v, want id %s name Eden", data.Organization, orgID)
	}
	if data.Role != "admin" || len(data.Permissions) != 1 || data.Permissions[0] != "*" {
		t.Fatalf("profile role/permissions = %q/%v, want admin/[*]", data.Role, data.Permissions)
	}
}

// TestMe_RejectsUnauthenticated proves /v1/me sits behind the auth spine: no token → 401, before any
// stage runs (the route requires no grant, but a valid identity IS required).
func TestMe_RejectsUnauthenticated(t *testing.T) {
	t.Parallel()
	srv := newProfileServer(t, &fakeStore{}, &fakeRBAC{})
	recorder := do(srv, http.MethodGet, "/v1/me", "", nil)
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("GET /v1/me (no token) status = %d, want 401", recorder.Code)
	}
}

// TestMe_AnyGrantIsAccepted proves /v1/me requires NO specific grant: a token carrying an unrelated
// grant (or none) still reads the profile — authenticated-only is the route's authorization.
func TestMe_AnyGrantIsAccepted(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 12, 0, 0, 0, time.UTC)
	userID := uuid.New()
	userStore := &fakeStore{row: persistence.User{ID: userID, Email: "ann@eden.local", Name: "Ann", CreatedAt: stamp, UpdatedAt: stamp}}
	rbacStore := &fakeRBAC{membership: persistence.Membership{OrganizationName: "Eden", Role: "member", Permissions: []string{}}}
	srv := newProfileServer(t, userStore, rbacStore)

	// A token with NO grants at all still authenticates → 200 (the route authorizes against the zero Grant).
	recorder := do(srv, http.MethodGet, "/v1/me", tokenForSubject(t, userID.String()), nil)
	if recorder.Code != http.StatusOK {
		t.Fatalf("GET /v1/me (no grants) status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
}

// TestMe_MalformedSubjectIsBadRequest proves the execute stage rejects a token whose subject is not a
// uuid (the bare token helper signs subject "tester") with a 400 — a malformed caller, not a 500.
func TestMe_MalformedSubjectIsBadRequest(t *testing.T) {
	t.Parallel()
	srv := newProfileServer(t, &fakeStore{}, &fakeRBAC{})
	recorder := do(srv, http.MethodGet, "/v1/me", token(t), nil) // subject "tester" — not a uuid.
	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("GET /v1/me (non-uuid subject) status = %d, want 400; body=%s", recorder.Code, recorder.Body.String())
	}
}

// TestBootstrap_ReturnsProfile proves the PUBLIC login bootstrap now returns the default user's PROFILE
// (the same shape /v1/me returns): the existing top-level user fields PLUS organization/role/
// permissions, so the tokenless frontend can show them. No token (pre-identity, like the probes).
func TestBootstrap_ReturnsProfile(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 12, 0, 0, 0, time.UTC)
	userID := uuid.New()
	orgID := uuid.New()
	userStore := &fakeStore{row: persistence.User{ID: userID, Email: "boss@eden.local", Name: "Boss", IsDefault: true, CreatedAt: stamp, UpdatedAt: stamp}}
	rbacStore := &fakeRBAC{membership: persistence.Membership{
		OrganizationID:   orgID,
		OrganizationName: "Eden",
		Role:             "admin",
		Permissions:      []string{"*"},
	}}
	srv := newProfileServer(t, userStore, rbacStore)

	recorder := do(srv, http.MethodGet, "/bootstrap/default-user", "", nil)
	if recorder.Code != http.StatusOK {
		t.Fatalf("GET /bootstrap/default-user status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
	var envelope struct {
		Data struct {
			// The EXISTING top-level fields the login E2E asserts — must still be present.
			ID        string `json:"id"`
			Email     string `json:"email"`
			Name      string `json:"name"`
			IsDefault bool   `json:"isDefault"`
			// The NEW profile fields alongside.
			Organization struct {
				ID   string `json:"id"`
				Name string `json:"name"`
			} `json:"organization"`
			Role        string   `json:"role"`
			Permissions []string `json:"permissions"`
		} `json:"data"`
	}
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode envelope: %v", err)
	}
	data := envelope.Data
	// The existing fields still hold (the login client keeps working).
	if data.ID != userID.String() || data.Email != "boss@eden.local" || data.Name != "Boss" || !data.IsDefault {
		t.Fatalf("bootstrap user fields = %+v, want the default user boss@eden.local", data)
	}
	// The new profile fields are present.
	if data.Organization.ID != orgID.String() || data.Organization.Name != "Eden" {
		t.Fatalf("bootstrap organization = %+v, want id %s name Eden", data.Organization, orgID)
	}
	if data.Role != "admin" || len(data.Permissions) != 1 || data.Permissions[0] != "*" {
		t.Fatalf("bootstrap role/permissions = %q/%v, want admin/[*]", data.Role, data.Permissions)
	}
}
