package agentsessiontest

import (
	"strings"

	"github.com/gophersys/libs/go/agentsession"
)

// TestingT is the minimal testing surface the public assertion helpers depend on, so a
// consumer can call them from any *testing.T without importing a heavier seam.
type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
}

// AssertNoSecretInEvent fails if canary appears in ANY redaction-eligible field of an
// Event (the message/thinking deltas, the tool arg/result digests, the terminal text,
// the Extension bytes) — the redaction-by-construction guarantee, runnable per Event.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); this fake/test helper takes it by value.
func AssertNoSecretInEvent(t TestingT, event agentsession.Event, canary string) {
	t.Helper()
	if canary == "" {
		return
	}
	for _, field := range eventStrings(event) {
		if strings.Contains(field, canary) {
			t.Errorf("credential canary leaked into a %s event field", event.Kind)
			return
		}
	}
}

// AssertNoSecretInStream fails if canary appears in ANY emitted Event of a drained
// stream — the whole-session redaction guarantee, runnable.
func AssertNoSecretInStream(t TestingT, events []agentsession.Event, canary string) {
	t.Helper()
	for i := range events {
		AssertNoSecretInEvent(t, events[i], canary)
	}
}

// eventStrings projects every human-readable / byte field of an Event so a leak check is
// total. It deliberately reaches into every payload variant.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); this fake/test helper takes it by value.
func eventStrings(event agentsession.Event) []string {
	out := []string{event.SessionID, event.TurnID, string(event.Extension)}
	if event.Message != nil {
		out = append(out, event.Message.Role, event.Message.Delta)
	}
	if event.Tool != nil {
		out = append(out, event.Tool.Name, event.Tool.ArgsSummary, event.Tool.PartialDigest,
			event.Tool.ResultDigest, event.Tool.GrantID, event.Tool.CallID)
	}
	if event.Permission != nil {
		out = append(out, event.Permission.RequestID, event.Permission.Tool,
			event.Permission.Reason, event.Permission.By)
	}
	if event.Usage != nil {
		out = append(out, event.Usage.Model, event.Usage.Harness)
	}
	if event.Terminal != nil {
		out = append(out, event.Terminal.ResultText, event.Terminal.StopReason,
			event.Terminal.Detail, event.Terminal.By)
	}
	return out
}
