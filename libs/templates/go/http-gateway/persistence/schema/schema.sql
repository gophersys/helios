-- http-gateway schema (ADR-0023: sqlc over pgx). This is the DDL sqlc type-checks queries against;
-- it is the SAME shape the migrations in ../migrations apply to a real database. Keep this file and
-- the migration set in lockstep (the authoring rule 20-schema-and-migrations enforces it).
--
-- SKELETON: a single `resource` table is the worked example a generated app replaces/extends. It is
-- intentionally minimal — a name plus the audit-column mixin (created_at/updated_at) — not a domain
-- model. A generated app adds its own tables (each paired with a numbered migration) and replaces
-- this one.

CREATE TABLE IF NOT EXISTS resource (
    -- id is the server-minted primary key (uuid). The execute stage generates it; the database does
    -- not default it, so an insert is explicit and reproducible.
    id          uuid        PRIMARY KEY,
    -- name is the resource's human label; NOT NULL so a row always carries one.
    name        text        NOT NULL,
    -- created_at / updated_at are the audit-column mixin every persisted resource carries. created_at
    -- is stamped once at insert and never moves; updated_at is bumped on every mutation (the update
    -- query sets it to now()). Both default to now() so an insert that omits them is still well-formed.
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
