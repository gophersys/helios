// Package identity builds the gateway's request-identity verifier from the secrets seam. It is the
// one place the JWT signing key is resolved (through the secrets.Provider redaction port) and turned
// into the edenhttp dev-JWT verifier the spine's Middleware drives. The package name is `identity`
// per HNS-1 (the banned token `auth` becomes `identity`, rule 11).
//
// The dev-JWT HMAC verifier is the template's default identity path (behind auth even locally,
// ADR-0022 #3) — a complete implementation, not a stub. A generated app that fronts a real IdP binds
// its own edenhttp.TokenVerifier behind the SAME port here — the Middleware and the routes never change.
package identity

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// NewVerifier resolves the JWT signing secret from ref through the secrets port and returns the
// CONCRETE edenhttp dev-JWT HMAC verifier built over it (return-concrete). The server wires the SAME
// verifier two ways: wrapped in NewDBVerifier as the spine's authenticate-and-DB-authorize TokenVerifier,
// AND exposed (its Sign method) to the /auth/login handler to MINT a token — one signing key both mints
// and verifies. The secret is used ONLY to construct the verifier and is zeroized immediately after (the
// secrets.Use point-of-use scope) — it never reaches a log or a field. A missing/denied secret is a
// wrapped, inspectable error; the value never appears in it.
func NewVerifier(ctx context.Context, provider secrets.Provider, ref secrets.Reference) (*edenhttp.HMACVerifier, error) {
	if ref.IsZero() {
		return nil, errors.New(errors.KindInvalid, "identity: a JWT secret Reference is required (the gateway is behind auth even locally)")
	}
	secret, err := provider.Resolve(ctx, ref)
	if err != nil {
		return nil, errors.Wrap(errors.KindOf(err), "identity: resolve jwt signing secret", err)
	}
	defer secret.Zeroize()

	var verifier *edenhttp.HMACVerifier
	useErr := secret.Use(func(plaintext []byte) error {
		built, buildErr := edenhttp.NewHMACVerifier(string(plaintext))
		if buildErr != nil {
			return errors.Wrap(errors.KindInvalid, "identity: new hmac verifier", buildErr)
		}
		verifier = built
		return nil
	})
	if useErr != nil {
		return nil, errors.Wrap(errors.KindInvalid, "identity: build jwt verifier", useErr)
	}
	return verifier, nil
}
