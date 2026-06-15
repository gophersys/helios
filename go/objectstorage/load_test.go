//go:build load

package objectstorage_test

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"strconv"
	"sync"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/objectstorage/objectstoragetest"
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

// TestLoad_ConcurrentPutGetDeleteRaceClean fans out N goroutines that each Put a distinct object,
// Get it back byte-for-byte, then Delete it, through a SHARED *Store over the concurrency-safe fake
// Backend. Proven under -race at fan-out; goleak.VerifyNone asserts the goroutine high-water returns
// to baseline (no reaper goroutine leaked per operation) and every object is reaped (the store is
// empty of the fanned-out keys afterward).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make it flaky.
func TestLoad_ConcurrentPutGetDeleteRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	store, err := objectstorage.New(objectstorage.Config{}, objectstorage.Deps{Backend: objectstoragetest.NewBackend()})
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	payload := objectstoragetest.SeededPayload
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
			if _, perr := store.Put(ctx, ref, bytes.NewReader(payload), objectstorage.PutOptions{Size: int64(len(payload))}); perr != nil {
				t.Errorf("worker %d: Put error = %v", i, perr)
				return
			}
			reader, _, gerr := store.Get(ctx, ref)
			if gerr != nil {
				t.Errorf("worker %d: Get error = %v", i, gerr)
				return
			}
			got, _ := io.ReadAll(reader)
			_ = reader.Close()
			if !bytes.Equal(got, payload) {
				t.Errorf("worker %d: round-trip drift under fan-out", i)
				return
			}
			if derr := store.Delete(ctx, ref); derr != nil {
				t.Errorf("worker %d: Delete error = %v", i, derr)
			}
		}(i)
	}
	reaped.Wait()

	// Every fanned-out object was Deleted: a List of the load prefix returns nothing (all reaped).
	remaining, lerr := store.List(ctx, "eden", "load/")
	if lerr != nil {
		t.Fatalf("List error = %v", lerr)
	}
	if len(remaining) != 0 {
		t.Errorf("%d objects survived the fan-out delete, want 0 (all reaped)", len(remaining))
	}
}
