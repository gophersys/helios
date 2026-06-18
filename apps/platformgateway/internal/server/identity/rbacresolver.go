package identity

import (
	"context"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// adminRole is the IOTEA OrganizationRole that bypasses permission checks: an admin member holds the
// wildcard "*" grant (covers every namespace:action) regardless of their permission set's explicit
// strings. The role vocabulary (member|admin) is the persistence membership's, cited here once.
const adminRole = "admin"

// MembershipReader is the one-method RBAC port the persistence-backed resolver needs: a user's
// first/default membership by id. The concrete *persistence.RBAC satisfies it (it is the SAME method the
// /v1/me route reads through), so the composition root binds one facade for both. A fake satisfies it for
// the unit lane.
type MembershipReader interface {
	MembershipFor(ctx context.Context, userID uuid.UUID) (persistence.Membership, error)
}

// RBACGrantResolver is the persistence-backed GrantResolver: it loads a user's membership and projects
// its permission strings into the typed edenhttp.Grant set the DB-driven verifier hands the spine. It is
// the IOTEA permission read made authoritative per request — the JWT carries only the user id, this loads
// what that user may do RIGHT NOW. It holds only the MembershipReader port, so it is safe for concurrent
// use.
type RBACGrantResolver struct {
	rbac MembershipReader
}

// NewRBACGrantResolver builds the persistence-backed resolver over the membership-read port (accept
// interfaces, return concrete — the caller receives a usable *RBACGrantResolver, the GrantResolver the
// DB-driven verifier drives).
func NewRBACGrantResolver(rbac MembershipReader) *RBACGrantResolver {
	return &RBACGrantResolver{rbac: rbac}
}

// ResolveGrants loads the user's membership and returns the grants it confers. Each permission string
// ("namespace:action", or "*") is parsed via edenhttp.ParseGrant into a typed Grant. If the membership's
// role is "admin", the wildcard "*" grant is ENSURED present (the IOTEA admin bypass: admin covers every
// namespace:action even if the permission set did not list "*"). A user with no membership arrives as the
// facade's typed KindNotFound — propagated so the verifier collapses it to a 401 (an unknown caller). A
// malformed permission string is a typed KindInternal (a seed defect, not a caller fault).
func (r *RBACGrantResolver) ResolveGrants(ctx context.Context, userID uuid.UUID) ([]edenhttp.Grant, error) {
	membership, err := r.rbac.MembershipFor(ctx, userID)
	if err != nil {
		// Preserve the Kind (a missing membership is KindNotFound) so the verifier's wrap turns it into a
		// 401; the boundary wrap keeps the chain for the server log.
		return nil, errors.Wrap(errors.KindOf(err), "identity: load membership for grants", err)
	}

	grants := make([]edenhttp.Grant, 0, len(membership.Permissions)+1)
	hasWildcard := false
	for _, permission := range membership.Permissions {
		grant, parseErr := edenhttp.ParseGrant(permission)
		if parseErr != nil {
			// A permission string that does not parse is a seed/data defect, not a caller fault → 500-class.
			return nil, errors.Wrap(errors.KindInternal, "identity: parse permission string", parseErr)
		}
		if grant.Namespace == "*" && grant.Action == "*" {
			hasWildcard = true
		}
		grants = append(grants, grant)
	}

	// The IOTEA admin bypass: an admin member covers everything. Ensure the wildcard "*" grant is present
	// (idempotent — skip if the permission set already listed "*").
	if membership.Role == adminRole && !hasWildcard {
		wildcard, parseErr := edenhttp.ParseGrant("*")
		if parseErr != nil {
			// "*" is a constant valid grant; a parse failure here would be an edenhttp contract break.
			return nil, errors.Wrap(errors.KindInternal, "identity: parse admin wildcard grant", parseErr)
		}
		grants = append(grants, wildcard)
	}
	return grants, nil
}

// compile-time assertion: *RBACGrantResolver is a GrantResolver (the DB-driven verifier's port) and the
// concrete *persistence.RBAC satisfies the membership-read port the resolver needs.
var (
	_ GrantResolver    = (*RBACGrantResolver)(nil)
	_ MembershipReader = (*persistence.RBAC)(nil)
)
