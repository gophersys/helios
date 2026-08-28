//go:build lifecycle

package envelope_test

import (
	"bytes"
	"context"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/libs/go/envelope"
)

// TestLifecycle_SealUnsealLeavesNoState is the leaf-library form of the full-object-lifecycle
// conformance (ADR-0020 dimension (c)): envelope holds no OS resource to Close, so its lifecycle
// invariant is stateless reuse — a single *Envelope handles many Seal/Unseal cycles with no state
// carried between them (the analog of "double-close is a no-op": re-using the handle is idempotent
// and never orphans key material). goleak asserts the goroutine half (no orphan goroutine/fd).
func TestLifecycle_SealUnsealLeavesNoState(t *testing.T) {
	defer goleak.VerifyNone(t)

	provider := secretstest.New(map[string]string{"connectors-kek": string(bytes.Repeat([]byte("KEK0"), 8))})
	env, err := envelope.New(
		envelope.Config{KEK: secrets.Ref("connectors-kek"), KEKVersion: 1},
		envelope.Deps{Secrets: provider},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	// Reuse the same handle across many cycles — each is independent; no state bleeds across.
	for i := range 50 {
		plaintext := []byte{byte(i), byte(i + 1), byte(i + 2)}
		sealed, serr := env.Seal(context.Background(), plaintext)
		if serr != nil {
			t.Fatalf("cycle %d Seal: %v", i, serr)
		}
		var got []byte
		if uerr := env.Unseal(context.Background(), sealed, func(pt []byte) error {
			got = append(got[:0], pt...)
			return nil
		}); uerr != nil {
			t.Fatalf("cycle %d Unseal: %v", i, uerr)
		}
		if !bytes.Equal(got, plaintext) {
			t.Fatalf("cycle %d: round-trip drifted", i)
		}
	}
}
