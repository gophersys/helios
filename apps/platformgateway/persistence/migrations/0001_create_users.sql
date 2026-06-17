-- 0001_create_users — the first migration (goose-style up/down). Migrations APPLY the schema to a
-- real database; the embedded startup migrate runner (persistence/migrate.go) runs the +goose Up
-- section on every boot (IOTEA-style: idempotent, CREATE ... IF NOT EXISTS), and the integration lane
-- runs the SAME section against a real postgres. schema/schema.sql is the SAME shape sqlc type-checks
-- against — keep them in lockstep.

-- +goose Up
CREATE TABLE IF NOT EXISTS users (
    id          uuid        PRIMARY KEY,
    email       text        NOT NULL UNIQUE,
    name        text        NOT NULL,
    is_default  boolean     NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS users_single_default ON users (is_default) WHERE is_default;

-- +goose Down
DROP TABLE users;
