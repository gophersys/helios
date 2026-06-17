//nolint:testpackage // white-box: exercises the unexported wire projection (toEventView/toAgentView/allowedControlTokens) directly.
package gateway

import (
	"slices"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/orchestrator"
)

// matrixStates is every agentsession State (terminal and non-terminal) — the projection must cover
// all 8.
var matrixStates = []agentsession.State{
	agentsession.StateInitializing,
	agentsession.StateReady,
	agentsession.StateRunning,
	agentsession.StateAwaitingInput,
	agentsession.StateAwaitingPermission,
	agentsession.StateCompleted,
	agentsession.StateFailed,
	agentsession.StateAborted,
}

// TestProjection_StateViewAllowedCitesLegalControls proves the SSE stateView projects EXACTLY the
// agentsession home's allowed-set for every state (no gateway-side re-derivation), and that
// canResolve is true iff awaiting-permission. This is what lets the UI derive its controls without
// re-encoding the matrix — and pins the bug cell: awaiting-permission must NOT advertise steer.
func TestProjection_StateViewAllowedCitesLegalControls(t *testing.T) {
	t.Parallel()
	for _, state := range matrixStates {
		view := toEventView(agentsession.Event{
			Kind:  agentsession.EventSessionState,
			State: &agentsession.StatePayload{From: agentsession.StateInitializing, To: state},
		})
		if view.State == nil {
			t.Fatalf("state %v: no stateView projected", state)
		}

		// The projected set must equal the agentsession home's tokens (referenced directly, so a
		// gateway-side hardcode would fail here).
		want := make([]string, 0)
		for _, kind := range agentsession.LegalControls(state) {
			want = append(want, kind.String())
		}
		if !slices.Equal(view.State.Allowed, want) {
			t.Errorf("state %v: allowed = %v, want %v (agentsession.LegalControls)", state, view.State.Allowed, want)
		}

		wantResolve := state == agentsession.StateAwaitingPermission
		if view.State.CanResolve != wantResolve {
			t.Errorf("state %v: canResolve = %v, want %v", state, view.State.CanResolve, wantResolve)
		}
	}

	// Spot-check the live bug cell explicitly: awaiting-permission allows only abort, never steer.
	awaiting := toEventView(agentsession.Event{
		Kind:  agentsession.EventSessionState,
		State: &agentsession.StatePayload{From: agentsession.StateRunning, To: agentsession.StateAwaitingPermission},
	})
	if slices.Contains(awaiting.State.Allowed, "steer") {
		t.Errorf("awaiting-permission must NOT allow steer (the shipped-bug cell), got %v", awaiting.State.Allowed)
	}
	if !slices.Contains(awaiting.State.Allowed, "abort") {
		t.Errorf("awaiting-permission must allow abort, got %v", awaiting.State.Allowed)
	}
}

// TestProjection_AgentViewCanResume proves the REST seed's CanResume is the record-plane resumable
// predicate (Suspended/Stopped only) — so a live session never seeds an offerable Resume.
func TestProjection_AgentViewCanResume(t *testing.T) {
	t.Parallel()
	for _, testCase := range []struct {
		status orchestrator.Status
		want   bool
	}{
		{orchestrator.StatusSuspended, true},
		{orchestrator.StatusStopped, true},
		{orchestrator.StatusRunning, false},
		{orchestrator.StatusFailed, false},
	} {
		view := toAgentView(orchestrator.Agent{Status: testCase.status})
		if view.CanResume != testCase.want {
			t.Errorf("status %v: canResume = %v, want %v", testCase.status, view.CanResume, testCase.want)
		}
	}
}
