//go:build lifecycle

package vaultadapter_test

import (
	"context"
	"testing"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"
)

// newAdapterErr builds a ModeUserpass adapter over transport and RETURNS the construction error (no
// *testing.T) — the lifecycle LifecycleFactory needs the error in band.
func newAdapterErr(transport vaultadapter.Transport) (*vaultadapter.Adapter, error) {
	return vaultadapter.New(
		vaultadapter.Config{Address: "http://127.0.0.1:8200", Mode: vaultadapter.ModeUserpass},
		vaultadapter.Dependencies{Username: "eden", Password: "passw0rd", Transport: transport},
	)
}

// TestLifecycle_VaultResolvedSecretZeroizeIdempotent is the full-object-lifecycle conformance
// (ADR-0020 dimension (c)) for the handle the Vault backend VENDS: a *secrets.Secret resolved
// through the adapter. The probe maps the LifecycleProbe port onto a Secret produced by a real
// adapter.Resolve over a seeded fake transport, so the drive exercises the adapter's mint path:
// construct (Resolve) -> use (read the value) -> first Close (Zeroize) -> SECOND Close is a no-op
// (double-Zeroize idempotent) -> CountOwned()==0 (no readable residue). The orphan-goroutine half
// is goleak.VerifyNone. Tagged //go:build lifecycle so the heavy probe stays out of the fast run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make it flaky.
func TestLifecycle_VaultResolvedSecretZeroizeIdempotent(t *testing.T) {
	defer goleak.VerifyNone(t)

	report := &tReport{t: t}
	harness := &tHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newVaultSecretProbe)
}

// vaultLifecyclePlaintext is the value the probe seeds and reads back through a real Resolve. It is
// a non-secret fixture token (this is a lifecycle drive, not a redaction drive) that doubles as a
// residue needle: CountOwned proves it is wiped after Close.
const vaultLifecyclePlaintext = "vault-lifecycle-plaintext-value"

// vaultSecretProbe binds a *secrets.Secret RESOLVED THROUGH THE ADAPTER to the LifecycleProbe port.
type vaultSecretProbe struct {
	secret *secrets.Secret
}

// newVaultSecretProbe resolves a fresh Secret through a real *vaultadapter.Adapter (seeded fake
// transport) — the construction half of the lifecycle: the adapter's parse→token→KV→mint path runs
// for real, then the lifecycle driver exercises the resulting handle.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newVaultSecretProbe(ctx context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	transport := &fakeTransport{kv: map[string]map[string]any{
		"eden/data/lifecycle": kvEnvelope(map[string]any{"token": vaultLifecyclePlaintext}),
	}}
	adapter, err := newAdapterErr(transport)
	if err != nil {
		return nil, func() {}, err
	}
	sec, err := adapter.Resolve(ctx, secrets.Ref("vault://eden/lifecycle#token"))
	if err != nil {
		return nil, func() {}, err
	}
	probe := &vaultSecretProbe{secret: sec}
	teardown := func() { probe.secret.Zeroize() }
	return probe, teardown, nil
}

// Use reads the resolved Secret once via its only legitimate read path, asserting the adapter
// minted exactly the seeded plaintext.
func (p *vaultSecretProbe) Use(context.Context) error {
	return p.secret.Use(func(b []byte) error {
		if string(b) != vaultLifecyclePlaintext {
			return secrets.NotFoundError{} // a wrong read is a lifecycle failure the driver surfaces
		}
		return nil
	})
}

// Close zeroizes the Secret; the library guarantees Zeroize is idempotent, so the driver's SECOND
// call must also be a clean no-op (the double-close invariant).
func (p *vaultSecretProbe) Close(context.Context) error {
	p.secret.Zeroize()
	return nil
}

// CountOwned reports how many readable plaintext bytes the Secret still exposes through Use; after
// Zeroize it must be zero.
func (p *vaultSecretProbe) CountOwned(context.Context) (int, error) {
	var n int
	err := p.secret.Use(func(b []byte) error { n = len(b); return nil })
	if err != nil {
		if is[secrets.ZeroizedError](err) {
			return 0, nil
		}
		return 0, err
	}
	return n, nil
}

// ── *testing.T adapters for the testing.Harness / testing.Report ports ──────────────────────────.

type tReport struct{ t *testing.T }

func (r *tReport) Errorf(format string, args ...any) { r.t.Errorf(format, args...) }
func (r *tReport) Fatalf(format string, args ...any) { r.t.Fatalf(format, args...) }
func (r *tReport) Skipf(format string, args ...any)  { r.t.Skipf(format, args...) }

type tHarness struct {
	t   *testing.T
	ctx context.Context
}

//nolint:ireturn // contract: Harness.Clock returns the Clock port; unused on the lifecycle path.
func (*tHarness) Clock() libtesting.Clock { return nil }

//nolint:ireturn // contract: Harness.RandomSource returns the RandomSource port; unused here.
func (*tHarness) RandomSource() libtesting.RandomSource { return nil }

func (*tHarness) Has(string) bool { return false }

func (h *tHarness) Context() context.Context { return h.ctx }

func (h *tHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }
