package vaultadapter_test

import (
	"testing"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// presentRef / absentRef are the conformance references: present resolves through the seeded fake
// transport to SeededPlaintext; absent names a KV path the transport does not hold (NotFound).
var (
	presentRef = secrets.Ref("vault://eden/connectors/present#token")
	absentRef  = secrets.Ref("vault://eden/connectors/absent#token")
)

// TestConformanceVaultAdapter runs THE exported Provider conformance suite (secrets.md §4) over
// the *vaultadapter.Adapter with a seeded fake transport — proving the Vault backend is a
// substitutable secrets.Provider (resolve, never-both-non-nil, typed NotFound/Invalid,
// error-carries-reference-never-value, Use-only, redaction-is-total, idempotent Zeroize,
// independence, reference round-trip) at the UNIT level. The REAL-Vault arm of dimension (d) is
// integration_test.go (//go:build integration), which runs THIS SAME suite shape against an actual
// hashicorp/vault container — the fake here weakens only the transport SOURCE, never the contract
// (ADR-0016 §2; secrets.md §3 minting note).
func TestConformanceVaultAdapter(t *testing.T) {
	t.Parallel()
	secretstest.RunProviderSuite(t, func() secrets.Provider {
		transport := &fakeTransport{kv: map[string]map[string]any{
			// present resolves; absent is simply absent from the map (→ NotFound).
			"eden/data/connectors/present": kvEnvelope(map[string]any{"token": secretstest.SeededPlaintext}),
		}}
		return newUserpassAdapter(t, transport)
	}, presentRef, absentRef)
}

// TestConformanceVaultBehindMediator runs the same suite over a production *secrets.Mediator that
// routes the "vault" scheme to the Vault adapter — the real composition-root wiring (secrets.md
// §5): the schemeless DefaultScheme is "vault", so present/absent route to the adapter. This proves
// the Vault backend slots behind the EXISTING Mediator port with NO contract change (ADR-0022 #1).
func TestConformanceVaultBehindMediator(t *testing.T) {
	t.Parallel()
	secretstest.RunProviderSuite(t, func() secrets.Provider {
		transport := &fakeTransport{kv: map[string]map[string]any{
			"eden/data/connectors/present": kvEnvelope(map[string]any{"token": secretstest.SeededPlaintext}),
		}}
		adapter := newUserpassAdapter(t, transport)
		med, err := secrets.New(
			secrets.Config{DefaultScheme: "vault"},
			secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": adapter}},
		)
		if err != nil {
			t.Fatalf("secrets.New error = %v", err)
		}
		return med
	}, presentRef, absentRef)
}
