package envelope_test

import (
	"context"
	"encoding/hex"
	"fmt"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/libs/go/envelope"
)

// seededCanary is the redaction needle (ADR-0020 dimension (f), rule 21 §f — the CENTRAL security
// property of an encryption library): a known sentinel plaintext that, once sealed, must appear in
// NO surfaced artifact — not in the Sealed record as plaintext, not in an error string, not in a
// fingerprint, not in any rendered form. One leak fails the lane. It is a SENTINEL, never a real
// credential.
const seededCanary = "SEEDED-CANARY-c2VjcmV0-envelope-do-not-leak"

// TestCanary_SealedRecordNeverCarriesPlaintext asserts the needle never appears in the Sealed
// record's byte blobs (nor as hex) — the no-plaintext-at-rest guarantee at the crypto level.
func TestCanary_SealedRecordNeverCarriesPlaintext(t *testing.T) {
	t.Parallel()
	env := newEnvelope(t)
	sealed, err := env.Seal(context.Background(), []byte(seededCanary))
	if err != nil {
		t.Fatalf("Seal: %v", err)
	}

	surfaces := map[string]string{
		"ciphertext":       string(sealed.Ciphertext),
		"wrapped-dek":      string(sealed.WrappedDEK),
		"nonce-ct":         string(sealed.NonceCiphertext),
		"nonce-dek":        string(sealed.NonceDEK),
		"ciphertext-hex":   hex.EncodeToString(sealed.Ciphertext),
		"wrapped-dek-hex":  hex.EncodeToString(sealed.WrappedDEK),
		"record-formatted": fmt.Sprintf("%v", sealed),
		"record-goformat":  fmt.Sprintf("%#v", sealed),
	}
	for name, surface := range surfaces {
		if strings.Contains(surface, seededCanary) {
			t.Fatalf("canary leaked in the %s surface", name)
		}
	}
}

// TestCanary_FingerprintNeverCarriesPlaintext asserts the fingerprint is one-way — the needle does
// not appear in the digest, so displaying a fingerprint reveals nothing about the value.
func TestCanary_FingerprintNeverCarriesPlaintext(t *testing.T) {
	t.Parallel()
	fingerprint := envelope.Fingerprint([]byte(seededCanary))
	if strings.Contains(fingerprint, seededCanary) {
		t.Fatalf("canary leaked in the fingerprint: %q", fingerprint)
	}
}

// TestCanary_ErrorsNeverCarryPlaintextOrKEK asserts no error surface (a KEK-resolution failure, a
// tamper rejection) ever embeds the plaintext or the KEK — only the loggable Reference may ride an
// error (the redaction-by-construction contract, §3/§4).
func TestCanary_ErrorsNeverCarryPlaintextOrKEK(t *testing.T) {
	t.Parallel()

	// (a) A KEK-resolution failure: the error carries the reference, never a value. The Provider
	// resolves nothing, so Seal fails at KEK resolution; the plaintext + a (fake) KEK sentinel must
	// not appear.
	provider := secretstest.New(nil)
	env, err := envelope.New(
		envelope.Config{KEK: secrets.Ref("absent-kek"), KEKVersion: 1},
		envelope.Deps{Secrets: provider},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if _, sealErr := env.Seal(context.Background(), []byte(seededCanary)); sealErr != nil {
		if strings.Contains(sealErr.Error(), seededCanary) {
			t.Fatalf("KEK-failure error leaked the plaintext: %q", sealErr.Error())
		}
	} else {
		t.Fatal("expected a KEK-resolution error")
	}

	// (b) A tamper rejection on a good sealer: the open-failure error must not carry the plaintext
	// (it never had it — GCM open failed) nor the KEK sentinel.
	good := newEnvelope(t)
	sealed, err := good.Seal(context.Background(), []byte(seededCanary))
	if err != nil {
		t.Fatalf("Seal: %v", err)
	}
	sealed.Ciphertext[0] ^= 0xFF // tamper
	openErr := good.Unseal(context.Background(), sealed, func([]byte) error { return nil })
	if openErr == nil {
		t.Fatal("expected a tamper-rejection error")
	}
	if strings.Contains(openErr.Error(), seededCanary) || strings.Contains(openErr.Error(), string(testKEK)) {
		t.Fatalf("tamper error leaked a secret: %q", openErr.Error())
	}
}
