package me

import (
	"context"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/me/view"
)

// execute is the business step: it reads the authenticated caller's id from the verified Identity's
// Subject (the JWT `sub`), parses it as a uuid, then loads the caller's user record + their
// first/default membership through the injected ports (the ONLY stage that touches persistence) and
// projects them to the wire Profile. A malformed subject is a typed KindInvalid (a token whose subject
// is not a uuid is a bad caller, → 400); a missing user or membership arrives as the persistence
// facade's typed KindNotFound, whose Kind execute preserves on the wrap so the envelope renders a 404.
// It runs only after authenticate/validate/AUTHORIZE (the zero-Grant route authenticates but requires
// no grant).
func execute(userStore UserGetter, rbacStore MembershipReader) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, identity edenhttp.Identity, _ Request) (Response, error) {
		userID, err := uuid.Parse(identity.Subject)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindInvalid, "me: token subject is not a valid user id", err)
		}
		user, err := userStore.Get(ctx, userID)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "me: fetch user", err)
		}
		membership, err := rbacStore.MembershipFor(ctx, userID)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "me: fetch membership", err)
		}
		return view.NewProfile(&user, &membership), nil
	}
}
