//go:build lifecycle

package minioadapter_test

import (
	"context"
	"strings"
	"sync"
	"testing"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/objectstorage/minioadapter"
)

// TestLifecycle_AdapterObjectDoubleDeleteIdempotent is the full-object-lifecycle conformance
// (ADR-0020 dimension (c)) for the object an adapter MANAGES, driven over the fake S3: construct
// (Put an object) → use (List confirms it is present) → first Close (Delete it) → SECOND Close is a
// no-op (S3 delete is idempotent) → CountOwned()==0 (the object is gone). The orphan-goroutine half
// is goleak.VerifyNone (the channel-based List must drain, not leak a goroutine). Tagged
// //go:build lifecycle so the heavy probe stays out of the fast run. The REAL-MinIO arm is the
// integration lane.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make it flaky.
func TestLifecycle_AdapterObjectDoubleDeleteIdempotent(t *testing.T) {
	defer goleak.VerifyNone(t)

	report := &tReport{t: t}
	harness := &tHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newObjectProbe)
}

// objectProbe binds an object MANAGED by the adapter (Put then Delete) to the LifecycleProbe port.
type objectProbe struct {
	mu      sync.Mutex
	adapter *minioadapter.Adapter
	ref     objectstorage.ObjectRef
	deleted bool
}

// newObjectProbe Puts an object through a real adapter over the fake S3 (the construction half:
// resolve→client→Put runs for real), then binds it to the lifecycle port.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newObjectProbe(ctx context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	adapter, err := newAdapter(newFakeS3(), seededSecrets())
	if err != nil {
		return nil, func() {}, err
	}
	ref, err := objectstorage.NewRef("eden", "lifecycle/managed.bin")
	if err != nil {
		return nil, func() {}, err
	}
	if _, err := adapter.PutObject(ctx, ref, strings.NewReader("lifecycle-managed-object"), 24, ""); err != nil {
		return nil, func() {}, err
	}
	probe := &objectProbe{adapter: adapter, ref: ref}
	teardown := func() { _ = probe.Close(ctx) }
	return probe, teardown, nil
}

// Use confirms the managed object is present via List (the adapter's channel-drain path).
func (p *objectProbe) Use(ctx context.Context) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	infos, err := p.adapter.ListObjects(ctx, p.ref.Bucket(), p.ref.Key())
	if err != nil {
		return err
	}
	for _, info := range infos {
		if info.Ref == p.ref {
			return nil
		}
	}
	return objectstorage.NotFoundError{Ref: p.ref}
}

// Close deletes the managed object; a second Close must be a clean no-op (S3 delete is idempotent).
func (p *objectProbe) Close(ctx context.Context) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.deleted {
		return nil
	}
	p.deleted = true
	return p.adapter.DeleteObject(ctx, p.ref)
}

// CountOwned reports how many objects the probe still manages: 1 while present, 0 after Delete.
func (p *objectProbe) CountOwned(ctx context.Context) (int, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	infos, err := p.adapter.ListObjects(ctx, p.ref.Bucket(), p.ref.Key())
	if err != nil {
		return 0, err
	}
	for _, info := range infos {
		if info.Ref == p.ref {
			return 1, nil
		}
	}
	return 0, nil
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
