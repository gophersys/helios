// Package projectpersistence is the REAL Postgres-backed gateway.ProjectStore — the durable home for
// the dashboard's Projects, behind the consumer-defined port with no gateway surface change. A
// Project (a plain serializable value: the idea, the redaction-safe ProductConfig, a status, the
// build session ref, timestamps — never a credential) serializes to one row; the dashboard lists the
// same rows across gateway replicas. The in-memory fake stays for devserve/unit; this is the
// production-shaped binding proven on a REAL postgres container.
//
// Storage shape: ONE table `projects` with the id promoted to the primary key and a BIGSERIAL `seq`
// for deterministic newest-first order + cursor pagination, plus the full Project as JSONB (so a
// forward-compatible field never breaks the row). The naming honors HNS-1: the package is
// `projectpersistence` (never `store`/`repo`/`db`); the exported type may idiomatically be a Go type.
package projectpersistence

import (
	"context"
	"encoding/json"
	"strconv"
	"sync"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// PostgresProjectStore is a real Postgres-backed gateway.ProjectStore. The caller owns Close.
type PostgresProjectStore struct {
	pool *pgxpool.Pool

	// The schema is ensured lazily, on the first operation, so NewPostgres does no network I/O (the
	// composition root stays effectively pure — pgxpool.New only parses the DSN). The mutex + flag
	// retries a transient ensure fault rather than caching it (a request racing postgres startup
	// does not poison the store forever, unlike a sync.Once).
	schemaMutex sync.Mutex
	schemaReady bool
}

// NewPostgres builds a ProjectStore over a pgx pool for dsn. The pool is lazy (it dials nothing until
// the first query), and the schema is ensured on first use — so this does no network I/O and a
// composition root may call it without a live database. A malformed DSN is a wrapped KindUnavailable.
func NewPostgres(ctx context.Context, dsn string) (*PostgresProjectStore, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "projectpersistence: open postgres pool", err)
	}
	return &PostgresProjectStore{pool: pool}, nil
}

// Close releases the connection pool (idempotent; a second Close is a no-op on a closed pool).
func (s *PostgresProjectStore) Close() { s.pool.Close() }

// ensure creates the projects table on first use (and retries on a transient fault). `seq`
// (BIGSERIAL) carries the newest-first order + the opaque pagination cursor; the JSONB `record`
// carries the whole Project.
func (s *PostgresProjectStore) ensure(ctx context.Context) error {
	s.schemaMutex.Lock()
	defer s.schemaMutex.Unlock()
	if s.schemaReady {
		return nil
	}
	const ddl = `
CREATE TABLE IF NOT EXISTS projects (
	id     TEXT PRIMARY KEY,
	seq    BIGSERIAL,
	record JSONB NOT NULL
)`
	if _, err := s.pool.Exec(ctx, ddl); err != nil {
		return errors.Wrap(errors.KindUnavailable, "projectpersistence: ensure projects schema", err)
	}
	s.schemaReady = true
	return nil
}

// Create persists a Project (id + timestamps already stamped by the handler) and returns the stored
// copy. Upsert-on-id so a retried create is idempotent.
//
//nolint:gocritic // gateway.Project is the copyable persisted record; the store persists its own copy.
func (s *PostgresProjectStore) Create(ctx context.Context, project gateway.Project) (gateway.Project, error) {
	if err := s.ensure(ctx); err != nil {
		return gateway.Project{}, err
	}
	blob, err := json.Marshal(project)
	if err != nil {
		return gateway.Project{}, errors.Wrap(errors.KindInternal, "projectpersistence: marshal project", err)
	}
	const upsert = `INSERT INTO projects (id, record) VALUES ($1,$2) ON CONFLICT (id) DO UPDATE SET record=$2`
	if _, err = s.pool.Exec(ctx, upsert, project.ID, blob); err != nil {
		return gateway.Project{}, errors.Wrap(errors.KindUnavailable, "projectpersistence: insert project row", err)
	}
	return project, nil
}

// Get returns one Project (a wrapped KindNotFound when absent).
func (s *PostgresProjectStore) Get(ctx context.Context, id string) (gateway.Project, error) {
	if err := s.ensure(ctx); err != nil {
		return gateway.Project{}, err
	}
	var blob []byte
	err := s.pool.QueryRow(ctx, `SELECT record FROM projects WHERE id=$1`, id).Scan(&blob)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return gateway.Project{}, errors.New(errors.KindNotFound, "projectpersistence: no project with id "+id)
		}
		return gateway.Project{}, errors.Wrap(errors.KindUnavailable, "projectpersistence: query project row", err)
	}
	return decode(blob)
}

// List returns the newest page of projects (ORDER BY seq DESC), bounded by filter.Limit, with the
// opaque Next cursor (the seq boundary) set when more rows remain. A cursor scopes the page to rows
// older than it (seq < cursor).
//
//nolint:gocritic // gateway.ProjectFilter is the frozen, copyable port input.
func (s *PostgresProjectStore) List(ctx context.Context, filter gateway.ProjectFilter) (gateway.ProjectPage, error) {
	if err := s.ensure(ctx); err != nil {
		return gateway.ProjectPage{}, err
	}
	limit := filter.Limit
	if limit <= 0 {
		limit = defaultPageSize
	}

	var (
		query string
		args  []any
	)
	if cursor, ok := parseCursor(filter.Cursor); ok {
		query = `SELECT seq, record FROM projects WHERE seq < $1 ORDER BY seq DESC LIMIT $2`
		args = []any{cursor, limit + 1}
	} else {
		query = `SELECT seq, record FROM projects ORDER BY seq DESC LIMIT $1`
		args = []any{limit + 1}
	}

	rows, err := s.pool.Query(ctx, query, args...)
	if err != nil {
		return gateway.ProjectPage{}, errors.Wrap(errors.KindUnavailable, "projectpersistence: list project rows", err)
	}
	defer rows.Close()

	// Fetch limit+1 to detect a further page; track each kept row's seq so the cursor is the seq of
	// the LAST row on THIS page (rows older than it form the next page).
	projects := make([]gateway.Project, 0, limit+1)
	seqs := make([]int64, 0, limit+1)
	for rows.Next() {
		var (
			seq  int64
			blob []byte
		)
		if scanErr := rows.Scan(&seq, &blob); scanErr != nil {
			return gateway.ProjectPage{}, errors.Wrap(errors.KindUnavailable, "projectpersistence: scan project row", scanErr)
		}
		project, decodeErr := decode(blob)
		if decodeErr != nil {
			return gateway.ProjectPage{}, decodeErr
		}
		projects = append(projects, project)
		seqs = append(seqs, seq)
	}
	if rowsErr := rows.Err(); rowsErr != nil {
		return gateway.ProjectPage{}, errors.Wrap(errors.KindUnavailable, "projectpersistence: iterate project rows", rowsErr)
	}

	// One extra row signals a further page: drop the probe row and surface the last KEPT row's seq.
	page := gateway.ProjectPage{Projects: projects}
	if len(projects) > limit {
		page.Projects = projects[:limit]
		page.Next = strconv.FormatInt(seqs[limit-1], 10)
	}
	return page, nil
}

// defaultPageSize bounds a list when the caller passes no limit (the handler normally clamps to the
// gateway's MaxPageSize; this is the store's own floor).
const defaultPageSize = 100

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

// decode reconstructs a Project from its JSONB row.
func decode(blob []byte) (gateway.Project, error) {
	var project gateway.Project
	if err := json.Unmarshal(blob, &project); err != nil {
		return gateway.Project{}, errors.Wrap(errors.KindInternal, "projectpersistence: unmarshal project record", err)
	}
	return project, nil
}

// compile-time assertion: *PostgresProjectStore satisfies the gateway.ProjectStore port.
var _ gateway.ProjectStore = (*PostgresProjectStore)(nil)
