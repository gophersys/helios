package clusterprobe

import (
	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// zeroSessionState is the "inner state not observed" sentinel (agentsession.StateInitializing,
// the zero State) — what sessionStateOf reports when no heartbeat was seen, mirroring live.go's
// rule of never fabricating a StateRunning the observation cannot vouch for.
const zeroSessionState = agentsession.StateInitializing

// deriveActual folds a workspace Descriptor (the HARD substrate lifecycle) + a health
// Heartbeat (the SOFT inner-loop signal) into one orchestrator.Actual — the right half of
// the reconcile diff. It is PURE (no I/O, no clock, no globals): the same (workspace, beat)
// inputs always yield the same Actual, which is exactly what makes any orchestrator replica
// compute the same Actual after a restart. The presence booleans say whether each half was
// observed; a half that was not observed reports its dead/zero value (never a fabricated
// "live").
//
//nolint:gocritic // hugeParam: workspace/beat are one observed reading folded once per agent; passing by value hands deriveActual an independent, pure snapshot.
func deriveActual(
	hasWorkspace bool, workspace workspaceprovider.Descriptor,
	hasBeat bool, beat agentruntime.Heartbeat,
) orchestrator.Actual {
	return orchestrator.Actual{
		WorkspaceLive: hasWorkspace && workspaceIsLive(workspace.State),
		SessionLive:   hasBeat && sessionIsLive(beat.Phase),
		SessionState:  sessionStateOf(hasBeat, beat),
		// Ledger is left at its zero value: the agent.<id>.health heartbeat carries LastSeq
		// (the transcript offset) but NOT the folded TokenLedger (agentruntime.Heartbeat —
		// Phase/SessionState/LastSeq only). This Probe will not FABRICATE a ledger the wire
		// does not carry — exactly as live.go leaves SessionState zero rather than hardcode a
		// StateRunning the side table cannot vouch for. A Probe that observes the usage stream
		// (a future enrichment tailing EventUsage, or a heartbeat protocol that adds a ledger
		// field) populates it, and reconcile's budget/ledger-tick arms then act on the truthful
		// value. Until then budget enforcement folds the ledger off the session's own
		// EventUsage stream, not off this Probe (orchestrator agentsession.md Q6).
	}
}

// workspaceIsLive reports whether a normalized workspace State counts as a LIVE workspace
// for the WorkspaceLive signal. Provisioning/Ready/Running/Degraded are live (the workspace
// exists and is — or is recovering toward — usable); Evicted/Gone are NOT live (the substrate
// reclaimed it / it is torn down — the drift signal the reconcile loop drives to Failed via
// the !WorkspaceLive arm in driveRunning). The closed State taxonomy is handled exhaustively
// (a future additive State defaults to NOT live — the conservative choice: an unrecognized
// state never masquerades as a live workspace).
func workspaceIsLive(state workspaceprovider.State) bool {
	switch state {
	case workspaceprovider.StateProvisioning,
		workspaceprovider.StateReady,
		workspaceprovider.StateRunning,
		workspaceprovider.StateDegraded:
		return true
	case workspaceprovider.StateEvicted, workspaceprovider.StateGone:
		return false
	default:
		return false
	}
}

// sessionIsLive reports whether a sidecar HealthPhase counts as a LIVE session for the
// SessionLive signal. Starting/Running/Draining are live (the sidecar is up — spawning,
// steady, or draining an in-flight turn); Stopped is NOT live (the sidecar drained, closed
// the session, and exited — its lifecycle terminal, agentruntime protocol.go PhaseStopped).
// The closed HealthPhase taxonomy is exhaustive; an unrecognized additive phase defaults to
// NOT live (the conservative choice — an unknown phase never masquerades as a live session).
func sessionIsLive(phase agentruntime.HealthPhase) bool {
	switch phase {
	case agentruntime.PhaseStarting,
		agentruntime.PhaseRunning,
		agentruntime.PhaseDraining:
		return true
	case agentruntime.PhaseStopped:
		return false
	default:
		return false
	}
}

// sessionStateOf returns the inner agent-loop state the reconcile loop branches on
// (driveRunning's unrecoverable-inner-state arm reads Actual.SessionState). It is the
// heartbeat's observed agentsession.State when a beat was seen; the zero value
// (agentsession.StateInitializing) when no beat was observed — the documented "not observed"
// sentinel, never a fabricated StateRunning. This is the field live.go could not populate (the
// in-process side table holds only the Session handle); the heartbeat IS that observation, so
// this cluster Probe populates it truthfully.
func sessionStateOf(hasBeat bool, beat agentruntime.Heartbeat) agentsession.State {
	if !hasBeat {
		return zeroSessionState
	}
	return beat.SessionState
}
