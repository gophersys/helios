// Package view is the ONE home (10 §9) for the `resource` wire projection: the JSON shape the
// OpenAPI contract's `ResourceView` schema mirrors, and the single seam that projects a domain
// persistence.Resource (pgtype-free, plain Go scalars) into it. Every resource route's execute stage
// produces a Resource through NewResource, so the wire shape is spelled once and the create/get/
// list/update routes render a row identically. It is a leaf: the route sub-packages import it, it
// imports none of them, so the resource package can compose the routes without an import cycle.
package view

import (
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// MaxNameLength bounds a resource name so a pathological payload cannot store an unbounded string.
// It is the ONE home for the name constraint both the create and update routes' validate stages
// cite — the rule is spelled once, not re-invented per route.
const MaxNameLength = 256

// ValidateName checks a resource name is well-formed: present (non-blank) and within MaxNameLength.
// It returns a typed errors.KindInvalid (→ 400) on a malformed name, so the create and update
// validate stages share one rule and the rejection branches by Kind, never by string. It is pure —
// it touches no port (the validate-stage contract).
func ValidateName(name string) error {
	if strings.TrimSpace(name) == "" {
		return errors.Wrap(errors.KindInvalid, "resource: validate name",
			edenhttp.RequestError{Reason: "name is required and must be non-blank"})
	}
	if len(name) > MaxNameLength {
		return errors.Wrap(errors.KindInvalid, "resource: validate name",
			edenhttp.RequestError{Reason: "name exceeds the maximum length"})
	}
	return nil
}

// ParseID parses a path id segment into a uuid, returning a typed errors.KindInvalid (→ 400) on a
// malformed id. It is the ONE home for the {id} path-parameter parse the get/update/delete routes
// share, so a bad id is a 400 with a stable Kind across all three.
func ParseID(raw string) (uuid.UUID, error) {
	id, err := uuid.Parse(raw)
	if err != nil {
		return uuid.UUID{}, errors.Wrap(errors.KindInvalid, "resource: parse id",
			edenhttp.RequestError{Reason: "path id is not a valid uuid"})
	}
	return id, nil
}

// Resource is the wire projection of a persisted resource — the success payload create/get/update
// return and the element type list returns. It mirrors the contract's `ResourceView` schema
// (operationId-stable field names), RFC3339-stamped so the contract's `format: date-time` holds. It
// carries plain JSON scalars only; no pgtype, no secret.
type Resource struct {
	// ID is the server-minted resource id (a uuid string).
	ID string `json:"id"`
	// Name is the resource's human label.
	Name string `json:"name"`
	// CreatedAt is the RFC3339 insert timestamp (immutable once stamped).
	CreatedAt string `json:"createdAt"`
	// UpdatedAt is the RFC3339 last-mutation timestamp.
	UpdatedAt string `json:"updatedAt"`
}

// NewResource projects a domain persistence.Resource into the wire Resource. It is the single place
// the domain row becomes the JSON DTO, so every route renders a resource the same way. Timestamps
// are normalized to UTC RFC3339 to satisfy the contract's date-time format. The row is taken by
// pointer (it is a heavy pgtype-free but timestamp-laden struct) to avoid copying it per call.
func NewResource(row *persistence.Resource) Resource {
	return Resource{
		ID:        row.ID.String(),
		Name:      row.Name,
		CreatedAt: row.CreatedAt.UTC().Format(time.RFC3339),
		UpdatedAt: row.UpdatedAt.UTC().Format(time.RFC3339),
	}
}
