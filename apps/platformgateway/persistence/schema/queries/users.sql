-- Queries for the `users` table. sqlc emits one typed Go method per `-- name:` directive into
-- ../../generated. The :one/:many/:exec suffix selects the return shape. These are the queries the
-- users routes' execute stages call through the injected Querier (never string SQL).
--
-- The read slice (get-by-id, list, get-default) plus the idempotent startup seed (EnsureDefaultUser).
-- A not-found is surfaced by the :one query returning pgx.ErrNoRows, which the persistence port maps
-- to a typed errors.KindNotFound. Create/update/delete are deferred to a later backend piece.

-- name: GetUser :one
SELECT id, email, name, is_default, created_at, updated_at
FROM users
WHERE id = $1;

-- name: ListUsers :many
SELECT id, email, name, is_default, created_at, updated_at
FROM users
ORDER BY created_at ASC
LIMIT $1 OFFSET $2;

-- name: GetDefaultUser :one
SELECT id, email, name, is_default, created_at, updated_at
FROM users
WHERE is_default
LIMIT 1;

-- name: EnsureDefaultUser :exec
-- The idempotent IOTEA-style startup seed: plant the default user if absent, do nothing if the email
-- already exists. ON CONFLICT keys on the unique email so a re-run on every boot is a safe no-op.
INSERT INTO users (id, email, name, is_default)
VALUES ($1, $2, $3, true)
ON CONFLICT (email) DO NOTHING;
