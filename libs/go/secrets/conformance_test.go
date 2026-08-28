package secrets_test

import (
	"testing"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// TestConformanceFake runs the exported Provider conformance suite (contract §4)
// against the canonical in-memory fake, proving the fake is a substitutable
// Provider and that the Secret type holds the redaction line.
func TestConformanceFake(t *testing.T) {
	t.Parallel()
	present := secrets.Ref("present-credential")
	absent := secrets.Ref("absent-credential")
	secretstest.RunProviderSuite(t, func() secrets.Provider {
		return secretstest.New(map[string]string{
			present.String(): secretstest.SeededPlaintext,
		})
	}, present, absent)
}

// TestConformanceMediator runs the identical Provider conformance suite (contract §4)
// against the production *secrets.Mediator — the concrete Provider returned by New
// (mediator.go: var _ Provider = (*Mediator)(nil)). The contract states the suite "proves
// any secrets.Provider (real adapter or secretstest.Provider) is substitutable", and the
// Mediator is a real production Provider, so it must pass the SAME property set the fake
// does — not merely the ad-hoc routing tests. The Mediator wraps a seeded fake adapter on
// the "test" scheme (which is also the DefaultScheme, so the schemeless `present`/`absent`
// references route to it), proving the full port contract holds through the routing layer.
func TestConformanceMediator(t *testing.T) {
	t.Parallel()
	present := secrets.Ref("present-credential")
	absent := secrets.Ref("absent-credential")
	secretstest.RunProviderSuite(t, func() secrets.Provider {
		adapter := secretstest.New(map[string]string{
			present.String(): secretstest.SeededPlaintext,
		})
		med, err := secrets.New(
			secrets.Config{DefaultScheme: "test"},
			secrets.Deps{Resolvers: map[string]secrets.Provider{"test": adapter}},
		)
		if err != nil {
			t.Fatalf("secrets.New error = %v", err)
		}
		return med
	}, present, absent)
}
