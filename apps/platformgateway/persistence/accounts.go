package persistence

import (
	"context"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgtype"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/persistence/generated"
)

// Provider names a credential provider in the IOTEA-style linked-identity model. The vocabulary is
// closed: "password" (a local credential whose provider_account_id is the lowercased email and whose
// PasswordHash holds the bcrypt digest) plus the OAuth providers "google"/"github" (the
// provider_account_id is the provider's stable account id; PasswordHash is empty). The login
// Authenticator and the seed cite these constants, never a bare string literal.
const (
	// ProviderPassword is the local-credential provider: provider_account_id == lowercased email,
	// PasswordHash == the bcrypt digest.
	ProviderPassword = "password"
	// ProviderGoogle is the Google OAuth provider (OAuth-ready: a GoogleAuthenticator would EnsureAccount
	// with this provider + the OAuth profile's account id, PasswordHash empty).
	ProviderGoogle = "google"
	// ProviderGitHub is the GitHub OAuth provider (OAuth-ready, the same find-or-create shape as Google).
	ProviderGitHub = "github"
)

// Account is the domain-facing linked-identity row the login Authenticator receives — plain Go scalars
// (uuid.UUID, string), NOT the generated pgtype-laden model. It links a provider identity (Provider +
// ProviderAccountID) to an Eden user (UserID); PasswordHash is the bcrypt digest the password provider
// checks against ("" for an OAuth account, whose password_hash column is NULL). The facade is the seam
// that converts the typed sqlc row into this shape so the Authenticator never imports pgtype.
//
// PasswordHash is a credential digest: it is read only by credential.Verify and is NEVER logged or put
// on an error field (the gosec/secretscan guard depends on it staying off every surfaced artifact).
type Account struct {
	ID                uuid.UUID
	UserID            uuid.UUID
	Provider          string
	ProviderAccountID string
	PasswordHash      string
}

// Accounts is the typed store over the `accounts` table (the linked-identity model). It wraps the
// sqlc-generated Querier (never string-built SQL) and is the ONE place pgx's not-found sentinel becomes a
// typed errors.KindNotFound — the login Authenticator maps that Kind to a 401 (an absent account is an
// unauthenticated caller, never revealed as "no such email"). It also owns the idempotent find-or-create
// seed (EnsureAccount). It holds only the Querier (over the concurrency-safe pool), so it is safe for
// concurrent use.
type Accounts struct {
	queries generated.Querier
}

// AccountFor resolves a (provider, providerAccountID) pair to its linked Account — the credential read
// the login Authenticator runs. For the password provider, providerAccountID is the lowercased email; the
// returned Account carries the linked UserID and the bcrypt PasswordHash to check against. A missing
// account is a typed errors.KindNotFound (not a bare pgx sentinel), so the Authenticator branches on Kind
// and answers 401 — never leaking which of provider/account-id was wrong.
func (a *Accounts) AccountFor(ctx context.Context, provider, providerAccountID string) (Account, error) {
	row, err := a.queries.GetAccountByProvider(ctx, generated.GetAccountByProviderParams{
		Provider:          provider,
		ProviderAccountID: providerAccountID,
	})
	if err != nil {
		if isNoRows(err) {
			return Account{}, notFoundAccount(provider)
		}
		return Account{}, errors.Wrap(errors.KindInternal, "persistence: get account by provider", err)
	}
	return fromAccountRow(&row), nil
}

// EnsureAccount idempotently seeds a linked identity (INSERT ... ON CONFLICT (provider,
// provider_account_id) DO NOTHING). It is the password-account startup seed AND the shape an OAuth
// find-or-create reuses: the composition root calls it on every boot after the user seed, so a fresh
// database gets the default user's password account and an existing one is left untouched. The id is
// supplied so the account's id is stable across restarts. passwordHash is the bcrypt digest for the
// password provider, or "" for an OAuth account (stored as a NULL password_hash). The hash is a
// credential value — it is passed here and never logged.
func (a *Accounts) EnsureAccount(ctx context.Context, id, userID uuid.UUID, provider, providerAccountID, passwordHash string) error {
	if err := a.queries.EnsureAccount(ctx, generated.EnsureAccountParams{
		ID:                toPgUUID(id),
		UserID:            toPgUUID(userID),
		Provider:          provider,
		ProviderAccountID: providerAccountID,
		PasswordHash:      toPgText(passwordHash),
	}); err != nil {
		return errors.Wrap(errors.KindUnavailable, "persistence: ensure account", err)
	}
	return nil
}

// notFoundAccount builds the canonical typed not-found error for an absent provider identity. Only the
// provider name (a safe enum scalar — "password"/"google"/"github") rides the error's field set; the
// provider_account_id (an email for the password provider) is NOT attached, so the failure path stays
// free of caller-supplied identifiers. Declared once so the Kind + message are consistent.
func notFoundAccount(provider string) error {
	return errors.New(errors.KindNotFound, "persistence: account not found").
		WithField("provider", provider)
}

// fromAccountRow converts a generated (pgtype-laden) row to the domain Account. The uuid bytes are
// unwrapped here and the nullable password_hash is flattened to "" when NULL (an OAuth account) — the
// single conversion seam, so the Authenticator never touches pgtype. The row is taken by pointer (a heavy
// pgtype-laden struct) to avoid copying it per call.
func fromAccountRow(row *generated.Account) Account {
	hash := ""
	if row.PasswordHash.Valid {
		hash = row.PasswordHash.String
	}
	return Account{
		ID:                uuid.UUID(row.ID.Bytes),
		UserID:            uuid.UUID(row.UserID.Bytes),
		Provider:          row.Provider,
		ProviderAccountID: row.ProviderAccountID,
		PasswordHash:      hash,
	}
}

// toPgText wraps a domain string as the pgtype.Text the generated Querier takes for a nullable text
// column. An empty string maps to SQL NULL (Valid=false), so an OAuth account (no password) stores a NULL
// password_hash rather than an empty digest. The single conversion seam for the nullable column.
func toPgText(value string) pgtype.Text {
	if value == "" {
		return pgtype.Text{}
	}
	return pgtype.Text{String: value, Valid: true}
}
