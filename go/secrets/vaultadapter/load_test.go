//go:build load

package vaultadapter_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"

	"go.uber.org/goleak"

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

// TestLoad_ConcurrentResolveRaceClean fans out N goroutines that each Resolve a reference through a
// SHARED *vaultadapter.Adapter over a seeded fake transport, read the plaintext via Use, and
// Zeroize the resulting Secret. The adapter's bootstrap is once-guarded and its transport map is
// read-only after seeding, so concurrent Resolve must be race-clean and each Resolve must return an
// INDEPENDENT Secret. Proven under -race at fan-out; goleak.VerifyNone asserts the goroutine
// high-water returns to baseline (no token-refresh goroutine leaked per Resolve).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make it flaky.
func TestLoad_ConcurrentResolveRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	const value = "fan-out-vault-secret"
	transport := &fakeTransport{kv: map[string]map[string]any{
		"eden/data/fanout": kvEnvelope(map[string]any{"token": value}),
	}}
	adapter := newUserpassAdapter(t, transport)
	ref := secrets.Ref("vault://eden/fanout#token")

	n := loadN()
	var reaped sync.WaitGroup
	reaped.Add(n)
	for i := range n {
		go func(i int) {
			defer reaped.Done()
			sec, err := adapter.Resolve(context.Background(), ref)
			if err != nil {
				t.Errorf("worker %d: Resolve error = %v", i, err)
				return
			}
			var got string
			if uerr := sec.Use(func(b []byte) error { got = string(b); return nil }); uerr != nil {
				t.Errorf("worker %d: Use error = %v", i, uerr)
				return
			}
			if got != value {
				t.Errorf("worker %d: Use saw %q, want %q (independence violated under fan-out)", i, got, value)
			}
			sec.Zeroize()
			if zerr := sec.Use(func([]byte) error { return nil }); !is[secrets.ZeroizedError](zerr) {
				t.Errorf("worker %d: Use after Zeroize not ZeroizedError: %v", i, zerr)
			}
		}(i)
	}
	reaped.Wait()

	// The once-guarded bootstrap logged in exactly once across all N concurrent first-Resolves.
	if transport.loginCount != 1 {
		t.Errorf("login count under fan-out = %d, want exactly 1 (sticky bootstrap)", transport.loginCount)
	}
}
