package platformconnectoradapter_test

import (
	"testing"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/platformconnectoradapter"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// presentRef / absentRef are the conformance references: present resolves through the seeded fake
// transport (an envelope-sealed row) to SeededPlaintext; absent names a connector id the transport does
// not hold (NotFound).
var (
	presentRef = secrets.Ref("eden://connector/present")
	absentRef  = secrets.Ref("eden://connector/absent")
)

// TestConformancePlatformConnectorAdapter runs THE exported Provider conformance suite (secrets.md §4)
// over the *platformconnectoradapter.Adapter with a seeded fake transport + a REAL envelope.Sealer over
// a fake KEK — proving the connector backend is a substitutable secrets.Provider (resolve,
// never-both-non-nil, typed NotFound/Invalid, error-carries-reference-never-value, Use-only,
// redaction-is-total, idempotent Zeroize, independence, reference round-trip) at the UNIT level. The
// REAL-Postgres arm of dimension (d) is integration_test.go (//go:build integration), which runs THIS
// SAME suite shape against an actual postgres — the fake here weakens only the ROW-LOAD source, never
// the contract (ADR-0016 §2; secrets.md §3 minting note). The crypto (envelope) is real in BOTH lanes.
func TestConformancePlatformConnectorAdapter(t *testing.T) {
	t.Parallel()
	secretstest.RunProviderSuite(t, func() secrets.Provider {
		transport := seededTransport(t, "present", secretstest.SeededPlaintext)
		return newAdapter(t, transport)
	}, presentRef, absentRef)
}

// TestConformanceConnectorBehindMediator runs the same suite over a production *secrets.Mediator that
// routes the "eden" scheme to the connector adapter ALONGSIDE the "vault" scheme — the real
// composition-root wiring (secrets.md §5, ADR-0029 §4): eden://connector/<id> routes to THIS adapter,
// vault:// would route to the Vault adapter. This proves the connector backend slots behind the
// EXISTING Mediator port with NO contract change (the load-bearing win), keyed under its own scheme.
func TestConformanceConnectorBehindMediator(t *testing.T) {
	t.Parallel()
	secretstest.RunProviderSuite(t, func() secrets.Provider {
		transport := seededTransport(t, "present", secretstest.SeededPlaintext)
		adapter := newAdapter(t, transport)
		// DefaultScheme stays vault (the production default); an eden reference carries its own scheme
		// explicitly, so it routes to the eden resolver regardless of the default.
		med, err := secrets.New(
			secrets.Config{DefaultScheme: "vault"},
			secrets.Deps{Resolvers: map[string]secrets.Provider{
				"eden": adapter,
			}},
		)
		if err != nil {
			t.Fatalf("secrets.New: %v", err)
		}
		return med
	}, presentRef, absentRef)
}

// compile-time: the adapter satisfies the port the suite is written against.
var _ secrets.Provider = (*platformconnectoradapter.Adapter)(nil)
