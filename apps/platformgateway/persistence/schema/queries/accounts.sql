-- Queries for the `accounts` linked-identity table (the OAuth-ready authentication seam). sqlc emits one
-- typed Go method per `-- name:` directive into ../../generated; the :one/:exec suffix selects the return
-- shape. These are the queries the login Authenticator and the password-account seed call through the
-- injected Querier (never string SQL): the credential read by (provider, provider_account_id) plus the
-- idempotent find-or-create seed.
--
-- The vocabulary is provider ∈ {"password","google","github"}: for "password" the provider_account_id is
-- the lowercased email and password_hash holds the bcrypt digest; for an OAuth provider the
-- provider_account_id is the provider's stable account id and password_hash is NULL. A missing account
-- yields pgx.ErrNoRows, which the facade maps to a typed errors.KindNotFound.

-- name: GetAccountByProvider :one
-- The credential read the login Authenticator runs: resolve a (provider, provider_account_id) pair to its
-- account, returning the linked user_id and the password_hash the password provider checks against. The
-- (provider, provider_account_id) pair is UNIQUE, so this is a :one read; a missing pair is pgx.ErrNoRows
-- (→ the facade's KindNotFound → a 401 the Authenticator renders, never revealing which half was wrong).
SELECT id, user_id, provider, provider_account_id, password_hash, created_at, updated_at
FROM accounts
WHERE provider = $1 AND provider_account_id = $2;

-- name: EnsureAccount :exec
-- The idempotent find-or-create seed: plant the provider identity (with its linked user + optional
-- password_hash) if absent, do nothing if the (provider, provider_account_id) pair already exists. ON
-- CONFLICT keys on the UNIQUE (provider, provider_account_id) pair so a re-run on every boot is a safe
-- no-op (the existing account's hash is left untouched). It is the password-account seed AND the shape an
-- OAuth find-or-create would reuse (provider 'google'/'github', a NULL password_hash).
INSERT INTO accounts (id, user_id, provider, provider_account_id, password_hash)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (provider, provider_account_id) DO NOTHING;
