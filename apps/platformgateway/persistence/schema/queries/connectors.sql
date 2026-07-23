-- Queries for the user/org connector store (connectors + connector_secrets). sqlc emits one typed Go
-- method per `-- name:` directive into ../../generated; the :one/:many/:exec suffix selects the return
-- shape. These are the queries the connectors facade calls through the injected Querier (never string
-- SQL). The value is NEVER read back: there is NO query that SELECTs the plaintext (there is no
-- plaintext at rest); the sealed material (connector_secrets) is read only by the agent-resolution
-- path, and the metadata reads NEVER touch connector_secrets so a list never SELECTs ciphertext.
--
-- EVERY read/update/delete is TENANT-SCOPED: it carries `organization_id = $callerOrg` in its WHERE
-- clause (ADR-0029 §2.3), so a caller in one org can never touch another org's connector — a
-- cross-org id yields pgx.ErrNoRows, which the facade maps to a typed errors.KindNotFound (404).

-- name: CreateConnector :one
-- Insert a connector's metadata row and return it. The sealed material is inserted separately
-- (CreateConnectorSecret) inside the same transaction. A (organization_id, kind, name) collision
-- violates the UNIQUE constraint → pgx unique-violation, which the facade maps to KindConflict (409).
INSERT INTO connectors (id, organization_id, user_id, kind, name, account_hint, fingerprint, created_by)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
RETURNING id, organization_id, user_id, kind, name, account_hint, fingerprint, created_by, created_at, updated_at;

-- name: CreateConnectorSecret :exec
-- Insert the sealed material for a connector (the libs/go/envelope Sealed record). Written in the same
-- transaction as CreateConnector so a connector never exists without its sealed secret.
INSERT INTO connector_secrets (connector_id, ciphertext, wrapped_dek, nonce_ciphertext, nonce_dek, kek_version)
VALUES ($1, $2, $3, $4, $5, $6);

-- name: GetConnector :one
-- Read a single connector's metadata by id, TENANT-SCOPED. A row owned by another org is invisible
-- (the organization_id predicate excludes it) → pgx.ErrNoRows → KindNotFound (404). Never SELECTs the
-- sealed material.
SELECT id, organization_id, user_id, kind, name, account_hint, fingerprint, created_by, created_at, updated_at
FROM connectors
WHERE id = $1 AND organization_id = $2;

-- name: ListConnectors :many
-- List a page of the caller's org connectors, oldest-first, TENANT-SCOPED. Never SELECTs the sealed
-- material. limit/offset are the validated pagination window.
SELECT id, organization_id, user_id, kind, name, account_hint, fingerprint, created_by, created_at, updated_at
FROM connectors
WHERE organization_id = $1
ORDER BY created_at ASC
LIMIT $2 OFFSET $3;

-- name: ReplaceConnectorCredential :one
-- Re-seal a connector's credential (rotation/replace): update the account_hint + fingerprint + bump
-- updated_at, TENANT-SCOPED. Returns the updated metadata row; a row owned by another org matches
-- nothing → pgx.ErrNoRows → KindNotFound (404). The sealed material is replaced separately
-- (ReplaceConnectorSecret) in the same transaction.
UPDATE connectors
SET account_hint = $3, fingerprint = $4, updated_at = now()
WHERE id = $1 AND organization_id = $2
RETURNING id, organization_id, user_id, kind, name, account_hint, fingerprint, created_by, created_at, updated_at;

-- name: ReplaceConnectorSecret :exec
-- Replace the sealed material for an existing connector (the new Sealed record after a re-seal). Run
-- in the same transaction as ReplaceConnectorCredential.
UPDATE connector_secrets
SET ciphertext = $2, wrapped_dek = $3, nonce_ciphertext = $4, nonce_dek = $5, kek_version = $6
WHERE connector_id = $1;

-- name: DeleteConnector :one
-- Revoke a connector by id, TENANT-SCOPED. The ON DELETE CASCADE on connector_secrets purges the
-- sealed material atomically. RETURNING id makes a delete of an absent/other-org connector yield no
-- row (pgx.ErrNoRows → KindNotFound, 404) — a delete is never a silent success.
DELETE FROM connectors
WHERE id = $1 AND organization_id = $2
RETURNING id;
