package persistence

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/persistence/generated"
)

// uniqueViolationCode is the PostgreSQL SQLSTATE for a unique-constraint violation (23505). It is the
// ONE place the raw pgconn code is named — the facade maps it to a typed errors.KindConflict so the
// route execute stage branches on Kind (409), never on a driver code.
const uniqueViolationCode = "23505"

// Connector is the domain-facing metadata row the connectors route execute stages receive — plain Go
// scalars (uuid.UUID, *uuid.UUID, time.Time), NOT the generated pgtype-laden model. It carries NO
// credential value and NO sealed material: only the loggable metadata the write-only API returns
// (ADR-0029, doc 19). UserID is nil for an ORG-scoped connector, set for a USER-scoped one.
type Connector struct {
	ID             uuid.UUID
	OrganizationID uuid.UUID
	UserID         *uuid.UUID // nil => org-scoped
	Kind           string
	Name           string
	AccountHint    string
	Fingerprint    string
	CreatedBy      uuid.UUID
	CreatedAt      time.Time
	UpdatedAt      time.Time
}

// SealedMaterial is the domain-facing carrier of the envelope-sealed credential the facade writes to
// connector_secrets. It mirrors the libs/go/envelope Sealed record's byte blobs + kek version; the
// facade converts it to the generated params so the route execute stage never touches pgtype. It is
// NEVER read back for display — only written on create/replace (and read only by the agent-resolution
// path, not this read slice).
type SealedMaterial struct {
	Ciphertext      []byte
	WrappedDEK      []byte
	NonceCiphertext []byte
	NonceDEK        []byte
	KEKVersion      int32
}

// Connectors is the typed store over the connectors + connector_secrets tables (ADR-0029). It wraps
// the sqlc-generated Querier (never string-built SQL) and holds the pool so create/replace run their
// two writes (metadata + sealed material) in ONE transaction — a connector never exists without its
// sealed secret. It is the ONE place pgx's not-found sentinel becomes a typed errors.KindNotFound and
// a unique violation becomes errors.KindConflict. It holds only the pool + Querier (both
// concurrency-safe), so it is safe for concurrent use.
type Connectors struct {
	pool    *pgxpool.Pool
	queries generated.Querier
}

// Create inserts a connector's metadata + its sealed material in one transaction and returns the
// domain row (never the value). A (organization_id, kind, name) collision is a typed
// errors.KindConflict (→ 409); any other fault rolls back and is wrapped with its Kind. createdBy is
// the audit actor; userID is nil for an org-scoped connector.
func (c *Connectors) Create(
	ctx context.Context,
	id, organizationID uuid.UUID,
	userID *uuid.UUID,
	kind, name, accountHint, fingerprint string,
	createdBy uuid.UUID,
	sealed SealedMaterial,
) (Connector, error) {
	transaction, err := c.pool.Begin(ctx)
	if err != nil {
		return Connector{}, errors.Wrap(errors.KindUnavailable, "persistence: begin connector create tx", err)
	}
	// Rollback is a no-op after Commit; the deferred rollback guards every early return.
	defer func() { _ = transaction.Rollback(ctx) }() //nolint:errcheck // rollback error is unactionable after a returned fault (Commit already ran on the happy path).

	tx := generated.New(transaction)
	row, err := tx.CreateConnector(ctx, generated.CreateConnectorParams{
		ID:             toPgUUID(id),
		OrganizationID: toPgUUID(organizationID),
		UserID:         toPgUUIDOrNull(userID),
		Kind:           kind,
		Name:           name,
		AccountHint:    accountHint,
		Fingerprint:    fingerprint,
		CreatedBy:      toPgUUID(createdBy),
	})
	if err != nil {
		if isUniqueViolation(err) {
			return Connector{}, conflictConnector(kind, name)
		}
		return Connector{}, errors.Wrap(errors.KindInternal, "persistence: insert connector", err)
	}
	if err := tx.CreateConnectorSecret(ctx, generated.CreateConnectorSecretParams{
		ConnectorID:     toPgUUID(id),
		Ciphertext:      sealed.Ciphertext,
		WrappedDek:      sealed.WrappedDEK,
		NonceCiphertext: sealed.NonceCiphertext,
		NonceDek:        sealed.NonceDEK,
		KekVersion:      sealed.KEKVersion,
	}); err != nil {
		return Connector{}, errors.Wrap(errors.KindInternal, "persistence: insert connector secret", err)
	}
	if err := transaction.Commit(ctx); err != nil {
		return Connector{}, errors.Wrap(errors.KindUnavailable, "persistence: commit connector create tx", err)
	}
	return fromConnectorRow(&row), nil
}

// Get fetches a single connector by id, TENANT-SCOPED to organizationID. A row owned by another org
// is invisible (the organization_id predicate excludes it) → typed errors.KindNotFound (404), never a
// cross-tenant leak.
func (c *Connectors) Get(ctx context.Context, id, organizationID uuid.UUID) (Connector, error) {
	row, err := c.queries.GetConnector(ctx, generated.GetConnectorParams{
		ID:             toPgUUID(id),
		OrganizationID: toPgUUID(organizationID),
	})
	if err != nil {
		if isNoRows(err) {
			return Connector{}, notFoundConnector(id.String())
		}
		return Connector{}, errors.Wrap(errors.KindInternal, "persistence: get connector", err)
	}
	return fromConnectorRow(&row), nil
}

// List returns a page of the caller's org connectors oldest-first, TENANT-SCOPED to organizationID.
// The returned slice is never nil (an empty org renders `[]`, never null). It never SELECTs the
// sealed material.
func (c *Connectors) List(ctx context.Context, organizationID uuid.UUID, limit, offset int32) ([]Connector, error) {
	rows, err := c.queries.ListConnectors(ctx, generated.ListConnectorsParams{
		OrganizationID: toPgUUID(organizationID),
		Limit:          limit,
		Offset:         offset,
	})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "persistence: list connectors", err)
	}
	out := make([]Connector, len(rows))
	for i := range rows {
		out[i] = fromConnectorRow(&rows[i])
	}
	return out, nil
}

// Replace re-seals a connector's credential (rotation/replace): it updates the metadata (account_hint
// + fingerprint) and the sealed material in one transaction, TENANT-SCOPED to organizationID. A
// connector owned by another org matches nothing → typed errors.KindNotFound (404). Returns the
// updated domain row (never the value).
func (c *Connectors) Replace(
	ctx context.Context,
	id, organizationID uuid.UUID,
	accountHint, fingerprint string,
	sealed SealedMaterial,
) (Connector, error) {
	transaction, err := c.pool.Begin(ctx)
	if err != nil {
		return Connector{}, errors.Wrap(errors.KindUnavailable, "persistence: begin connector replace tx", err)
	}
	defer func() { _ = transaction.Rollback(ctx) }() //nolint:errcheck // unactionable after a returned fault / a committed tx.

	tx := generated.New(transaction)
	row, err := tx.ReplaceConnectorCredential(ctx, generated.ReplaceConnectorCredentialParams{
		ID:             toPgUUID(id),
		OrganizationID: toPgUUID(organizationID),
		AccountHint:    accountHint,
		Fingerprint:    fingerprint,
	})
	if err != nil {
		if isNoRows(err) {
			return Connector{}, notFoundConnector(id.String())
		}
		return Connector{}, errors.Wrap(errors.KindInternal, "persistence: replace connector credential", err)
	}
	if err := tx.ReplaceConnectorSecret(ctx, generated.ReplaceConnectorSecretParams{
		ConnectorID:     toPgUUID(id),
		Ciphertext:      sealed.Ciphertext,
		WrappedDek:      sealed.WrappedDEK,
		NonceCiphertext: sealed.NonceCiphertext,
		NonceDek:        sealed.NonceDEK,
		KekVersion:      sealed.KEKVersion,
	}); err != nil {
		return Connector{}, errors.Wrap(errors.KindInternal, "persistence: replace connector secret", err)
	}
	if err := transaction.Commit(ctx); err != nil {
		return Connector{}, errors.Wrap(errors.KindUnavailable, "persistence: commit connector replace tx", err)
	}
	return fromConnectorRow(&row), nil
}

// Delete revokes a connector by id, TENANT-SCOPED to organizationID. The ON DELETE CASCADE purges the
// sealed material atomically. A delete of an absent/other-org connector yields no row → typed
// errors.KindNotFound (404) — a delete is never a silent success.
func (c *Connectors) Delete(ctx context.Context, id, organizationID uuid.UUID) error {
	_, err := c.queries.DeleteConnector(ctx, generated.DeleteConnectorParams{
		ID:             toPgUUID(id),
		OrganizationID: toPgUUID(organizationID),
	})
	if err != nil {
		if isNoRows(err) {
			return notFoundConnector(id.String())
		}
		return errors.Wrap(errors.KindInternal, "persistence: delete connector", err)
	}
	return nil
}

// isUniqueViolation reports whether err is a PostgreSQL unique-constraint violation (SQLSTATE 23505) —
// the ONE place the raw pgconn code is inspected, so the mapping to KindConflict lives once (typed
// inspection via errors.AsType, never a string match — the errors contract).
func isUniqueViolation(err error) bool {
	if pgErr, ok := errors.AsType[*pgconn.PgError](err); ok && pgErr != nil {
		return pgErr.Code == uniqueViolationCode
	}
	return false
}

// notFoundConnector builds the canonical typed not-found error for a connector id. The id is a safe
// scalar; the value is never involved. Declared once so the Kind + message are consistent.
func notFoundConnector(id string) error {
	return errors.New(errors.KindNotFound, "persistence: connector not found").
		WithField("connector-id", id)
}

// conflictConnector builds the canonical typed conflict error for a (kind, name) collision within an
// org. kind + name are safe scalars (never the value). Declared once.
func conflictConnector(kind, name string) error {
	return errors.New(errors.KindConflict, "persistence: connector already exists").
		WithField("connector-kind", kind).
		WithField("connector-name", name)
}

// fromConnectorRow converts a generated (pgtype-laden) row to the domain Connector. uuid bytes,
// nullable user_id, and timestamps are unwrapped here — the single conversion seam, so the execute
// stages never touch pgtype. The row is taken by pointer (a heavy pgtype-laden struct).
func fromConnectorRow(row *generated.Connector) Connector {
	return Connector{
		ID:             uuid.UUID(row.ID.Bytes),
		OrganizationID: uuid.UUID(row.OrganizationID.Bytes),
		UserID:         fromPgUUIDOrNil(row.UserID),
		Kind:           row.Kind,
		Name:           row.Name,
		AccountHint:    row.AccountHint,
		Fingerprint:    row.Fingerprint,
		CreatedBy:      uuid.UUID(row.CreatedBy.Bytes),
		CreatedAt:      row.CreatedAt.Time,
		UpdatedAt:      row.UpdatedAt.Time,
	}
}

// toPgUUIDOrNull wraps a nullable domain uuid as the pgtype.UUID the generated Querier takes: a nil
// pointer is the NULL user_id (an org-scoped connector), a set pointer is a valid uuid.
func toPgUUIDOrNull(id *uuid.UUID) pgtype.UUID {
	if id == nil {
		return pgtype.UUID{Valid: false}
	}
	return pgtype.UUID{Bytes: *id, Valid: true}
}

// fromPgUUIDOrNil converts a nullable pgtype.UUID back to a *uuid.UUID: an invalid (NULL) column is
// nil (org-scoped), a valid one is the concrete uuid.
func fromPgUUIDOrNil(id pgtype.UUID) *uuid.UUID {
	if !id.Valid {
		return nil
	}
	value := uuid.UUID(id.Bytes)
	return &value
}

// compile-time: the pool satisfies the narrow interface Begin needs (documents the tx dependency).
var _ interface {
	Begin(ctx context.Context) (pgx.Tx, error)
} = (*pgxpool.Pool)(nil)
