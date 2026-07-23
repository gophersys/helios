// Package connectorcredential is the agentgateway-side wiring that lets a session CONSUME a
// user-uploaded connector credential (ADR-0029 §4 / doc 19 §4 — the A3 follow-on). It provides the
// two composition-root seams the platformconnectoradapter needs:
//
//   - a REAL pgx-backed platformconnectoradapter.SealedRowLoader that loads the envelope-sealed
//     connector row from the platformgateway `connectors` domain's Postgres, TENANT-SCOPED to a
//     caller org (the WHERE organization_id predicate — the cross-tenant isolation invariant,
//     ADR-0029 §2.3). The secrets module stays pgx-free (ADR-0029 §4: the real binding lives in the
//     consumer), so this is where the database dependency for connector resolution lives.
//   - a derivation: given a project's owning org, choose the session's Spec.Credential — an
//     eden://connector/<id> reference when the org has a `claude-api` connector, else the platform
//     EDEN_CREDENTIAL_REF fallback (doc 19 §4). The fallback is NEVER regressed: no org, no
//     connectors database, or a lookup fault all degrade to the platform reference.
//
// The connectors table lives in the platformgateway database (ADR-0029: the connectors domain is the
// platformgateway's), which is DISTINCT from the agentgateway's own record-plane DSN — the sealed
// material is read directly from Postgres by the agent-resolution plane (doc 19 §3.4: "the sealed
// material is read only by the agent-resolution path"). There is no plaintext read route (there is no
// plaintext at rest); this reads only the sealed blobs and unseals them via envelope through the
// adapter.
package connectorcredential

import (
	"context"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/platformconnectoradapter"
)

// claudeConnectorKind is the closed-enum connector kind an agent's harness credential is derived from:
// a user-uploaded Claude API token (ADR-0029 §5). Only this kind is consulted for the supervisor/
// propose harness credential — github/openrouter are distinct planes.
const claudeConnectorKind = "claude-api"

// referencePrefix is the scheme+resource an eden connector reference renders as: "eden://connector/".
// The derivation renders "eden://connector/<id>" for the chosen connector; the adapter parses it back.
const referencePrefix = "eden://connector/"

// PostgresLoader is the REAL platformconnectoradapter.SealedRowLoader: it loads the envelope-sealed
// material for a connector id from the platformgateway connectors/connector_secrets tables. It holds a
// pgx pool over the platformgateway database. A pgx.ErrNoRows (a missing id) is the zero SealedRecord —
// the documented "no such connector" sentinel the adapter maps to NotFound. Safe for concurrent use
// (the pool is).
//
// It is PROCESS-WIDE (one loader behind the process-wide secrets.Mediator, resolving every session's
// eden://connector/<id>), so it loads by CONNECTOR ID ALONE — the caller-org authorization (ADR-0029
// §4) is enforced UPSTREAM at DERIVATION time: the Deriver selects the id from the owning org's OWN
// `claude-api` connectors (the WHERE organization_id predicate lives in DeriveClaudeCredential), so a
// derived reference already names a connector the org owns. The id is a server-minted, unguessable
// UUID, so an org can only ever hold references to its own connectors. (The lib-level org-scoped load
// — the WHERE organization_id defense-in-depth — is exercised in the platformconnectoradapter
// integration lane; the process-wide app adapter's org gate is the derivation.)
type PostgresLoader struct {
	pool *pgxpool.Pool
}

// NewPostgresLoader builds a PostgresLoader over an already-open pool. The pool is owned by the caller
// (the composition root opens + closes it). PURE: no I/O.
func NewPostgresLoader(pool *pgxpool.Pool) *PostgresLoader {
	return &PostgresLoader{pool: pool}
}

// loadSealedQuery selects the sealed material for a connector id, JOINed to its metadata row. The value
// is NEVER selected (there is no plaintext column); only the sealed blobs + the kek version are read
// (doc 19 §3.4).
const loadSealedQuery = `
	SELECT cs.ciphertext, cs.wrapped_dek, cs.nonce_ciphertext, cs.nonce_dek, cs.kek_version
	FROM connector_secrets cs
	JOIN connectors c ON c.id = cs.connector_id
	WHERE c.id = $1`

// LoadSealed implements platformconnectoradapter.SealedRowLoader. It parses the opaque connector id,
// runs the SELECT, and returns the sealed record. A non-uuid id or a miss is the zero SealedRecord
// (mapped to NotFound by the adapter); a real database fault is a wrapped KindUnavailable the adapter
// maps to UnavailableError (the retryable signal). It never returns a plaintext (there is none at rest).
func (l *PostgresLoader) LoadSealed(ctx context.Context, id string) (platformconnectoradapter.SealedRecord, error) {
	connectorID, err := uuid.Parse(id)
	if err != nil {
		// A non-uuid connector id names no row; return the absent zero value so the adapter maps it to
		// NotFound (not a leaked parse error).
		return platformconnectoradapter.SealedRecord{}, nil //nolint:nilerr // a bad id is "no such connector", the documented sentinel.
	}
	var record platformconnectoradapter.SealedRecord
	row := l.pool.QueryRow(ctx, loadSealedQuery, connectorID)
	scanErr := row.Scan(&record.Ciphertext, &record.WrappedDEK, &record.NonceCiphertext, &record.NonceDEK, &record.KEKVersion)
	if scanErr != nil {
		if errors.Is(scanErr, pgx.ErrNoRows) {
			return platformconnectoradapter.SealedRecord{}, nil // miss → absent
		}
		return platformconnectoradapter.SealedRecord{}, errors.Wrap(errors.KindUnavailable, "connectorcredential: load sealed connector row", scanErr)
	}
	return record, nil
}

// compile-time: *PostgresLoader is a platformconnectoradapter.SealedRowLoader.
var _ platformconnectoradapter.SealedRowLoader = (*PostgresLoader)(nil)

// Deriver derives a session's harness credential reference from a project's owning org: the org's
// `claude-api` connector when one exists, else the platform fallback. It holds a pgx pool over the
// platformgateway connectors database + the loggable fallback reference. When the pool is nil (no
// connectors database configured) DeriveClaudeCredential ALWAYS returns the fallback — so a deployment
// without the connectors DSN behaves EXACTLY as today (the fallback is never regressed). Safe for
// concurrent use.
type Deriver struct {
	pool     *pgxpool.Pool
	fallback secrets.Reference
}

// NewDeriver builds a Deriver over an already-open connectors pool (nil = "no connectors database; use
// the fallback for everything") and the platform fallback reference (the EDEN_CREDENTIAL_REF plane).
// PURE: no I/O. The pool is owned by the caller.
func NewDeriver(pool *pgxpool.Pool, fallback secrets.Reference) *Deriver {
	return &Deriver{pool: pool, fallback: fallback}
}

// latestClaudeConnectorQuery selects the newest `claude-api` connector id for an org (a connector is
// UNIQUE per (org, kind, name), so an org may hold several claude-api connectors under different names;
// the most recently created is the effective one). TENANT-SCOPED to the org. It never reads the value.
const latestClaudeConnectorQuery = `
	SELECT id
	FROM connectors
	WHERE organization_id = $1 AND kind = $2
	ORDER BY created_at DESC
	LIMIT 1`

// DeriveClaudeCredential returns the credential reference the session's Spec.Credential folds for a
// project owned by organizationID: an eden://connector/<id> reference when the org has a `claude-api`
// connector, else the platform fallback (doc 19 §4). It NEVER regresses the fallback: a nil pool, a
// no-connector org, OR a lookup fault all return the fallback (a connector lookup failure must not break
// session creation — the platform credential still works). The returned reference is loggable; it names
// a connector or the fallback, never a value.
func (d *Deriver) DeriveClaudeCredential(ctx context.Context, organizationID uuid.UUID) secrets.Reference {
	if d.pool == nil {
		return d.fallback // no connectors database → the platform reference, exactly as today
	}
	var connectorID uuid.UUID
	row := d.pool.QueryRow(ctx, latestClaudeConnectorQuery, organizationID, claudeConnectorKind)
	if err := row.Scan(&connectorID); err != nil {
		// No claude-api connector for this org (pgx.ErrNoRows) OR a transient lookup fault: fall back to
		// the platform credential. A connector lookup failure must never break session creation.
		return d.fallback
	}
	return secrets.Ref(referencePrefix + connectorID.String())
}

// Seam is the fully-wired connector-credential composition the gateway holds: the "eden" scheme adapter
// to register in the secrets Mediator, the Deriver that picks a session's credential reference, and the
// Close that releases the owned connectors pool. It is the ONE object a composition root builds and
// holds. When no connectors DSN is configured, Build returns a DEGRADED Seam (Adapter nil, Deriver
// always-fallback) so a deployment without the connectors database behaves exactly as today.
type Seam struct {
	// Adapter is the platformconnectoradapter.Adapter to register under the "eden" scheme in the
	// secrets Mediator (nil when no connectors database is configured — then eden://connector/<id> is
	// never derived, so the scheme need not be bound).
	Adapter *platformconnectoradapter.Adapter
	// Deriver picks a session's Spec.Credential from the project's owning org (fallback-only when no
	// connectors database is configured). Never nil.
	Deriver *Deriver
	// Close releases the owned connectors pool (a no-op when none was opened). Never nil.
	Close func()
}

// Config is the immutable Build input: the connectors database DSN (empty ⇒ the degraded fallback-only
// Seam), the KEK reference the envelope Sealer resolves through (the SAME platform-Vault reference the
// platformgateway connectors domain seals under), the KEK version, and the platform fallback credential
// reference (EDEN_CREDENTIAL_REF).
type Config struct {
	// ConnectorsDSN is the resolved DSN of the platformgateway connectors database. Empty ⇒ no connector
	// resolution (the degraded Seam: Deriver always returns the fallback, Adapter is nil).
	ConnectorsDSN string
	// KEK is the loggable secrets.Reference the envelope KEK resolves from (e.g.
	// vault://eden/production#connectors-kek). Required when ConnectorsDSN is set.
	KEK secrets.Reference
	// KEKVersion is the KEK generation stamp (>= 1; defaults to 1 when unset).
	KEKVersion int
	// Fallback is the platform credential reference the derivation falls back to (EDEN_CREDENTIAL_REF).
	// Required.
	Fallback secrets.Reference
}

// Deps is the injected hexagon: the secrets.Provider the envelope KEK resolves through (the SAME
// process-wide Vault-backed provider the rest of the gateway holds).
type Deps struct {
	// Secrets is the redaction port the envelope KEK is resolved through. Required when Config.ConnectorsDSN is set.
	Secrets secrets.Provider
}

// Build wires the connector-credential seam: it opens the connectors pool (when a DSN is configured),
// builds the process-wide sealed-row loader + the platformconnectoradapter over the injected secrets
// provider (the KEK plane), and the org→credential Deriver. When no DSN is configured it returns a
// DEGRADED Seam (Adapter nil, Deriver always-fallback, Close a no-op) so today's behavior is preserved
// exactly. It opens the pool at the edge (a composition-root startup step); the Deriver/loader do no
// I/O until a session is created.
func Build(ctx context.Context, configuration Config, dependencies Deps) (Seam, error) {
	if configuration.ConnectorsDSN == "" {
		// No connectors database: the fallback-only Seam. eden://connector/<id> is never derived, so no
		// adapter/scheme is needed — every session gets the platform EDEN_CREDENTIAL_REF, exactly as today.
		return Seam{
			Adapter: nil,
			Deriver: NewDeriver(nil, configuration.Fallback),
			Close:   func() {},
		}, nil
	}
	if dependencies.Secrets == nil {
		return Seam{}, errors.New(errors.KindInvalid, "connectorcredential: Deps.Secrets is required when a connectors DSN is configured (the KEK resolution port)")
	}
	if configuration.KEK.IsZero() {
		return Seam{}, errors.New(errors.KindInvalid, "connectorcredential: Config.KEK is required when a connectors DSN is configured")
	}

	pool, err := pgxpool.New(ctx, configuration.ConnectorsDSN)
	if err != nil {
		return Seam{}, errors.Wrap(errors.KindUnavailable, "connectorcredential: open connectors database pool", err)
	}
	adapter, err := platformconnectoradapter.New(
		platformconnectoradapter.Config{KEK: configuration.KEK, KEKVersion: configuration.KEKVersion},
		platformconnectoradapter.Deps{Loader: NewPostgresLoader(pool), Secrets: dependencies.Secrets},
	)
	if err != nil {
		pool.Close()
		return Seam{}, errors.Wrap(errors.KindInternal, "connectorcredential: build connector adapter", err)
	}
	return Seam{
		Adapter: adapter,
		Deriver: NewDeriver(pool, configuration.Fallback),
		Close:   pool.Close,
	}, nil
}
