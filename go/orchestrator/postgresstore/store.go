package postgresstore

import (
	"context"
	_ "embed"
	"encoding/json"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
)

// schemaDDL is the canonical table definition, embedded from schema.sql so the checked-in
// reference schema and the one EnsureSchema applies can never drift.
//
//go:embed schema.sql
var schemaDDL string

// Config is the immutable, fully-resolved configuration for a PostgresStore. It is empty today (the
// connection pool is an injected dependency, the schema name is fixed) and exists so the
// constructor spine New(configuration, dependencies) is uniform and a future knob (a schema
// namespace, a statement timeout) lands without a signature break.
type Config struct{}

// Deps is the injected record of ports a PostgresStore holds (the hexagon). The Pool is the
// pgx connection pool, owned and Closed by the COMPOSITION ROOT (not by the PostgresStore) — the PostgresStore
// borrows it for the orchestrator's lifetime, which is why New does not own teardown.
type Deps struct {
	// Pool is a ready pgx connection pool the PostgresStore issues queries against. Required.
	Pool *pgxpool.Pool
}

// PostgresStore is the production Postgres orchestrator.DesiredStore. Its zero value is unusable;
// construct it with New. It is safe for concurrent use (pgxpool is concurrency-safe and the
// PostgresStore holds no mutable state of its own). It binds the frozen 3-method DesiredStore port
// (Put/Get/List) and adds Delete as the reap/GC seam the Reaper drives (a method on the
// concrete type, NOT a widening of the port — accept-interface, return-concrete).
type PostgresStore struct {
	pool *pgxpool.Pool
}

// New constructs a PostgresStore from its configuration and dependencies. It is PURE: it validates the
// injected pool and returns the concrete *PostgresStore — no connection, no I/O, no schema application
// (that is EnsureSchema, called once at startup by the composition root). A nil Pool is a
// wrapped ConfigError (KindInvalid).
//
//nolint:gocritic // Config is the contract's immutable value input; New takes it by value (the constructor spine).
func New(_ Config, dependencies Deps) (*PostgresStore, error) {
	if dependencies.Pool == nil {
		return nil, errors.Wrap(errors.KindInvalid, "orchestrator/postgresstore: construct store",
			&orchestrator.ConfigError{Reason: "a pgx connection pool is required (Deps.Pool)"})
	}
	return &PostgresStore{pool: dependencies.Pool}, nil
}

// EnsureSchema applies the idempotent DDL (CREATE TABLE / INDEX IF NOT EXISTS), so a fresh
// database is usable and an existing one is unchanged. The composition root calls it ONCE at
// startup, OUT of the pure constructor. Idempotent: a second call is a no-op.
func (s *PostgresStore) EnsureSchema(ctx context.Context) error {
	if _, err := s.pool.Exec(ctx, schemaDDL); err != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestrator/postgresstore: ensure agents schema", err)
	}
	return nil
}

// Put records or REPLACES an Agent (the desired intent + last-observed actual). It is the sole
// write path: the reconcile loop writes actual-status and the Manager verbs write
// desired-intent, both through here. Idempotent on the id (the level-based reconcile contract:
// re-Putting the same record is a no-op-equivalent upsert).
//
// It REJECTS a non-project-namespaced id with a wrapped KindInvalid error — the cross-project
// collision fix enforced at the boundary: only an id minted by MintAgentID (agent-<project>-<n>)
// may enter the shared store, so a bare `agent-<n>` from the v0 single-node minter cannot
// clobber a peer project's row under the id-PK upsert.
//
//nolint:gocritic // Agent is the contract's copyable serializable record; the store persists its own copy by value.
func (s *PostgresStore) Put(ctx context.Context, agent orchestrator.Agent) error {
	if !isProjectNamespaced(agent.ID, agent.Tenant) {
		return errors.Wrap(errors.KindInvalid, "orchestrator/postgresstore: put agent",
			&orchestrator.InvalidRequestError{Reason: "agent id must be project-namespaced (mint via postgresstore.MintAgentID); got " + quoteID(agent.ID)})
	}
	columns, err := promote(agent)
	if err != nil {
		return err
	}
	const upsert = `
INSERT INTO agents (
    id, org_id, project_id, template_name, template_version, run_id,
    desired, status, terminal, cluster_id, workspace_handle, session_ref,
    ledger, limits, created_by, created_at, updated_at, detail, record
) VALUES (
    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19
)
ON CONFLICT (id) DO UPDATE SET
    org_id=$2, project_id=$3, template_name=$4, template_version=$5, run_id=$6,
    desired=$7, status=$8, terminal=$9, cluster_id=$10, workspace_handle=$11, session_ref=$12,
    ledger=$13, limits=$14, created_by=$15, created_at=$16, updated_at=$17, detail=$18, record=$19`
	_, err = s.pool.Exec(
		ctx, upsert,
		columns.id, columns.organizationID, columns.projectID, columns.templateName, columns.templateVersion, columns.runID,
		columns.desired, columns.status, columns.terminal, columns.clusterID, columns.workspaceHandle, columns.sessionRef,
		columns.ledgerJSON, columns.limitsJSON, columns.createdBy, columns.createdAt, columns.updatedAt, columns.detail, columns.recordJSON,
	)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestrator/postgresstore: upsert agent row", err)
	}
	return nil
}

// Get returns one Agent record, or a wrapped NotFoundError (KindNotFound) if absent.
func (s *PostgresStore) Get(ctx context.Context, id orchestrator.AgentID) (orchestrator.Agent, error) {
	var recordJSON []byte
	err := s.pool.QueryRow(ctx, `SELECT record FROM agents WHERE id=$1`, string(id)).Scan(&recordJSON)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return orchestrator.Agent{}, errors.Wrap(errors.KindNotFound, "orchestrator/postgresstore: get agent",
				&orchestrator.NotFoundError{ID: id})
		}
		return orchestrator.Agent{}, errors.Wrap(errors.KindUnavailable, "orchestrator/postgresstore: query agent row", err)
	}
	return decodeAgent(recordJSON)
}

// List returns the records matching filter in deterministic (seq) order, with the SAME
// Cursor/Limit pagination the in-memory store asserts. The tenant/template/status/active
// predicates are real SQL against the promoted columns, so the multi-node store never scans
// the whole table for a filtered running-set view.
//
//nolint:gocritic // contract §3: DesiredStore.List takes the Filter by value (the frozen port surface).
func (s *PostgresStore) List(ctx context.Context, filter orchestrator.Filter) (orchestrator.Page, error) {
	where, args := buildWhere(&filter)
	query := "SELECT record FROM agents" + where + " ORDER BY seq ASC"
	rows, err := s.pool.Query(ctx, query, args...)
	if err != nil {
		return orchestrator.Page{}, errors.Wrap(errors.KindUnavailable, "orchestrator/postgresstore: list agent rows", err)
	}
	defer rows.Close()

	matched := make([]orchestrator.Agent, 0)
	for rows.Next() {
		var recordJSON []byte
		if scanErr := rows.Scan(&recordJSON); scanErr != nil {
			return orchestrator.Page{}, errors.Wrap(errors.KindUnavailable, "orchestrator/postgresstore: scan agent row", scanErr)
		}
		agent, decodeErr := decodeAgent(recordJSON)
		if decodeErr != nil {
			return orchestrator.Page{}, decodeErr
		}
		matched = append(matched, agent)
	}
	if rowsErr := rows.Err(); rowsErr != nil {
		return orchestrator.Page{}, errors.Wrap(errors.KindUnavailable, "orchestrator/postgresstore: iterate agent rows", rowsErr)
	}
	return paginate(matched, &filter), nil
}

// promote projects an Agent onto its row columns + the marshaled JSONB record/ledger/limits.
//
//nolint:gocritic // Agent is the contract's copyable serializable record; promote takes its own copy by value.
func promote(agent orchestrator.Agent) (promotedColumns, error) {
	record := toRecord(agent)
	recordJSON, err := json.Marshal(record)
	if err != nil {
		return promotedColumns{}, errors.Wrap(errors.KindInternal, "orchestrator/postgresstore: marshal agent record", err)
	}
	ledgerJSON, err := json.Marshal(agent.Ledger)
	if err != nil {
		return promotedColumns{}, errors.Wrap(errors.KindInternal, "orchestrator/postgresstore: marshal agent ledger", err)
	}
	limitsJSON, err := json.Marshal(agent.Limits)
	if err != nil {
		return promotedColumns{}, errors.Wrap(errors.KindInternal, "orchestrator/postgresstore: marshal agent limits", err)
	}
	return promotedColumns{
		id:              string(agent.ID),
		organizationID:  agent.Tenant.OrganizationID,
		projectID:       agent.Tenant.ProjectID,
		templateName:    agent.Template.Name,
		templateVersion: agent.Template.Version,
		runID:           agent.RunID,
		desired:         int16(agent.Desired),
		status:          int16(agent.Status),
		terminal:        agent.Status.Terminal(),
		clusterID:       agent.Cluster.ID,
		workspaceHandle: agent.Workspace.String(),
		sessionRef:      string(agent.Session),
		ledgerJSON:      ledgerJSON,
		limitsJSON:      limitsJSON,
		createdBy:       agent.By,
		createdAt:       agent.CreatedAt.UTC(),
		updatedAt:       agent.UpdatedAt.UTC(),
		detail:          agent.Detail,
		recordJSON:      recordJSON,
	}, nil
}

// decodeAgent reconstructs an Agent from its persisted JSONB record.
func decodeAgent(recordJSON []byte) (orchestrator.Agent, error) {
	var record agentRecord
	if err := json.Unmarshal(recordJSON, &record); err != nil {
		return orchestrator.Agent{}, errors.Wrap(errors.KindInternal, "orchestrator/postgresstore: unmarshal agent record", err)
	}
	return fromRecord(&record)
}

// quoteID renders an id for an error message (loggable; the id carries no secret).
func quoteID(id orchestrator.AgentID) string {
	return "\"" + string(id) + "\""
}

// compile-time assertion: *PostgresStore is an orchestrator.DesiredStore (the frozen port it binds).
var _ orchestrator.DesiredStore = (*PostgresStore)(nil)
