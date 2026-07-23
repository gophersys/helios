package create

import (
	"context"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// execute is the business step: it resolves the caller's organization (the tenancy key), SEALS the
// credential value via the injected envelope.Sealer, computes its one-way fingerprint, mints a
// server-side connector id, and inserts the connector + its sealed material through the Creator port.
// It projects the persisted row to the wire Response — which carries NO value. It runs only AFTER the
// pipeline authenticated, parsed, validated, and AUTHORIZED the request.
//
// The credential VALUE lives only in this function's local scope: it is sealed into an
// envelope.Sealed and its fingerprint taken, then it goes out of scope. It is NEVER put on the
// Response, NEVER logged, NEVER passed to persistence in the clear (only the ciphertext is). A
// membership-less caller is a 404 (they own no org, hence no connectors).
func execute(connectorStore Creator, tenants tenantResolver, sealer envelope.Sealer) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, identity edenhttp.Identity, input Request) (Response, error) {
		callerID, err := uuid.Parse(identity.Subject)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindInvalid, "create: parse caller subject", err)
		}
		organizationID, err := tenants.OrganizationFor(ctx, callerID)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "create: resolve caller organization", err)
		}

		// Seal the credential (the value crosses into the crypto here and nowhere else). The Sealed
		// record + fingerprint are all that leave this block; the plaintext does not.
		sealed, err := sealer.Seal(ctx, []byte(input.Value))
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "create: seal credential", err)
		}
		fingerprint := envelope.Fingerprint([]byte(input.Value))

		row, err := connectorStore.Create(
			ctx,
			uuid.New(), organizationID, userScopeID(input.Scope),
			input.Kind, input.Name, input.AccountHint, fingerprint,
			callerID,
			toSealedMaterial(sealed),
		)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "create: insert connector", err)
		}
		return view.NewConnector(&row), nil
	}
}

// userScopeID returns the owning user id for a user-scoped connector, or nil for an org-scoped one
// (the NULL user_id). validate already proved a user-scoped TargetID parses, so the parse here cannot
// fail; a defensive nil on an unexpected parse keeps the connector org-scoped rather than panicking.
func userScopeID(scope view.ScopeInput) *uuid.UUID {
	if scope.Level != view.ScopeUser {
		return nil
	}
	id, err := uuid.Parse(scope.TargetID)
	if err != nil {
		return nil
	}
	return &id
}

// toSealedMaterial converts the envelope.Sealed record into the persistence carrier the Creator port
// takes. It is the seam between the crypto lib's value type and the data layer's — spelled once here
// (the update route shares the shape via its own copy, kept in lockstep). KEKVersion is narrowed to
// int32 (the column type); envelope versions are small positive ints, so the narrowing is safe.
func toSealedMaterial(sealed envelope.Sealed) persistence.SealedMaterial {
	return persistence.SealedMaterial{
		Ciphertext:      sealed.Ciphertext,
		WrappedDEK:      sealed.WrappedDEK,
		NonceCiphertext: sealed.NonceCiphertext,
		NonceDEK:        sealed.NonceDEK,
		KEKVersion:      int32(sealed.KEKVersion), //nolint:gosec // G115: KEK versions are small positive ints (1,2,...), never near int32 overflow.
	}
}
