package login_test

import (
	"context"
	"testing"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/server/credential"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/login"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// fakeAccounts is the in-memory AccountReader: it records the (provider, providerAccountID) it was asked
// for and returns a fixed account or a typed error, so the authenticator's logic is tested without a DB.
type fakeAccounts struct {
	account       persistence.Account
	err           error
	gotProvider   string
	gotAccountKey string
}

func (f *fakeAccounts) AccountFor(_ context.Context, provider, providerAccountID string) (persistence.Account, error) {
	f.gotProvider = provider
	f.gotAccountKey = providerAccountID
	if f.err != nil {
		return persistence.Account{}, f.err
	}
	return f.account, nil
}

// TestAuthenticate_HappyPath proves a matching credential resolves to the linked user id, and that the
// email is normalized (trimmed + lowercased) into the password provider's provider_account_id lookup key.
func TestAuthenticate_HappyPath(t *testing.T) {
	t.Parallel()
	userID := uuid.New()
	hash, err := credential.Hash("eden")
	if err != nil {
		t.Fatalf("hash: %v", err)
	}
	accounts := &fakeAccounts{account: persistence.Account{UserID: userID, PasswordHash: hash}}
	authenticator := login.NewPasswordAuthenticator(accounts)

	got, err := authenticator.Authenticate(context.Background(), login.Credentials{Email: "  Ann@Eden.Local ", Password: "eden"})
	if err != nil {
		t.Fatalf("Authenticate = %v, want nil", err)
	}
	if got != userID {
		t.Fatalf("Authenticate returned %s, want %s", got, userID)
	}
	if accounts.gotProvider != persistence.ProviderPassword {
		t.Fatalf("looked up provider %q, want %q", accounts.gotProvider, persistence.ProviderPassword)
	}
	if accounts.gotAccountKey != "ann@eden.local" {
		t.Fatalf("looked up provider_account_id %q, want the normalized email ann@eden.local", accounts.gotAccountKey)
	}
}

// TestAuthenticate_WrongPasswordIsUnauthenticated proves a bad password is a typed KindUnauthenticated.
func TestAuthenticate_WrongPasswordIsUnauthenticated(t *testing.T) {
	t.Parallel()
	hash, err := credential.Hash("right")
	if err != nil {
		t.Fatalf("hash: %v", err)
	}
	authenticator := login.NewPasswordAuthenticator(&fakeAccounts{account: persistence.Account{UserID: uuid.New(), PasswordHash: hash}})

	_, err = authenticator.Authenticate(context.Background(), login.Credentials{Email: "ann@eden.local", Password: "wrong"})
	if errors.KindOf(err) != errors.KindUnauthenticated {
		t.Fatalf("Authenticate(wrong password) Kind = %v, want KindUnauthenticated", errors.KindOf(err))
	}
}

// TestAuthenticate_MissingAccountIsUnauthenticated proves a missing account (the facade's KindNotFound) is
// COLLAPSED to KindUnauthenticated (the same 401 as a wrong password) — never a 404 that reveals the email
// is unknown.
func TestAuthenticate_MissingAccountIsUnauthenticated(t *testing.T) {
	t.Parallel()
	authenticator := login.NewPasswordAuthenticator(&fakeAccounts{err: errors.New(errors.KindNotFound, "account not found")})

	_, err := authenticator.Authenticate(context.Background(), login.Credentials{Email: "ghost@eden.local", Password: "x"})
	if errors.KindOf(err) != errors.KindUnauthenticated {
		t.Fatalf("Authenticate(missing account) Kind = %v, want KindUnauthenticated (not 404)", errors.KindOf(err))
	}
}

// TestNormalizeEmail proves the normalization (trim + lowercase) the seed and the authenticator share.
func TestNormalizeEmail(t *testing.T) {
	t.Parallel()
	cases := []struct{ in, want string }{
		{in: "  Ann@Eden.Local ", want: "ann@eden.local"},
		{in: "BOSS@EDEN.LOCAL", want: "boss@eden.local"},
		{in: "already@lower.com", want: "already@lower.com"},
	}
	for _, c := range cases {
		if got := login.NormalizeEmail(c.in); got != c.want {
			t.Fatalf("NormalizeEmail(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}
