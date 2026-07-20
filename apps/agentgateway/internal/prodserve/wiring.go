package prodserve

import (
	"context"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/orchestrator"
)

// orchestratorTelemetry closes the narrow orchestrator.Telemetry port (Emit(ctx, ObservabilityEvent))
// onto a full observability.Provider for the STATELESS RECORD PLANE the gateway holds — a distinct
// composition from the orchestrator ROLE's reconcile-plane telemetry (that shim lives in
// orchestratorservice). Here the only orchestration events are admission/limit ticks from Spawn (no
// reconcile transitions — this Pool never runs the loop), so the mapping is compact: one dotted Name
// per Kind on PlaneAgent, redaction-safe Fields only (the tenancy keys + the agent id + the already-
// redacted Detail — never a secret). It is best-effort and non-blocking (the Provider never blocks).
type orchestratorTelemetry struct {
	provider observability.Provider
}

// static assertion: the shim binds the orchestrator.Telemetry port the record-plane Pool holds.
var _ orchestrator.Telemetry = orchestratorTelemetry{}

// Emit maps one record-plane ObservabilityEvent onto an observability.Event on PlaneAgent. A rejected
// spawn is a Warning the operator should see; an admitted spawn is informational. NO field is a secret.
//
//nolint:gocritic // ObservabilityEvent is a small copyable value envelope; the shim receives its own copy by design.
func (t orchestratorTelemetry) Emit(ctx context.Context, event orchestrator.ObservabilityEvent) {
	severity := observability.SeverityInfo
	name := "orchestrator.spawn.admitted"
	if event.Kind == orchestrator.ObsLimitRejected {
		severity = observability.SeverityWarn
		name = "orchestrator.spawn.limit-rejected"
	}
	t.provider.Emit(ctx, observability.Event{
		Plane:    observability.PlaneAgent,
		Severity: severity,
		Name:     name,
		Fields: []observability.Field{
			observability.String("eden.agent", string(event.AgentID)),
			observability.String("eden.org", event.Tenant.OrganizationID),
			observability.String("eden.project", event.Tenant.ProjectID),
			observability.String("eden.orchestration.kind", event.Kind.String()),
			observability.String("eden.detail", event.Detail),
		},
	})
}

// templateStore is the production record-plane orchestrator.TemplateStore: it resolves the agent
// templates a POST /sessions create names into the immutable AgentTemplate the Manager records the
// desired spawn under. The record plane only needs the template's IDENTITY (Ref) + a sane default
// sandbox — the ORCHESTRATOR (the separate deployment) owns the authoritative template→pod compile
// when it reconciles the desired record, so this store never has to compile a workload sandbox.
//
// It resolves ANY well-formed TemplateRef to a minimal AgentTemplate carrying that Ref (so the UI's
// create request is admitted and the desired row is written under the named template); a ZERO ref is
// the one honest rejection — a classified TemplateNotFoundError (KindNotFound → 404 with its Kind,
// never an unknown 404). This is deliberately permissive at the RECORD layer: admission (tenancy +
// the concurrency ceiling) is enforced by the Pool over the DesiredStore, and the orchestrator
// validates the template against its own authoritative catalog when it provisions — a create for a
// template the cluster cannot ultimately provision surfaces as a FAILED reconcile the dashboard shows,
// not as a lost request. Its zero value is usable (it holds no state).
type templateStore struct{}

// static assertion: templateStore binds the frozen orchestrator.TemplateStore port (Resolve only).
var _ orchestrator.TemplateStore = templateStore{}

// Resolve returns the minimal AgentTemplate for a well-formed ref, or a classified
// TemplateNotFoundError for a zero ref (an ill-formed create request).
//
//nolint:gocritic // contract: TemplateStore.Resolve takes the TemplateRef by value (the frozen port surface).
func (templateStore) Resolve(_ context.Context, ref orchestrator.TemplateRef) (orchestrator.AgentTemplate, error) {
	if ref.IsZero() {
		return orchestrator.AgentTemplate{}, errors.Wrap(errors.KindNotFound, "prodserve: resolve template",
			&orchestrator.TemplateNotFoundError{Ref: ref})
	}
	return orchestrator.AgentTemplate{Ref: ref}, nil
}
