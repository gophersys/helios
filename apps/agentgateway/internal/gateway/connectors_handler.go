package gateway

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"strings"

	"github.com/gophersys/libs/go/errors"
)

// connectors_handler holds the Settings → Connectors surface (the user-secrets manager, design §3):
// list the caller's connectors, connect a provider (the credential crosses ONCE), and disconnect
// (revoke) one. Every route is enveloped (the edenhttp {data, errors, kind} shape) and 503 when no
// ConnectorStore is wired (the Connectors dep is OPTIONAL). A ConnectorView NEVER carries the
// plaintext value — the write-only invariant (§2).

// handleListConnectors returns every connector for the caller's scope (the Settings section loads
// these to render its write-only list). Never a value — only fingerprint + account hint per row.
func (g *Gateway) handleListConnectors(w http.ResponseWriter, r *http.Request) {
	if g.dependencies.Connectors == nil {
		g.writeEnvelopeError(w, errors.New(errors.KindUnavailable, "gateway: connector persistence is not configured"))
		return
	}

	connectors, err := g.dependencies.Connectors.List(r.Context())
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	views := make([]connectorView, 0, len(connectors))
	for i := range connectors {
		views = append(views, toConnectorView(connectors[i]))
	}
	g.writeData(w, http.StatusOK, listConnectorsResponse{Connectors: views})
}

// handleCreateConnector connects a provider: it validates the kind against the closed enum, digests
// the plaintext credential to a one-way fingerprint (the plaintext is discarded immediately — it is
// NEVER stored, logged, nor projected onto the response), and upserts the connector. The credential
// crosses HERE exactly once; the 201 response carries only the write-only view (fingerprint + hint).
func (g *Gateway) handleCreateConnector(w http.ResponseWriter, r *http.Request) {
	if g.dependencies.Connectors == nil {
		g.writeEnvelopeError(w, errors.New(errors.KindUnavailable, "gateway: connector persistence is not configured"))
		return
	}

	var request createConnectorRequest
	if err := decodeJSON(r, &request); err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	if err := validateConnectorKind(request.Kind); err != nil {
		g.writeEnvelopeError(w, err)
		return
	}
	if strings.TrimSpace(request.Value) == "" {
		g.writeEnvelopeError(w, errors.Wrap(errors.KindInvalid, "gateway: create connector",
			RequestError{Reason: "value is required"}))
		return
	}

	identifier, err := generateConnectorID()
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	name := strings.TrimSpace(request.Name)
	if name == "" {
		name = request.Kind // default the display name to the provider kind.
	}

	// Digest the plaintext to the one-way fingerprint, then let it fall out of scope — the plaintext
	// is never retained past this line (no store field, no log, no response field).
	fingerprint := fingerprintCredential(request.Value)

	connector := Connector{
		ID:          identifier,
		Kind:        strings.TrimSpace(request.Kind),
		Name:        name,
		Scope:       normalizeConnectorScope(ConnectorScope{Level: request.Scope.Level, TargetID: request.Scope.TargetID}),
		State:       ConnectorStateHealthy,
		AccountHint: deriveAccountHint(request.Kind, fingerprint),
		Fingerprint: fingerprint,
		UpdatedAt:   g.dependencies.Clock.Now(),
	}

	stored, err := g.dependencies.Connectors.Put(r.Context(), connector)
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	// The audit line carries only non-secret identifiers — never the value, never the fingerprint's
	// preimage (design §1.1 audit trail).
	g.logInfo("gateway: connector connected", "id", stored.ID, "kind", stored.Kind, "scope", stored.Scope.Level)
	g.writeData(w, http.StatusCreated, toConnectorView(stored))
}

// handleDeleteConnector revokes (disconnects) a connector by id. It is enveloped-error on fault; a
// clean revoke returns 204 with no body.
func (g *Gateway) handleDeleteConnector(w http.ResponseWriter, r *http.Request) {
	if g.dependencies.Connectors == nil {
		g.writeEnvelopeError(w, errors.New(errors.KindUnavailable, "gateway: connector persistence is not configured"))
		return
	}

	id := strings.TrimSpace(r.PathValue("id"))
	if id == "" {
		g.writeEnvelopeError(w, errors.Wrap(errors.KindInvalid, "gateway: delete connector",
			RequestError{Reason: "id is required"}))
		return
	}

	if err := g.dependencies.Connectors.Delete(r.Context(), id); err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	g.logInfo("gateway: connector disconnected", "id", id)
	w.WriteHeader(http.StatusNoContent)
}

// generateConnectorID mints an opaque, collision-resistant connector id ("connector-" + 18 hex chars
// from a cryptographic source), the same shape as the project id. A rand fault is the only error
// path (surfaced as KindInternal).
func generateConnectorID() (string, error) {
	var raw [9]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return "", errors.Wrap(errors.KindInternal, "gateway: generate connector id", err)
	}
	return "connector-" + hex.EncodeToString(raw[:]), nil
}

// deriveAccountHint synthesizes a NON-SECRET account hint for the dev backend (the real platform
// derives it from the provider's own /whoami on validate). It never derives from the plaintext value
// — only from the kind + the already-public fingerprint tag — so no secret material leaks. Honest
// chrome: a short, provider-shaped label the write-only row shows beside the fingerprint.
func deriveAccountHint(kind, fingerprint string) string {
	switch strings.TrimSpace(kind) {
	case ConnectorKindGitHub:
		return "gh-" + fingerprint
	case ConnectorKindClaudeAPI:
		return "claude-" + fingerprint
	case ConnectorKindOpenRouter:
		return "or-" + fingerprint
	default:
		return ""
	}
}
