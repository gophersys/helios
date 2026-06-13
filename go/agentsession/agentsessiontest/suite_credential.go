package agentsessiontest

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// assertCredentialSeam proves the credential never leaks: the seeded canary appears in
// NO emitted Event (Extension, summaries, deltas, terminal text), no recorded Command,
// and no error; the Spawn was asked to inject the loggable Reference, never the value.
func assertCredentialSeam(t *testing.T, newAdapter func() *Adapter) {
	t.Helper()
	adapter := newAdapter()
	h := newHarness(t, adapter)
	events := promptAndDrain(t, h)

	// The canary appears nowhere on the stream.
	for i := range events {
		AssertNoSecretInEvent(t, events[i], SeededCanary)
	}
	// Nor in any recorded Command.
	for _, command := range adapter.Received() {
		if strings.Contains(command.Text, SeededCanary) {
			t.Errorf("a recorded Command leaked the credential value")
		}
	}
	// The adapter was asked to inject the loggable Reference (refs only).
	refs := adapter.InjectedRefs()
	if len(refs) == 0 {
		t.Fatal("Spawn was never asked to inject a credential reference")
	}
	for _, ref := range refs {
		if ref.String() != credentialRef {
			t.Errorf("injected reference = %q, want %q", ref.String(), credentialRef)
		}
		if strings.Contains(ref.String(), SeededCanary) {
			t.Errorf("the injected Reference carried the value (it must be loggable, value-less)")
		}
	}
	// The seeded provider DID resolve the credential server-side (the seam is exercised,
	// not bypassed) — quiesced because the session has fully drained.
	if len(h.provider.Resolved) == 0 {
		t.Errorf("the credential was never resolved server-side at Open")
	}
}

// assertSilentBadToken proves the silent-bad-token defense: a harness that closes its
// event channel without ever confirming readiness converts to AuthError at Open (NOT
// trusted as success). The AuthError carries the Reference, never the value.
func assertSilentBadToken(t *testing.T, _ func() *Adapter) {
	t.Helper()
	// A harness that SPAWNS successfully but whose event stream closes before any Ready
	// handshake (a silently-bad token: the process starts, auth fails, and it exits
	// confirming nothing). SpawnNonReadying drives the library pump's GENUINE
	// no-ready->AuthError SYNTHESIS end to end — NOT a Spawn-error shortcut — so this case
	// is non-vacuous (a pump that trusted the silent close as success would FAIL here).
	adapter := New().SpawnNonReadying()
	h := newHarness(t, adapter)
	_, err := h.pool.Open(context.Background(), h.spec())
	if !asType[agentsession.AuthError](err) {
		t.Fatalf("a harness that never confirms readiness must convert to AuthError, got %v (%T)", err, err)
	}
	assertKind(t, err, errors.KindUnauthenticated, "AuthError")
	authErr, ok := errors.AsType[agentsession.AuthError](err)
	if !ok {
		t.Fatal("AuthError not inspectable")
	}
	if authErr.Reference.String() != credentialRef {
		t.Errorf("AuthError must carry the Reference %q, got %q", credentialRef, authErr.Reference.String())
	}
	if strings.Contains(err.Error(), SeededCanary) {
		t.Errorf("AuthError leaked the credential value")
	}
}

// assertBudgetAbort proves the single budget authority: when a cumulative EventUsage
// cost crosses Budget.MaxCostMicros, the library issues an Abort and the terminal carries
// TurnBudgetExceeded (the harness-native cap is not relied upon).
func assertBudgetAbort(t *testing.T, _ func() *Adapter) {
	t.Helper()
	// The script ticks usage OVER the budget mid-turn, then would continue — but the
	// library must Abort. The fake's Abort reaction yields an Aborted terminal; the
	// library re-stamps the budget outcome.
	overBudget := agentsession.UsageMeter{
		Model: "fake-fable-5", Harness: "fake",
		InputTokens: 1000, OutputTokens: 1000, CacheReadTokens: 0, CacheCreationTokens: 0,
		CostMicros: 9_000_000, Cumulative: true,
	}
	adapter := New(
		MessageStart("assistant"),
		TextDelta("spending"),
		Usage(overBudget),
		// No terminal scripted: the library's Abort drives the fake to an Aborted terminal.
	)
	h := newHarness(t, adapter)
	session := h.open(t, func(spec *agentsession.Spec) {
		spec.Budget = agentsession.Budget{MaxCostMicros: 5_000_000}
	})
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	events, err := drain(context.Background(), session.Events(context.Background(), agentsession.FromSeq(0)))
	if err != nil {
		t.Fatalf("drain: %v", err)
	}
	last := events[len(events)-1]
	if !last.IsTerminal() {
		t.Fatalf("budget-exceeded session did not reach a terminal")
	}
	if last.Terminal == nil || last.Terminal.Outcome != agentsession.TurnBudgetExceeded {
		t.Errorf("terminal Outcome = %v, want TurnBudgetExceeded", terminalOutcome(last))
	}
	// The library issued an Abort (the single authority acted).
	if !abortRecorded(adapter) {
		t.Errorf("the library must issue an Abort when the budget is crossed")
	}
}

// assertTypedErrors proves the typed error set is errors.AsType-inspectable with stable
// Kinds (a RouteError for an unknown route; a ConfigError from New on a missing dep).
func assertTypedErrors(t *testing.T, _ func() *Adapter) {
	t.Helper()
	// Unknown route -> RouteError(invalid).
	h := newHarness(t, New(canonicalScript()...))
	_, err := h.pool.Open(context.Background(), agentsession.Spec{
		Routing:    agentsession.RouteKey{Role: "nonexistent"},
		Credential: secretsRef(),
	})
	if !asType[agentsession.RouteError](err) {
		t.Errorf("Open with an unknown route must be RouteError, got %v (%T)", err, err)
	}
	assertKind(t, err, errors.KindInvalid, "RouteError")

	// New with no adapters -> ConfigError(invalid).
	_, newErr := agentsession.New(agentsession.Config{}, agentsession.Deps{})
	if !asType[agentsession.ConfigError](newErr) {
		t.Errorf("New with no adapters must be ConfigError, got %v (%T)", newErr, newErr)
	}
	assertKind(t, newErr, errors.KindInvalid, "ConfigError")
}

// assertCloseIdempotent proves Close is idempotent and does not tear down the pod (the
// fake has no pod; the contract is that Close only reaps the session handle).
func assertCloseIdempotent(t *testing.T, _ func() *Adapter) {
	t.Helper()
	h := newHarness(t, New(canonicalScript()...))
	session := h.open(t, nil)
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	if _, err := drain(context.Background(), session.Events(context.Background(), agentsession.FromSeq(0))); err != nil {
		t.Fatalf("drain: %v", err)
	}
	for i := range 3 {
		if err := session.Close(context.Background()); err != nil {
			t.Errorf("Close #%d must be idempotent, got %v", i+1, err)
		}
	}
}

// terminalOutcome safely projects a terminal event's outcome for diagnostics.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); this fake/test helper takes it by value.
func terminalOutcome(event agentsession.Event) any {
	if event.Terminal == nil {
		return "<nil terminal>"
	}
	return event.Terminal.Outcome
}

// abortRecorded reports whether the adapter received an Abort command.
func abortRecorded(adapter *Adapter) bool {
	for _, command := range adapter.Received() {
		if command.Kind == agentsession.CommandAbort {
			return true
		}
	}
	return false
}
