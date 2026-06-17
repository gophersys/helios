// Package agentconfigpersistence is the REAL Postgres-backed gateway.AgentConfigStore — the durable
// home for the Settings → Agents per-agent-type user configuration, behind the consumer-defined port
// with no gateway surface change. Each configuration (a plain serializable value: the model, tool grants,
// sandbox posture — never a credential) is one row keyed by agent type. The in-memory fake stays for
// devserve/unit; this is the production-shaped binding proven on a REAL postgres container.
//
// Storage shape: ONE table `agent_configs` keyed by agent_type, with the whole configuration as JSONB (so a
// forward-compatible field never breaks the row). HNS-1: the package is `agentconfigpersistence`
// (never `store`/`repo`/`db`); the exported type may idiomatically be a Go type.
package agentconfigpersistence

import (
	"context"
	"encoding/json"
	"sync"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// PostgresAgentConfigStore is a real Postgres-backed gateway.AgentConfigStore. The caller owns Close.
type PostgresAgentConfigStore struct {
	pool *pgxpool.Pool

	// The schema is ensured lazily on the first operation (and retried on a transient fault), so
	// NewPostgres does no network I/O — the composition root stays effectively pure.
	schemaMutex sync.Mutex
	schemaReady bool
}

// NewPostgres builds an AgentConfigStore over a pgx pool for dsn. The pool is lazy (it dials nothing
// until the first query) and the schema is ensured on first use, so this does no network I/O and a
// composition root may call it without a live database. A malformed DSN is a wrapped KindUnavailable.
func NewPostgres(ctx context.Context, dsn string) (*PostgresAgentConfigStore, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "agentconfigpersistence: open postgres pool", err)
	}
	return &PostgresAgentConfigStore{pool: pool}, nil
}

// Close releases the connection pool (idempotent).
func (s *PostgresAgentConfigStore) Close() { s.pool.Close() }

// ensure creates the agent_configs table on first use (and retries on a transient fault).
func (s *PostgresAgentConfigStore) ensure(ctx context.Context) error {
	s.schemaMutex.Lock()
	defer s.schemaMutex.Unlock()
	if s.schemaReady {
		return nil
	}
	const ddl = `
CREATE TABLE IF NOT EXISTS agent_configs (
	agent_type TEXT PRIMARY KEY,
	record     JSONB NOT NULL
)`
	if _, err := s.pool.Exec(ctx, ddl); err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentconfigpersistence: ensure agent_configs schema", err)
	}
	s.schemaReady = true
	return nil
}

// Put upserts the configuration for its agent type and returns the stored copy.
//
//nolint:gocritic // gateway.AgentConfig is the copyable persisted record; the store persists its own copy.
func (s *PostgresAgentConfigStore) Put(ctx context.Context, configuration gateway.AgentConfig) (gateway.AgentConfig, error) {
	if err := s.ensure(ctx); err != nil {
		return gateway.AgentConfig{}, err
	}
	blob, err := json.Marshal(configuration)
	if err != nil {
		return gateway.AgentConfig{}, errors.Wrap(errors.KindInternal, "agentconfigpersistence: marshal agent configuration", err)
	}
	const upsert = `INSERT INTO agent_configs (agent_type, record) VALUES ($1,$2) ON CONFLICT (agent_type) DO UPDATE SET record=$2`
	if _, err = s.pool.Exec(ctx, upsert, configuration.AgentType, blob); err != nil {
		return gateway.AgentConfig{}, errors.Wrap(errors.KindUnavailable, "agentconfigpersistence: upsert agent configuration row", err)
	}
	return configuration, nil
}

// Get returns one configuration (a wrapped KindNotFound when absent).
func (s *PostgresAgentConfigStore) Get(ctx context.Context, agentType string) (gateway.AgentConfig, error) {
	if err := s.ensure(ctx); err != nil {
		return gateway.AgentConfig{}, err
	}
	var blob []byte
	err := s.pool.QueryRow(ctx, `SELECT record FROM agent_configs WHERE agent_type=$1`, agentType).Scan(&blob)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return gateway.AgentConfig{}, errors.New(errors.KindNotFound, "agentconfigpersistence: no configuration for agent type "+agentType)
		}
		return gateway.AgentConfig{}, errors.Wrap(errors.KindUnavailable, "agentconfigpersistence: query agent configuration row", err)
	}
	return decode(blob)
}

// List returns every saved configuration, ordered by agent type for a deterministic Settings render.
func (s *PostgresAgentConfigStore) List(ctx context.Context) ([]gateway.AgentConfig, error) {
	if err := s.ensure(ctx); err != nil {
		return nil, err
	}
	rows, err := s.pool.Query(ctx, `SELECT record FROM agent_configs ORDER BY agent_type ASC`)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "agentconfigpersistence: list agent configuration rows", err)
	}
	defer rows.Close()

	configs := make([]gateway.AgentConfig, 0)
	for rows.Next() {
		var blob []byte
		if scanErr := rows.Scan(&blob); scanErr != nil {
			return nil, errors.Wrap(errors.KindUnavailable, "agentconfigpersistence: scan agent configuration row", scanErr)
		}
		configuration, decodeErr := decode(blob)
		if decodeErr != nil {
			return nil, decodeErr
		}
		configs = append(configs, configuration)
	}
	if rowsErr := rows.Err(); rowsErr != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "agentconfigpersistence: iterate agent configuration rows", rowsErr)
	}
	return configs, nil
}

// decode reconstructs an AgentConfig from its JSONB row.
func decode(blob []byte) (gateway.AgentConfig, error) {
	var configuration gateway.AgentConfig
	if err := json.Unmarshal(blob, &configuration); err != nil {
		return gateway.AgentConfig{}, errors.Wrap(errors.KindInternal, "agentconfigpersistence: unmarshal agent configuration record", err)
	}
	return configuration, nil
}

// compile-time assertion: *PostgresAgentConfigStore satisfies the gateway.AgentConfigStore port.
var _ gateway.AgentConfigStore = (*PostgresAgentConfigStore)(nil)
