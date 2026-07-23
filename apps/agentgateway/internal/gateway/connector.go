package gateway

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// This file is the CONNECTOR contract for the agentgateway's dev/settings surface: the Connector
// value, the ConnectorStore port (the consumer-defined persistence seam), and the wire DTOs the
// Settings → Connectors section exchanges. A Connector is a USER's stored credential for a provider
// (claude-api / github / openrouter) the platform's agents consume — the write-only user-secrets
// manager (connectors design §2/§3).
//
// The CANONICAL home for connectors is platformgateway's /v1/connectors, envelope-encrypted in
// Postgres (design §1.1, Brief A). This gateway carries a FAITHFUL dev counterpart so the frontend's
// Connectors section is exercised by the same real create→save→list→delete E2E the live demo runs —
// the same real-vs-fake mirror the AgentConfig/Proposer/ProjectStore seams use. The WIRE SHAPE is
// identical to §2: a ConnectorView NEVER carries the plaintext value; the credential crosses the
// create body ONCE and is answered with only {id, kind, name, scope, state, accountHint, fingerprint}.
//
// The invariant is enforced BY CONSTRUCTION here: the plaintext lives only on the write path (Connect),
// is digested to a one-way fingerprint, and is never stored on the Connector value nor projected onto
// a view. The dev store does not even retain the plaintext (it keeps only the fingerprint) — so no
// read path can leak it.

// ConnectorKind is the closed v1 provider enum (§2.2). Only kinds whose connect path works are
// admitted (honest chrome, P-D6). LOCKED v1 set mirrors the three ESO bootstrap items.
const (
	ConnectorKindClaudeAPI  = "claude-api"
	ConnectorKindGitHub     = "github"
	ConnectorKindOpenRouter = "openrouter"
)

// connectorKinds is the closed admit-set validate checks a Connect request against.
var connectorKinds = map[string]struct{}{
	ConnectorKindClaudeAPI:  {},
	ConnectorKindGitHub:     {},
	ConnectorKindOpenRouter: {},
}

// Connector scope levels (§2.2). `org` is the v1 DEFAULT (user_id NULL ⇒ org-scoped).
const (
	ConnectorScopeOrg     = "org"
	ConnectorScopeUser    = "user"
	ConnectorScopeProject = "project"
)

// Connector lifecycle states (§2). `healthy` == a validated, live credential; `not-set` == an
// offered-but-uncredentialed row. The dev backend marks a freshly-connected credential `healthy`.
const (
	ConnectorStateHealthy = "healthy"
	ConnectorStateNotSet  = "not-set"
)

// ConnectorScope is a connector's scope binding (§2.2). TargetID is empty for an org scope.
type ConnectorScope struct {
	Level    string `json:"level"`
	TargetID string `json:"targetId,omitempty"`
}

// Connector is the stored connector record (the dev counterpart of platformgateway's row). It holds
// NO plaintext value — only the one-way Fingerprint (design §1.1: a truncated SHA-256, safe to store
// and show) and the non-secret account hint. One concept, one home.
type Connector struct {
	ID          string
	Kind        string
	Name        string
	Scope       ConnectorScope
	State       string
	AccountHint string
	Fingerprint string
	UpdatedAt   time.Time
}

// ConnectorStore is the connectors persistence port: the consumer-defined seam the Settings →
// Connectors section reads and writes through. A real platformgateway domain backs it in production;
// an in-memory fake backs it in devserve (the real-vs-fake mirror the AgentConfigStore uses). It is
// OPTIONAL on Deps: when nil the /connectors routes are a 503.
//
// List returns every connector for the caller's scope; Put upserts one keyed by (Kind, Name) and
// returns the stored copy; Delete removes one by id (a wrapped KindNotFound when absent).
type ConnectorStore interface {
	List(ctx context.Context) ([]Connector, error)
	Put(ctx context.Context, connector Connector) (Connector, error)
	Delete(ctx context.Context, id string) error
}

// validateConnectorKind admits only the closed v1 enum (§2.2 → KindInvalid → 400 off-list).
func validateConnectorKind(kind string) error {
	if _, ok := connectorKinds[strings.TrimSpace(kind)]; !ok {
		return errors.New(errors.KindInvalid, "gateway: unsupported connector kind "+kind)
	}
	return nil
}

// normalizeConnectorScope folds a scope input into a valid scope (an unrecognized level resolves to
// the org DEFAULT — the same forgiving stance the agent-config normalizer takes). An org scope
// clears its target id (org-wide, no target).
func normalizeConnectorScope(scope ConnectorScope) ConnectorScope {
	switch strings.ToLower(strings.TrimSpace(scope.Level)) {
	case ConnectorScopeUser:
		scope.Level = ConnectorScopeUser
	case ConnectorScopeProject:
		scope.Level = ConnectorScopeProject
	default:
		scope.Level = ConnectorScopeOrg
		scope.TargetID = ""
	}
	return scope
}

// fingerprintCredential digests the plaintext to the one-way display fingerprint (design §1.1: a
// truncated SHA-256 last-4 / short hex, safe to store and show — the same class as a password hash).
// It is the ONLY thing the write path derives from the plaintext; the plaintext is discarded after.
func fingerprintCredential(plaintext string) string {
	sum := sha256.Sum256([]byte(plaintext))
	// The last-4 of the hex digest — a stable, non-reversible short tag for the write-only display.
	return hex.EncodeToString(sum[:])[:4]
}

// ── wire DTOs ──────────────────────────────────────────────────────────────────.

// createConnectorRequest is the body of POST /connectors (§2.2): the create fields. `Value` is the
// plaintext credential — it crosses this seam EXACTLY once and is never echoed back.
type createConnectorRequest struct {
	Kind  string           `json:"kind"`
	Name  string           `json:"name"`
	Value string           `json:"value"`
	Scope connectorScopeIn `json:"scope"`
}

// connectorScopeIn is the scope input on a create request (§2.2 ScopeInput).
type connectorScopeIn struct {
	Level    string `json:"level"`
	TargetID string `json:"targetId,omitempty"`
}

// connectorScopeView is the JSON projection of a connector's scope.
type connectorScopeView struct {
	Level    string `json:"level"`
	TargetID string `json:"targetId,omitempty"`
}

// connectorView is the §2 wire projection of a Connector — the binding FE↔BE shape. It has NO value
// field, EVER: only the fingerprint + account hint. This mirrors platformgateway's view.Connector.
type connectorView struct {
	ID          string             `json:"id"`
	Kind        string             `json:"kind"`
	Name        string             `json:"name"`
	Scope       connectorScopeView `json:"scope"`
	State       string             `json:"state"`
	AccountHint string             `json:"accountHint"`
	Fingerprint string             `json:"fingerprint"`
}

// listConnectorsResponse is the body of GET /connectors (wrapped in the data envelope): the caller's
// connectors.
type listConnectorsResponse struct {
	Connectors []connectorView `json:"connectors"`
}

// toConnectorView projects a Connector onto its wire DTO. It CANNOT carry a value — the Connector
// value holds no plaintext (only the fingerprint), so the write-only invariant holds by construction.
//
//nolint:gocritic // Connector is the copyable persisted record; the projector reads it by value.
func toConnectorView(connector Connector) connectorView {
	return connectorView{
		ID:   connector.ID,
		Kind: connector.Kind,
		Name: connector.Name,
		Scope: connectorScopeView{
			Level:    connector.Scope.Level,
			TargetID: connector.Scope.TargetID,
		},
		State:       connector.State,
		AccountHint: connector.AccountHint,
		Fingerprint: connector.Fingerprint,
	}
}
