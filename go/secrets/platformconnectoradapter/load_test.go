//go:build load

package platformconnectoradapter_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
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

// TestLoad_ConcurrentResolveRaceClean fans out N goroutines that each Resolve a connector reference
// through a SHARED *platformconnectoradapter.Adapter over a seeded fake transport + real envelope
// crypto, read the plaintext via Use, and Zeroize the resulting Secret. The adapter holds no per-Resolve
// state and the transport map is read-only after seeding, so concurrent Resolve must be race-clean and
// each Resolve must return an INDEPENDENT Secret. Proven under -race at fan-out; goleak.VerifyNone
// asserts the goroutine high-water returns to baseline (no per-Resolve goroutine leaked).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make it flaky.
func TestLoad_ConcurrentResolveRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	const (
		id    = "fanout-connector"
		value = "fan-out-connector-secret"
	)
	transport := seededTransport(t, id, value)
	adapter := newAdapter(t, transport)
	ref := secrets.Ref("eden://connector/" + id)

	n := loadN()
	var reaped sync.WaitGroup
	reaped.Add(n)
	for i := range n {
		go func(i int) {
			defer reaped.Done()
			sec, err := adapter.Resolve(context.Background(), ref)
			if err != nil {
				t.Errorf("worker %d: Resolve err = %v", i, err)
				return
			}
			var got string
			if uerr := sec.Use(func(b []byte) error { got = string(b); return nil }); uerr != nil {
				t.Errorf("worker %d: Use err = %v", i, uerr)
				return
			}
			if got != value {
				t.Errorf("worker %d: Use saw %q, want %q (independence violated under fan-out)", i, got, value)
			}
			sec.Zeroize()
			if zerr := sec.Use(func([]byte) error { return nil }); !errors.IsType[secrets.ZeroizedError](zerr) {
				t.Errorf("worker %d: Use after Zeroize not ZeroizedError: %v", i, zerr)
			}
		}(i)
	}
	reaped.Wait()
}
