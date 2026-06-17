// Package me is the GET /v1/me route: the authenticated caller's own profile (user + IOTEA RBAC
// context). One of the 5-file route packages a resource decomposes into (ADR-0023): route.go /
// parse.go / validate.go / execute.go / effect.go, authorization the declarative Required Grant.
//
// /me requires NO grant — the zero edenhttp.Grant means authenticated-only: any signed-in caller may
// read THEIR OWN profile (the subject comes from the verified token, not a path param, so a caller can
// only ever read themselves). execute reads the caller's user record + their first/default membership
// and projects them to a Profile; a caller with no user row or no membership is a typed KindNotFound
// the pipeline renders as 404.
package me

import (
	"context"
	"net/http"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/observability"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/me/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// Request is the typed input: /me carries no body, no path, no query — the caller is the verified
// token's subject, read in execute from the Identity. The empty struct keeps the five-file shape
// uniform (parse/validate still run; they have nothing to decode/reject).
type Request struct{}

// Response is the caller's profile (the contract's `MeProfile` schema): the user fields + the RBAC
// organization/role/permissions.
type Response = view.Profile

// UserGetter is the single-method users port this route needs (the caller's user record by id).
// *persistence.Users satisfies it; a fake satisfies it for the unit lane.
type UserGetter interface {
	Get(ctx context.Context, id uuid.UUID) (persistence.User, error)
}

// MembershipReader is the single-method RBAC port this route needs (the caller's first/default
// membership by user id). *persistence.RBAC satisfies it; a fake satisfies it for the unit lane.
type MembershipReader interface {
	MembershipFor(ctx context.Context, userID uuid.UUID) (persistence.Membership, error)
}

// Register assembles the handler and binds GET /me (mounted under /v1). Required is the ZERO Grant —
// authenticated-only, no grant required (the pipeline still authenticates; it just does not authorize
// against a namespace:action). SuccessStatus defaults to 200.
func Register(mux *http.ServeMux, userStore UserGetter, rbacStore MembershipReader, provider observability.Provider) {
	handler := edenhttp.Handler[Request, Response]{
		Parse:    parse,
		Validate: validate,
		Required: edenhttp.Grant{}, // authenticated-only: any signed-in caller reads their own profile.
		Execute:  execute(userStore, rbacStore),
		Action:   effect(provider),
	}
	mux.Handle("GET /me", handler)
}
