// Package view is the ONE home (10 §9) for the `/me` wire projection: the Profile JSON shape the
// OpenAPI contract's profile schema mirrors, and the single seam that projects a domain user +
// membership (pgtype-free, plain Go scalars) into it. The /v1/me route's execute stage produces a
// Profile through NewProfile, and the pre-identity login bootstrap renders the default user's profile
// through the SAME NewProfile, so the authenticated profile read and the public login surface agree on
// the profile shape. It reuses the users wire User for the user part (one concept, one home — the user
// shape is spelled once in users/view), and adds the RBAC organization/role/permissions. It is a leaf:
// the route sub-package and the bootstrap import it, it imports none of them.
package view

import (
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// Organization is the wire projection of the organization a caller belongs to — the id + display name
// the profile card shows. It carries plain JSON scalars only.
type Organization struct {
	// ID is the organization id (a uuid string).
	ID string `json:"id"`
	// Name is the organization's display name.
	Name string `json:"name"`
}

// Profile is the authenticated caller's profile: the user fields (the shared users wire User, embedded
// so the user shape is spelled once) plus the IOTEA RBAC context — the organization the caller belongs
// to, their role (member|admin), and the permission set's "namespace:action" permission strings
// ("*" = all). It is the payload /v1/me returns and the shape the login bootstrap renders the default
// user's profile as, so the two surfaces agree.
type Profile struct {
	// User is the caller's user record (id, email, name, isDefault, timestamps) — the shared wire shape.
	view.User
	// Organization is the organization the caller belongs to (id + name).
	Organization Organization `json:"organization"`
	// Role is the member's role in the organization: "member" or "admin" (admin bypasses checks).
	Role string `json:"role"`
	// Permissions is the member's permission-set grant strings ("namespace:action", "*" = all). Never
	// null — an empty set renders as [].
	Permissions []string `json:"permissions"`
}

// NewProfile projects a domain persistence.User + persistence.Membership into the wire Profile. It is
// the single place the domain rows become the JSON DTO, so the /me route and the login bootstrap render
// a profile the same way. The user part is delegated to users/view.NewUser (the one home for the user
// shape). Permissions is normalized to a non-nil slice so the contract's array is `[]`, never `null`.
// The rows are taken by pointer (heavy timestamp/pgtype-derived structs) to avoid copying per call.
func NewProfile(user *persistence.User, membership *persistence.Membership) Profile {
	permissions := membership.Permissions
	if permissions == nil {
		permissions = []string{}
	}
	return Profile{
		User: view.NewUser(user),
		Organization: Organization{
			ID:   membership.OrganizationID.String(),
			Name: membership.OrganizationName,
		},
		Role:        membership.Role,
		Permissions: permissions,
	}
}
