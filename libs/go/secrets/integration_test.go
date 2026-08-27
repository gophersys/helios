//go:build integration

package secrets_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// The integration lane (`ctl.sh integration`, ADR-0020 dimension (d)) runs the SAME exported
// Provider conformance suite (secretstest.RunProviderSuite) over the REAL production substrate
// for this leaf library. secrets is a pure, in-process value library — its EDEN_INTEGRATION_CMDS
// is "go", so the "real substrate" it leverages is the Go runtime itself (the standard library's
// encoding/json, log/slog, fmt verb machinery, and sync primitives the Secret's redaction and
// concurrency invariants ride on), NOT docker/k3d (there is no daemon to provision: a secret
// reference resolves to bytes in memory, not to a container). The contract holding over the real
// production *secrets.Mediator — the concrete Provider New returns — under the integration tag is
// the dimension-(d) proof for this lib: the full port contract (resolve, redaction-is-total,
// independence, typed errors, the Use-only read path) is exercised through the real routing layer,
// not a mock of it.

// TestIntegration_MediatorConformsToProviderPort runs the full Provider conformance suite over
// the production *secrets.Mediator, with a seeded fake adapter on the "test" scheme (also the
// DefaultScheme, so the schemeless present/absent references route to it). This is the real
// production code path end-to-end: New wires the routing Mediator, every conformance property
// (happy path, never-both-non-nil, typed NotFound/Invalid, error-carries-reference-never-value,
// Use-only, redaction-is-total, idempotent Zeroize, independence, reference round-trip) holds
// through it.
func TestIntegration_MediatorConformsToProviderPort(t *testing.T) {
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

// TestIntegration_RealRoutingAcrossSchemes drives the Mediator over MULTIPLE real adapters bound
// to distinct schemes and resolves a reference through each, proving the routing table the
// composition root injects works against the real Mediator (not a mock router): each Reference
// reaches exactly the adapter that owns its scheme, the resolved Secret exposes the right value
// through Use, and an unbound scheme yields the typed InvalidReferenceError.
func TestIntegration_RealRoutingAcrossSchemes(t *testing.T) {
	t.Parallel()
	vault := secretstest.New(map[string]string{"vault://db#password": "vault-pw"})
	env := secretstest.New(map[string]string{"env://API_KEY": "env-key"})
	med, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": vault, "env": env}},
	)
	if err != nil {
		t.Fatalf("secrets.New error = %v", err)
	}
	ctx := context.Background()

	for _, tc := range []struct {
		ref  string
		want string
	}{
		{"vault://db#password", "vault-pw"},
		{"env://API_KEY", "env-key"},
	} {
		sec, rerr := med.Resolve(ctx, secrets.Ref(tc.ref))
		if rerr != nil {
			t.Fatalf("Resolve(%q) error = %v", tc.ref, rerr)
		}
		var got string
		if uerr := sec.Use(func(b []byte) error { got = string(b); return nil }); uerr != nil {
			t.Fatalf("Use(%q) error = %v", tc.ref, uerr)
		}
		sec.Zeroize()
		if got != tc.want {
			t.Errorf("Resolve(%q) routed to the wrong value: got %q want %q", tc.ref, got, tc.want)
		}
	}

	// An unbound scheme is unroutable → typed InvalidReferenceError, never a panic or a wrong route.
	if _, rerr := med.Resolve(ctx, secrets.Ref("keychain://thing")); !errors.IsType[secrets.InvalidReferenceError](rerr) {
		t.Errorf("Resolve(unbound scheme) error not AsType[InvalidReferenceError]: %v", rerr)
	}
}
