package update

import (
	"context"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/view"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// execute is the business step: it resolves the caller's organization (the tenancy key), RE-SEALS the
// new credential value via the injected envelope.Sealer under a fresh DEK, computes its fingerprint,
// and replaces the connector's stored ciphertext + metadata THROUGH THAT ORG (the ONLY stage that
// touches persistence). A connector owned by another org is invisible — the tenant-scoped update
// matches nothing and yields the facade's typed KindNotFound (404). It runs only after
// authenticate/validate/AUTHORIZE. The new value lives only in this local scope (sealed, fingerprinted,
// then out of scope); it is NEVER returned or logged.
func execute(connectorStore Replacer, tenants tenantResolver, sealer envelope.Sealer) func(context.Context, edenhttp.Identity, Request) (Response, error) {
	return func(ctx context.Context, identity edenhttp.Identity, input Request) (Response, error) {
		callerID, err := uuid.Parse(identity.Subject)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindInvalid, "update: parse caller subject", err)
		}
		organizationID, err := tenants.OrganizationFor(ctx, callerID)
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "update: resolve caller organization", err)
		}

		sealed, err := sealer.Seal(ctx, []byte(input.Value))
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "update: re-seal credential", err)
		}
		fingerprint := envelope.Fingerprint([]byte(input.Value))

		row, err := connectorStore.Replace(ctx, input.ID, organizationID, input.AccountHint, fingerprint, toSealedMaterial(sealed))
		if err != nil {
			return Response{}, errors.Wrap(errors.KindOf(err), "update: replace connector credential", err)
		}
		return view.NewConnector(&row), nil
	}
}

// toSealedMaterial converts the envelope.Sealed record into the persistence carrier the Replacer port
// takes — the same seam the create route uses, kept in lockstep. KEKVersion is narrowed to int32 (the
// column type); envelope versions are small positive ints, so the narrowing is safe.
func toSealedMaterial(sealed envelope.Sealed) persistence.SealedMaterial {
	return persistence.SealedMaterial{
		Ciphertext:      sealed.Ciphertext,
		WrappedDEK:      sealed.WrappedDEK,
		NonceCiphertext: sealed.NonceCiphertext,
		NonceDEK:        sealed.NonceDEK,
		KEKVersion:      int32(sealed.KEKVersion), //nolint:gosec // G115: KEK versions are small positive ints (1,2,...), never near int32 overflow.
	}
}
