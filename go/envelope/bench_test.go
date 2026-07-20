package envelope_test

import (
	"bytes"
	"context"
	"testing"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/libs/go/envelope"
)

// The package-level sinks keep the benchmarked work observable so the compiler cannot prove the
// result dead and elide the crypto being measured. An `any` sink stays off any sentinel path.
//
//nolint:gochecknoglobals // benchmark sinks must be package-level so the compiler cannot elide the measured work.
var (
	sinkSealed envelope.Sealed
	sinkString string
)

// benchEnvelope builds a benchmark Envelope over a fake Provider yielding a fixed 32-byte KEK. The
// fake resolves in-memory, so the benchmark measures the AES-256-GCM seal/wrap cost, not I/O.
func benchEnvelope(b *testing.B) *envelope.Envelope {
	b.Helper()
	provider := secretstest.New(map[string]string{"connectors-kek": string(bytes.Repeat([]byte("KEK0"), 8))})
	env, err := envelope.New(
		envelope.Config{KEK: secrets.Ref("connectors-kek"), KEKVersion: 1},
		envelope.Deps{Secrets: provider},
	)
	if err != nil {
		b.Fatalf("New: %v", err)
	}
	return env
}

// BenchmarkSeal measures the seal spine — the write-path hot loop (mint DEK, encrypt, resolve+wrap).
// The performance lane (`ctl.sh bench` / `bench-guard`, ADR-0020 dimension (g)) records it at
// -benchmem -count=10 and benchstat guards HEAD vs .benchbaseline (> +10% time/allocs fails).
func BenchmarkSeal(b *testing.B) {
	env := benchEnvelope(b)
	plaintext := []byte("sk-ant-a-fake-sentinel-token-value-of-realistic-length")
	var out envelope.Sealed
	b.ReportAllocs()
	for b.Loop() {
		s, err := env.Seal(context.Background(), plaintext)
		if err != nil {
			b.Fatalf("Seal: %v", err)
		}
		out = s
	}
	sinkSealed = out
}

// BenchmarkUnseal measures the read-path hot loop (resolve+open KEK, open ciphertext), the path an
// agent session takes to resolve a connector.
func BenchmarkUnseal(b *testing.B) {
	env := benchEnvelope(b)
	sealed, err := env.Seal(context.Background(), []byte("sk-ant-a-fake-sentinel-token-value"))
	if err != nil {
		b.Fatalf("Seal: %v", err)
	}
	b.ReportAllocs()
	for b.Loop() {
		if uerr := env.Unseal(context.Background(), sealed, func([]byte) error { return nil }); uerr != nil {
			b.Fatalf("Unseal: %v", uerr)
		}
	}
}

// BenchmarkFingerprint measures the change-detection digest (SHA-256 + truncate), computed on every
// write.
func BenchmarkFingerprint(b *testing.B) {
	plaintext := []byte("sk-ant-a-fake-sentinel-token-value")
	var fp string
	b.ReportAllocs()
	for b.Loop() {
		fp = envelope.Fingerprint(plaintext)
	}
	sinkString = fp
}
