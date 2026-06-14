package agentruntime_test

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
)

// TestCanary_CredentialNeverLeaksOnBus is the redaction no-leak property (ADR-0020 dimension (f)).
// The harness seeds a credential canary (agentruntimetest.SeededCanary) behind the secrets provider;
// agentsession resolves it server-side to spawn the harness. It must appear in NO published
// EventEnvelope and NO Heartbeat — not in any field, not in the marshaled JSON wire bytes. One
// occurrence fails the lane. This runs the FULL canonical script so every event kind is checked.
func TestCanary_CredentialNeverLeaksOnBus(t *testing.T) {
	t.Parallel()
	runtime, bus, _ := agentruntimetest.NewRuntime(t, fastHeartbeat, agentruntimetest.CanonicalScript()...)
	if reason := runFor(noopCancelContext(), t, runtime)(); reason.String() == "" {
		t.Fatal("run did not terminate")
	}

	canary := agentruntimetest.SeededCanary
	for _, envelope := range bus.Events() {
		assertNoCanaryInValue(t, "event-envelope", envelope, canary)
	}
	for _, heartbeat := range bus.Heartbeats() {
		assertNoCanaryInValue(t, "heartbeat", heartbeat, canary)
	}
}

// assertNoCanaryInValue marshals the value to its full JSON wire form and asserts the canary needle
// appears nowhere — the by-construction wire-level redaction check (the secret is an opaque Reference;
// no value path exists into a bus message).
func assertNoCanaryInValue(t *testing.T, label string, value any, canary string) {
	t.Helper()
	encoded, err := json.Marshal(value)
	if err != nil {
		t.Fatalf("%s: marshal for canary scan: %v", label, err)
	}
	if strings.Contains(string(encoded), canary) {
		t.Fatalf("%s: SEEDED CANARY LEAKED onto the bus wire: %s", label, encoded)
	}
}
