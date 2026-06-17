-- 0002_create_rbac — the IOTEA-style multi-tenant RBAC foundation (goose-style up/down). It APPLIES
-- the RBAC tables to a real database; the embedded startup migrate runner (persistence/migrate.go)
-- runs the +goose Up section on every boot (idempotent, CREATE ... IF NOT EXISTS), and the
-- integration lane runs the SAME section against a real postgres. schema/schema.sql is the SAME shape
-- sqlc type-checks against — keep them in lockstep.
--
-- The model is User → OrganizationMember (role + a PermissionSet) → Organization (IOTEA RBAC, the
-- prior art in MateoSegura/IOTEA-archive). Permissions are "namespace:action" strings ("*" = all);
-- the admin role bypasses checks. This migration plants the SCHEMA only — the composition root seeds
-- the default organization + admin permission set + admin membership after Migrate (data is separate
-- from schema, the same split as the default-user seed).

-- +goose Up
CREATE TABLE IF NOT EXISTS organizations (
    id          uuid        PRIMARY KEY,
    name        text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS permission_sets (
    id              uuid        PRIMARY KEY,
    organization_id uuid        NOT NULL REFERENCES organizations (id),
    name            text        NOT NULL,
    permissions     text[]      NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_members (
    id                uuid        PRIMARY KEY,
    organization_id   uuid        NOT NULL REFERENCES organizations (id),
    user_id           uuid        NOT NULL REFERENCES users (id),
    role              text        NOT NULL DEFAULT 'member',
    permission_set_id uuid        NOT NULL REFERENCES permission_sets (id),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, user_id)
);

-- +goose Down
DROP TABLE organization_members;
DROP TABLE permission_sets;
DROP TABLE organizations;
