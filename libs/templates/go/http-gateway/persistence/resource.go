package persistence

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgtype"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/persistence/generated"
)

// Resource is the domain-facing row the route execute stages receive — plain Go scalars (uuid.UUID,
// time.Time), NOT the generated pgtype-laden model. The facade is the seam that converts the typed
// sqlc row to/from the domain shape so the execute stages never import pgtype. created_at/updated_at
// are the audit-column mixin every persisted resource carries.
type Resource struct {
	ID        uuid.UUID
	Name      string
	CreatedAt time.Time
	UpdatedAt time.Time
}

// Resources is the typed CRUD store over the `resource` table. It wraps the sqlc-generated Querier
// (never string-built SQL) and is the ONE place pgx's not-found sentinel becomes a typed
// errors.KindNotFound — the execute stage maps that Kind to a 404 at the transport boundary. It holds
// only the Querier (over the concurrency-safe pool), so it is safe for concurrent use.
type Resources struct {
	queries generated.Querier
}

// Create inserts a new resource. The id is server-minted (the database does not default it), so the
// caller supplies it; created_at/updated_at are stamped by the database default. Returns the
// persisted row.
func (r *Resources) Create(ctx context.Context, id uuid.UUID, name string) (Resource, error) {
	row, err := r.queries.CreateResource(ctx, generated.CreateResourceParams{
		ID:   toPgUUID(id),
		Name: name,
	})
	if err != nil {
		return Resource{}, errors.Wrap(errors.KindInternal, "persistence: create resource", err)
	}
	return fromRow(&row), nil
}

// Get fetches a resource by id. A missing row is a typed errors.KindNotFound (not a bare pgx
// sentinel), so the execute stage can branch on Kind and the envelope renders a 404.
func (r *Resources) Get(ctx context.Context, id uuid.UUID) (Resource, error) {
	row, err := r.queries.GetResource(ctx, toPgUUID(id))
	if err != nil {
		if isNoRows(err) {
			return Resource{}, notFound(id)
		}
		return Resource{}, errors.Wrap(errors.KindInternal, "persistence: get resource", err)
	}
	return fromRow(&row), nil
}

// List returns a page of resources newest-first. limit/offset are the pagination window the caller
// validated; the returned slice is never nil (sqlc emit_empty_slices), so the execute stage renders
// an empty list, never a null.
func (r *Resources) List(ctx context.Context, limit, offset int32) ([]Resource, error) {
	rows, err := r.queries.ListResources(ctx, generated.ListResourcesParams{Limit: limit, Offset: offset})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "persistence: list resources", err)
	}
	out := make([]Resource, len(rows))
	for i := range rows {
		out[i] = fromRow(&rows[i])
	}
	return out, nil
}

// Update sets a resource's name and bumps updated_at (the query does the bump). A missing row is a
// typed errors.KindNotFound. Returns the updated row.
func (r *Resources) Update(ctx context.Context, id uuid.UUID, name string) (Resource, error) {
	row, err := r.queries.UpdateResource(ctx, generated.UpdateResourceParams{
		ID:   toPgUUID(id),
		Name: name,
	})
	if err != nil {
		if isNoRows(err) {
			return Resource{}, notFound(id)
		}
		return Resource{}, errors.Wrap(errors.KindInternal, "persistence: update resource", err)
	}
	return fromRow(&row), nil
}

// Delete removes a resource by id. A missing row is a typed errors.KindNotFound (the DELETE ...
// RETURNING yields no row), so a delete of an absent resource is a 404, not a silent success.
func (r *Resources) Delete(ctx context.Context, id uuid.UUID) error {
	if _, err := r.queries.DeleteResource(ctx, toPgUUID(id)); err != nil {
		if isNoRows(err) {
			return notFound(id)
		}
		return errors.Wrap(errors.KindInternal, "persistence: delete resource", err)
	}
	return nil
}

// notFound builds the canonical typed not-found error for a resource id. The id is a safe scalar
// (string), so it rides the error's redaction-safe field set. Declared once so the Kind + message are
// consistent across Get/Update/Delete.
func notFound(id uuid.UUID) error {
	return errors.New(errors.KindNotFound, "persistence: resource not found").
		WithField("resource-id", id.String())
}

// fromRow converts a generated (pgtype-laden) row to the domain Resource. uuid bytes and timestamps
// are unwrapped here — the single conversion seam, so the execute stages never touch pgtype. The row
// is taken by pointer (it is a heavy pgtype-laden struct) to avoid copying it at every call site.
func fromRow(row *generated.Resource) Resource {
	return Resource{
		ID:        uuid.UUID(row.ID.Bytes),
		Name:      row.Name,
		CreatedAt: row.CreatedAt.Time,
		UpdatedAt: row.UpdatedAt.Time,
	}
}

// toPgUUID wraps a domain uuid.UUID as the pgtype.UUID the generated Querier takes. Valid is always
// true — a uuid.UUID is always a concrete 16-byte value (the zero UUID is a real value, not NULL).
func toPgUUID(id uuid.UUID) pgtype.UUID {
	return pgtype.UUID{Bytes: id, Valid: true}
}
