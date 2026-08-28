//go:build lifecycle

package objectstorage_test

import (
	"bytes"
	"context"
	"io"
	"sync"
	"testing"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/objectstorage/objectstoragetest"
)

// TestLifecycle_GetReaderDoubleCloseIdempotent is the full-object-lifecycle conformance (ADR-0020
// dimension (c)) for the handle the store VENDS: the io.ReadCloser returned by Get. The probe maps
// the LifecycleProbe port onto a reader opened by a real fake-backed *Client.Get, so the drive
// exercises Put → Get: construct (open) → use (read the bytes) → first Close → SECOND Close is a
// no-op (double-close idempotent) → CountOwned()==0 (the reader is released). The orphan-goroutine
// half is goleak.VerifyNone. Tagged //go:build lifecycle so the heavy probe stays out of the fast
// run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make it flaky.
func TestLifecycle_GetReaderDoubleCloseIdempotent(t *testing.T) {
	defer goleak.VerifyNone(t)

	report := &tReport{t: t}
	harness := &tHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newReaderProbe)
}

// readerProbe binds a *Client.Get reader to the LifecycleProbe port. It tracks open/closed state so
// CountOwned reports 1 while the reader is live and 0 after Close, and so a second Close is a clean
// no-op (the double-close invariant the io.ReadCloser must satisfy).
type readerProbe struct {
	mu     sync.Mutex
	reader io.ReadCloser
	closed bool
}

// newReaderProbe Puts the seeded payload through a real fake-backed *Client, then Gets it back and
// binds the resulting reader to the lifecycle port — the construction half: the store's
// validate→Put→Get path runs for real, then the driver exercises the handle.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newReaderProbe(ctx context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	objectStore, err := objectstorage.New(objectstorage.Config{}, objectstorage.Deps{Backend: objectstoragetest.NewBackend()})
	if err != nil {
		return nil, func() {}, err
	}
	ref, err := objectstorage.NewRef("eden", "lifecycle/object.bin")
	if err != nil {
		return nil, func() {}, err
	}
	payload := objectstoragetest.SeededPayload
	if _, err := objectStore.Put(ctx, ref, bytes.NewReader(payload), objectstorage.PutOptions{Size: int64(len(payload))}); err != nil {
		return nil, func() {}, err
	}
	reader, _, err := objectStore.Get(ctx, ref)
	if err != nil {
		return nil, func() {}, err
	}
	probe := &readerProbe{reader: reader}
	teardown := func() { _ = probe.Close(ctx) }
	return probe, teardown, nil
}

// Use reads the whole object through its only read path, asserting the store vended exactly the
// seeded payload.
func (p *readerProbe) Use(context.Context) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	got, err := io.ReadAll(p.reader)
	if err != nil {
		return err
	}
	if !bytes.Equal(got, objectstoragetest.SeededPayload) {
		return objectstorage.NotFoundError{} // a wrong read is a lifecycle failure the driver surfaces
	}
	return nil
}

// Close closes the reader; a second Close must be a clean no-op (the double-close invariant).
func (p *readerProbe) Close(context.Context) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return nil
	}
	p.closed = true
	return p.reader.Close()
}

// CountOwned reports how many open readers the probe still owns: 1 while live, 0 after Close.
func (p *readerProbe) CountOwned(context.Context) (int, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return 0, nil
	}
	return 1, nil
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

//nolint:ireturn // contract: Harness.Clock returns the Clock port; unused on this lifecycle path.
func (*tHarness) Clock() libtesting.Clock { return nil }

//nolint:ireturn // contract: Harness.RandomSource returns the RandomSource port; unused here.
func (*tHarness) RandomSource() libtesting.RandomSource { return nil }

func (*tHarness) Has(string) bool { return false }

func (h *tHarness) Context() context.Context { return h.ctx }

func (h *tHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }
