# Rule — Schema & migrations (sqlc over pgx)

> Injected at SessionStart (ADR-0023). The data layer is TYPED, not string-built. The home is
> `persistence/`.

## The two-file lockstep

A persisted change is ALWAYS two edits kept in lockstep:

1. **`persistence/schema/schema.sql`** — the DDL sqlc type-checks queries against (the desired
   shape).
2. **`persistence/migrations/NNNN_<name>.sql`** — a NEW numbered goose-style up/down migration that
   APPLIES that change to a real database.

The schema and the migration set must describe the SAME shape. The integration lane runs the
migrations against the REAL postgres, so a schema that the migrations cannot produce fails there.

## Queries are typed

- Add named queries to `persistence/schema/queries/*.sql` with the `-- name: X :one|:many|:exec`
  directive. sqlc emits one typed Go method per query into `persistence/generated/`.
- A route's **execute** stage calls the generated Querier through an injected port — NEVER
  string-built SQL, NEVER `fmt.Sprintf` into a query.
- After any schema/query edit: `bash ./ctl.sh generate` (or `bash persistence/ctl.sh generate`).

## Hard rules

- **Never edit a shipped migration.** A change is a NEW numbered migration; the applied history is
  append-only.
- **Never hand-edit `persistence/generated/`** — it is sqlc output (only `doc.go` is hand-written).
- **`persistence` is the package/dir name** — never `db`, `repo`, or `store` (HNS-1 rule 11).
- The data layer is proven against a REAL postgres in the integration lane (ADR-0016 §2: never
  mocked). A query that only passes against a mock is not done.
