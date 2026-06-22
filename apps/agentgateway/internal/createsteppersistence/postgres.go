// Package createsteppersistence is the REAL Postgres-backed gateway.CreateStepStore — the durable
// home for the DB-first create-saga's per-step ledger, behind the consumer-defined port with no
// gateway surface change. Each row is one saga step of one project: the idempotency + replay record
// the saga advances from PENDING to a terminal done/failed. The in-memory fake stays for devserve/unit;
// this is the production-shaped binding proven on a REAL postgres container.
//
// Storage shape: ONE table `project_create_steps` keyed by (project_id, step) — the natural
// idempotency key the saga reuses on replay — with status + idempotency_key as first-class columns
// (queried/uniqued) and the redaction-safe machine result as JSONB `output` (so a forward-compatible
// step shape never breaks the row). HNS-1: the package is `createsteppersistence` (never
// `store`/`repo`/`db`); the exported type may idiomatically be a Go type.
package createsteppersistence

import (
	"context"
	"strconv"
	"sync"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// PostgresCreateStepStore is a real Postgres-backed gateway.CreateStepStore. The caller owns Close.
type PostgresCreateStepStore struct {
	pool  *pgxpool.Pool
	clock gateway.Clock // stamps StartedAt on Record + FinishedAt on Advance; defaults to the wall clock.

	// The schema is ensured lazily on the first operation (and retried on a transient fault), so
	// NewPostgres does no network I/O — the composition root stays effectively pure.
	schemaMutex sync.Mutex
	schemaReady bool
}

// Option configures a PostgresCreateStepStore at construction. The only knob is the Clock the ledger
// stamps step times with — injected so a test is deterministic; defaulted to the wall clock so the
// production call site need not supply one.
type Option func(*PostgresCreateStepStore)

// WithClock injects the Clock the ledger stamps StartedAt/FinishedAt from. A nil clock is ignored.
func WithClock(clock gateway.Clock) Option {
	return func(s *PostgresCreateStepStore) {
		if clock != nil {
			s.clock = clock
		}
	}
}

// systemClock is the wall-clock default. The clock is read only inside an I/O method, so NewPostgres
// stays pure.
type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// NewPostgres builds a CreateStepStore over a pgx pool for dsn. The pool is lazy (it dials nothing
// until the first query) and the schema is ensured on first use, so this does no network I/O and a
// composition root may call it without a live database. A malformed DSN is a wrapped KindUnavailable.
func NewPostgres(ctx context.Context, dsn string, options ...Option) (*PostgresCreateStepStore, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "createsteppersistence: open postgres pool", err)
	}
	ledger := &PostgresCreateStepStore{pool: pool, clock: systemClock{}}
	for _, option := range options {
		option(ledger)
	}
	return ledger, nil
}

// Close releases the connection pool (idempotent).
func (s *PostgresCreateStepStore) Close() { s.pool.Close() }

// ensure creates the project_create_steps table on first use (and retries on a transient fault). The
// composite primary key (project_id, step) IS the idempotency key the saga replays against; status +
// idempotency_key are first-class columns; output is the redaction-safe JSONB machine result.
func (s *PostgresCreateStepStore) ensure(ctx context.Context) error {
	s.schemaMutex.Lock()
	defer s.schemaMutex.Unlock()
	if s.schemaReady {
		return nil
	}
	const ddl = `
CREATE TABLE IF NOT EXISTS project_create_steps (
	project_id      TEXT        NOT NULL,
	step            TEXT        NOT NULL,
	status          TEXT        NOT NULL,
	idempotency_key TEXT        NOT NULL,
	output          JSONB,
	started_at      TIMESTAMPTZ NOT NULL,
	finished_at     TIMESTAMPTZ,
	PRIMARY KEY (project_id, step)
)`
	if _, err := s.pool.Exec(ctx, ddl); err != nil {
		return errors.Wrap(errors.KindUnavailable, "createsteppersistence: ensure project_create_steps schema", err)
	}
	s.schemaReady = true
	return nil
}

// Record inserts a PENDING step keyed by (project_id, step) — idempotent on that key (ON CONFLICT DO
// NOTHING), so a replay of an already-recorded step returns the stored row unchanged (the first
// record's idempotency_key + started_at win). Status is forced to PENDING and started_at stamped from
// the injected Clock.
//
//nolint:gocritic // gateway.CreateStep is the copyable ledger record; the store persists its own copy.
func (s *PostgresCreateStepStore) Record(ctx context.Context, step gateway.CreateStep) (gateway.CreateStep, error) {
	if err := s.ensure(ctx); err != nil {
		return gateway.CreateStep{}, err
	}
	step.Status = gateway.CreateStepStatusPending
	step.StartedAt = s.clock.Now()
	step.FinishedAt = time.Time{}

	const insert = `
INSERT INTO project_create_steps (project_id, step, status, idempotency_key, output, started_at)
VALUES ($1,$2,$3,$4,$5,$6)
ON CONFLICT (project_id, step) DO NOTHING`
	if _, err := s.pool.Exec(
		ctx, insert,
		step.ProjectID, step.Step, step.Status, step.IdempotencyKey, jsonbOrNil(step.Output), step.StartedAt,
	); err != nil {
		return gateway.CreateStep{}, errors.Wrap(errors.KindUnavailable, "createsteppersistence: insert create step row", err)
	}
	// Return the row that now stands (the freshly-inserted one OR the prior winner on a conflict), so a
	// replay observes the first record's state — the idempotency contract.
	return s.Get(ctx, step.ProjectID, step.Step)
}

// Advance transitions a recorded step to a terminal status (done/failed) with its Output, stamping
// finished_at from the injected Clock. An off-contract or non-terminal status is a wrapped KindInvalid;
// a step never recorded is a wrapped KindNotFound.
func (s *PostgresCreateStepStore) Advance(ctx context.Context, projectID, step, status string, output gateway.RawJSON) (gateway.CreateStep, error) {
	if err := s.ensure(ctx); err != nil {
		return gateway.CreateStep{}, err
	}
	if !gateway.ValidCreateStepStatus(status) || status == gateway.CreateStepStatusPending {
		return gateway.CreateStep{}, errors.New(errors.KindInvalid,
			"createsteppersistence: advance create step to a non-terminal status "+strconv.Quote(status))
	}
	const update = `
UPDATE project_create_steps SET status=$3, output=$4, finished_at=$5
WHERE project_id=$1 AND step=$2`
	tag, err := s.pool.Exec(ctx, update, projectID, step, status, jsonbOrNil(output), s.clock.Now())
	if err != nil {
		return gateway.CreateStep{}, errors.Wrap(errors.KindUnavailable, "createsteppersistence: advance create step row", err)
	}
	if tag.RowsAffected() == 0 {
		return gateway.CreateStep{}, errors.New(errors.KindNotFound,
			"createsteppersistence: no create step "+strconv.Quote(step)+" for project "+projectID)
	}
	return s.Get(ctx, projectID, step)
}

// Get returns one step by (project_id, step) (a wrapped KindNotFound when absent).
func (s *PostgresCreateStepStore) Get(ctx context.Context, projectID, step string) (gateway.CreateStep, error) {
	if err := s.ensure(ctx); err != nil {
		return gateway.CreateStep{}, err
	}
	row := s.pool.QueryRow(ctx,
		`SELECT project_id, step, status, idempotency_key, output, started_at, finished_at
		 FROM project_create_steps WHERE project_id=$1 AND step=$2`, projectID, step)
	got, err := scanStep(row)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return gateway.CreateStep{}, errors.New(errors.KindNotFound,
				"createsteppersistence: no create step "+strconv.Quote(step)+" for project "+projectID)
		}
		return gateway.CreateStep{}, errors.Wrap(errors.KindUnavailable, "createsteppersistence: query create step row", err)
	}
	return got, nil
}

// List returns every step of one project in started_at order (the saga's replay/inspection read).
func (s *PostgresCreateStepStore) List(ctx context.Context, projectID string) ([]gateway.CreateStep, error) {
	if err := s.ensure(ctx); err != nil {
		return nil, err
	}
	rows, err := s.pool.Query(ctx,
		`SELECT project_id, step, status, idempotency_key, output, started_at, finished_at
		 FROM project_create_steps WHERE project_id=$1 ORDER BY started_at ASC, step ASC`, projectID)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "createsteppersistence: list create step rows", err)
	}
	defer rows.Close()

	steps := make([]gateway.CreateStep, 0)
	for rows.Next() {
		step, scanErr := scanStep(rows)
		if scanErr != nil {
			return nil, errors.Wrap(errors.KindUnavailable, "createsteppersistence: scan create step row", scanErr)
		}
		steps = append(steps, step)
	}
	if rowsErr := rows.Err(); rowsErr != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "createsteppersistence: iterate create step rows", rowsErr)
	}
	return steps, nil
}

// rowScanner is the narrow read seam pgx.Row and pgx.Rows both satisfy, so scanStep serves Get (one
// row) and List (many) without duplicating the column order.
type rowScanner interface {
	Scan(destinations ...any) error
}

// scanStep reads one project_create_steps row into a CreateStep. A NULL finished_at maps to the zero
// time (the omitempty wire tells a step still in flight); a NULL output maps to a nil RawJSON.
func scanStep(row rowScanner) (gateway.CreateStep, error) {
	var (
		step       gateway.CreateStep
		output     []byte
		finishedAt *time.Time
	)
	if err := row.Scan(&step.ProjectID, &step.Step, &step.Status, &step.IdempotencyKey, &output, &step.StartedAt, &finishedAt); err != nil {
		//nolint:wrapcheck // the caller (Get) inspects pgx.ErrNoRows on the RAW error to map a missing row to KindNotFound, then wraps; classifying/wrapping here would mask that decision.
		return gateway.CreateStep{}, err
	}
	if len(output) > 0 {
		step.Output = output
	}
	if finishedAt != nil {
		step.FinishedAt = *finishedAt
	}
	return step, nil
}

// jsonbOrNil renders a RawJSON for a JSONB column: a present document is passed through verbatim; an
// empty one becomes a SQL NULL (not the JSON literal null), so an unwritten output column is NULL and
// scanStep maps it back to a nil RawJSON.
func jsonbOrNil(raw gateway.RawJSON) any {
	if len(raw) == 0 {
		return nil
	}
	return []byte(raw)
}

// compile-time assertion: *PostgresCreateStepStore satisfies the gateway.CreateStepStore port.
var _ gateway.CreateStepStore = (*PostgresCreateStepStore)(nil)
