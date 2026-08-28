-- 0001_create_resource — the first migration (goose-style up/down). Migrations APPLY the schema to a
-- real database (the integration lane runs them against the REAL postgres before exercising the
-- queries); schema/schema.sql is the SAME shape sqlc type-checks against. Keep them in lockstep.
--
-- SKELETON: the worked `resource` table with the audit-column mixin (created_at/updated_at). A
-- generated app adds a numbered migration per schema change (never edits a shipped one) and pairs it
-- with the schema.sql edit.

-- +goose Up
CREATE TABLE resource (
    id          uuid        PRIMARY KEY,
    name        text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- +goose Down
DROP TABLE resource;
