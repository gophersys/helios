//go:build lifecycle

package secrets_test

import (
	"context"
	"testing"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// TestLifecycle_SecretZeroizeIdempotentNoResidue is the full-object-lifecycle conformance
// (ADR-0020 dimension (c)) for the secrets closeable handle: a *secrets.Secret. The Secret's
// "Close" is Zeroize — it wipes and marks the bytes spent. The probe maps the LifecycleProbe
// port onto the Secret: Use reads the plaintext, Close calls Zeroize, and CountOwned reports
// the number of live (un-wiped) plaintext bytes the Secret still exposes through Use. The
// driver asserts construct -> use -> first Close -> SECOND Close is a no-op (double-Zeroize is
// idempotent) -> CountOwned()==0 (no residual readable bytes — the wipe completed and Use is
// now permanently ZeroizedError). The orphan-goroutine half is asserted by goleak.VerifyNone.
// Tagged `//go:build lifecycle` so the probe stays out of the fast unit run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling's goroutines would make it flaky, so the lifecycle/leak probe runs serially.
func TestLifecycle_SecretZeroizeIdempotentNoResidue(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c)

	report := &tReport{t: t}
	harness := &tHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newSecretProbe)
}

// secretLifecyclePlaintext is the bytes the lifecycle probe mints and reads back. It is a
// non-secret fixture token (this is a lifecycle drive, not a redaction drive), but it doubles
// as a leak needle: CountOwned proves it is wiped after Close.
const secretLifecyclePlaintext = "lifecycle-plaintext-value"

// secretProbe binds a *secrets.Secret to the testing.LifecycleProbe port. Its "owned resource"
// is the readable plaintext: CountOwned reads the number of bytes Use can still observe, which
// drops to 0 exactly once at Zeroize.
type secretProbe struct {
	secret *secrets.Secret
}

// newSecretProbe mints a fresh, real *secrets.Secret via the test minting seam. It is the
// testing.LifecycleFactory the driver invokes once per run.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newSecretProbe(_ context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	sec := secretstest.MintSecret([]byte(secretLifecyclePlaintext))
	probe := &secretProbe{secret: sec}
	// Teardown is a final best-effort Zeroize so a failed assertion never leaves readable bytes.
	teardown := func() { probe.secret.Zeroize() }
	return probe, teardown, nil
}

// Use exercises the live Secret once via its only legitimate read path, asserting it exposes
// the minted plaintext before any Close.
func (p *secretProbe) Use(context.Context) error {
	return p.secret.Use(func(b []byte) error {
		if string(b) != secretLifecyclePlaintext {
			return secrets.NotFoundError{} // a wrong read is a lifecycle failure the driver surfaces
		}
		return nil
	})
}

// Close zeroizes the Secret. The library guarantees Zeroize is idempotent, so the driver's
// SECOND call must also be a clean no-op (the double-close invariant).
func (p *secretProbe) Close(context.Context) error {
	p.secret.Zeroize()
	return nil
}

// CountOwned reports how many readable plaintext bytes the Secret still exposes through Use.
// After Zeroize it must be zero: the backing bytes were wiped exactly once and Use is now
// permanently ZeroizedError, so no readable residue is owned.
func (p *secretProbe) CountOwned(context.Context) (int, error) {
	var n int
	err := p.secret.Use(func(b []byte) error {
		n = len(b)
		return nil
	})
	if err != nil {
		// After Zeroize, Use returns ZeroizedError — no readable bytes are owned.
		if is[secrets.ZeroizedError](err) {
			return 0, nil
		}
		return 0, err
	}
	return n, nil
}

// ── *testing.T adapters for the testing.Harness / testing.Report ports ────────────────.

// tReport adapts *testing.T to the testing.Report sink AssertLifecycle reports into.
type tReport struct{ t *testing.T }

func (r *tReport) Errorf(format string, args ...any) { r.t.Errorf(format, args...) }
func (r *tReport) Fatalf(format string, args ...any) { r.t.Fatalf(format, args...) }
func (r *tReport) Skipf(format string, args ...any)  { r.t.Skipf(format, args...) }

// tHarness adapts *testing.T's lifecycle needs to the testing.Harness port. Only Cleanup and
// Context are exercised by AssertLifecycle; the deterministic-source accessors are part of the
// frozen 5-method port and are never called on this path. Cleanup delegates to *testing.T.Cleanup
// so the teardown runs (LIFO) at test end — keeping the goleak check honest even on a mid-run
// assertion failure.
type tHarness struct {
	t   *testing.T
	ctx context.Context
}

//nolint:ireturn // contract §2: Harness.Clock returns the Clock port; unused on the lifecycle path.
func (*tHarness) Clock() libtesting.Clock { return nil }

//nolint:ireturn // contract §2: Harness.RandomSource returns the RandomSource port; unused here.
func (*tHarness) RandomSource() libtesting.RandomSource { return nil }

func (*tHarness) Has(string) bool { return false }

func (h *tHarness) Context() context.Context { return h.ctx }

func (h *tHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }
