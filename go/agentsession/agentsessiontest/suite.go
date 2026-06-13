package agentsessiontest

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// Run drives any agentsession.Adapter through the substitutability properties
// (contract §4). The unit arm runs the scripted fake; a real adapter runs the SAME Run
// against a recorded/replayed harness stream. newAdapter builds a FRESH Adapter per
// case so cases never share mutable script/received state.
//
// The properties asserted: lifecycle legality, Seq monotonicity (== transcript offset),
// replay==tail (gap-free/dup-free, including after terminate), multi-client fan-out
// parity, forward compatibility (Extension never dropped/fatal), all four token kinds +
// attribution, grant linkage, the two-decider permission round-trip, capability honesty,
// the credential seam, budget abort (one authority), and secret-safety by construction.
//
//nolint:thelper // Run IS the suite entrypoint; subtests carry t directly.
func Run(t *testing.T, newAdapter func() *Adapter) {
	t.Run("LifecycleLegality", func(t *testing.T) { assertLifecycleLegality(t, newAdapter) })
	t.Run("SeqMonotonicEqualsTranscriptOffset", func(t *testing.T) { assertSeqMonotonic(t, newAdapter) })
	t.Run("ReplayEqualsTailGapFree", func(t *testing.T) { assertReplayEqualsTail(t, newAdapter) })
	t.Run("MultiClientFanoutParity", func(t *testing.T) { assertFanoutParity(t, newAdapter) })
	t.Run("ForwardCompatExtensionNeverDropped", func(t *testing.T) { assertForwardCompat(t, newAdapter) })
	t.Run("FourTokenKindsAndAttribution", func(t *testing.T) { assertFourTokenKinds(t, newAdapter) })
	t.Run("GrantLinkage", func(t *testing.T) { assertGrantLinkage(t, newAdapter) })
	t.Run("PermissionRoundTripPolicy", func(t *testing.T) { assertPermissionPolicy(t, newAdapter) })
	t.Run("PermissionRoundTripHumanIdempotent", func(t *testing.T) { assertPermissionHuman(t, newAdapter) })
	t.Run("SteerObservableMidStream", func(t *testing.T) { assertSteerObservable(t, newAdapter) })
	t.Run("CapabilityHonesty", func(t *testing.T) { assertCapabilityHonesty(t, newAdapter) })
	t.Run("CredentialSeamHolds", func(t *testing.T) { assertCredentialSeam(t, newAdapter) })
	t.Run("SilentBadTokenConvertsToAuthError", func(t *testing.T) { assertSilentBadToken(t, newAdapter) })
	t.Run("BudgetAbortOneAuthority", func(t *testing.T) { assertBudgetAbort(t, newAdapter) })
	t.Run("TypedErrors", func(t *testing.T) { assertTypedErrors(t, newAdapter) })
	t.Run("CloseIdempotent", func(t *testing.T) { assertCloseIdempotent(t, newAdapter) })
}

// asType reports whether err's chain carries a *E (the Go 1.26 single-arg AsType form),
// keeping every suite call site on one typed-error idiom.
func asType[E error](err error) bool {
	_, ok := errors.AsType[E](err)
	return ok
}

// assertKind asserts err classifies to the expected errors.Kind.
func assertKind(t *testing.T, err error, want errors.Kind, description string) {
	t.Helper()
	if err == nil {
		t.Errorf("%s: expected an error of kind %v, got nil", description, want)
		return
	}
	if got := errors.KindOf(err); got != want {
		t.Errorf("%s: KindOf = %v, want %v (err: %v)", description, got, want, err)
	}
}

// promptAndDrain opens, prompts, and drains a fresh full-path session, returning the
// ordered events. It is the shared spine of the ordering/replay/usage properties.
func promptAndDrain(t *testing.T, h *harness) []agentsession.Event {
	t.Helper()
	session := h.open(t, nil)
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	events, err := drain(context.Background(), session.Events(context.Background(), agentsession.FromSeq(0)))
	if err != nil {
		t.Fatalf("drain: %v", err)
	}
	return events
}

// secretsRef is the suite's seeded credential reference.
func secretsRef() secrets.Reference { return secrets.Ref(credentialRef) }

// usageMeter is the canonical four-token attribution tick the suite reuses.
func usageMeter() agentsession.UsageMeter {
	return agentsession.UsageMeter{
		Model: "fake-fable-5", Harness: "fake",
		InputTokens: 100, OutputTokens: 40, CacheReadTokens: 60, CacheCreationTokens: 20,
		CostMicros: 1500, Cumulative: true,
	}
}

// fullLedger is the canonical authoritative terminal ledger.
func fullLedger() agentsession.TokenLedger {
	return agentsession.TokenLedger{
		UsageMeter:     usageMeter(),
		Turns:          1,
		ToolUses:       1,
		WallTime:       12 * time.Millisecond,
		ToolUsesByName: map[string]int32{"Write": 1},
	}
}
