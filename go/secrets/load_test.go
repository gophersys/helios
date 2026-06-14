//go:build load

package secrets_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
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

// TestLoad_ConcurrentResolveUseZeroizeRaceClean fans out N goroutines that each Resolve a
// reference through a SHARED *secrets.Mediator, read the plaintext via Use, and Zeroize the
// resulting Secret. The contract documents the Mediator as safe for concurrent use (its
// resolver map is read-only after New) and each Resolve returns an INDEPENDENT Secret the
// caller owns; this proves both under -race at fan-out. goleak.VerifyNone asserts the
// goroutine high-water returns to baseline afterward (ADR-0020 dimension (e)). 0 races, all N
// Secrets read correctly and reaped (Zeroized), no orphan goroutine.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling's goroutines would make it flaky.
func TestLoad_ConcurrentResolveUseZeroizeRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	const value = "fan-out-secret-value"
	ref := secrets.Ref("vault://eden/fanout#token")

	adapter := secretstest.New(map[string]string{ref.String(): value})
	med, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": adapter}},
	)
	if err != nil {
		t.Fatalf("secrets.New error = %v", err)
	}

	var reaped sync.WaitGroup
	reaped.Add(n)
	for i := range n {
		go func(i int) {
			defer reaped.Done()
			sec, rerr := med.Resolve(context.Background(), ref)
			if rerr != nil {
				t.Errorf("worker %d: Resolve error = %v", i, rerr)
				return
			}
			// Each worker independently reads then wipes ITS OWN Secret. A shared/aliased Secret
			// would surface as a torn read or a double-Zeroize panic under -race.
			var got string
			if uerr := sec.Use(func(b []byte) error { got = string(b); return nil }); uerr != nil {
				t.Errorf("worker %d: Use error = %v", i, uerr)
				return
			}
			if got != value {
				t.Errorf("worker %d: Use saw %q, want %q (independence violated under fan-out)", i, got, value)
			}
			sec.Zeroize()
			// After this worker's Zeroize, ITS Secret is spent — but a sibling's Secret must be
			// unaffected (independence); we don't touch siblings here.
			if zerr := sec.Use(func([]byte) error { return nil }); !is[secrets.ZeroizedError](zerr) {
				t.Errorf("worker %d: Use after Zeroize not ZeroizedError: %v", i, zerr)
			}
		}(i)
	}
	reaped.Wait()
}

// TestLoad_ConcurrentUseVsZeroizeOnSharedSecretRaceClean stresses the within-Secret
// concurrency contract (secret.go: Use=RLock reentrant reads, Zeroize=Lock) at fan-out: N
// readers Use the SAME Secret while one goroutine Zeroizes it. Under -race the RWMutex must
// admit either the intact plaintext or a ZeroizedError, never a torn/partially-wiped slice. A
// lock-free weakening of the read path would flag the data race here.
//
//nolint:paralleltest // shares goleak's whole-process view with the sibling above.
func TestLoad_ConcurrentUseVsZeroizeOnSharedSecretRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	const plaintext = "shared-secret-race-load"
	sec := secretstest.MintSecret([]byte(plaintext))

	var wg sync.WaitGroup
	wg.Add(n + 1)
	for i := range n {
		go func(i int) {
			defer wg.Done()
			err := sec.Use(func(b []byte) error {
				if s := string(b); s != plaintext {
					t.Errorf("worker %d: Use observed a torn/zeroed slice: %q (want intact or ZeroizedError)", i, s)
				}
				return nil
			})
			if err != nil && !is[secrets.ZeroizedError](err) {
				t.Errorf("worker %d: Use returned an unexpected error (not ZeroizedError): %v", i, err)
			}
		}(i)
	}
	go func() {
		defer wg.Done()
		sec.Zeroize()
	}()
	wg.Wait()

	// After the readers and the wiper join, the Secret is permanently spent.
	if err := sec.Use(func([]byte) error { return nil }); !is[secrets.ZeroizedError](err) {
		t.Errorf("Use after the load completed not ZeroizedError: %v", err)
	}
}
