package orchestratorservice

import (
	"context"

	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/orchestrator"
)

// observabilityTelemetry is the seam that closes orchestrator.Telemetry (the narrow
// Emit(ctx, ObservabilityEvent) port the Pool emits on) onto a full observability.Provider.
// It lives HERE, at the composition root, NOT in the orchestrator library — so orchestrator
// stays a leaf-ish library that never imports observability's Event shape (the mapping is the
// seam's job, mirroring how secrets.TelemetryValue closes the observability seam structurally).
//
// It maps every orchestration-plane ObservabilityKind onto a stable, low-cardinality dotted
// Event Name on observability.PlaneAgent (agent runs / transitions / cost ledger), stamping the
// transition (from→to), the tenancy keys, the agent id, the redacted detail, and the folded
// token ledger as redaction-safe Fields. NO field is ever a secret value (the Detail is the
// orchestrator's already-redacted reason; the tenancy keys and ids are loggable by contract).
type observabilityTelemetry struct {
	provider observability.Provider
}

// static assertion: the shim binds the orchestrator.Telemetry port the Pool holds.
var _ orchestrator.Telemetry = observabilityTelemetry{}

// newObservabilityTelemetry wraps an observability.Provider as the orchestrator.Telemetry seam.
func newObservabilityTelemetry(provider observability.Provider) observabilityTelemetry {
	return observabilityTelemetry{provider: provider}
}

// Emit maps one orchestration-plane ObservabilityEvent onto an observability.Event on
// PlaneAgent and hands it to the Provider. Telemetry is best-effort and non-blocking (the
// Provider's Emit never blocks the hot path), so a dropped event can never fail a transition —
// the Pool's emit already treats this as fire-and-forget.
//
//nolint:gocritic // ObservabilityEvent is a small copyable value envelope; the shim receives its own copy by design.
func (t observabilityTelemetry) Emit(ctx context.Context, event orchestrator.ObservabilityEvent) {
	fields := []observability.Field{
		observability.String("eden.agent", string(event.AgentID)),
		observability.String("eden.org", event.Tenant.OrganizationID),
		observability.String("eden.project", event.Tenant.ProjectID),
		observability.String("eden.orchestration.kind", event.Kind.String()),
		observability.String("eden.orchestration.from", event.From.String()),
		observability.String("eden.orchestration.to", event.To.String()),
		observability.String("eden.detail", event.Detail),
		observability.Int64("eden.cost.micros", event.Ledger.CostMicros),
		observability.Int64("eden.cost.turns", int64(event.Ledger.Turns)),
	}
	t.provider.Emit(ctx, observability.Event{
		Plane:    observability.PlaneAgent,
		Severity: severityFor(event.Kind),
		Name:     eventNameFor(event.Kind),
		Fields:   fields,
	})
}

// eventNameFor maps an orchestration-plane kind onto the stable, dotted, low-cardinality OTel
// Event name. The names are the orchestration-plane vocabulary the dashboard/log backend groups
// by; they are append-only with the ObservabilityKind set (10 §9).
func eventNameFor(kind orchestrator.ObservabilityKind) string {
	switch kind {
	case orchestrator.ObsSpawnAdmitted:
		return "orchestrator.spawn.admitted"
	case orchestrator.ObsLimitRejected:
		return "orchestrator.spawn.limit-rejected"
	case orchestrator.ObsTransition:
		return "orchestrator.agent.transition"
	case orchestrator.ObsLedgerTick:
		return "orchestrator.agent.ledger-tick"
	case orchestrator.ObsBudgetExceeded:
		return "orchestrator.agent.budget-exceeded"
	case orchestrator.ObsReconcileError:
		return "orchestrator.agent.reconcile-error"
	default:
		return "orchestrator.agent.transition"
	}
}

// severityFor classifies an orchestration-plane kind onto an observability Severity: a rejected
// spawn or a reconcile fault is a Warning/Error the operator should see; every other transition
// is informational.
func severityFor(kind orchestrator.ObservabilityKind) observability.Severity {
	switch kind {
	case orchestrator.ObsReconcileError:
		return observability.SeverityError
	case orchestrator.ObsLimitRejected, orchestrator.ObsBudgetExceeded:
		return observability.SeverityWarn
	case orchestrator.ObsSpawnAdmitted, orchestrator.ObsTransition, orchestrator.ObsLedgerTick:
		return observability.SeverityInfo
	default:
		return observability.SeverityInfo
	}
}
