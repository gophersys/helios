package edenhttp_test

import (
	"bytes"
	"encoding/base64"
	"strings"
	"testing"
	"time"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/edenhttptest"
)

// The `property` ctl.sh verb runs go test with RAPID_CHECKS set (default 1000 iterations/property,
// ADR-0020 dimension (a)); rapid reads it directly.

// TestProperty_GrantRoundTrip proves a parsed Grant renders back to a string that re-parses to the
// SAME grant — the grammar's parse/render is a stable bijection over well-formed grants.
func TestProperty_GrantRoundTrip(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		namespace := rapid.StringMatching(`[a-z][a-z0-9-]{0,12}`).Draw(rt, "namespace")
		action := rapid.StringMatching(`[a-z*][a-z0-9-]{0,12}`).Draw(rt, "action")
		original := edenhttp.NewGrant(namespace, action)
		reparsed, err := edenhttp.ParseGrant(original.String())
		if err != nil {
			rt.Fatalf("re-parse %q: %v", original.String(), err)
		}
		if reparsed != original {
			rt.Fatalf("grant drifted: %q -> %q", original, reparsed)
		}
	})
}

// TestProperty_GrantSelfCovers proves a non-wildcard grant always covers itself (reflexivity) — the
// authorize stage admits a caller that holds exactly the required grant.
func TestProperty_GrantSelfCovers(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		grant := edenhttp.NewGrant(
			rapid.StringMatching(`[a-z]{1,10}`).Draw(rt, "namespace"),
			rapid.StringMatching(`[a-z]{1,10}`).Draw(rt, "action"),
		)
		if !grant.Covers(grant) {
			rt.Fatalf("grant %q does not cover itself", grant)
		}
	})
}

// TestProperty_JWTRoundTrip proves a token Sign-ed with any subject + grant set Verify-s back to the
// SAME identity — the dev-JWT codec is a faithful round trip and the signature always re-validates.
func TestProperty_JWTRoundTrip(t *testing.T) {
	t.Parallel()
	verifier := edenhttptest.NewVerifier()
	rapid.Check(t, func(rt *rapid.T) {
		subject := rapid.StringMatching(`[a-z][a-z0-9-]{0,20}`).Draw(rt, "subject")
		count := rapid.IntRange(0, 4).Draw(rt, "grantCount")
		grants := make([]edenhttp.Grant, 0, count)
		for index := 0; index < count; index++ {
			grants = append(grants, edenhttp.NewGrant(
				rapid.StringMatching(`[a-z]{1,8}`).Draw(rt, "ns"),
				rapid.StringMatching(`[a-z]{1,8}`).Draw(rt, "act"),
			))
		}
		token, err := verifier.Sign(subject, grants, edenhttptest.FixedInstant.Add(time.Hour))
		if err != nil {
			rt.Fatalf("sign: %v", err)
		}
		identity, err := verifier.Verify(token, edenhttptest.FixedInstant)
		if err != nil {
			rt.Fatalf("verify: %v", err)
		}
		if identity.Subject != subject {
			rt.Fatalf("subject drifted: %q -> %q", subject, identity.Subject)
		}
		if len(identity.Grants) != len(grants) {
			rt.Fatalf("grant count drifted: %d -> %d", len(grants), len(identity.Grants))
		}
		for index := range grants {
			if identity.Grants[index] != grants[index] {
				rt.Fatalf("grant %d drifted: %q -> %q", index, grants[index], identity.Grants[index])
			}
		}
	})
}

// TestProperty_TamperedSignatureRejected proves that perturbing a byte of a valid token's SIGNATURE
// segment makes Verify reject it — the HMAC gate has no soft spot. The mutation is confined to the
// signature segment (the last dot-separated part) so the assertion is exact: a different signature
// over the same header+claims must not validate (a header/claims edit can re-encode to the same
// decoded bytes at a base64 boundary, which is a separate concern covered by the tamper-claims unit).
func TestProperty_TamperedSignatureRejected(t *testing.T) {
	t.Parallel()
	verifier := edenhttptest.NewVerifier()
	base := edenhttptest.MintToken("sessions:control")
	lastDot := strings.LastIndex(base, ".")
	rapid.Check(t, func(rt *rapid.T) {
		signatureLen := len(base) - lastDot - 1
		offset := rapid.IntRange(0, signatureLen-1).Draw(rt, "offset")
		position := lastDot + 1 + offset
		replacement := rapid.SampledFrom([]byte("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")).Draw(rt, "byte")
		if base[position] == replacement {
			return // a no-op edit would (correctly) still verify; skip it.
		}
		mutated := []byte(base)
		mutated[position] = replacement
		// Skip the rare base64-boundary case where a different signature CHARACTER decodes to the
		// same signature BYTES (a trailing-bits collision): only a genuinely different signature is
		// expected to be rejected. Compare the decoded signatures to be exact.
		if sameDecodedSignature(base, string(mutated), lastDot) {
			return
		}
		if _, err := verifier.Verify(string(mutated), edenhttptest.FixedInstant); err == nil {
			rt.Fatalf("a one-byte signature mutation at %d verified as valid: %q", position, string(mutated))
		}
	})
}

// sameDecodedSignature reports whether two tokens carry the same DECODED signature bytes despite a
// textual difference in the signature segment (a base64 trailing-bits collision), so the tamper
// property skips a mutation that does not actually change the signature.
func sameDecodedSignature(original, mutated string, lastDot int) bool {
	originalSig, errA := base64.RawURLEncoding.DecodeString(original[lastDot+1:])
	mutatedSig, errB := base64.RawURLEncoding.DecodeString(mutated[lastDot+1:])
	if errA != nil || errB != nil {
		return false // a now-undecodable signature is genuinely different (and will be rejected).
	}
	return bytes.Equal(originalSig, mutatedSig)
}
