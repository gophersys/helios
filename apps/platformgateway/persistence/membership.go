package persistence

import (
	"context"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/persistence/generated"
)

// Membership is the domain-facing RBAC projection the route execute stages receive — plain Go scalars
// (uuid.UUID, []string), NOT the generated pgtype-laden row. It is the IOTEA model flattened to what a
// profile read needs: the organization a user belongs to (id + name), the member's role
// (member|admin — admin bypasses permission checks), and the permission set the member draws on (its
// name + the "namespace:action" permission strings, "*" = all). The facade converts the typed sqlc row
// into this shape so the execute stages never import pgtype.
type Membership struct {
	OrganizationID    uuid.UUID
	OrganizationName  string
	Role              string
	PermissionSetName string
	Permissions       []string
}

// RBAC is the typed store over the IOTEA-style RBAC tables (organizations, permission_sets,
// organization_members). It wraps the sqlc-generated Querier (never string-built SQL) and is the ONE
// place pgx's not-found sentinel becomes a typed errors.KindNotFound — the execute stage maps that
// Kind to a 404 at the transport boundary. It also owns the idempotent startup seed (EnsureOrganization
// / EnsurePermissionSet / EnsureMembership). It holds only the Querier (over the concurrency-safe pool),
// so it is safe for concurrent use.
type RBAC struct {
	queries generated.Querier
}

// MembershipFor returns a user's FIRST/default membership projected to the domain Membership. A user
// with no membership is a typed errors.KindNotFound (not a bare pgx sentinel), so the execute stage
// can branch on Kind and the envelope renders a 404. The Permissions slice is never nil — an absent
// permission array decodes to the empty slice, so the wire renders `[]`, never `null`.
func (r *RBAC) MembershipFor(ctx context.Context, userID uuid.UUID) (Membership, error) {
	row, err := r.queries.GetMembershipByUser(ctx, toPgUUID(userID))
	if err != nil {
		if isNoRows(err) {
			return Membership{}, notFoundMembership(userID.String())
		}
		return Membership{}, errors.Wrap(errors.KindInternal, "persistence: get membership", err)
	}
	permissions := row.Permissions
	if permissions == nil {
		permissions = []string{}
	}
	return Membership{
		OrganizationID:    uuid.UUID(row.OrganizationID.Bytes),
		OrganizationName:  row.OrganizationName,
		Role:              row.Role,
		PermissionSetName: row.PermissionSetName,
		Permissions:       permissions,
	}, nil
}

// EnsureOrganization idempotently seeds an organization (INSERT ... ON CONFLICT (id) DO NOTHING). The
// id is supplied (a fixed uuid in the composition root) so the default organization is stable across
// restarts and a re-seed on every boot is a safe no-op.
func (r *RBAC) EnsureOrganization(ctx context.Context, id uuid.UUID, name string) error {
	if err := r.queries.EnsureOrganization(ctx, generated.EnsureOrganizationParams{
		ID:   toPgUUID(id),
		Name: name,
	}); err != nil {
		return errors.Wrap(errors.KindUnavailable, "persistence: ensure organization", err)
	}
	return nil
}

// EnsurePermissionSet idempotently seeds an org-level permission set (INSERT ... ON CONFLICT (id) DO
// NOTHING). permissions is the "namespace:action" grant set ("*" = all); it is never nil on the wire —
// a nil slice is normalized to the empty set so the column is the empty array, never NULL.
func (r *RBAC) EnsurePermissionSet(ctx context.Context, id, organizationID uuid.UUID, name string, permissions []string) error {
	if permissions == nil {
		permissions = []string{}
	}
	if err := r.queries.EnsurePermissionSet(ctx, generated.EnsurePermissionSetParams{
		ID:             toPgUUID(id),
		OrganizationID: toPgUUID(organizationID),
		Name:           name,
		Permissions:    permissions,
	}); err != nil {
		return errors.Wrap(errors.KindUnavailable, "persistence: ensure permission set", err)
	}
	return nil
}

// EnsureMembership idempotently seeds an organization membership (INSERT ... ON CONFLICT
// (organization_id, user_id) DO NOTHING). It links the user to the organization with a role and the
// permission set the role draws on; re-seeding the same user in the same org is a no-op, so the boot
// seed is safe to run on every start.
func (r *RBAC) EnsureMembership(ctx context.Context, id, organizationID, userID, permissionSetID uuid.UUID, role string) error {
	if err := r.queries.EnsureMembership(ctx, generated.EnsureMembershipParams{
		ID:              toPgUUID(id),
		OrganizationID:  toPgUUID(organizationID),
		UserID:          toPgUUID(userID),
		Role:            role,
		PermissionSetID: toPgUUID(permissionSetID),
	}); err != nil {
		return errors.Wrap(errors.KindUnavailable, "persistence: ensure membership", err)
	}
	return nil
}

// notFoundMembership builds the canonical typed not-found error for a user's membership. The user id is
// a safe scalar, so it rides the error's redaction-safe field set. Declared once so the Kind + message
// are consistent.
func notFoundMembership(userID string) error {
	return errors.New(errors.KindNotFound, "persistence: membership not found").
		WithField("user-id", userID)
}
