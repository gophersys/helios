package connectorcredential_test

import (
	"context"
	"testing"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/agentgateway/internal/connectorcredential"
)

// fallbackRef is the platform credential reference the derivation degrades to (the EDEN_CREDENTIAL_REF
// plane) — the behavior that must NEVER be regressed.
var fallbackRef = secrets.Ref("vault://eden/production#setup-token")

// TestDeriveClaudeCredential_NilPoolReturnsFallback proves the load-bearing degrade-honest rule: with
// no connectors database (a nil pool — a deployment without the connectors DSN), the derivation ALWAYS
// returns the platform fallback, so today's behavior is preserved exactly.
func TestDeriveClaudeCredential_NilPoolReturnsFallback(t *testing.T) {
	t.Parallel()
	deriver := connectorcredential.NewDeriver(nil, fallbackRef)
	got := deriver.DeriveClaudeCredential(context.Background(), uuid.New())
	if got.String() != fallbackRef.String() {
		t.Errorf("DeriveClaudeCredential(nil pool) = %q, want the fallback %q", got.String(), fallbackRef.String())
	}
}

// TestBuild_NoDSNReturnsDegradedSeam proves that with no connectors DSN, Build returns a degraded Seam
// (Adapter nil, Deriver always-fallback, Close a no-op) — a deployment without the connectors database
// behaves exactly as today, and no "eden" scheme is bound.
func TestBuild_NoDSNReturnsDegradedSeam(t *testing.T) {
	t.Parallel()
	seam, err := connectorcredential.Build(
		context.Background(),
		connectorcredential.Config{Fallback: fallbackRef}, // no ConnectorsDSN
		connectorcredential.Deps{},
	)
	if err != nil {
		t.Fatalf("Build(no DSN) err = %v", err)
	}
	if seam.Adapter != nil {
		t.Error("Build(no DSN): Adapter should be nil (no eden scheme to bind)")
	}
	if seam.Deriver == nil {
		t.Fatal("Build(no DSN): Deriver must never be nil")
	}
	if seam.Close == nil {
		t.Fatal("Build(no DSN): Close must never be nil")
	}
	seam.Close() // a no-op; must not panic
	got := seam.Deriver.DeriveClaudeCredential(context.Background(), uuid.New())
	if got.String() != fallbackRef.String() {
		t.Errorf("degraded Deriver = %q, want the fallback", got.String())
	}
}

// TestBuild_DSNWithoutSecretsIsInvalid proves Build rejects a connectors DSN without the KEK resolution
// port (the KEK plane must be wired when connector resolution is on).
func TestBuild_DSNWithoutSecretsIsInvalid(t *testing.T) {
	t.Parallel()
	_, err := connectorcredential.Build(
		context.Background(),
		connectorcredential.Config{
			ConnectorsDSN: "postgres://ignored",
			KEK:           secrets.Ref("vault://eden/production#connectors-kek"),
			Fallback:      fallbackRef,
		},
		connectorcredential.Deps{}, // no Secrets
	)
	if err == nil {
		t.Fatal("Build(DSN without Secrets) should error")
	}
}
