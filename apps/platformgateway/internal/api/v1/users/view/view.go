// Package view is the ONE home (10 §9) for the `users` wire projection: the JSON shape the OpenAPI
// contract's `UserView` schema mirrors, and the single seam that projects a domain persistence.User
// (pgtype-free, plain Go scalars) into it. Every users route's execute stage produces a User through
// NewUser, so the wire shape is spelled once and get/list render a row identically. The pre-identity
// login bootstrap renders the default user through the SAME NewUser, so the login surface and the
// authenticated API agree on the user shape. It is a leaf: the route sub-packages import it, it
// imports none of them, so the users package can compose the routes without an import cycle.
package view

import (
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// User is the wire projection of a persisted user — the success payload get returns and the element
// type list returns (and the login bootstrap's payload). It mirrors the contract's `UserView` schema
// (operationId-stable field names), RFC3339-stamped so the contract's `format: date-time` holds. It
// carries plain JSON scalars only; no pgtype, no secret (a user row has no credential field).
type User struct {
	// ID is the server-minted user id (a uuid string).
	ID string `json:"id"`
	// Email is the user's unique login handle.
	Email string `json:"email"`
	// Name is the user's display name.
	Name string `json:"name"`
	// IsDefault marks the single default user (the login bootstrap's target).
	IsDefault bool `json:"isDefault"`
	// CreatedAt is the RFC3339 insert timestamp (immutable once stamped).
	CreatedAt string `json:"createdAt"`
	// UpdatedAt is the RFC3339 last-mutation timestamp.
	UpdatedAt string `json:"updatedAt"`
}

// NewUser projects a domain persistence.User into the wire User. It is the single place the domain
// row becomes the JSON DTO, so every route (and the login bootstrap) renders a user the same way.
// Timestamps are normalized to UTC RFC3339 to satisfy the contract's date-time format. The row is
// taken by pointer (a heavy timestamp-laden struct) to avoid copying it per call.
func NewUser(row *persistence.User) User {
	return User{
		ID:        row.ID.String(),
		Email:     row.Email,
		Name:      row.Name,
		IsDefault: row.IsDefault,
		CreatedAt: row.CreatedAt.UTC().Format(time.RFC3339),
		UpdatedAt: row.UpdatedAt.UTC().Format(time.RFC3339),
	}
}

// ParseID parses a path id segment into a uuid, returning a typed errors.KindInvalid (→ 400) on a
// malformed id. It is the ONE home for the {id} path-parameter parse the get route uses, so a bad id
// is a 400 with a stable Kind.
func ParseID(raw string) (uuid.UUID, error) {
	id, err := uuid.Parse(raw)
	if err != nil {
		return uuid.UUID{}, errors.Wrap(errors.KindInvalid, "users: parse id",
			edenhttp.RequestError{Reason: "path id is not a valid uuid"})
	}
	return id, nil
}
