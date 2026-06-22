-- schema.sql — the orchestrator.DesiredStore Postgres schema (production).
--
-- ONE table holds the durable desired-state record. The scalar reconcile/List filter keys
-- are promoted to columns (so List is an indexed SQL query, never an in-memory scan) and
-- the whole orchestrator.Agent rides a forward-compatible JSONB `record` (so a new Agent
-- field never breaks an existing row). `desired` and `status` are SEPARATE smallints — the
-- intent the reconcile loop drives toward vs the last-observed actual — so a SQL reader sees
-- the diff a reconcile pass closes.
--
-- The store applies this DDL idempotently at New (CREATE ... IF NOT EXISTS). It is checked
-- in as the canonical reference schema and for an out-of-band migration tool.

CREATE TABLE IF NOT EXISTS agents (
    -- Identity. The id is the globally-unique, project-namespaced handle (agent-<project>-<n>,
    -- minted by postgresstore.MintAgentID) — the cross-project-collision fix. It is the PK, so
    -- a duplicate across projects is structurally impossible.
    id               TEXT        PRIMARY KEY,

    -- Tenancy (07 §6) — the admission + List scope. org_id/project_id mirror Agent.Tenant.
    org_id           UUID        NOT NULL,
    project_id       UUID        NOT NULL,

    -- The desired template pin (immutable). Promoted so a List by template is an index hit.
    template_name    TEXT        NOT NULL,
    template_version TEXT        NOT NULL,

    -- The engine Run this session serves ("" / NULL for a bare chat session).
    run_id           TEXT        NOT NULL DEFAULT '',

    -- desired = the terminal intent the loop drives toward (orchestrator.Desired);
    -- status  = the last-observed actual lifecycle (orchestrator.Status) — SEPARATE, never merged.
    desired          SMALLINT    NOT NULL,
    status           SMALLINT    NOT NULL,
    -- terminal is the materialized Status.Terminal() predicate, so the OnlyActive filter is a
    -- column test (terminal = false) rather than an IN-list of every non-terminal status.
    terminal         BOOLEAN     NOT NULL,

    -- The cluster the workspace is provisioned on (ADR-0012); "" == the default cluster.
    cluster_id       TEXT        NOT NULL DEFAULT '',

    -- Opaque, loggable refs — NEVER live handles, NEVER secrets. workspace_handle is the
    -- workspaceprovider.Handle canonical string (re-parsed on read); session_ref is the opaque
    -- agentsession SessionRef a consumer resolves through agentsession to tail Events.
    workspace_handle TEXT        NOT NULL DEFAULT '',
    session_ref      TEXT        NOT NULL DEFAULT '',

    -- ledger = the last-observed agentsession.TokenLedger aggregate (FinOps/budget input);
    -- limits = the effective orchestrator.Limits. Both are structured values stored as JSONB.
    ledger           JSONB       NOT NULL DEFAULT '{}'::jsonb,
    limits           JSONB       NOT NULL DEFAULT '{}'::jsonb,

    -- Audit identity of the spawner/stopper (07 §7); never a secret.
    created_by       TEXT        NOT NULL DEFAULT '',

    created_at       TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL,

    -- The last transition detail (a REDACTED reason on a fault; never a credential).
    detail           TEXT        NOT NULL DEFAULT '',

    -- The whole orchestrator.Agent as a forward-compatible record. A field added to Agent
    -- round-trips here without a schema change; the promoted columns mirror it for filtering.
    record           JSONB       NOT NULL,

    -- seq gives List a stable, deterministic insertion order for the offset cursor — the SAME
    -- ordering the in-memory store's insertion-order List asserts in the conformance suite.
    seq              BIGSERIAL
);

-- project_id is the hot List/admission filter key — index it (the brief's INDEXED column).
CREATE INDEX IF NOT EXISTS agents_project_id_idx ON agents (project_id);

-- The running-set view (List Tenant + OnlyActive) is the dashboard's hot read; a composite
-- partial index over the live agents of a project serves it directly.
CREATE INDEX IF NOT EXISTS agents_active_by_project_idx ON agents (project_id, seq) WHERE terminal = FALSE;
