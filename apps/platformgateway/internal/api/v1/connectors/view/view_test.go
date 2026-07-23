package view

import (
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// TestIsValidKind asserts the closed v1 kind vocabulary: the three shipped kinds pass, anything else
// (a plausible-but-unshipped kind) fails — honest chrome (only a kind whose connect path works ships).
func TestIsValidKind(t *testing.T) {
	t.Parallel()
	for _, k := range []string{KindClaudeAPI, KindGitHub, KindOpenRouter} {
		if !IsValidKind(k) {
			t.Fatalf("IsValidKind(%q) = false, want true", k)
		}
	}
	for _, k := range []string{"aws", "gcp", "", "CLAUDE-API"} {
		if IsValidKind(k) {
			t.Fatalf("IsValidKind(%q) = true, want false (off-list)", k)
		}
	}
}

// TestIsValidScopeLevel asserts the closed scope vocabulary (org|user).
func TestIsValidScopeLevel(t *testing.T) {
	t.Parallel()
	if !IsValidScopeLevel(ScopeOrg) || !IsValidScopeLevel(ScopeUser) {
		t.Fatal("org/user must be valid scope levels")
	}
	if IsValidScopeLevel("project") || IsValidScopeLevel("") {
		t.Fatal("project/empty must be invalid scope levels")
	}
}

// TestNewConnector_ProjectsScopeAndCarriesNoValue asserts the projection: an org-scoped row (nil
// UserID) renders scope "org" with no targetId; a user-scoped row renders "user" with the owner id;
// and the wire type carries the fingerprint but has no value field (it structurally cannot leak one).
func TestNewConnector_ProjectsScopeAndCarriesNoValue(t *testing.T) {
	t.Parallel()
	now := time.Now()

	orgRow := persistence.Connector{
		ID: uuid.New(), OrganizationID: uuid.New(), UserID: nil,
		Kind: KindClaudeAPI, Name: "org token", AccountHint: "me@x", Fingerprint: "abc123",
		CreatedBy: uuid.New(), CreatedAt: now, UpdatedAt: now,
	}
	orgView := NewConnector(&orgRow)
	if orgView.Scope.Level != ScopeOrg || orgView.Scope.TargetID != "" {
		t.Fatalf("org-scoped projection = %+v, want level org / empty targetId", orgView.Scope)
	}
	if orgView.Fingerprint != "abc123" || orgView.State != stateSet {
		t.Fatalf("projection dropped fingerprint/state: %+v", orgView)
	}

	owner := uuid.New()
	userRow := persistence.Connector{
		ID: uuid.New(), OrganizationID: uuid.New(), UserID: &owner,
		Kind: KindGitHub, Name: "user token", Fingerprint: "def456",
		CreatedBy: uuid.New(), CreatedAt: now, UpdatedAt: now,
	}
	userView := NewConnector(&userRow)
	if userView.Scope.Level != ScopeUser || userView.Scope.TargetID != owner.String() {
		t.Fatalf("user-scoped projection = %+v, want level user / owner targetId", userView.Scope)
	}
}

// TestParseID rejects a malformed path id with KindInvalid and accepts a valid uuid.
func TestParseID(t *testing.T) {
	t.Parallel()
	if _, err := ParseID("not-a-uuid"); err == nil {
		t.Fatal("ParseID(bad) = nil error, want a typed 400")
	}
	id := uuid.New()
	got, err := ParseID(id.String())
	if err != nil || got != id {
		t.Fatalf("ParseID(valid) = %v, %v; want %v, nil", got, err, id)
	}
}
