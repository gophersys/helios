package identity

import (
	"context"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// GrantResolver is the consumer-defined port the DB-driven verifier loads a caller's grants through: it
// turns an authenticated user id into the set of grants that user holds RIGHT NOW (from the database),
// not whatever a token once embedded. It is the SHAPE OF THE NEED (one method) — the persistence-backed
// RBACGrantResolver realizes it, and a fake realizes it for the unit/route lane.
//
// This is the IOTEA permission model (PERMISSION_SYSTEM_GUIDE): the JWT carries ONLY the user id, and
// the authoritative grant set is loaded per request, so a permission revoked in the DB takes effect on
// the caller's very next request without re-issuing a token.
type GrantResolver interface {
	// ResolveGrants returns the grants the user holds, loaded from the authoritative store. An unknown
	// user (no membership) is a typed error, which the verifier surfaces as an authentication failure.
	ResolveGrants(ctx context.Context, userID uuid.UUID) ([]edenhttp.Grant, error)
}

// dbVerifier is the edenhttp.TokenVerifier that makes AUTHORIZE DB-driven. It wraps the dev-JWT
// HMACVerifier for AUTHENTICATION (proving the token's subject is genuine) but IGNORES any grants the
// token carries: the grants are loaded fresh from the GrantResolver for the verified subject. So the JWT
// is reduced to a signed assertion of "who you are" (the IOTEA invariant), and "what you may do" is the
// database's answer, re-read every request.
type dbVerifier struct {
	hmac     *edenhttp.HMACVerifier
	resolver GrantResolver
}

// NewDBVerifier builds the DB-driven TokenVerifier from the dev-JWT HMAC verifier (the authentication
// half) and a grant resolver (the authorization half). The SAME *edenhttp.HMACVerifier the composition
// root builds is wrapped here for the spine AND exposed (its Sign) to the /auth/login mint, so one signing
// key both mints and verifies. Returns the edenhttp.TokenVerifier port the spine's Deps accept (accept
// interfaces; the spine receives a usable verifier).
//
//nolint:ireturn // returns the edenhttp.TokenVerifier port the spine's Deps accept (the frozen surface).
func NewDBVerifier(hmac *edenhttp.HMACVerifier, resolver GrantResolver) edenhttp.TokenVerifier {
	return &dbVerifier{hmac: hmac, resolver: resolver}
}

// Verify authenticates the token via the HMAC verifier (subject only — any embedded grants are
// discarded), parses the subject as a user id, loads that user's grants from the resolver, and returns an
// Identity whose Grants are the DB-resolved set. A malformed subject, an unknown user, or a resolver fault
// is a typed KindUnauthenticated error — the spine forces any Verify error to a 401, so the caller is
// rejected as unauthenticated rather than leaking a 500. now is the spine's injected clock instant
// (forwarded to the HMAC verify so expiry stays deterministic under test).
func (v *dbVerifier) Verify(token string, now time.Time) (edenhttp.Identity, error) {
	// (a) HMAC-authenticate the token to get the genuine subject. The Identity's Grants here are the
	// token's embedded set — deliberately DISCARDED below in favor of the DB's answer. The HMAC verifier
	// already returns KindUnauthenticated; the wrap preserves that Kind and adds this layer's context.
	authenticated, err := v.hmac.Verify(token, now)
	if err != nil {
		return edenhttp.Identity{}, errors.Wrap(errors.KindOf(err), "identity: authenticate token", err)
	}

	// (b) The subject is the Eden user id. A subject that is not a uuid is a token we do not trust.
	userID, err := uuid.Parse(authenticated.Subject)
	if err != nil {
		return edenhttp.Identity{}, errors.Wrap(errors.KindUnauthenticated,
			"identity: token subject is not a valid user id", err)
	}

	// (c) Load the caller's grants from the authoritative store (the IOTEA per-request permission read).
	grants, err := v.resolver.ResolveGrants(context.Background(), userID)
	if err != nil {
		// An unknown user / resolver fault is an authentication failure: collapse it to
		// KindUnauthenticated so the spine answers 401 (never a 500 leaking the cause to the client).
		return edenhttp.Identity{}, errors.Wrap(errors.KindUnauthenticated,
			"identity: resolve grants for subject", err)
	}

	// (d) The Identity the spine stashes: the verified subject + the DB-resolved grants (NOT the token's).
	return edenhttp.Identity{Subject: authenticated.Subject, Grants: grants}, nil
}

// compile-time assertion: *dbVerifier is an edenhttp.TokenVerifier (the spine's identity port).
var _ edenhttp.TokenVerifier = (*dbVerifier)(nil)
