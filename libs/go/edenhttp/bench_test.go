package edenhttp_test

import (
	"testing"
	"time"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/edenhttptest"
)

// sink keeps the compiler from eliding the benchmarked work (the package-level any sink pattern).
var sink any

// BenchmarkNew measures the pure construction spine (the hot path the composition root calls).
func BenchmarkNew(b *testing.B) {
	b.ReportAllocs()
	verifier := edenhttptest.NewVerifier()
	clock := edenhttptest.FixedClock{}
	for b.Loop() {
		spine, _ := edenhttp.New(edenhttp.Config{}, edenhttp.Deps{Verifier: verifier, Clock: clock}) //nolint:errcheck // bench: the error path is covered by unit tests; here we measure the happy spine.
		sink = spine
	}
}

// BenchmarkVerify measures the dev-JWT verify hot path (every authenticated request runs it once).
func BenchmarkVerify(b *testing.B) {
	b.ReportAllocs()
	verifier := edenhttptest.NewVerifier()
	token := edenhttptest.MintToken("sessions:control", "sessions:read")
	now := edenhttptest.FixedInstant
	for b.Loop() {
		identity, _ := verifier.Verify(token, now) //nolint:errcheck // bench: the error path is unit-covered; here we measure the happy verify.
		sink = identity
	}
}

// BenchmarkGrantCovers measures the authorize-stage grant match (run on every authorized request).
func BenchmarkGrantCovers(b *testing.B) {
	b.ReportAllocs()
	held := edenhttp.NewGrant("sessions", "*")
	required := edenhttp.NewGrant("sessions", "control")
	for b.Loop() {
		sink = held.Covers(required)
	}
}

// BenchmarkSign measures the dev-JWT mint path (the dev composition + a test mints with it).
func BenchmarkSign(b *testing.B) {
	b.ReportAllocs()
	verifier := edenhttptest.NewVerifier()
	grants := []edenhttp.Grant{edenhttp.NewGrant("sessions", "control")}
	expiresAt := edenhttptest.FixedInstant.Add(time.Hour)
	for b.Loop() {
		token, _ := verifier.Sign("user-1", grants, expiresAt) //nolint:errcheck // bench: unit-covered error path; measure the happy sign.
		sink = token
	}
}
