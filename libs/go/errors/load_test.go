//go:build load

package errors_test

import (
	"os"
	"strconv"
	"sync"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/errors"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500 in-process;
// ADR-0020 dimension (e) threshold).
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_ConcurrentConstructionRaceClean fans out N goroutines that each mint, wrap, derive,
// and inspect errors concurrently against a SHARED immutable *Error. errors documents that a
// shared *Error is safe across goroutines (immutable after construction, copy-on-write
// derivation); this test proves it under -race at fan-out, and goleak asserts the goroutine
// high-water returns to baseline (0 leaked) afterward (ADR-0020 dimension (e)).
func TestLoad_ConcurrentConstructionRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	shared := errors.Wrap(errors.KindUnavailable, "shared cause",
		errors.New(errors.KindNotFound, "root"))

	var wg sync.WaitGroup
	wg.Add(n)
	for i := range n {
		go func(i int) {
			defer wg.Done()
			// Concurrent reads of the shared error.
			_ = errors.KindOf(shared)
			_ = shared.Error()
			// Concurrent derivation (copy-on-write — must not mutate `shared`).
			d := shared.WithCode("c"+strconv.Itoa(i)).WithField("worker", i)
			if errors.KindOf(d) != errors.KindUnavailable {
				t.Errorf("worker %d: derived Kind drifted under fan-out", i)
			}
		}(i)
	}
	wg.Wait()

	// The shared error is unchanged after N concurrent derivations (no orphaned state).
	if errors.KindOf(shared) != errors.KindUnavailable {
		t.Fatalf("shared error Kind mutated under load")
	}
}
