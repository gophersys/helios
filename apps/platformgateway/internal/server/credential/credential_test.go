package credential_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/server/credential"
)

// TestHashThenVerify proves the round-trip: a hashed plaintext verifies against its own digest, and a
// different plaintext does not (the digest is salted, so the same plaintext hashes differently each time
// yet still verifies).
func TestHashThenVerify(t *testing.T) {
	t.Parallel()
	const plaintext = "correct horse battery staple"
	hash, err := credential.Hash(plaintext)
	if err != nil {
		t.Fatalf("Hash: %v", err)
	}
	if hash == plaintext {
		t.Fatal("Hash returned the plaintext verbatim (not a digest)")
	}
	if err := credential.Verify(hash, plaintext); err != nil {
		t.Fatalf("Verify(matching) = %v, want nil", err)
	}
}

// TestHashIsSalted proves two hashes of the SAME plaintext differ (bcrypt salts), yet both verify.
func TestHashIsSalted(t *testing.T) {
	t.Parallel()
	const plaintext = "eden"
	a, err := credential.Hash(plaintext)
	if err != nil {
		t.Fatalf("Hash a: %v", err)
	}
	b, err := credential.Hash(plaintext)
	if err != nil {
		t.Fatalf("Hash b: %v", err)
	}
	if a == b {
		t.Fatal("two hashes of the same plaintext are identical (unsalted)")
	}
	if err := credential.Verify(a, plaintext); err != nil {
		t.Fatalf("Verify(a) = %v, want nil", err)
	}
	if err := credential.Verify(b, plaintext); err != nil {
		t.Fatalf("Verify(b) = %v, want nil", err)
	}
}

// TestVerifyMismatchIsUnauthenticated proves a wrong plaintext is a typed KindUnauthenticated (→ 401),
// the Kind the login flow maps to an unauthenticated response.
func TestVerifyMismatchIsUnauthenticated(t *testing.T) {
	t.Parallel()
	hash, err := credential.Hash("right")
	if err != nil {
		t.Fatalf("Hash: %v", err)
	}
	err = credential.Verify(hash, "wrong")
	if err == nil {
		t.Fatal("Verify(mismatch) = nil, want an error")
	}
	if errors.KindOf(err) != errors.KindUnauthenticated {
		t.Fatalf("Verify(mismatch) Kind = %v, want KindUnauthenticated", errors.KindOf(err))
	}
}

// TestVerifyMalformedHashIsUnauthenticated proves a non-bcrypt hash is also a KindUnauthenticated (not a
// panic / 500): an authentication failure, surfaced uniformly.
func TestVerifyMalformedHashIsUnauthenticated(t *testing.T) {
	t.Parallel()
	err := credential.Verify("not-a-bcrypt-hash", "anything")
	if err == nil {
		t.Fatal("Verify(malformed hash) = nil, want an error")
	}
	if errors.KindOf(err) != errors.KindUnauthenticated {
		t.Fatalf("Verify(malformed hash) Kind = %v, want KindUnauthenticated", errors.KindOf(err))
	}
}

// TestErrorsNeverCarryCredential proves neither the plaintext nor the hash appears in a Verify error
// message (the redaction property — a credential never leaks through the failure path).
func TestErrorsNeverCarryCredential(t *testing.T) {
	t.Parallel()
	const plaintext = "leak-canary-plaintext"
	hash, err := credential.Hash("other")
	if err != nil {
		t.Fatalf("Hash: %v", err)
	}
	verr := credential.Verify(hash, plaintext)
	if verr == nil {
		t.Fatal("expected a mismatch error")
	}
	if strings.Contains(verr.Error(), plaintext) {
		t.Fatalf("Verify error leaked the plaintext: %q", verr.Error())
	}
	if strings.Contains(verr.Error(), hash) {
		t.Fatalf("Verify error leaked the hash: %q", verr.Error())
	}
}

// TestHashRejectsOverlongPassword proves a plaintext beyond bcrypt's 72-byte limit is a typed KindInvalid
// (not a silent truncation / panic) — the one Hash error branch.
func TestHashRejectsOverlongPassword(t *testing.T) {
	t.Parallel()
	overlong := strings.Repeat("x", 100) // > 72 bytes; bcrypt rejects it.
	_, err := credential.Hash(overlong)
	if err == nil {
		t.Fatal("Hash(overlong) = nil error, want KindInvalid")
	}
	if errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("Hash(overlong) Kind = %v, want KindInvalid", errors.KindOf(err))
	}
}
