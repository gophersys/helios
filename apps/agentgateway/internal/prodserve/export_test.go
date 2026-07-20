package prodserve

import (
	"context"

	"github.com/gophersys/libs/go/orchestrator"
)

// The white-box test seam: it exposes the package-internal composition units (the pure Config
// validation, the record-plane template store, and the propose-wiring seam) to the black-box
// prodserve_test files WITHOUT widening the public surface (BuildProductionGateway is the only
// exported constructor). These are the pure wiring internals a fast unit test exercises mock-free.

// ValidateConfig re-exports the pure Config.validate seam for the unit test.
func ValidateConfig(configuration *Config) error { return configuration.validate() }

// ResolveTemplate re-exports the record-plane templateStore.Resolve seam for the unit test.
//
//nolint:gocritic // the test drives Resolve through the orchestrator.TemplateStore contract (ref by value).
func ResolveTemplate(ctx context.Context, ref orchestrator.TemplateRef) (orchestrator.AgentTemplate, error) {
	return templateStore{}.Resolve(ctx, ref)
}

// ProposerConfigured reports whether buildProposer wires a proposer for the given credential state —
// the seam the propose degrade-honest test asserts (nil credential → no proposer → the route 503s).
func ProposerConfigured(credentialReference string) bool {
	configuration := Config{CredentialReference: credentialReference}
	return buildProposer(nil, &configuration, nil) != nil
}
