// Package auditpersistence is the REAL Postgres-backed gateway.AuditStore — the durable, append-only
// home for a project's audit trail, behind the consumer-defined port with no gateway surface change.
// Each row is one immutable event: at occurred_at, an action happened to a project, optionally by an
// actor, with a redaction-safe JSONB detail. The in-memory fake stays for devserve/unit; this is the
// production-shaped binding proven on a REAL postgres container.
//
// Storage shape: ONE table `audit_events` with a BIGSERIAL `seq` (the monotonic order + cursor key),
// project_id/action/actor as first-class columns (queried/scoped), occurred_at as TIMESTAMPTZ, and the
// structured detail as JSONB (so a forward-compatible detail shape never breaks the row). There is no
// UPDATE and no DELETE path — the trail is immutable by construction. HNS-1: the package is
// `auditpersistence` (never `store`/`repo`/`db`); the exported type may idiomatically be a Go type.
package auditpersistence

import (
	"context"
	"strconv"
	"sync"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// PostgresAuditStore is a real Postgres-backed gateway.AuditStore. The caller owns Close.
type PostgresAuditStore struct {
	pool *pgxpool.Pool

	// The schema is ensured lazily on the first operation (and retried on a transient fault), so
	// NewPostgres does no network I/O — the composition root stays effectively pure.
	schemaMutex sync.Mutex
	schemaReady bool
}

// NewPostgres builds an AuditStore over a pgx pool for dsn. The pool is lazy (it dials nothing until
// the first query) and the schema is ensured on first use, so this does no network I/O and a
// composition root may call it without a live database. A malformed DSN is a wrapped KindUnavailable.
func NewPostgres(ctx context.Context, dsn string) (*PostgresAuditStore, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "auditpersistence: open postgres pool", err)
	}
	return &PostgresAuditStore{pool: pool}, nil
}

// Close releases the connection pool (idempotent).
func (s *PostgresAuditStore) Close() { s.pool.Close() }

// ensure creates the audit_events table on first use (and retries on a transient fault). `seq`
// (BIGSERIAL) carries the newest-first order + the opaque pagination cursor; the `(project_id, seq)`
// index serves the per-project scoped page.
func (s *PostgresAuditStore) ensure(ctx context.Context) error {
	s.schemaMutex.Lock()
	defer s.schemaMutex.Unlock()
	if s.schemaReady {
		return nil
	}
	const ddl = `
CREATE TABLE IF NOT EXISTS audit_events (
	seq         BIGSERIAL PRIMARY KEY,
	project_id  TEXT        NOT NULL,
	action      TEXT        NOT NULL,
	actor       TEXT        NOT NULL DEFAULT '',
	detail      JSONB,
	occurred_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_events_project_seq ON audit_events (project_id, seq DESC)`
	if _, err := s.pool.Exec(ctx, ddl); err != nil {
		return errors.Wrap(errors.KindUnavailable, "auditpersistence: ensure audit_events schema", err)
	}
	s.schemaReady = true
	return nil
}

// Append inserts one event, letting the database assign seq (RETURNING it), and returns the stored
// copy with seq populated. occurred_at is taken as the caller stamped it (the gateway's Clock). There
// is no upsert and no delete — the trail is immutable.
//
//nolint:gocritic // gateway.AuditEvent is the copyable record; the store persists its own copy.
func (s *PostgresAuditStore) Append(ctx context.Context, event gateway.AuditEvent) (gateway.AuditEvent, error) {
	if err := s.ensure(ctx); err != nil {
		return gateway.AuditEvent{}, err
	}
	const insert = `
INSERT INTO audit_events (project_id, action, actor, detail, occurred_at)
VALUES ($1,$2,$3,$4,$5) RETURNING seq`
	if err := s.pool.QueryRow(
		ctx, insert,
		event.ProjectID, event.Action, event.Actor, jsonbOrNil(event.Detail), event.OccurredAt,
	).Scan(&event.Seq); err != nil {
		return gateway.AuditEvent{}, errors.Wrap(errors.KindUnavailable, "auditpersistence: insert audit event row", err)
	}
	return event, nil
}

// List returns the newest page of events (ORDER BY seq DESC), scoped to filter.ProjectID when set,
// bounded by filter.Limit, with the opaque Next cursor (the last kept row's seq) set when more rows
// remain. A cursor scopes the page to events older than it (seq < cursor) — the SAME cursor semantics
// as the project store.
//
//nolint:gocritic // gateway.AuditFilter is the frozen, copyable port input.
func (s *PostgresAuditStore) List(ctx context.Context, filter gateway.AuditFilter) (gateway.AuditPage, error) {
	if err := s.ensure(ctx); err != nil {
		return gateway.AuditPage{}, err
	}
	limit := filter.Limit
	if limit <= 0 {
		limit = defaultPageSize
	}

	// Build the WHERE incrementally: an optional project scope, an optional cursor. Fetch limit+1 to
	// detect a further page (the same probe-row technique the project store uses).
	clauses := make([]string, 0, 2)
	args := make([]any, 0, 3)
	if filter.ProjectID != "" {
		args = append(args, filter.ProjectID)
		clauses = append(clauses, "project_id=$"+strconv.Itoa(len(args)))
	}
	if cursor, ok := parseCursor(filter.Cursor); ok {
		args = append(args, cursor)
		clauses = append(clauses, "seq<$"+strconv.Itoa(len(args)))
	}
	where := ""
	if len(clauses) > 0 {
		where = " WHERE " + clauses[0]
		for _, clause := range clauses[1:] {
			where += " AND " + clause
		}
	}
	args = append(args, limit+1)
	query := "SELECT seq, project_id, action, actor, detail, occurred_at FROM audit_events" +
		where + " ORDER BY seq DESC LIMIT $" + strconv.Itoa(len(args))

	rows, err := s.pool.Query(ctx, query, args...)
	if err != nil {
		return gateway.AuditPage{}, errors.Wrap(errors.KindUnavailable, "auditpersistence: list audit event rows", err)
	}
	defer rows.Close()

	events := make([]gateway.AuditEvent, 0, limit+1)
	for rows.Next() {
		event, scanErr := scanEvent(rows)
		if scanErr != nil {
			return gateway.AuditPage{}, errors.Wrap(errors.KindUnavailable, "auditpersistence: scan audit event row", scanErr)
		}
		events = append(events, event)
	}
	if rowsErr := rows.Err(); rowsErr != nil {
		return gateway.AuditPage{}, errors.Wrap(errors.KindUnavailable, "auditpersistence: iterate audit event rows", rowsErr)
	}

	page := gateway.AuditPage{Events: events}
	if len(events) > limit {
		page.Events = events[:limit]
		page.Next = strconv.FormatInt(events[limit-1].Seq, 10)
	}
	return page, nil
}

// defaultPageSize bounds a list when the caller passes no limit.
const defaultPageSize = 100

// scanEvent reads one audit_events row into an AuditEvent. A NULL detail maps to a nil RawJSON.
func scanEvent(rows interface{ Scan(...any) error }) (gateway.AuditEvent, error) {
	var (
		event  gateway.AuditEvent
		detail []byte
	)
	if err := rows.Scan(&event.Seq, &event.ProjectID, &event.Action, &event.Actor, &detail, &event.OccurredAt); err != nil {
		//nolint:wrapcheck // the sole caller (List) wraps this scan error with the store's KindUnavailable context.
		return gateway.AuditEvent{}, err
	}
	if len(detail) > 0 {
		event.Detail = detail
	}
	return event, nil
}

// parseCursor decodes an opaque list cursor (a seq boundary). A blank or malformed cursor yields the
// first page (ok=false) rather than an error — a stale cursor degrades to "from the top", never a 500.
func parseCursor(cursor string) (int64, bool) {
	if cursor == "" {
		return 0, false
	}
	value, err := strconv.ParseInt(cursor, 10, 64)
	if err != nil || value <= 0 {
		return 0, false
	}
	return value, true
}

// jsonbOrNil renders a RawJSON for a JSONB column: a present document is passed through verbatim; an
// empty one becomes a SQL NULL, so an event with no detail stores NULL and scanEvent maps it back to a
// nil RawJSON.
func jsonbOrNil(raw gateway.RawJSON) any {
	if len(raw) == 0 {
		return nil
	}
	return []byte(raw)
}

// compile-time assertion: *PostgresAuditStore satisfies the gateway.AuditStore port.
var _ gateway.AuditStore = (*PostgresAuditStore)(nil)
