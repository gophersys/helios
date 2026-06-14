package secrets_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// The sinks below prevent the compiler from proving the benchmarked work dead and eliding it.
// `any` keeps them off any typed sentinel path (ADR-0020 §g); they are package-level so the
// optimizer cannot see across the benchmark boundary.
//
//nolint:gochecknoglobals // benchmark sinks must be package-level so the compiler cannot elide the measured work.
var (
	sink    any
	sinkStr string
)

// BenchmarkParseReference measures the reference parse/validate spine — the hot path every
// config-driven Reference passes through (shape validation, no I/O). The performance lane
// (`ctl.sh bench` / `bench-guard`, ADR-0020 dimension (g)) records this at -benchmem -count=10
// and benchstat guards HEAD vs the .benchbaseline so a regression > +10% time or allocs fails.
func BenchmarkParseReference(b *testing.B) {
	const raw = "vault://eden/connectors/github#token"
	var (
		r   secrets.Reference
		err error
	)
	b.ReportAllocs()
	for b.Loop() {
		r, err = secrets.ParseReference(raw)
	}
	sink = r
	sink = err
}

// BenchmarkReferenceScheme measures the routing-key extraction (Scheme) the Mediator switches on
// for every Resolve.
func BenchmarkReferenceScheme(b *testing.B) {
	r := secrets.Ref("vault://eden/connectors/github#token")
	b.ReportAllocs()
	for b.Loop() {
		sinkStr = r.Scheme()
	}
}

// BenchmarkMintSecret measures the Secret constructor (private copy of the plaintext) — the cost
// every Resolve pays to hand back an independent, owned Secret.
func BenchmarkMintSecret(b *testing.B) {
	plaintext := []byte("sk-benchmark-secret-value-0123456789")
	var sec *secrets.Secret
	b.ReportAllocs()
	for b.Loop() {
		sec = secretstest.MintSecret(plaintext)
	}
	sink = sec
}

// BenchmarkSecretUse measures the only read path — the RLock-scoped Use call consumers make at
// point of use. It is reentrant-read-safe, so this is the per-use overhead under no contention.
func BenchmarkSecretUse(b *testing.B) {
	sec := secretstest.MintSecret([]byte("sk-benchmark-secret-value-0123456789"))
	defer sec.Zeroize()
	var (
		n   int
		err error
	)
	b.ReportAllocs()
	for b.Loop() {
		err = sec.Use(func(p []byte) error { n = len(p); return nil })
	}
	sink = n
	sink = err
}

// BenchmarkSecretRedact measures the load-bearing redaction surface (the Format override that
// closes every fmt verb at once) — the per-render cost on any log/telemetry path that touches a
// Secret. It must be cheap because it runs on every accidental render attempt.
func BenchmarkSecretRedact(b *testing.B) {
	sec := secretstest.MintSecret([]byte("sk-benchmark-secret-value-0123456789"))
	defer sec.Zeroize()
	b.ReportAllocs()
	for b.Loop() {
		sinkStr = sec.String()
	}
}

// BenchmarkMediatorResolve measures the full production resolve spine: route by scheme → adapter
// Resolve → mint an independent Secret. This is the hottest end-to-end path a consumer drives.
func BenchmarkMediatorResolve(b *testing.B) {
	ref := secrets.Ref("vault://eden/connectors/github#token")
	adapter := secretstest.New(map[string]string{ref.String(): "sk-benchmark-secret-value-0123456789"})
	med, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": adapter}},
	)
	if err != nil {
		b.Fatalf("secrets.New error = %v", err)
	}
	ctx := context.Background()
	var (
		sec  *secrets.Secret
		rerr error
	)
	b.ReportAllocs()
	for b.Loop() {
		sec, rerr = med.Resolve(ctx, ref)
		if sec != nil {
			sec.Zeroize()
		}
	}
	sink = sec
	sink = rerr
}
