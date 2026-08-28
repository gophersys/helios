//go:build lifecycle

package platformconnectoradapter_test

import (
	"context"
	"fmt"
	"testing"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/platformconnectoradapter"
)

// connectorLifecyclePlaintext is the value the probe seeds and reads back through a real Resolve. It is
// a non-secret fixture token (this is a lifecycle drive, not a redaction drive) that doubles as a
// residue needle: CountOwned proves it is wiped after Close.
const connectorLifecyclePlaintext = "connector-lifecycle-plaintext-value"

// TestLifecycle_ConnectorResolvedSecretZeroizeIdempotent is the full-object-lifecycle conformance
// (ADR-0020 dimension (c)) for the handle the connector backend VENDS: a *secrets.Secret resolved
// through the adapter. The probe maps the LifecycleProbe port onto a Secret produced by a real
// adapter.Resolve over a seeded fake transport + real envelope crypto, so the drive exercises the
// adapter's load → Unseal → mint path: construct (Resolve) -> use (read the value) -> first Close
// (Zeroize) -> SECOND Close is a no-op (double-Zeroize idempotent) -> CountOwned()==0 (no readable
// residue). The orphan-goroutine half is goleak.VerifyNone. Tagged //go:build lifecycle so the heavy
// probe stays out of the fast run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make it flaky.
func TestLifecycle_ConnectorResolvedSecretZeroizeIdempotent(t *testing.T) {
	defer goleak.VerifyNone(t)

	report := &tReport{t: t}
	harness := &tHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newConnectorSecretProbe)
}

// connectorSecretProbe binds a *secrets.Secret RESOLVED THROUGH THE ADAPTER to the LifecycleProbe port.
type connectorSecretProbe struct {
	secret *secrets.Secret
}

// newConnectorSecretProbe resolves a fresh Secret through a real *platformconnectoradapter.Adapter
// (seeded fake transport + real envelope crypto) — the construction half of the lifecycle: the
// adapter's load → Unseal → mint path runs for real, then the lifecycle driver exercises the handle.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newConnectorSecretProbe(ctx context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	const id = "lifecycle-connector"
	reporter := panicReporter{id: id}
	transport := &fakeTransport{records: map[string]platformconnectoradapter.SealedRecord{
		id: sealValue(reporter, newSealer(reporter), connectorLifecyclePlaintext),
	}}
	adapter, err := platformconnectoradapter.New(
		platformconnectoradapter.Config{KEK: secrets.Ref(kekReference), KEKVersion: 1},
		platformconnectoradapter.Deps{Loader: transport, Secrets: newKEKProvider()},
	)
	if err != nil {
		return nil, func() {}, err
	}
	sec, err := adapter.Resolve(ctx, secrets.Ref("eden://connector/"+id))
	if err != nil {
		return nil, func() {}, err
	}
	probe := &connectorSecretProbe{secret: sec}
	teardown := func() { probe.secret.Zeroize() }
	return probe, teardown, nil
}

// Use reads the resolved Secret once via its only legitimate read path, asserting the adapter minted
// exactly the seeded plaintext.
func (p *connectorSecretProbe) Use(context.Context) error {
	return p.secret.Use(func(b []byte) error {
		if string(b) != connectorLifecyclePlaintext {
			return secrets.NotFoundError{} // a wrong read is a lifecycle failure the driver surfaces
		}
		return nil
	})
}

// Close zeroizes the Secret; the library guarantees Zeroize is idempotent, so the driver's SECOND call
// must also be a clean no-op (the double-close invariant).
func (p *connectorSecretProbe) Close(context.Context) error {
	p.secret.Zeroize()
	return nil
}

// CountOwned reports how many readable plaintext bytes the Secret still exposes through Use; after
// Zeroize it must be zero.
func (p *connectorSecretProbe) CountOwned(context.Context) (int, error) {
	var n int
	err := p.secret.Use(func(b []byte) error { n = len(b); return nil })
	if err != nil {
		if errors.IsType[secrets.ZeroizedError](err) {
			return 0, nil
		}
		return 0, err
	}
	return n, nil
}

// panicReporter is a fatalReporter that panics on failure — the lifecycle factory has no *testing.T in
// scope, and a seeding fault here is a programmer error (a bad KEK fixture), not a test assertion. It
// lets newConnectorSecretProbe reuse the shared sealValue/newSealer helpers.
type panicReporter struct{ id string }

func (panicReporter) Helper() {}

func (p panicReporter) Fatalf(format string, args ...any) {
	panic("platformconnectoradapter lifecycle seed for " + p.id + ": " + fmt.Sprintf(format, args...))
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
