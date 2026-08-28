package mint_test

import (
	"bytes"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/secrets/internal/mint"
)

// These tests exercise the mint seam through its EXPORTED API only (package mint_test), and they
// deliberately do NOT import the secrets package. That isolation is the whole point: in a real
// process secrets.init() Registers the hook before any importer of secretstest reaches Hook(), so
// the unregistered-panic branch is unreachable through the normal graph. A black-box test that
// never triggers secrets.init() leaves the hook unregistered, which is the only way to cover that
// guard branch — and to prove Register/Hook round-trip the constructor faithfully.

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) covers the mint seam too. mint holds a single function variable and spawns no
// goroutine, so the only ignore is the benign runtime poller root; threshold is ZERO leaks.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}

// TestHookPanicsWhenUnregistered covers the guard branch: Hook() called before any Register must
// panic with a clear message rather than return a nil constructor (which would NPE at the call
// site). Because this test binary never imports secrets, secrets.init() never runs, so the hook
// is genuinely unregistered here — the only context that exercises the branch. It must run BEFORE
// any Register call in this binary, so it does not call t.Parallel() (a parallel sibling could
// Register first and mask the panic).
//
//nolint:paralleltest // mutates the package-global hook via the unregistered→Register ordering; must run serially.
func TestHookPanicsWhenUnregistered(t *testing.T) {
	defer func() {
		if recover() == nil {
			t.Fatal("Hook() did not panic when the minting hook was unregistered")
		}
	}()
	_ = mint.Hook()
}

// TestRegisterThenHookRoundTrips covers the happy path: Register installs a constructor and Hook
// returns THAT constructor, which builds from the bytes it is handed. The seam must not mutate or
// alias the constructor's behavior. It runs after the unregistered case (no t.Parallel) so the two
// do not race over the package-global hook.
//
//nolint:paralleltest // mutates the package-global hook; must run serially after the unregistered case.
func TestRegisterThenHookRoundTrips(t *testing.T) {
	var gotInput []byte
	mint.Register(func(plaintext []byte) any {
		gotInput = plaintext
		return string(plaintext) // a stand-in payload; the real one returns *secrets.Secret
	})

	got := mint.Hook()
	if got == nil {
		t.Fatal("Hook() returned nil after Register")
	}
	out, ok := got([]byte("payload")).(string)
	if !ok {
		t.Fatalf("constructor returned a non-string stand-in payload")
	}
	if out != "payload" {
		t.Errorf("constructor produced %q, want %q", out, "payload")
	}
	if !bytes.Equal(gotInput, []byte("payload")) {
		t.Errorf("constructor saw input %q, want %q (Hook must pass bytes through unchanged)", gotInput, "payload")
	}
}
