//go:build load

package minioadapter_test

import (
	"context"
	"fmt"
	"os"
	"strconv"
	"strings"
	"sync"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/objectstorage"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500 in-process;
// ADR-0020 dimension (e)).
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_ConcurrentAdapterOpsRaceClean fans out N goroutines that each Put a distinct object,
// List-confirm it, and Delete it, through a SHARED *minioadapter.Adapter over the concurrency-safe
// fake S3. Proven under -race at fan-out; goleak.VerifyNone asserts the goroutine high-water returns
// to baseline (the channel-based List drains and leaks no goroutine per call), and a final List
// confirms every object was reaped.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make it flaky.
func TestLoad_ConcurrentAdapterOpsRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	adapter, err := newAdapter(newFakeS3(), seededSecrets())
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	ctx := context.Background()

	n := loadN()
	var reaped sync.WaitGroup
	reaped.Add(n)
	for i := range n {
		go func(i int) {
			defer reaped.Done()
			ref, rerr := objectstorage.NewRef("eden", fmt.Sprintf("load/object-%d.bin", i))
			if rerr != nil {
				t.Errorf("worker %d: NewRef error = %v", i, rerr)
				return
			}
			if _, perr := adapter.PutObject(ctx, ref, strings.NewReader("fan-out-object"), 14, ""); perr != nil {
				t.Errorf("worker %d: PutObject error = %v", i, perr)
				return
			}
			if _, lerr := adapter.ListObjects(ctx, "eden", ref.Key()); lerr != nil {
				t.Errorf("worker %d: ListObjects error = %v", i, lerr)
				return
			}
			if derr := adapter.DeleteObject(ctx, ref); derr != nil {
				t.Errorf("worker %d: DeleteObject error = %v", i, derr)
			}
		}(i)
	}
	reaped.Wait()

	remaining, lerr := adapter.ListObjects(ctx, "eden", "load/")
	if lerr != nil {
		t.Fatalf("ListObjects error = %v", lerr)
	}
	if len(remaining) != 0 {
		t.Errorf("%d objects survived the fan-out delete, want 0 (all reaped)", len(remaining))
	}
}
