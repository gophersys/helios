package vaultadapter

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// internalLoginTransport is a white-box Transport fake: it records the password bytes the adapter
// presented at login (so the test can confirm the login actually consumed the credential) and
// serves one seeded secret. It lives in the internal test package so the test can also reach the
// adapter's unexported passwordSecret field and prove the post-login zeroize.
type internalLoginTransport struct {
	loginCount     int
	loginPassword  string
	tokenInstalled string
	kv             map[string]map[string]any
}

func (t *internalLoginTransport) Login(_ context.Context, _ string, data map[string]any) (string, error) {
	t.loginCount++
	if pw, ok := data["password"].(string); ok {
		t.loginPassword = pw
	}
	return "internal-login-token", nil
}

func (t *internalLoginTransport) SetToken(token string) { t.tokenInstalled = token }

func (t *internalLoginTransport) ReadKeyValue(_ context.Context, apiPath string) (map[string]any, error) {
	if d, ok := t.kv[apiPath]; ok {
		return d, nil
	}
	return nil, nil //nolint:nilnil // documented "no such secret" sentinel mapped to NotFound.
}

// TestZeroize_BootstrapPasswordIsWipedAfterLogin proves the high-severity fix: the userpass
// bootstrap password is NOT retained as resident plaintext for the adapter's lifetime. It is held
// only as a transient *secrets.Secret that is Zeroized the moment the single userpass login attempt
// completes. The test reads the unexported passwordSecret directly (white-box):
//
//   - BEFORE the first Resolve, the password Secret holds the injected credential (Use yields it).
//   - The first Resolve triggers the once-guarded login, which presents that credential to the
//     transport (asserted via loginPassword), then Zeroizes the Secret.
//   - AFTER the login, the password Secret is spent: Use returns a typed ZeroizedError, i.e. there
//     is no readable plaintext password resident on the adapter.
//
// WEAKEN-TO-CONFIRM: remove the `defer a.passwordSecret.Zeroize()` in ensureToken's ModeUserpass
// branch (i.e. retain the password past login). Then the post-login Use below succeeds with the
// plaintext still readable and the ZeroizedError assertion FAILS — exactly the resident-plaintext
// finding this fix closes.
func TestZeroize_BootstrapPasswordIsWipedAfterLogin(t *testing.T) {
	t.Parallel()

	const password = "bootstrap-userpass-password-do-not-retain"
	transport := &internalLoginTransport{kv: map[string]map[string]any{
		"eden/data/p": {"data": map[string]any{"k": "value"}},
	}}

	adapter, err := New(
		Config{Address: "http://127.0.0.1:8200", Mode: ModeUserpass},
		Deps{Username: "eden", Password: password, Transport: transport},
	)
	if err != nil {
		t.Fatalf("New(ModeUserpass) error = %v", err)
	}

	// Before the bootstrap login, the password Secret is live and holds the injected credential.
	if adapter.passwordSecret == nil {
		t.Fatal("ModeUserpass adapter must mint a password Secret in New")
	}
	pre, err := secrets.Use1(adapter.passwordSecret, func(b []byte) (string, error) { return string(b), nil })
	if err != nil {
		t.Fatalf("password Secret unreadable before login: %v", err)
	}
	if pre != password {
		t.Fatalf("password Secret held %q before login, want the injected credential", pre)
	}

	// First Resolve drives the once-guarded userpass login.
	sec, err := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/p#k"))
	if err != nil {
		t.Fatalf("Resolve error = %v", err)
	}
	sec.Zeroize()

	// The login consumed exactly the injected password.
	if transport.loginCount != 1 {
		t.Errorf("login count = %d, want exactly 1", transport.loginCount)
	}
	if transport.loginPassword != password {
		t.Errorf("login presented password %q, want the injected credential", transport.loginPassword)
	}

	// After login, the password Secret is wiped: NO resident plaintext password remains.
	_, postErr := secrets.Use1(adapter.passwordSecret, func(b []byte) (string, error) { return string(b), nil })
	if !errors.IsType[secrets.ZeroizedError](postErr) {
		t.Fatalf("password Secret still readable after login (error = %v); the bootstrap password "+
			"must be Zeroized, not retained as resident plaintext", postErr)
	}
}

// TestZeroize_BootstrapPasswordWipedEvenOnLoginFailure proves the wipe is unconditional: a failed
// login (the once-guard never retries, so the credential is dead either way) still Zeroizes the
// password Secret, leaving no resident plaintext after a sticky bootstrap error.
//
// WEAKEN-TO-CONFIRM: move the Zeroize out of the deferred position to only the success path; then a
// login-error run leaves the password readable and this ZeroizedError assertion FAILS.
func TestZeroize_BootstrapPasswordWipedEvenOnLoginFailure(t *testing.T) {
	t.Parallel()

	transport := &failingLoginTransport{}
	adapter, err := New(
		Config{Address: "http://127.0.0.1:8200", Mode: ModeUserpass},
		Deps{Username: "eden", Password: "another-password", Transport: transport},
	)
	if err != nil {
		t.Fatalf("New error = %v", err)
	}

	// The login fails; Resolve surfaces a typed error (mapped from the transport failure).
	if _, rerr := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/p#k")); rerr == nil {
		t.Fatal("Resolve with a failing login returned nil error")
	}

	_, postErr := secrets.Use1(adapter.passwordSecret, func(b []byte) (string, error) { return string(b), nil })
	if !errors.IsType[secrets.ZeroizedError](postErr) {
		t.Fatalf("password Secret still readable after a FAILED login (error = %v); the credential "+
			"must be wiped on success OR failure", postErr)
	}
}

// failingLoginTransport always fails Login, to drive the sticky-bootstrap-error path.
type failingLoginTransport struct{}

func (*failingLoginTransport) Login(context.Context, string, map[string]any) (string, error) {
	return "", errors.New(errors.KindUnavailable, "vault login refused")
}
func (*failingLoginTransport) SetToken(string) {}
func (*failingLoginTransport) ReadKeyValue(context.Context, string) (map[string]any, error) {
	return nil, nil //nolint:nilnil // unreached: the login fails before any read.
}
