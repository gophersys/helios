package observabilitytest

import (
	"github.com/gophersys/libs/go/observability"
)

// newFakeFromDeps builds the PUBLIC *Provider (the same type kernel tests inject)
// in its Exporter-backed mode, from a full Config/Deps. This is the factory the
// conformance suite (Run) drives, so the fake proven substitutable against the
// real adapter is the very fake consumers use — not a private duplicate of
// state.go. It honors DefaultPlane, MinSeverity, resource stamping, Scope
// correlation, and ships resource-stamped Records to Deps.Exporter on Flush, and
// returns a *ConfigError on the same validation failures the real New rejects
// (empty ServiceName, nil Exporter, nil Clock) so the NewValidationErrors property
// holds for the fake too.
//
// It returns the observability.Provider interface because the contract §4
// conformance harness signature (func(Config, Deps) (Provider, error)) requires
// it; this public fake is passed to Run exactly where the real New is.
//
//nolint:ireturn // contract §4 conformance harness signature returns Provider.
func newFakeFromDeps(configuration observability.Config, dependencies observability.Deps) (observability.Provider, error) {
	if configuration.ServiceName == "" {
		return nil, &observability.ConfigError{Field: "ServiceName", Message: "required"}
	}
	if dependencies.Exporter == nil {
		return nil, &observability.ConfigError{Field: "Exporter", Message: "required (non-nil)"}
	}
	if dependencies.Clock == nil {
		return nil, &observability.ConfigError{Field: "Clock", Message: "required (non-nil)"}
	}

	resource := map[string]string{
		"service.name":                configuration.ServiceName,
		"service.version":             configuration.ServiceVersion,
		"deployment.environment.name": configuration.Environment,
	}
	for k, v := range configuration.ResourceAttrs {
		// ResourceAttrs never override the reserved OTel keys above (mirrors state.go).
		if _, reserved := resource[k]; reserved {
			continue
		}
		resource[k] = v
	}

	defPlane := configuration.DefaultPlane
	if defPlane == observability.PlaneUnset {
		defPlane = observability.PlaneSelf
	}

	clock := dependencies.Clock
	return &Provider{
		state: &fakeState{
			exporter:    dependencies.Exporter,
			resource:    resource,
			minSeverity: configuration.MinSeverity,
		},
		clock:    clock.Now,
		defPlane: defPlane,
	}, nil
}

// flushError wraps the Exporter cause with %w (Unwrap), mirroring the real impl's
// Flush contract so the conformance FlushIsSoleBlockingErrorCall property holds.
type flushError struct{ cause error }

func (e *flushError) Error() string { return "observabilitytest: flush: " + e.cause.Error() }
func (e *flushError) Unwrap() error { return e.cause }
