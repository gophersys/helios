package envelope_test

import (
	"bytes"
	"context"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/libs/go/envelope"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS set (default 1000 iterations/property,
// ADR-0020 dimension (a)); rapid reads it from the environment directly.

// TestProperty_SealUnsealIsIdentity is the cardinal round-trip invariant over arbitrary plaintext
// (contract §4, rule 21 §a): for ANY byte plaintext, Seal-then-Unseal reveals exactly it. This is
// the property that makes the crypto trustworthy — not one example, but the whole input space.
func TestProperty_SealUnsealIsIdentity(t *testing.T) {
	t.Parallel()
	env := newEnvelope(t)
	rapid.Check(t, func(rt *rapid.T) {
		plaintext := rapid.SliceOf(rapid.Byte()).Draw(rt, "plaintext")
		sealed, err := env.Seal(context.Background(), plaintext)
		if err != nil {
			rt.Fatalf("Seal: %v", err)
		}
		var revealed []byte
		if err := env.Unseal(context.Background(), sealed, func(pt []byte) error {
			revealed = append([]byte(nil), pt...)
			return nil
		}); err != nil {
			rt.Fatalf("Unseal: %v", err)
		}
		if !bytes.Equal(revealed, plaintext) {
			rt.Fatalf("round-trip drifted: revealed %d bytes, sealed %d bytes", len(revealed), len(plaintext))
		}
	})
}

// TestProperty_FingerprintDeterministicAndCollisionResistant asserts fingerprint stability (same
// input → same digest) and that distinct inputs almost never collide (a 64-bit truncation over
// rapid-drawn distinct pairs). Fingerprint is pure, so this is a total function property (§a).
func TestProperty_FingerprintDeterministicAndCollisionResistant(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		a := rapid.SliceOfN(rapid.Byte(), 1, 64).Draw(rt, "a")
		// Fingerprint the SAME bytes twice via distinct copies so this is a determinism check, not
		// a compiler-visible identical-expression tautology (staticcheck SA4000).
		aCopy := append([]byte(nil), a...)
		if envelope.Fingerprint(a) != envelope.Fingerprint(aCopy) {
			rt.Fatalf("Fingerprint not deterministic for %d-byte input", len(a))
		}
		b := rapid.SliceOfN(rapid.Byte(), 1, 64).Draw(rt, "b")
		if !bytes.Equal(a, b) && envelope.Fingerprint(a) == envelope.Fingerprint(b) {
			rt.Fatalf("Fingerprint collision on distinct inputs (%d vs %d bytes)", len(a), len(b))
		}
	})
}

// TestProperty_KEKVersionRecorded asserts the configured KEKVersion is stamped on every Sealed for
// any version >= 1 — the rotation-coexistence invariant (contract §5) holds across the version space.
func TestProperty_KEKVersionRecorded(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		version := rapid.IntRange(1, 1000).Draw(rt, "version")
		provider := secretstest.New(map[string]string{kekReferenceName: string(testKEK)})
		env, err := envelope.New(
			envelope.Config{KEK: secrets.Ref(kekReferenceName), KEKVersion: version},
			envelope.Deps{Secrets: provider},
		)
		if err != nil {
			rt.Fatalf("New(version=%d): %v", version, err)
		}
		sealed, err := env.Seal(context.Background(), []byte("v"))
		if err != nil {
			rt.Fatalf("Seal: %v", err)
		}
		if sealed.KEKVersion != version {
			rt.Fatalf("Sealed.KEKVersion = %d, want %d", sealed.KEKVersion, version)
		}
	})
}
