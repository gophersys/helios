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

-- IOTEA-style multi-tenant RBAC foundation (migration 0002). The model is User → OrganizationMember
-- (role + a PermissionSet) → Organization: a user belongs to an organization through a membership
-- row that carries a role (member|admin) and references the PermissionSet whose `permissions` array
-- ("namespace:action" strings, "*" = all) names what the member may do. The startup seed plants a
-- default organization, an admin PermissionSet (permissions {*}), and the default user as an admin
-- member. This slice is the DATA MODEL + the read surface (/v1/me, the bootstrap profile); it does
-- NOT rewrite the edenhttp auth spine (the JWT grants remain the authorize source).

CREATE TABLE IF NOT EXISTS organizations (
    -- id is the server-minted primary key (uuid). The seed supplies a fixed id so the default
    -- organization is stable across restarts.
    id          uuid        PRIMARY KEY,
    -- name is the organization's display name (shown in the profile card).
    name        text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS permission_sets (
    -- id is the server-minted primary key (uuid). The seed supplies a fixed id for the admin set.
    id              uuid        PRIMARY KEY,
    -- organization_id scopes the permission set to its owning organization (org-level set).
    organization_id uuid        NOT NULL REFERENCES organizations (id),
    -- name is the set's label (e.g. "Admin", "ReadOnly", "Default").
    name            text        NOT NULL,
    -- permissions is the array of "namespace:action" grant strings ("*" = all), the IOTEA permission
    -- vocabulary. The default is the empty set (a no-permission set), never NULL.
    permissions     text[]      NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_members (
    -- id is the server-minted primary key (uuid).
    id                uuid        PRIMARY KEY,
    -- organization_id + user_id link a user to an organization; the pair is UNIQUE (a user has at most
    -- one membership per organization), the key the idempotent seed's ON CONFLICT targets.
    organization_id   uuid        NOT NULL REFERENCES organizations (id),
    user_id           uuid        NOT NULL REFERENCES users (id),
    -- role is the IOTEA OrganizationRole: 'member' (permission-checked) or 'admin' (bypasses checks).
    role              text        NOT NULL DEFAULT 'member',
    -- permission_set_id is the org-level PermissionSet the member draws its permissions from.
    permission_set_id uuid        NOT NULL REFERENCES permission_sets (id),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, user_id)
);

-- IOTEA-style linked-identity model (migration 0003), the OAuth-ready authentication seam. An
-- `accounts` row is a credential record that links an authentication PROVIDER identity to an Eden
-- user, mirroring the IOTEA prisma `Account` model (provider + providerAccountId, unique together).
-- The provider vocabulary is {"password","google","github"}: for the "password" provider the
-- provider_account_id is the lowercased email and password_hash holds the bcrypt digest; for an OAuth
-- provider (google/github) the provider_account_id is the provider's stable account id and
-- password_hash is NULL (OAuth carries no password). Authentication resolves a (provider,
-- provider_account_id) pair to its user_id; the JWT then carries ONLY that user id, and the
-- DB-driven authorize loads the user's grants from the RBAC tables per request. Adding an OAuth
-- provider therefore changes only USER RESOLUTION (find-or-create the user+account from the OAuth
-- profile) — the mint + authorize path is identical (the IOTEA OAuth invariant).

CREATE TABLE IF NOT EXISTS accounts (
    -- id is the server-minted primary key (uuid). The password-account seed supplies a fixed id so the
    -- default user's password account is stable across restarts and the ON CONFLICT seed is a no-op.
    id                  uuid        PRIMARY KEY,
    -- user_id is the Eden user this provider identity is linked to (the account resolves to it on login).
    user_id             uuid        NOT NULL REFERENCES users (id),
    -- provider is the authentication provider: 'password' (local credential) or 'google'|'github' (OAuth).
    provider            text        NOT NULL,
    -- provider_account_id is the identity WITHIN the provider: the lowercased email for 'password', the
    -- provider's stable account id for an OAuth provider. (provider, provider_account_id) is UNIQUE.
    provider_account_id text        NOT NULL,
    -- password_hash is the bcrypt digest, set ONLY by the 'password' provider; NULL for an OAuth account
    -- (OAuth carries no password). It is a credential digest, never logged (gosec/secretscan guard it).
    password_hash       text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    -- A provider identity is single-valued: (provider, provider_account_id) is the natural key the
    -- find-or-create seed's ON CONFLICT targets, so a re-seed on every boot is a safe no-op.
    UNIQUE (provider, provider_account_id)
);
