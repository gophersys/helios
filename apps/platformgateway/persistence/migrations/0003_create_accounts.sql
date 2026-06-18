-- 0003_create_accounts — the IOTEA-style linked-identity model (goose-style up/down), the OAuth-ready
-- authentication seam. It APPLIES the `accounts` table to a real database; the embedded startup migrate
-- runner (persistence/migrate.go) runs the +goose Up section on every boot (idempotent, CREATE ... IF
-- NOT EXISTS), and the integration lane runs the SAME section against a real postgres. schema/schema.sql
-- is the SAME shape sqlc type-checks against — keep them in lockstep.
--
-- An `accounts` row links an authentication PROVIDER identity to an Eden user (the IOTEA prisma `Account`
-- model: provider + providerAccountId, UNIQUE together). The provider vocabulary is
-- {"password","google","github"}: for "password" the provider_account_id is the lowercased email and
-- password_hash holds the bcrypt digest; for an OAuth provider (google/github) the provider_account_id is
-- the provider's stable account id and password_hash is NULL. Authentication resolves (provider,
-- provider_account_id) to user_id; the JWT carries ONLY that user id, and the DB-driven authorize loads
-- the user's grants per request. Adding an OAuth provider changes only USER RESOLUTION — the mint +
-- authorize path is unchanged.

-- +goose Up
CREATE TABLE IF NOT EXISTS accounts (
    id                  uuid        PRIMARY KEY,
    user_id             uuid        NOT NULL REFERENCES users (id),
    provider            text        NOT NULL,
    provider_account_id text        NOT NULL,
    password_hash       text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_account_id)
);

-- +goose Down
DROP TABLE accounts;
