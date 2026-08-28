# persistence — the sqlc/pgx data layer (codegen axis #1)

> Directory README + Nx codegen sub-project. The data layer is TYPED, not string-built (ADR-0023:
> sqlc over pgx). `bash ./ctl.sh generate` runs sqlc over `schema/` + the query `.sql` files and
> emits the typed Querier into `generated/`.

## Layout

| Path | Intent |
|---|---|
| `sqlc.yaml` | The sqlc configuration (engine=postgresql, sql_package=pgx/v5, out=generated). |
| `schema/schema.sql` | The DDL sqlc type-checks queries against (the same shape the migrations apply). |
| `schema/queries/*.sql` | The named queries (`-- name: X :one/:many/:exec`); sqlc emits one typed Go method each. |
| `migrations/NNNN_*.sql` | Numbered goose-style up/down migrations that APPLY the schema to a real database. |
| `generated/` | The sqlc OUTPUT (the Querier + row models). GENERATED — never hand-edited (only `doc.go` is hand-written, to keep the package compiling pre-generation). |

## The discipline

- A schema change is a NEW numbered migration paired with the `schema.sql` edit — never an edit to a
  shipped migration (authoring rule `20-schema-and-migrations`).
- The execute stage of a route calls the generated Querier through an injected port — never
  string-built SQL.
- The integration lane (`bash ../ctl.sh integration`) runs the migrations against the REAL postgres
  and exercises the queries — the data layer is proven against a real database, never mocked
  (ADR-0016 §2).

## Sub-project

This is its own Nx project (`http-gateway-template-persistence`) so the data layer regenerates
independently; the parent template's `generate` verb delegates here.
