package edenhttp

import (
	"github.com/gophersys/libs/go/errors"
)

// Identity is the authenticated caller a verified bearer token resolves to: the Subject (the audit
// identity — a user id, echoed into a control message's `By`) and the set of Grants the token
// carries (the namespace:action vocabulary). It is an immutable value the middleware stashes on the
// request context (IdentityFrom) for a pipeline's authorize stage to consult. It holds NO secret —
// the token value never rides here.
//
// The lib's auth CONCEPT is "identity" (HNS-1 rule 11: never a concept named `auth`); this is its
// one home.
type Identity struct {
	// Subject is the authenticated principal id (the JWT `sub`), used as the audit `By` stamp.
	Subject string
	// Grants is the namespace:action set the token authorizes. Authorize admits a required Grant
	// iff some element here Covers it.
	Grants []Grant
}

// Authorize reports nil iff this Identity holds a Grant that Covers required, else a typed
// *errors.Error of Kind KindPermission (→ 403). An Identity with no covering grant is denied; the
// error message names the required grant (operator-safe — a grant token is not a secret) but never
// the held set verbatim. This is the authorize stage's decision, callable directly by a handler
// that authorizes outside the typed pipeline.
func (i Identity) Authorize(required Grant) error {
	for _, held := range i.Grants {
		if held.Covers(required) {
			return nil
		}
	}
	return errors.Wrap(errors.KindPermission, "edenhttp: authorize",
		RequestError{Reason: "missing grant " + required.String()})
}

// HasGrant reports whether this Identity holds a grant covering required (the boolean form of
// Authorize, for a caller that branches rather than returns an error).
func (i Identity) HasGrant(required Grant) bool {
	return i.Authorize(required) == nil
}
