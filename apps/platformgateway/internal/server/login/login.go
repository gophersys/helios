// Package login is the OAuth-ready authentication seam: the Authenticator port that turns a set of
// credentials into the Eden user id the login flow mints a JWT for, and the password implementation of
// it. It is the SINGLE place the gateway resolves "who is this caller" — the seam a real IdP (Google,
// GitHub) drops in behind without touching the mint-or-authorize path.
//
// The IOTEA invariant (PERMISSION_SYSTEM_GUIDE, prior art at MateoSegura/IOTEA-archive): the JWT carries
// ONLY the user id; permissions are loaded from the DB per request (the DB-driven verifier), and the
// admin role bypasses checks. OAuth changes only USER RESOLUTION — a GoogleAuthenticator/
// GithubAuthenticator implements the SAME Authenticate contract by exchanging the OAuth code → the
// provider profile → find-or-create the user + the linked account → return the user id; the rest of the
// flow (mint the JWT, then DB-driven authorize) is IDENTICAL. See PasswordAuthenticator for the worked
// shape; an OAuth authenticator differs only in how it obtains the (provider, providerAccountID) pair
// and that it find-or-creates rather than verifying a password.
//
// The package name is `login` (the entry the flow reads) — not `auth` (banned, rule 11). It owns the
// authentication CONCEPT (resolve a caller to a user id); `identity` owns token VERIFICATION (the spine
// seam), and the two stay separate homes.
package login

import (
	"context"
	"strings"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/server/credential"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// Credentials is the input an Authenticator resolves to a user id. For the password provider it is an
// email + a plaintext password; an OAuth authenticator would carry an OAuth authorization code instead
// (a future field), but the port's SHAPE — credentials in, user id out — is provider-agnostic, which is
// what lets a new provider slot in behind the same Authenticate contract. The plaintext Password is a
// credential value: it is read only by credential.Verify and is NEVER logged or put on an error.
type Credentials struct {
	// Email is the login handle (the password provider lowercases it to the provider_account_id).
	Email string
	// Password is the plaintext password the password provider checks against the stored bcrypt digest.
	Password string
}

// Authenticator is the consumer-defined authentication port the /auth/login handler drives: it turns a
// set of Credentials into the authenticated Eden user id, or a typed error. It is the SHAPE OF THE NEED
// (one method, well under the 10 §9 ceiling), not a mirror of a password library — the password
// implementation realizes it here, and a production deployment binds a Google/GitHub OAuth authenticator
// behind the SAME port without touching the login handler, the mint, or the DB-driven authorize.
//
// Authenticate MUST surface a failed authentication as a typed KindUnauthenticated error (→ 401), and it
// must NOT reveal which factor failed (a missing account and a bad password are the same 401 — never
// "no such email"). It reads no env and no clock of its own.
type Authenticator interface {
	// Authenticate resolves the credentials to the authenticated user id. A missing account or a bad
	// credential is a typed KindUnauthenticated error; the user id is returned only on success.
	Authenticate(ctx context.Context, credentials Credentials) (uuid.UUID, error)
}

// AccountReader is the one-method persistence port the password authenticator needs: the credential read
// by (provider, providerAccountID). The concrete *persistence.Accounts satisfies it; a fake satisfies it
// for the unit lane. It is the shape of the need — the authenticator does not depend on the whole
// persistence facade, only the credential lookup.
type AccountReader interface {
	AccountFor(ctx context.Context, provider, providerAccountID string) (persistence.Account, error)
}

// PasswordAuthenticator is the local-credential Authenticator: it looks up the "password" account for
// the lowercased email, verifies the plaintext against the stored bcrypt digest, and returns the linked
// user id. It is the worked reference for the OAuth seam — a GoogleAuthenticator would implement the same
// Authenticate by exchanging the OAuth code for a profile, find-or-creating the user + account, and
// returning the user id (no password verify step); the mint + DB-driven authorize downstream are
// unchanged.
//
// Construct via NewPasswordAuthenticator. It holds only the AccountReader port, so it is safe for
// concurrent use.
type PasswordAuthenticator struct {
	accounts AccountReader
}

// NewPasswordAuthenticator builds the password authenticator over the account-read port (accept
// interfaces, return concrete — the caller receives a usable *PasswordAuthenticator, the Authenticator
// the login handler drives).
func NewPasswordAuthenticator(accounts AccountReader) *PasswordAuthenticator {
	return &PasswordAuthenticator{accounts: accounts}
}

// Authenticate resolves email+password to the linked user id. It lowercases the email to the password
// provider's provider_account_id, loads the "password" account, and verifies the plaintext against the
// stored bcrypt digest. A MISSING account and a BAD password are BOTH a typed KindUnauthenticated error
// (→ 401) carrying NO caller-supplied identifier — so the login surface never reveals which of
// email/password was wrong. The user id is returned only on a verified credential.
func (p *PasswordAuthenticator) Authenticate(ctx context.Context, credentials Credentials) (uuid.UUID, error) {
	providerAccountID := normalizeEmail(credentials.Email)
	account, err := p.accounts.AccountFor(ctx, persistence.ProviderPassword, providerAccountID)
	if err != nil {
		// A missing account (the facade's KindNotFound) is an authentication failure, NOT a 404: collapse
		// it to KindUnauthenticated so the spine answers 401 and the response never reveals that the email
		// is unknown. The cause is preserved for the server log; the message carries no identifier.
		return uuid.UUID{}, errors.Wrap(errors.KindUnauthenticated, "login: no password account for credentials", err)
	}
	if err := credential.Verify(account.PasswordHash, credentials.Password); err != nil {
		// credential.Verify already returns KindUnauthenticated on a mismatch; re-wrap with this layer's
		// context. Same Kind, same 401 — indistinguishable from the missing-account case by design.
		return uuid.UUID{}, errors.Wrap(errors.KindUnauthenticated, "login: password does not match", err)
	}
	return account.UserID, nil
}

// NormalizeEmail folds an email to the password provider's provider_account_id form: trimmed +
// lowercased. It is the ONE home for that normalization (10 §9) — the login authenticator AND the
// composition root's password-account seed both call it, so a user seeded under " Ann@Eden.Local " logs
// in as "ann@eden.local" and the (provider, provider_account_id) key matches on both sides.
func NormalizeEmail(email string) string { return normalizeEmail(email) }

// normalizeEmail is the unexported implementation NormalizeEmail and Authenticate share.
func normalizeEmail(email string) string { return strings.ToLower(strings.TrimSpace(email)) }

// compile-time assertion: *PasswordAuthenticator is an Authenticator (the port the login handler drives;
// an OAuth authenticator would carry the same assertion).
var _ Authenticator = (*PasswordAuthenticator)(nil)
