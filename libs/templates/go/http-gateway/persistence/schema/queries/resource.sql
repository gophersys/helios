-- Queries for the `resource` table. sqlc emits one typed Go method per `-- name:` directive into
-- ../../generated. The :one/:many/:exec suffix selects the return shape. These are the worked
-- examples a generated app's execute stages call through the injected Querier (never string SQL).
--
-- Full CRUD over the reference resource: create, get-by-id, list (paginated), update, delete. A
-- not-found is surfaced by the :one query returning pgx.ErrNoRows, which the persistence port maps to
-- a typed errors.KindNotFound; the constructor is generated server-side (the database does not default
-- the id), so an insert supplies it explicitly.

-- name: CreateResource :one
INSERT INTO resource (id, name)
VALUES ($1, $2)
RETURNING id, name, created_at, updated_at;

-- name: GetResource :one
SELECT id, name, created_at, updated_at
FROM resource
WHERE id = $1;

-- name: ListResources :many
SELECT id, name, created_at, updated_at
FROM resource
ORDER BY created_at DESC
LIMIT $1 OFFSET $2;

-- name: UpdateResource :one
UPDATE resource
SET name = $2,
    updated_at = now()
WHERE id = $1
RETURNING id, name, created_at, updated_at;

-- name: DeleteResource :one
DELETE FROM resource
WHERE id = $1
RETURNING id;
