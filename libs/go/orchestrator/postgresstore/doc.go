// Package postgresstore is the PRODUCTION Postgres binding of orchestrator.DesiredStore
// — the durable record of WHAT SHOULD RUN, and the ONE adapter swap (contract §6) that
// carries the orchestrator from single-node to multi-node with NO change to its frozen
// port surface. The in-memory orchestratortest.DesiredStore stays the dev/unit double;
// THIS is the binding a real control plane runs against, proven on a real postgres.
//
// Module: github.com/gophersys/libs/go/orchestrator (this is a PACKAGE inside the existing
// orchestrator module, not a separate module). It promotes the shape the test-only
// orchestratortest.PostgresStore validated (one `agents` table, the reconcile/List filter
// keys promoted to indexed columns, the whole Agent as a forward-compatible JSONB record)
// into a production component with the constructor spine New(configuration, dependencies).
//
// WHY a JSONB record beside promoted columns: the orchestrator.Agent is a plain
// serializable value holding only OPAQUE refs (the workspaceprovider.Handle as its
// loggable string, the opaque SessionRef) — never a live handle, never a secret value
// (07 §2) — so it round-trips through one row unchanged, and a forward-compatible field
// added to Agent never breaks an existing row. The promoted columns (org_id, project_id,
// template, desired, status, ...) carry exactly the keys List's filter/pagination needs,
// so List is a real SQL query against an index, not an in-memory table scan — the property
// that makes the multi-node running-set view cheap.
//
// The reconcile loop is the only writer of actual-status; the Manager verbs write
// desired-intent — both arrive through Put. The store NEVER interprets a record: it
// persists desired (the intent the loop drives toward) and status (the last-observed
// actual) as SEPARATE columns so a SQL reader sees the diff the reconcile pass closes.
//
// Cross-project id collision (the fix this package owns): the v0 single-node minter stamps
// `agent-<n>` from a per-Pool counter, so two control planes (or two projects) sharing one
// store would both mint `agent-1` and the second Put would CLOBBER the first under an
// id-PK upsert. This package mints a globally-unique, project-namespaced, deterministic id
// — MintAgentID(tenant, sequence) → `agent-<projectID>-<sequence>` — and Put REJECTS a
// non-namespaced id with a typed KindInvalid error, so the collision is structurally
// impossible at the persistence boundary, not merely unlikely.
package postgresstore
