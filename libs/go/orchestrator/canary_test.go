package orchestrator_test

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// The credential canary is the redaction needle (ADR-0020 dimension (f)): the orchestratortest
// harness seeds orchestratortest.SeededCanary as the plaintext that orchestratortest.
// SeededCredentialRef resolves to SERVER-SIDE at agentsession.Open. The orchestrator threads
// only the loggable secrets.Reference through Spawn → the fold → agentsession.Spec.Credential;
// the VALUE has NO path onto the published surface (no Agent record, no ObservabilityEvent, no
// DesiredStore row, no error string, no recorded workspace spec). One leak fails the lane. The
// `secretscan` verb runs `go test -run 'Canary|Redact|Secret'`, so these names match.

// canaryManager builds a deterministic Manager seeded with the default template; the harness
// already wires the seeded canary into the secrets provider.
func canaryManager(t *testing.T) *orchestratortest.Manager {
	t.Helper()
	return orchestratortest.New(
		orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()),
		orchestratortest.WithMaxConcurrent(0),
	)
}

// canaryRequest is the canonical SpawnRequest whose Credential resolves to the seeded canary.
func canaryRequest() orchestrator.SpawnRequest {
	return orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: "org-canary", ProjectID: "proj-canary"},
		Template:   orchestratortest.DefaultTemplate().Ref,
		Credential: secrets.Ref(orchestratortest.SeededCredentialRef),
		By:         "canary",
		RunID:      "run-canary",
	}
}

// TestCanary_CredentialNeverSurfacesOnHappyPath spawns an agent whose credential resolves to
// the seeded canary, drives it through the FULL lifecycle (Spawn → Provisioning → Running →
// Stop → Stopped), then asserts the canary appears in NONE of: any Agent record version (the
// full Put history, not just the final record), any ObservabilityEvent, or any recorded
// workspace spec/env. Reaching Running with a non-empty SessionRef is the NON-VACUOUS proof the
// opaque credential actually threaded through to agentsession.Open (Open resolves the reference
// server-side and would fail → StatusFailed if the credential had not flowed) — so this is a
// real end-to-end thread, not a credential that was simply never used.
func TestCanary_CredentialNeverSurfacesOnHappyPath(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	manager := canaryManager(t)
	manager.Probe().SetDefault(orchestrator.Actual{WorkspaceLive: true, SessionLive: true})

	agent, err := manager.Spawn(ctx, canaryRequest())
	if err != nil {
		t.Fatalf("Spawn: %v", err)
	}
	// Drive to Running (Pending → Provisioning → Running).
	for pass := 0; pass < 6; pass++ {
		got, gerr := manager.Get(ctx, agent.ID)
		if gerr != nil {
			t.Fatalf("Get: %v", gerr)
		}
		if got.Status == orchestrator.StatusRunning {
			break
		}
		if _, rerr := manager.Reconcile(ctx); rerr != nil {
			t.Fatalf("Reconcile: %v", rerr)
		}
	}
	running, err := manager.Get(ctx, agent.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if running.Status != orchestrator.StatusRunning {
		t.Fatalf("agent reached %v, want Running (the credential did not thread through Open)", running.Status)
	}
	// NON-VACUITY: a Running agent with a SessionRef means agentsession.Open resolved the
	// credential server-side and succeeded — the opaque reference genuinely flowed.
	if running.Session == "" {
		t.Fatalf("Running agent has no SessionRef — the credential did not thread through Open")
	}

	// Drive a full Stop so the record is finalized and the workspace released.
	if err := manager.Stop(ctx, agent.ID, "operator"); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	for pass := 0; pass < 4; pass++ {
		if _, rerr := manager.Reconcile(ctx); rerr != nil {
			t.Fatalf("Reconcile drain: %v", rerr)
		}
	}

	// The runnable carries-refs-never-values guarantee over every record version, every
	// ObservabilityEvent, and every recorded workspace spec/env.
	manager.AssertNoSecretInRecord(t, orchestratortest.SeededCanary)

	// And the loggable record carries the ref's downstream effects (a SessionRef, a Detail) but
	// never the raw plaintext on the surface a consumer reads.
	final, err := manager.Get(ctx, agent.ID)
	if err != nil {
		t.Fatalf("Get final: %v", err)
	}
	if strings.Contains(final.Detail, orchestratortest.SeededCanary) {
		t.Fatalf("canary leaked into the terminal record Detail: %q", final.Detail)
	}
}

// TestCanary_CredentialNeverSurfacesThroughFailure proves the credential VALUE never surfaces
// through the FAILURE path. A spawn whose credential resolves to the canary is reconciled, but
// the workspace Provision is forced to fail with a quota fault → the agent is marked Failed with
// a REDACTED reason. The terminal record's Detail (and every record version + ObservabilityEvent)
// must be canary-free: a fault that interpolated the resolved secret into its message would leak
// it, and the orchestrator's redactCause prefixes only the stable error Kind, never a value.
func TestCanary_CredentialNeverSurfacesThroughFailure(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	manager := canaryManager(t)

	agent, err := manager.Spawn(ctx, canaryRequest())
	if err != nil {
		t.Fatalf("Spawn: %v", err)
	}
	// Force the next Provision to fail.
	manager.Workspaces().FailProvisionWith(&workspaceprovider.QuotaExceededError{Resource: "workspaces"})

	if _, rerr := manager.Reconcile(ctx); rerr != nil {
		t.Fatalf("Reconcile: %v", rerr)
	}
	failed, err := manager.Get(ctx, agent.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if failed.Status != orchestrator.StatusFailed {
		t.Fatalf("after forced provision failure status = %v, want Failed", failed.Status)
	}
	if failed.Detail == "" {
		t.Fatalf("Failed record carries no detail (want a redacted provision reason)")
	}
	if strings.Contains(failed.Detail, orchestratortest.SeededCanary) {
		t.Fatalf("canary leaked into the Failed record Detail: %q", failed.Detail)
	}

	// The full guard over every record version + every event + the recorded workspace spec.
	manager.AssertNoSecretInRecord(t, orchestratortest.SeededCanary)
}

// TestSecret_RefIsLoggableValueIsNot is the unit-level redaction guarantee: the loggable
// secrets.Reference renders WITHOUT the plaintext (it is safe to log/telemeter), so the
// orchestrator threading the ref through a record/event never carries the value. This guards
// the seam at the source — if a Reference ever rendered its plaintext, every downstream record
// the orchestrator stamps it onto would leak.
func TestSecret_RefIsLoggableValueIsNot(t *testing.T) {
	t.Parallel()
	ref := secrets.Ref(orchestratortest.SeededCredentialRef)
	if strings.Contains(ref.String(), orchestratortest.SeededCanary) {
		t.Fatalf("secrets.Reference.String() leaked the plaintext canary: %q", ref.String())
	}
	if ref.String() == "" {
		t.Fatalf("secrets.Reference renders empty — the loggable ref must carry the URI for diagnostics")
	}
}
