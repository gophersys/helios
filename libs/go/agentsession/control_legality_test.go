package agentsession_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// This file is the EXHAUSTIVE (state × command) legality matrix test — every one of the 8 states ×
// 3 turn-taking commands is asserted, against an independently-written truth table, at both the pure
// LegalControls/CanControl layer AND the guardControl enforcer. It is the coverage whose absence let
// "Steer is illegal in state awaiting-permission" ship: the old suite proved only the lone legal
// Steer-in-Running cell and a single Abort-after-terminal cell.

// matrixStates is every State, terminal and non-terminal (the matrix rows).
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

// matrixCommands is every turn-taking CommandKind (the matrix columns).
var matrixCommands = []agentsession.CommandKind{
	agentsession.CommandPrompt,
	agentsession.CommandSteer,
	agentsession.CommandAbort,
}

// legalMatrix is the EXPECTED (state × command) legality — the canonical truth table written out by
// hand, independent of the implementation, so a drift in LegalControls fails HERE. (CapSteer present;
// the capability axis is asserted separately.)
var legalMatrix = map[agentsession.State]map[agentsession.CommandKind]bool{
	agentsession.StateInitializing:       {agentsession.CommandPrompt: false, agentsession.CommandSteer: false, agentsession.CommandAbort: true},
	agentsession.StateReady:              {agentsession.CommandPrompt: true, agentsession.CommandSteer: false, agentsession.CommandAbort: true},
	agentsession.StateRunning:            {agentsession.CommandPrompt: false, agentsession.CommandSteer: true, agentsession.CommandAbort: true},
	agentsession.StateAwaitingInput:      {agentsession.CommandPrompt: true, agentsession.CommandSteer: false, agentsession.CommandAbort: true},
	agentsession.StateAwaitingPermission: {agentsession.CommandPrompt: false, agentsession.CommandSteer: false, agentsession.CommandAbort: true},
	agentsession.StateCompleted:          {agentsession.CommandPrompt: false, agentsession.CommandSteer: false, agentsession.CommandAbort: false},
	agentsession.StateFailed:             {agentsession.CommandPrompt: false, agentsession.CommandSteer: false, agentsession.CommandAbort: false},
	agentsession.StateAborted:            {agentsession.CommandPrompt: false, agentsession.CommandSteer: false, agentsession.CommandAbort: false},
}

// TestControlMatrix_CanControlMatchesTruthTable walks EVERY (state × command) cell and asserts
// CanControl agrees with the hand-written truth table — the exhaustive matrix the suite lacked.
func TestControlMatrix_CanControlMatchesTruthTable(t *testing.T) {
	t.Parallel()
	for _, state := range matrixStates {
		for _, command := range matrixCommands {
			want := legalMatrix[state][command]
			if got := agentsession.CanControl(state, command); got != want {
				t.Errorf("CanControl(%v, %v) = %v, want %v", state, command, got, want)
			}
		}
	}
}

// TestControlMatrix_GuardEnforcesMatrix proves guardControl (CapSteer present) admits a command IFF
// CanControl says it is legal, for every cell — and that an illegal cell returns a typed StateError
// carrying KindConflict and naming the offending state (the cell the live bug lived in, now pinned).
func TestControlMatrix_GuardEnforcesMatrix(t *testing.T) {
	t.Parallel()
	for _, state := range matrixStates {
		for _, command := range matrixCommands {
			err := agentsession.GuardControlForTest(state, agentsession.CapFull, agentsession.Command{Kind: command})
			if agentsession.CanControl(state, command) {
				if err != nil {
					t.Errorf("guardControl(%v, %v) = %v, want nil (legal cell)", state, command, err)
				}
				continue
			}
			assertIllegalControl(t, state, command, err)
		}
	}
}

// assertIllegalControl asserts a guardControl rejection of an illegal cell is a typed StateError
// (KindConflict) naming the offending state.
func assertIllegalControl(t *testing.T, state agentsession.State, command agentsession.CommandKind, err error) {
	t.Helper()
	if err == nil {
		t.Errorf("guardControl(%v, %v) = nil, want a StateError (illegal cell)", state, command)
		return
	}
	if errors.KindOf(err) != errors.KindConflict {
		t.Errorf("guardControl(%v, %v) kind = %v, want KindConflict", state, command, errors.KindOf(err))
	}
	if !errors.IsType[agentsession.StateError](err) {
		t.Errorf("guardControl(%v, %v) is not a StateError: %T", state, command, err)
	}
	if !strings.Contains(err.Error(), "is illegal in state "+state.String()) {
		t.Errorf("guardControl(%v, %v) message = %q, want it to name the illegal state", state, command, err.Error())
	}
}

// TestControlMatrix_SteerCapAbsentIsInvalidEverywhere proves the SECOND legality axis (capability):
// with CapSteer ABSENT, a Steer is an UnsupportedError (KindInvalid) in EVERY state — the capability
// check precedes the state check, so even the lone legal Steer cell (Running) reports it first.
func TestControlMatrix_SteerCapAbsentIsInvalidEverywhere(t *testing.T) {
	t.Parallel()
	for _, state := range matrixStates {
		err := agentsession.GuardControlForTest(state, agentsession.CapAbsent, agentsession.Command{Kind: agentsession.CommandSteer})
		if errors.KindOf(err) != errors.KindInvalid {
			t.Errorf("Steer with CapAbsent in %v: kind = %v, want KindInvalid", state, errors.KindOf(err))
		}
		if !errors.IsType[agentsession.UnsupportedError](err) {
			t.Errorf("Steer with CapAbsent in %v: not an UnsupportedError: %T (%v)", state, err, err)
		}
	}
}

// TestControlMatrix_LegalControlsSetsAreExact asserts LegalControls returns EXACTLY the expected set
// per state (no missing, no extra element) — the projection the gateway sends to the UI is this set.
func TestControlMatrix_LegalControlsSetsAreExact(t *testing.T) {
	t.Parallel()
	for _, state := range matrixStates {
		got := map[agentsession.CommandKind]bool{}
		for _, command := range agentsession.LegalControls(state) {
			if got[command] {
				t.Errorf("LegalControls(%v) returned %v twice", state, command)
			}
			got[command] = true
		}
		for _, command := range matrixCommands {
			if got[command] != legalMatrix[state][command] {
				t.Errorf("LegalControls(%v) membership of %v = %v, want %v", state, command, got[command], legalMatrix[state][command])
			}
		}
	}
}

// TestControlMatrix_CommandTokens pins the stable wire/UI tokens the projection depends on.
func TestControlMatrix_CommandTokens(t *testing.T) {
	t.Parallel()
	for command, want := range map[agentsession.CommandKind]string{
		agentsession.CommandPrompt: "prompt",
		agentsession.CommandSteer:  "steer",
		agentsession.CommandAbort:  "abort",
	} {
		if got := command.String(); got != want {
			t.Errorf("CommandKind(%d).String() = %q, want %q", command, got, want)
		}
	}
}
