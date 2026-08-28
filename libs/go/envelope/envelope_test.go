package envelope_test

import (
	"bytes"
	"context"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/libs/go/envelope"
)

// kekReferenceName is the bare-name KEK reference the tests seed the fake Provider with. It stands
// for the production vault://eden/production#connectors-kek — the test resolves it to a fixed 32-byte
// AES-256 key so Seal/Unseal exercise the real crypto over a real (fake-sourced) KEK.
const kekReferenceName = "connectors-kek"

// testKEK is a fixed, non-secret 32-byte AES-256 key the fake Provider resolves the KEK reference
// to. It is a SENTINEL test key (a repeating pattern), never a real credential — the whole point of
// envelope is that it never sees a real KEK in a test; this exercises the 32-byte-key path.
var testKEK = bytes.Repeat([]byte("KEK0"), 8) // 32 bytes

// newEnvelope builds a *envelope.Envelope wired to a fake secrets.Provider that resolves the KEK
// reference to testKEK. It is the conformance two-binding's FAKE binding — the same suite runs
// against a real Vault-backed Provider in a composition root, but envelope's own gate needs only a
// Provider that yields a 32-byte key (envelope has no real substrate of its own; the KEK source is
// the injected port).
func newEnvelope(t *testing.T) *envelope.Envelope {
	t.Helper()
	provider := secretstest.New(map[string]string{kekReferenceName: string(testKEK)})
	env, err := envelope.New(
		envelope.Config{KEK: secrets.Ref(kekReferenceName), KEKVersion: 1},
		envelope.Deps{Secrets: provider},
	)
	if err != nil {
		t.Fatalf("New: unexpected error: %v", err)
	}
	return env
}

// TestNew_RejectsMalformedWiring asserts New is a pure validator: a nil Provider, a zero KEK
// reference, or a KEKVersion < 1 is a typed KindInvalid, never a usable Envelope (the constructor
// spine, contract §2).
func TestNew_RejectsMalformedWiring(t *testing.T) {
	t.Parallel()
	provider := secretstest.New(map[string]string{kekReferenceName: string(testKEK)})

	cases := []struct {
		name          string
		configuration envelope.Config
		dependencies  envelope.Deps
	}{
		{"nil-secrets", envelope.Config{KEK: secrets.Ref(kekReferenceName), KEKVersion: 1}, envelope.Deps{Secrets: nil}},
		{"zero-kek", envelope.Config{KEKVersion: 1}, envelope.Deps{Secrets: provider}},
		{"zero-version", envelope.Config{KEK: secrets.Ref(kekReferenceName), KEKVersion: 0}, envelope.Deps{Secrets: provider}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			env, err := envelope.New(tc.configuration, tc.dependencies)
			if env != nil {
				t.Fatalf("New(%s): expected nil Envelope on invalid wiring", tc.name)
			}
			if !errors.IsType[*errors.Error](err) || errors.KindOf(err) != errors.KindInvalid {
				t.Fatalf("New(%s): want KindInvalid *errors.Error, got %v", tc.name, err)
			}
		})
	}
}

// TestSealUnseal_RoundTrip is the cardinal correctness property (contract §4): Seal then Unseal is
// the identity for a plaintext, and the plaintext is revealed ONLY inside the Use callback.
func TestSealUnseal_RoundTrip(t *testing.T) {
	t.Parallel()
	env := newEnvelope(t)
	plaintext := []byte("sk-ant-a-fake-sentinel-token-value")

	sealed, err := env.Seal(context.Background(), plaintext)
	if err != nil {
		t.Fatalf("Seal: unexpected error: %v", err)
	}

	var revealed []byte
	if err := env.Unseal(context.Background(), sealed, func(pt []byte) error {
		// Copy inside the window — the slice is valid only here (mirrors secrets.Secret.Use).
		revealed = append(revealed[:0], pt...)
		return nil
	}); err != nil {
		t.Fatalf("Unseal: unexpected error: %v", err)
	}
	if !bytes.Equal(revealed, plaintext) {
		t.Fatalf("round-trip mismatch: revealed %q, want %q", revealed, plaintext)
	}
}

// TestSeal_RecordCarriesNoPlaintextOrKEK asserts the Sealed record's blobs never contain the
// plaintext or the KEK in the clear — the no-plaintext-at-rest invariant at the value level (the
// DB-scan proof test lives in the connectors domain; this is the crypto-level guarantee).
func TestSeal_RecordCarriesNoPlaintextOrKEK(t *testing.T) {
	t.Parallel()
	env := newEnvelope(t)
	plaintext := []byte("SENTINEL-PLAINTEXT-do-not-leak")

	sealed, err := env.Seal(context.Background(), plaintext)
	if err != nil {
		t.Fatalf("Seal: unexpected error: %v", err)
	}
	for name, blob := range map[string][]byte{
		"ciphertext":  sealed.Ciphertext,
		"wrapped-dek": sealed.WrappedDEK,
	} {
		if bytes.Contains(blob, plaintext) {
			t.Fatalf("%s blob contains the plaintext in the clear", name)
		}
		if bytes.Contains(blob, testKEK) {
			t.Fatalf("%s blob contains the KEK in the clear", name)
		}
	}
	if sealed.KEKVersion != 1 {
		t.Fatalf("Sealed.KEKVersion = %d, want 1 (the configured version)", sealed.KEKVersion)
	}
}

// TestSeal_FreshDEKAndNoncePerCall asserts two Seals of the SAME plaintext produce DIFFERENT
// ciphertext/nonces (a fresh DEK + random nonce each) — the misuse-resistance property. Identical
// output would signal a reused key/nonce, the one catastrophic GCM failure.
func TestSeal_FreshDEKAndNoncePerCall(t *testing.T) {
	t.Parallel()
	env := newEnvelope(t)
	plaintext := []byte("same-plaintext-twice")

	a, err := env.Seal(context.Background(), plaintext)
	if err != nil {
		t.Fatalf("Seal a: %v", err)
	}
	b, err := env.Seal(context.Background(), plaintext)
	if err != nil {
		t.Fatalf("Seal b: %v", err)
	}
	if bytes.Equal(a.Ciphertext, b.Ciphertext) {
		t.Fatal("two Seals of the same plaintext produced identical ciphertext (nonce/DEK reuse)")
	}
	if bytes.Equal(a.NonceCiphertext, b.NonceCiphertext) || bytes.Equal(a.NonceDEK, b.NonceDEK) {
		t.Fatal("two Seals produced identical nonces (nonce reuse — catastrophic GCM misuse)")
	}
	if bytes.Equal(a.WrappedDEK, b.WrappedDEK) {
		t.Fatal("two Seals produced identical wrapped DEKs (DEK reuse)")
	}
}

// TestUnseal_RejectsTamperedRecord asserts a modified Sealed field fails Unseal with KindInvalid
// (GCM authenticity) — a tampered ciphertext, wrapped DEK, or nonce is not something the KEK opens.
func TestUnseal_RejectsTamperedRecord(t *testing.T) {
	t.Parallel()
	env := newEnvelope(t)
	sealed, err := env.Seal(context.Background(), []byte("authentic"))
	if err != nil {
		t.Fatalf("Seal: %v", err)
	}

	mutate := func(b []byte) []byte {
		out := append([]byte(nil), b...)
		out[0] ^= 0xFF
		return out
	}
	cases := map[string]envelope.Sealed{
		"tampered-ciphertext":  {Ciphertext: mutate(sealed.Ciphertext), WrappedDEK: sealed.WrappedDEK, NonceCiphertext: sealed.NonceCiphertext, NonceDEK: sealed.NonceDEK, KEKVersion: sealed.KEKVersion},
		"tampered-wrapped-dek": {Ciphertext: sealed.Ciphertext, WrappedDEK: mutate(sealed.WrappedDEK), NonceCiphertext: sealed.NonceCiphertext, NonceDEK: sealed.NonceDEK, KEKVersion: sealed.KEKVersion},
		"tampered-nonce-ct":    {Ciphertext: sealed.Ciphertext, WrappedDEK: sealed.WrappedDEK, NonceCiphertext: mutate(sealed.NonceCiphertext), NonceDEK: sealed.NonceDEK, KEKVersion: sealed.KEKVersion},
	}
	for name, bad := range cases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()
			err := env.Unseal(context.Background(), bad, func([]byte) error { return nil })
			if errors.KindOf(err) != errors.KindInvalid {
				t.Fatalf("%s: want KindInvalid, got %v", name, err)
			}
		})
	}
}

// TestUnseal_RejectsZeroRecord asserts the zero/short Sealed record is KindInvalid before the cipher
// is ever touched (the isZero guard).
func TestUnseal_RejectsZeroRecord(t *testing.T) {
	t.Parallel()
	env := newEnvelope(t)
	err := env.Unseal(context.Background(), envelope.Sealed{}, func([]byte) error { return nil })
	if errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("zero Sealed: want KindInvalid, got %v", err)
	}
}

// TestUnseal_WrongKEKFails asserts a record sealed under one KEK does not open under a different KEK
// — the isolation guarantee (a different KEK is a different key, GCM open fails).
func TestUnseal_WrongKEKFails(t *testing.T) {
	t.Parallel()
	sealer := newEnvelope(t)
	sealed, err := sealer.Seal(context.Background(), []byte("scoped-to-kek-A"))
	if err != nil {
		t.Fatalf("Seal: %v", err)
	}

	otherKEK := bytes.Repeat([]byte("XXXX"), 8) // a DIFFERENT 32-byte key
	otherProvider := secretstest.New(map[string]string{kekReferenceName: string(otherKEK)})
	opener, err := envelope.New(
		envelope.Config{KEK: secrets.Ref(kekReferenceName), KEKVersion: 1},
		envelope.Deps{Secrets: otherProvider},
	)
	if err != nil {
		t.Fatalf("New opener: %v", err)
	}
	if err := opener.Unseal(context.Background(), sealed, func([]byte) error { return nil }); errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("wrong-KEK Unseal: want KindInvalid, got %v", err)
	}
}

// TestUnseal_KEKResolutionFailurePropagates asserts a KEK the Provider cannot resolve yields the
// port's Kind (NotFound here), carrying the loggable reference — not a crash, not a leak.
func TestUnseal_KEKResolutionFailurePropagates(t *testing.T) {
	t.Parallel()
	// A Provider that resolves NOTHING (zero value) → every reference is NotFound.
	provider := secretstest.New(nil)
	env, err := envelope.New(
		envelope.Config{KEK: secrets.Ref("absent-kek"), KEKVersion: 1},
		envelope.Deps{Secrets: provider},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	_, err = env.Seal(context.Background(), []byte("x"))
	if errors.KindOf(err) != errors.KindNotFound {
		t.Fatalf("Seal with unresolvable KEK: want KindNotFound (port Kind), got %v", err)
	}
}

// TestUnseal_FnErrorPropagatesUnchanged asserts Unseal is a pass-through for fn's error (contract
// §3): the caller's own error Kind survives, so a caller can branch on it.
func TestUnseal_FnErrorPropagatesUnchanged(t *testing.T) {
	t.Parallel()
	env := newEnvelope(t)
	sealed, err := env.Seal(context.Background(), []byte("payload"))
	if err != nil {
		t.Fatalf("Seal: %v", err)
	}
	sentinel := errors.New(errors.KindConflict, "caller's own error")
	got := env.Unseal(context.Background(), sealed, func([]byte) error { return sentinel })
	if errors.KindOf(got) != errors.KindConflict {
		t.Fatalf("fn error not passed through: want KindConflict, got %v", got)
	}
}

// TestFingerprint asserts the fingerprint is deterministic, one-way, non-empty for non-empty input,
// empty for empty input, and DIFFERENT for different plaintexts (change-detection).
func TestFingerprint(t *testing.T) {
	t.Parallel()
	a := envelope.Fingerprint([]byte("token-one"))
	b := envelope.Fingerprint([]byte("token-two"))
	again := envelope.Fingerprint([]byte("token-one"))

	if a == "" || b == "" {
		t.Fatal("Fingerprint of non-empty plaintext must be non-empty")
	}
	if a != again {
		t.Fatalf("Fingerprint not deterministic: %q != %q", a, again)
	}
	if a == b {
		t.Fatal("Fingerprint collision on distinct plaintexts (change-detection broken)")
	}
	if envelope.Fingerprint(nil) != "" {
		t.Fatal("Fingerprint(nil) must be the empty string (nothing to hint at)")
	}
	if len(a) != 16 {
		t.Fatalf("Fingerprint length = %d, want 16 hex chars", len(a))
	}
	// One-way: the fingerprint must not contain the plaintext.
	if bytes.Contains([]byte(a), []byte("token-one")) {
		t.Fatal("Fingerprint leaks the plaintext")
	}
}

// TestKEKRotation_TwoGenerationsCoexist asserts the rotation model: a record sealed under KEKVersion
// 1 is re-wrapped under KEKVersion 2 (Unseal-then-Seal), and BOTH generations open under their
// respective KEKs — the coexistence window (contract §5). The DEK is preserved; only the wrapping
// changes.
func TestKEKRotation_TwoGenerationsCoexist(t *testing.T) {
	t.Parallel()
	kekV1 := bytes.Repeat([]byte("V1AA"), 8)
	kekV2 := bytes.Repeat([]byte("V2BB"), 8)
	plaintext := []byte("rotate-me")

	v1 := mustEnvelope(t, kekV1, 1)
	v2 := mustEnvelope(t, kekV2, 2)

	sealedV1, err := v1.Seal(context.Background(), plaintext)
	if err != nil {
		t.Fatalf("Seal v1: %v", err)
	}

	// Re-wrap: unseal under v1, re-seal under v2 (the caller's re-wrap pass).
	var reWrapped envelope.Sealed
	if err := v1.Unseal(context.Background(), sealedV1, func(pt []byte) error {
		s, serr := v2.Seal(context.Background(), pt)
		reWrapped = s
		return serr
	}); err != nil {
		t.Fatalf("re-wrap: %v", err)
	}
	if reWrapped.KEKVersion != 2 {
		t.Fatalf("re-wrapped KEKVersion = %d, want 2", reWrapped.KEKVersion)
	}

	// The re-wrapped record opens under v2 and yields the original plaintext.
	var got []byte
	if err := v2.Unseal(context.Background(), reWrapped, func(pt []byte) error {
		got = append(got[:0], pt...)
		return nil
	}); err != nil {
		t.Fatalf("Unseal re-wrapped under v2: %v", err)
	}
	if !bytes.Equal(got, plaintext) {
		t.Fatalf("rotation lost the plaintext: got %q, want %q", got, plaintext)
	}
}

// mustEnvelope builds an Envelope over a fake Provider yielding the given KEK at the given version.
func mustEnvelope(t *testing.T, kek []byte, version int) *envelope.Envelope {
	t.Helper()
	provider := secretstest.New(map[string]string{kekReferenceName: string(kek)})
	env, err := envelope.New(
		envelope.Config{KEK: secrets.Ref(kekReferenceName), KEKVersion: version},
		envelope.Deps{Secrets: provider},
	)
	if err != nil {
		t.Fatalf("mustEnvelope: %v", err)
	}
	return env
}
