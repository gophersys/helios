//go:build integration || load

package orchestratortest

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// PostgresStore is a REAL Postgres-backed orchestrator.DesiredStore — the ONE multi-node
// swap (contract §6): desired-state survives a node recycle, so Resume/re-adopt works after
// a control-plane restart, behind the EXISTING DesiredStore port with NO orchestrator
// surface change. The Agent record (a plain serializable value holding only opaque refs —
// the Workspace Handle string + the opaque SessionRef, never a live handle and never a
// secret) serializes to one row; a stateless second orchestrator instance reads the same
// rows and reconciles the same world. The in-memory DesiredStore stays for dev/unit; this is
// the production-shaped binding proven on a REAL postgres container.
//
// Storage shape: ONE table `agents` with the scalar reconcile-keys promoted to columns (so
// List's filter/pagination is a real SQL query, not an in-memory scan) plus the full record
// as JSONB (so a forward-compatible field never breaks the row). The reconcile loop is the
// only writer of actual-status; the Manager verbs write desired-intent — both through Put.
type PostgresStore struct {
	pool *pgxpool.Pool
}

// NewPostgresStore connects to dsn, ensures the schema, and returns a real DesiredStore. The
// caller owns Close (registered on t.Cleanup by the harness). It is the durable binding the
// multi-node orchestrator runs against.
func NewPostgresStore(ctx context.Context, dsn string) (*PostgresStore, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "orchestratortest: connect postgres", err)
	}
	store := &PostgresStore{pool: pool}
	if err := store.ensureSchema(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return store, nil
}

// Close releases the connection pool (idempotent; a second Close is a no-op on a closed
// pool).
func (s *PostgresStore) Close() { s.pool.Close() }

// ensureSchema creates the agents table if absent. The promoted columns carry exactly the
// reconcile/List filter keys; the JSONB carries the whole record for forward-compatibility.
func (s *PostgresStore) ensureSchema(ctx context.Context) error {
	const ddl = `
CREATE TABLE IF NOT EXISTS agents (
	id            TEXT PRIMARY KEY,
	organization  TEXT NOT NULL,
	project       TEXT NOT NULL,
	template_name TEXT NOT NULL,
	template_ver  TEXT NOT NULL,
	status        SMALLINT NOT NULL,
	terminal      BOOLEAN NOT NULL,
	seq           BIGSERIAL,
	record        JSONB NOT NULL
)`
	if _, err := s.pool.Exec(ctx, ddl); err != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestratortest: ensure agents schema", err)
	}
	return nil
}

// Put upserts the Agent record. The promoted columns mirror the JSONB so a SQL filter never
// drifts from the record. Idempotent on ID (the level-based reconcile contract).
//
//nolint:gocritic // Agent is the contract's copyable serializable record; the store persists its own copy.
func (s *PostgresStore) Put(ctx context.Context, agent orchestrator.Agent) error {
	blob, err := json.Marshal(toRow(&agent))
	if err != nil {
		return errors.Wrap(errors.KindInternal, "orchestratortest: marshal agent record", err)
	}
	const upsert = `
INSERT INTO agents (id, organization, project, template_name, template_ver, status, terminal, record)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
ON CONFLICT (id) DO UPDATE SET
	organization=$2, project=$3, template_name=$4, template_ver=$5,
	status=$6, terminal=$7, record=$8`
	_, err = s.pool.Exec(
		ctx, upsert,
		string(agent.ID), agent.Tenant.OrganizationID, agent.Tenant.ProjectID,
		agent.Template.Name, agent.Template.Version,
		int16(agent.Status), agent.Status.Terminal(), blob,
	)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestratortest: put agent row", err)
	}
	return nil
}

// Get returns one Agent record (a wrapped NotFoundError if absent).
func (s *PostgresStore) Get(ctx context.Context, id orchestrator.AgentID) (orchestrator.Agent, error) {
	var blob []byte
	err := s.pool.QueryRow(ctx, `SELECT record FROM agents WHERE id=$1`, string(id)).Scan(&blob)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return orchestrator.Agent{}, errors.Wrap(errors.KindNotFound, "orchestratortest: get agent row",
				&orchestrator.NotFoundError{ID: id})
		}
		return orchestrator.Agent{}, errors.Wrap(errors.KindUnavailable, "orchestratortest: query agent row", err)
	}
	return fromBlob(blob)
}

// List returns the records matching filter, in deterministic insertion (seq) order, with the
// same Cursor/Limit pagination as the in-memory store (the contract the suite asserts). The
// tenant/template/status/active filters are real SQL predicates so the multi-node store never
// scans the whole table.
//
//nolint:gocritic // contract §3: DesiredStore.List takes the Filter by value (the frozen port surface).
func (s *PostgresStore) List(ctx context.Context, filter orchestrator.Filter) (orchestrator.Page, error) {
	where, args := buildWhere(&filter)
	query := "SELECT id, record FROM agents" + where + " ORDER BY seq ASC"
	rows, err := s.pool.Query(ctx, query, args...)
	if err != nil {
		return orchestrator.Page{}, errors.Wrap(errors.KindUnavailable, "orchestratortest: list agent rows", err)
	}
	defer rows.Close()

	matched := make([]orchestrator.Agent, 0)
	for rows.Next() {
		var id string
		var blob []byte
		if scanErr := rows.Scan(&id, &blob); scanErr != nil {
			return orchestrator.Page{}, errors.Wrap(errors.KindUnavailable, "orchestratortest: scan agent row", scanErr)
		}
		agent, decodeErr := fromBlob(blob)
		if decodeErr != nil {
			return orchestrator.Page{}, decodeErr
		}
		matched = append(matched, agent)
	}
	if rowsErr := rows.Err(); rowsErr != nil {
		return orchestrator.Page{}, errors.Wrap(errors.KindUnavailable, "orchestratortest: iterate agent rows", rowsErr)
	}
	return paginate(matched, &filter)
}

// buildWhere renders the SQL WHERE clause + positional args for a Filter. It mirrors the
// in-memory matchesFilter exactly (tenant, template name/version, OnlyActive, statuses) so
// the two bindings are behaviorally identical — the closure the conformance suite demands.
//
//nolint:nonamedreturns // the named results document the (whereClause, positionalArgs) pair the caller splices into the query.
func buildWhere(filter *orchestrator.Filter) (whereClause string, positionalArgs []any) {
	var (
		clauses []string
		args    []any
	)
	add := func(clause string, value any) {
		args = append(args, value)
		clauses = append(clauses, fmt.Sprintf(clause, len(args)))
	}
	if !filter.Tenant.IsZero() {
		add("organization=$%d", filter.Tenant.OrganizationID)
		add("project=$%d", filter.Tenant.ProjectID)
	}
	if filter.Template.Name != "" {
		add("template_name=$%d", filter.Template.Name)
	}
	if filter.Template.Version != "" {
		add("template_ver=$%d", filter.Template.Version)
	}
	if filter.OnlyActive {
		clauses = append(clauses, "terminal=false")
	}
	if len(filter.Statuses) > 0 {
		codes := make([]int16, len(filter.Statuses))
		for i, st := range filter.Statuses {
			codes[i] = int16(st)
		}
		add("status = ANY($%d)", codes)
	}
	if len(clauses) == 0 {
		return "", nil
	}
	out := " WHERE "
	for i, c := range clauses {
		if i > 0 {
			out += " AND "
		}
		out += c
	}
	return out, args
}

// agentRow is the JSON-serializable projection of an Agent the store persists in the JSONB
// column. It carries ONLY plain values and opaque refs (the Workspace Handle as its loggable
// string, the opaque SessionRef) — never a live handle, never a secret — so the record
// round-trips through a postgres row unchanged (contract §6).
type agentRow struct {
	ID            string                   `json:"id"`
	Organization  string                   `json:"organization"`
	Project       string                   `json:"project"`
	TemplateName  string                   `json:"templateName"`
	TemplateVer   string                   `json:"templateVer"`
	RunID         string                   `json:"runId"`
	Desired       uint8                    `json:"desired"`
	Status        uint8                    `json:"status"`
	Limits        orchestrator.Limits      `json:"limits"`
	ClusterID     string                   `json:"clusterId"`
	WorkspaceRaw  string                   `json:"workspace"` // the opaque, loggable Handle string (re-parsed on read)
	Session       string                   `json:"session"`
	Ledger        agentsession.TokenLedger `json:"ledger"`
	By            string                   `json:"by"`
	CreatedAtUnix int64                    `json:"createdAt"`
	UpdatedAtUnix int64                    `json:"updatedAt"`
	Detail        string                   `json:"detail"`
}

// toRow projects an Agent onto its serializable row form (the Handle flattens to its opaque
// string; everything else is already a plain value).
func toRow(agent *orchestrator.Agent) agentRow {
	return agentRow{
		ID:            string(agent.ID),
		Organization:  agent.Tenant.OrganizationID,
		Project:       agent.Tenant.ProjectID,
		TemplateName:  agent.Template.Name,
		TemplateVer:   agent.Template.Version,
		RunID:         agent.RunID,
		Desired:       uint8(agent.Desired),
		Status:        uint8(agent.Status),
		Limits:        agent.Limits,
		ClusterID:     agent.Cluster.ID,
		WorkspaceRaw:  agent.Workspace.String(),
		Session:       string(agent.Session),
		Ledger:        agent.Ledger,
		By:            agent.By,
		CreatedAtUnix: agent.CreatedAt.UnixNano(),
		UpdatedAtUnix: agent.UpdatedAt.UnixNano(),
		Detail:        agent.Detail,
	}
}

// fromBlob reconstructs an Agent from its JSONB row, re-parsing the opaque Workspace Handle
// string (a zero string round-trips to the zero Handle — a not-yet-provisioned agent).
func fromBlob(blob []byte) (orchestrator.Agent, error) {
	var row agentRow
	if err := json.Unmarshal(blob, &row); err != nil {
		return orchestrator.Agent{}, errors.Wrap(errors.KindInternal, "orchestratortest: unmarshal agent record", err)
	}
	handle, err := parseHandle(row.WorkspaceRaw)
	if err != nil {
		return orchestrator.Agent{}, err
	}
	return orchestrator.Agent{
		ID:        orchestrator.AgentID(row.ID),
		Tenant:    orchestrator.Tenancy{OrganizationID: row.Organization, ProjectID: row.Project},
		Template:  orchestrator.TemplateRef{Name: row.TemplateName, Version: row.TemplateVer},
		RunID:     row.RunID,
		Desired:   orchestrator.Desired(row.Desired),
		Status:    orchestrator.Status(row.Status),
		Limits:    row.Limits,
		Cluster:   orchestrator.ClusterRef{ID: row.ClusterID},
		Workspace: handle,
		Session:   orchestrator.SessionRef(row.Session),
		Ledger:    row.Ledger,
		By:        row.By,
		CreatedAt: unixOrZero(row.CreatedAtUnix),
		UpdatedAt: unixOrZero(row.UpdatedAtUnix),
		Detail:    row.Detail,
	}, nil
}

// parseHandle re-parses the opaque Handle string; the empty string round-trips to the zero
// Handle (a not-yet-provisioned or session-only agent).
func parseHandle(raw string) (workspaceprovider.Handle, error) {
	if raw == "" {
		return workspaceprovider.Handle{}, nil
	}
	handle, err := workspaceprovider.ParseHandle(raw)
	if err != nil {
		// A malformed persisted handle is corruption, not a not-found — surface it.
		return workspaceprovider.Handle{}, errors.Wrap(errors.KindInternal, "orchestratortest: re-parse persisted handle", err)
	}
	return handle, nil
}

// unixOrZero reconstructs a time from its UnixNano stamp, mapping the zero stamp back to the
// zero time (the not-yet-set timestamp on a fresh record).
func unixOrZero(nanos int64) time.Time {
	if nanos == 0 {
		return time.Time{}
	}
	return time.Unix(0, nanos).UTC()
}

// compile-time assertion: *PostgresStore is an orchestrator.DesiredStore.
var _ orchestrator.DesiredStore = (*PostgresStore)(nil)
