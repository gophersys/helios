-- platformgateway schema (ADR-0023: sqlc over pgx). This is the DDL sqlc type-checks queries
-- against; it is the SAME shape the migrations in ../migrations apply to a real database. Keep this
-- file and the migration set in lockstep (the authoring rule 20-schema-and-migrations enforces it).
--
-- `users` is the first domain table of Eden's platform API (the backend grows piece by piece). A
-- user is an account that owns work in Eden; exactly one row is the DEFAULT user (the IOTEA-style
-- startup seed plants it), which the pre-identity login bootstrap reads so the basic login lands on
-- a real, persisted identity.

CREATE TABLE IF NOT EXISTS users (
    -- id is the server-minted primary key (uuid). The seed supplies it explicitly (the database does
    -- not default it), so the default user's id is stable across restarts.
    id          uuid        PRIMARY KEY,
    -- email is the unique login handle; NOT NULL + UNIQUE so a user is addressable by it and the
    -- idempotent seed keys its ON CONFLICT on it.
    email       text        NOT NULL UNIQUE,
    -- name is the user's display name (shown in the dashboard's profile card).
    name        text        NOT NULL,
    -- is_default marks the single default user the login bootstrap returns. The partial unique index
    -- below allows AT MOST one row with is_default = true, so "the default user" is unambiguous.
    is_default  boolean     NOT NULL DEFAULT false,
    -- created_at / updated_at are the audit-column mixin every persisted row carries. created_at is
    -- stamped once at insert and never moves; updated_at is bumped on every mutation.
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- At most one default user: a partial unique index over the constant `true` predicate rejects a
-- second is_default row at the database, so the default identity is single-valued by construction.
CREATE UNIQUE INDEX IF NOT EXISTS users_single_default ON users (is_default) WHERE is_default;
