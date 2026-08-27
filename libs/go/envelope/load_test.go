//go:build load

package envelope_test

import (
	"bytes"
	"context"
	"os"
	"strconv"
	"sync"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/libs/go/envelope"
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

// TestLoad_ConcurrentSealUnsealRaceClean fans out N goroutines that each Seal+Unseal concurrently
// against a SHARED *Envelope. envelope documents the handle as safe for concurrent use (immutable
// configuration + a concurrency-safe injected Provider; each op resolves the KEK freshly and holds
// no per-op state on the struct). This proves it under -race at fan-out, and goleak asserts the
// goroutine high-water returns to baseline (ADR-0020 dimension (e)).
func TestLoad_ConcurrentSealUnsealRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	provider := secretstest.New(map[string]string{"connectors-kek": string(bytes.Repeat([]byte("KEK0"), 8))})
	env, err := envelope.New(
		envelope.Config{KEK: secrets.Ref("connectors-kek"), KEKVersion: 1},
		envelope.Deps{Secrets: provider},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	n := loadN()
	var wg sync.WaitGroup
	wg.Add(n)
	for i := range n {
		go func(i int) {
			defer wg.Done()
			plaintext := []byte("worker-" + strconv.Itoa(i))
			sealed, serr := env.Seal(context.Background(), plaintext)
			if serr != nil {
				t.Errorf("worker %d Seal: %v", i, serr)
				return
			}
			var got []byte
			if uerr := env.Unseal(context.Background(), sealed, func(pt []byte) error {
				got = append([]byte(nil), pt...)
				return nil
			}); uerr != nil {
				t.Errorf("worker %d Unseal: %v", i, uerr)
				return
			}
			if !bytes.Equal(got, plaintext) {
				t.Errorf("worker %d: round-trip drifted under fan-out", i)
			}
		}(i)
	}
	wg.Wait()
}
