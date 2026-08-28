package vaultadapter_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/secrets"
)

// The sinks below prevent the compiler from proving the benchmarked work dead and eliding it.
// `any` keeps them off any typed sentinel path (ADR-0020 §g); package-level so the optimizer cannot
// see across the benchmark boundary.
//
//nolint:gochecknoglobals // benchmark sinks must be package-level so the compiler cannot elide the measured work.
var (
	sink    any
	sinkStr string
)

// BenchmarkVaultResolve measures the adapter's full resolve hot path over the fake transport: parse
// reference → (sticky) token → KV read → unwrap the KV v2 envelope → mint an independent Secret.
// This is the per-Resolve cost a consumer pays at point of use, isolated from real network latency
// (the fake transport returns in-memory) so the benchmark measures the ADAPTER's CPU/alloc cost, not
// Vault's. The performance lane (`ctl.sh bench`/`bench-guard`, dimension (g)) guards it against the
// .benchbaseline.
func BenchmarkVaultResolve(b *testing.B) {
	transport := &fakeTransport{kv: map[string]map[string]any{
		"eden/data/connectors/github": kvEnvelope(map[string]any{"token": "benchmark-value-not-a-real-credential"}),
	}}
	adapter := newAdapterTB(b, transport)
	ref := secrets.Ref("vault://eden/connectors/github#token")
	ctx := context.Background()
	var (
		sec  *secrets.Secret
		rerr error
	)
	b.ReportAllocs()
	for b.Loop() {
		sec, rerr = adapter.Resolve(ctx, ref)
		if sec != nil {
			sec.Zeroize()
		}
	}
	sink = sec
	sink = rerr
}

// BenchmarkVaultParseReference measures just the reference parse spine (vault://<mount>/<path>#<key>
// → mount/path/key) the adapter runs on every Resolve before any I/O.
func BenchmarkVaultParseReference(b *testing.B) {
	transport := &fakeTransport{kv: map[string]map[string]any{
		"eden/data/connectors/github": kvEnvelope(map[string]any{"token": "v"}),
	}}
	adapter := newAdapterTB(b, transport)
	// Drive Resolve on a MISSING field so the parse + token + read run but no mint allocates — the
	// parse cost dominates. (A malformed ref would short-circuit before the token path.)
	ref := secrets.Ref("vault://eden/connectors/github#absent")
	ctx := context.Background()
	var rerr error
	b.ReportAllocs()
	for b.Loop() {
		_, rerr = adapter.Resolve(ctx, ref)
	}
	sinkStr = rerr.Error()
}
