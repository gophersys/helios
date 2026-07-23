// Package view is the ONE home (10 §9) for the `connectors` wire projection: the JSON shape the
// OpenAPI contract's `ConnectorView` schema mirrors, and the single seam that projects a domain
// persistence.Connector (pgtype-free, plain Go scalars) into it. Every connectors route's execute
// stage produces a Connector through NewConnector, so the wire shape is spelled once and
// create/get/list/update render a row identically. It is a leaf: the route sub-packages import it, it
// imports none of them, so the connectors package composes the routes without an import cycle.
//
// The wire projection carries the fingerprint, the account hint, and the scope — NEVER the credential
// value (ADR-0029, doc 19). There is no `value` field on this type, by construction: the plaintext
// crosses the create/update seam once and is never read back.
package view

import (
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// The closed v1 connector-kind vocabulary (ADR-0029 §5, honest chrome — only a kind whose connect
// path works ships). The create/update validate stages reject anything off this list with a typed
// errors.KindInvalid (→ 400). Declared once here so the vocabulary lives in one home the routes cite.
const (
	// KindClaudeAPI is a Claude API token (the anthropic setup-token class).
	KindClaudeAPI = "claude-api"
	// KindGitHub is a GitHub token (the gh-token class).
	KindGitHub = "github"
	// KindOpenRouter is an OpenRouter API key.
	KindOpenRouter = "openrouter"
)

// The connector scope levels (ADR-0029 §5). "org" is the default (shared across the org); "user"
// scopes the connector to one user's projects.
const (
	// ScopeOrg is the org-wide scope (user_id NULL) — the default.
	ScopeOrg = "org"
	// ScopeUser is the per-user scope (user_id set to the owner).
	ScopeUser = "user"
)

// validKinds is the closed set the validate stage checks membership against. A map for O(1) lookup;
// the ONE home for the enum-membership check.
var validKinds = map[string]struct{}{
	KindClaudeAPI:  {},
	KindGitHub:     {},
	KindOpenRouter: {},
}

// IsValidKind reports whether kind is a member of the closed v1 connector-kind vocabulary. The
// create/update validate stages call it and map a false to errors.KindInvalid (→ 400) — honest chrome.
func IsValidKind(kind string) bool {
	_, ok := validKinds[kind]
	return ok
}

// IsValidScopeLevel reports whether level is a member of the closed scope vocabulary (org|user).
func IsValidScopeLevel(level string) bool {
	return level == ScopeOrg || level == ScopeUser
}

// Scope is the wire projection of a connector's tenancy scope: "org" (shared across the org, the
// default) or "user" (only that user's projects use it). TargetID is the owning user id for a
// user-scoped connector, omitted for an org-scoped one. It mirrors the contract's `ConnectorScope`
// schema.
type Scope struct {
	// Level is the scope level: "org" or "user".
	Level string `json:"level"`
	// TargetID is the owning user id for a user-scoped connector (omitted when org-scoped).
	TargetID string `json:"targetId,omitempty"`
}

// ScopeInput is the request-side scope selector the create route decodes (the contract's
// `ConnectorScopeInput` schema). It lives here (one home) so create and any future scope-taking route
// share the shape; the create validate stage checks it. TargetID is required only for user scope.
type ScopeInput struct {
	// Level is the scope level: "org" (default) or "user". validate rejects anything off-list.
	Level string `json:"level"`
	// TargetID is the owning user id for a user-scoped connector (a uuid string); ignored for org scope.
	TargetID string `json:"targetId,omitempty"`
}

// Connector is the wire projection of a persisted connector — the success payload create/get/update
// return and the element type list returns. It mirrors the contract's `ConnectorView` schema
// (operationId-stable field names), RFC3339-stamped so the contract's `format: date-time` holds. It
// carries plain JSON scalars only; NO pgtype, and — the load-bearing invariant — NO credential value,
// ever. The write-only UI renders only the Fingerprint + AccountHint.
type Connector struct {
	// ID is the server-minted connector id (a uuid string).
	ID string `json:"id"`
	// Kind is the connector kind: "claude-api" | "github" | "openrouter".
	Kind string `json:"kind"`
	// Name is the connector's human label.
	Name string `json:"name"`
	// Scope is the connector's tenancy scope (org/user).
	Scope Scope `json:"scope"`
	// State is the connector's health state the UI renders as a status pill. v1 reports "set" for a
	// stored connector (the honest state — the credential is present; deeper health checks are future).
	State string `json:"state"`
	// AccountHint is a NON-secret display crumb (an account handle / masked email); never the value.
	AccountHint string `json:"accountHint"`
	// Fingerprint is the one-way truncated SHA-256 hint the write-only UI shows; never the value.
	Fingerprint string `json:"fingerprint"`
	// CreatedAt is the RFC3339 insert timestamp.
	CreatedAt string `json:"createdAt"`
	// UpdatedAt is the RFC3339 last-mutation timestamp.
	UpdatedAt string `json:"updatedAt"`
}

// stateSet is the honest v1 state a stored connector reports: the credential is present. Named once
// so create/get/list/update all render the same state token (a future health probe adds more states).
const stateSet = "set"

// NewConnector projects a domain persistence.Connector into the wire Connector. It is the single place
// the domain row becomes the JSON DTO, so every route renders a connector the same way — and the
// place the no-value invariant is upheld (the domain row carries no value either; only metadata).
// Timestamps are normalized to UTC RFC3339 to satisfy the contract's date-time format. The row is
// taken by pointer (a heavy timestamp-laden struct).
func NewConnector(row *persistence.Connector) Connector {
	scope := Scope{Level: "org"}
	if row.UserID != nil {
		scope.Level = "user"
		scope.TargetID = row.UserID.String()
	}
	return Connector{
		ID:          row.ID.String(),
		Kind:        row.Kind,
		Name:        row.Name,
		Scope:       scope,
		State:       stateSet,
		AccountHint: row.AccountHint,
		Fingerprint: row.Fingerprint,
		CreatedAt:   row.CreatedAt.UTC().Format(time.RFC3339),
		UpdatedAt:   row.UpdatedAt.UTC().Format(time.RFC3339),
	}
}

// ParseID parses a path id segment into a uuid, returning a typed errors.KindInvalid (→ 400) on a
// malformed id. It is the ONE home for the {id} path-parameter parse the get/update/removal routes
// use, so a bad id is a 400 with a stable Kind.
func ParseID(raw string) (uuid.UUID, error) {
	id, err := uuid.Parse(raw)
	if err != nil {
		return uuid.UUID{}, errors.Wrap(errors.KindInvalid, "connectors: parse id",
			edenhttp.RequestError{Reason: "path id is not a valid uuid"})
	}
	return id, nil
}
