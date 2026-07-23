package prodserve_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/agentgateway/internal/prodserve"
)

// stubProvider is a minimal non-nil secrets.Provider so a Config that only exercises the pure
// validate seam (never resolving) has a present provider. It is NEVER resolved in these tests —
// they cover the constructor's pre-flight, not a live pool.
type stubProvider struct{}

//nolint:nilnil // the stub is never resolved in the pure seam tests; the return is unreachable and only satisfies the port.
func (stubProvider) Resolve(context.Context, secrets.Reference) (*secrets.Secret, error) {
	return nil, nil
}

// validConfig is the fully-populated Config the validate happy-path expects; cases clear one field.
// Every string is an opaque vault:// REFERENCE (a path) or a non-secret literal, never a value.
//
//nolint:gosec // G101: the CredentialReference is an opaque vault path and the DSN has no password segment — fixtures, not credentials.
func validConfig() prodserve.Config {
	return prodserve.Config{
		Provider:            stubProvider{},
		DatabaseURL:         "postgres://eden@postgres:5432/eden?sslmode=disable",
		CredentialReference: "vault://eden/production#setup-token",
		Harness:             "claude-code",
		Model:               "opus",
		Workspace:           "/tmp/eden-gateway-workspace",
	}
}

// TestConfigValidate_HappyPath proves a fully-populated Config validates.
func TestConfigValidate_HappyPath(t *testing.T) {
	t.Parallel()
	configuration := validConfig()
	if err := prodserve.ValidateConfig(&configuration); err != nil {
		t.Fatalf("validate: unexpected error on the happy path: %v", err)
	}
}

// TestConfigValidate_MissingRequiredIsInvalid proves each required seam is a classified KindInvalid
// error naming the field (never echoing a value).
func TestConfigValidate_MissingRequiredIsInvalid(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name   string
		mutate func(*prodserve.Config)
	}{
		{"missing Provider", func(c *prodserve.Config) { c.Provider = nil }},
		{"missing DatabaseURL", func(c *prodserve.Config) { c.DatabaseURL = "" }},
		{"missing Workspace", func(c *prodserve.Config) { c.Workspace = "" }},
		{"missing Harness", func(c *prodserve.Config) { c.Harness = "" }},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			configuration := validConfig()
			testCase.mutate(&configuration)
			err := prodserve.ValidateConfig(&configuration)
			if err == nil {
				t.Fatalf("validate: want a typed error for %q, got nil", testCase.name)
			}
			if got := errors.KindOf(err); got != errors.KindInvalid {
				t.Fatalf("validate: error Kind = %v, want KindInvalid for %q (err: %v)", got, testCase.name, err)
			}
		})
	}
}

// TestTemplateStore_ResolvesWellFormedRef proves the record-plane template store admits a well-formed
// TemplateRef (returning the AgentTemplate carrying that ref) and REJECTS a zero ref with a
// classified KindNotFound — the honest degradation for an ill-formed create request (never a raw 404).
func TestTemplateStore_ResolvesWellFormedRef(t *testing.T) {
	t.Parallel()
	ref := orchestrator.TemplateRef{Name: "build-agent", Version: "1.0.0"}
	template, err := prodserve.ResolveTemplate(context.Background(), ref)
	if err != nil {
		t.Fatalf("Resolve: unexpected error for a well-formed ref: %v", err)
	}
	if template.Ref != ref {
		t.Fatalf("Resolve: template.Ref = %+v, want the requested %+v", template.Ref, ref)
	}

	_, zeroErr := prodserve.ResolveTemplate(context.Background(), orchestrator.TemplateRef{})
	if zeroErr == nil {
		t.Fatal("Resolve: want a typed error for a zero ref, got nil")
	}
	if got := errors.KindOf(zeroErr); got != errors.KindNotFound {
		t.Fatalf("Resolve: zero-ref error Kind = %v, want KindNotFound", got)
	}
	if !errors.IsType[*orchestrator.TemplateNotFoundError](zeroErr) {
		t.Fatalf("Resolve: zero-ref error is not a TemplateNotFoundError: %v", zeroErr)
	}
}

// TestBuildProposer_NilWithoutCredential proves the propose seam degrades honestly: with no credential
// reference the proposer is nil (the gateway then serves POST /product/propose as a classified 503,
// not a 404), and with a credential it is wired.
func TestBuildProposer_NilWithoutCredential(t *testing.T) {
	t.Parallel()
	if prodserve.ProposerConfigured("") {
		t.Fatal("buildProposer: want nil (no proposer) when no credential reference is configured")
	}
	if !prodserve.ProposerConfigured("vault://eden/production#setup-token") {
		t.Fatal("buildProposer: want a wired proposer when a credential reference is set")
	}
}

// TestBuildSessionPool_Constructs is the v0.1.7 crash-loop regression: the propose pool must
// CONSTRUCT from a valid Config (agentsession.New rejects a nil Transcript — the exact boot fault
// that CrashLooped the production pod because no test built the pool). Pure construction, no I/O.
func TestBuildSessionPool_Constructs(t *testing.T) {
	t.Parallel()
	configuration := validConfig()
	if err := prodserve.BuildSessionPoolSeam(&configuration); err != nil {
		t.Fatalf("buildSessionPool: the propose pool must construct from a valid Config (the v0.1.7 crash-loop): %v", err)
	}
}
