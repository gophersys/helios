package persistence

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgtype"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/persistence/generated"
)

// User is the domain-facing row the route execute stages receive — plain Go scalars (uuid.UUID,
// time.Time), NOT the generated pgtype-laden model. The facade is the seam that converts the typed
// sqlc row into this domain shape so the execute stages never import pgtype. IsDefault marks the
// single default user the login bootstrap returns; created_at/updated_at are the audit-column mixin.
type User struct {
	ID        uuid.UUID
	Email     string
	Name      string
	IsDefault bool
	CreatedAt time.Time
	UpdatedAt time.Time
}

// Users is the typed read store over the `users` table. It wraps the sqlc-generated Querier (never
// string-built SQL) and is the ONE place pgx's not-found sentinel becomes a typed errors.KindNotFound
// — the execute stage maps that Kind to a 404 at the transport boundary. It also owns the idempotent
// default-user seed (EnsureDefault). It holds only the Querier (over the concurrency-safe pool), so
// it is safe for concurrent use.
type Users struct {
	queries generated.Querier
}

// Get fetches a user by id. A missing row is a typed errors.KindNotFound (not a bare pgx sentinel),
// so the execute stage can branch on Kind and the envelope renders a 404.
func (u *Users) Get(ctx context.Context, id uuid.UUID) (User, error) {
	row, err := u.queries.GetUser(ctx, toPgUUID(id))
	if err != nil {
		if isNoRows(err) {
			return User{}, notFoundUser(id.String())
		}
		return User{}, errors.Wrap(errors.KindInternal, "persistence: get user", err)
	}
	return fromUserRow(&row), nil
}

// List returns a page of users oldest-first (the seed default user is the first account). limit/
// offset are the pagination window the caller validated; the returned slice is never nil
// (emit_empty_slices), so the execute stage renders an empty list, never a null.
func (u *Users) List(ctx context.Context, limit, offset int32) ([]User, error) {
	rows, err := u.queries.ListUsers(ctx, generated.ListUsersParams{Limit: limit, Offset: offset})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "persistence: list users", err)
	}
	out := make([]User, len(rows))
	for i := range rows {
		out[i] = fromUserRow(&rows[i])
	}
	return out, nil
}

// Default returns the single default user (the login bootstrap target). A missing default is a typed
// errors.KindNotFound — the startup seed should have planted it, so its absence is a real fault the
// bootstrap surfaces rather than masking.
func (u *Users) Default(ctx context.Context) (User, error) {
	row, err := u.queries.GetDefaultUser(ctx)
	if err != nil {
		if isNoRows(err) {
			return User{}, errors.New(errors.KindNotFound, "persistence: no default user (startup seed missing)")
		}
		return User{}, errors.Wrap(errors.KindInternal, "persistence: get default user", err)
	}
	return fromUserRow(&row), nil
}

// EnsureDefault idempotently seeds the default user (INSERT ... ON CONFLICT (email) DO NOTHING). It is
// the IOTEA-style startup seed: the composition root calls it on every boot after Migrate, so a fresh
// database gets the default account and an existing one is left untouched. The id is supplied so the
// default user's id is stable across restarts.
func (u *Users) EnsureDefault(ctx context.Context, id uuid.UUID, email, name string) error {
	if err := u.queries.EnsureDefaultUser(ctx, generated.EnsureDefaultUserParams{
		ID:    toPgUUID(id),
		Email: email,
		Name:  name,
	}); err != nil {
		return errors.Wrap(errors.KindUnavailable, "persistence: ensure default user", err)
	}
	return nil
}

// notFoundUser builds the canonical typed not-found error for a user id. The id is a safe scalar, so
// it rides the error's redaction-safe field set. Declared once so the Kind + message are consistent.
func notFoundUser(id string) error {
	return errors.New(errors.KindNotFound, "persistence: user not found").
		WithField("user-id", id)
}

// fromUserRow converts a generated (pgtype-laden) row to the domain User. uuid bytes and timestamps
// are unwrapped here — the single conversion seam, so the execute stages never touch pgtype. The row
// is taken by pointer (it is a heavy pgtype-laden struct) to avoid copying it at every call site.
func fromUserRow(row *generated.User) User {
	return User{
		ID:        uuid.UUID(row.ID.Bytes),
		Email:     row.Email,
		Name:      row.Name,
		IsDefault: row.IsDefault,
		CreatedAt: row.CreatedAt.Time,
		UpdatedAt: row.UpdatedAt.Time,
	}
}

// toPgUUID wraps a domain uuid.UUID as the pgtype.UUID the generated Querier takes. Valid is always
// true — a uuid.UUID is always a concrete 16-byte value (the zero UUID is a real value, not NULL).
func toPgUUID(id uuid.UUID) pgtype.UUID {
	return pgtype.UUID{Bytes: id, Valid: true}
}
