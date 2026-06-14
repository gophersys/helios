package agentsessiontest

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// SeededCanary is the credential plaintext the suite seeds so the no-leak assertions
// have a concrete needle. Open resolves it server-side, yet it must appear in NO emitted
// Event, no Command, no error string, and no transcript record.
const SeededCanary = "S3CR3T-setup-token-do-not-leak"

// credentialRef is the secrets.Reference the seeded canary resolves under (loggable;
// the value never rides it).
const credentialRef = "vault://eden/anthropic#setup-token" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value

// assistantRoute is the RouteKey/Route pair the harness binds (an interactive
// AssistantSession over the fake harness).
var (
	assistantKey   = agentsession.RouteKey{Role: "assistant"}
	assistantRoute = agentsession.Route{Harness: "fake", Model: "fake-fable-5"}
)

// fixedClock is a deterministic agentsession.Clock so the harness is reproducible.
type fixedClock struct{}

// Now returns a fixed instant.
func (fixedClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// harness bundles a constructed Pool over one fake Adapter + a real in-memory
// Transcript + a seeded secretstest Provider, plus the canonical Spec. Each case builds
// a fresh harness so cases never share mutable state.
type harness struct {
	pool       *agentsession.Pool
	adapter    *Adapter
	transcript *Transcript
	provider   *secretstest.Provider
}

// newHarness constructs a fresh Pool over the given fake adapter, a seeded provider, and
// a fresh in-memory transcript. The adapter declares CapFull by default.
func newHarness(t *testing.T, adapter *Adapter) *harness {
	t.Helper()
	provider := secretstest.New(map[string]string{credentialRef: SeededCanary})
	transcript := NewTranscript()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{assistantKey: assistantRoute}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    provider,
			Transcript: transcript,
			Clock:      fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("construct Pool: %v", err)
	}
	return &harness{pool: pool, adapter: adapter, transcript: transcript, provider: provider}
}

// OpenForIntegration constructs a Pool over the adapter and opens a session, reaped on
// Cleanup — the public seam the integration arm (a separate _test package) drives without
// reaching the unexported harness. The optional `with` mutates the canonical Spec.
//
//nolint:ireturn // contract §2: returns the Session port (the frozen surface the consumer holds).
func OpenForIntegration(t *testing.T, adapter *Adapter, with func(*agentsession.Spec)) agentsession.Session {
	t.Helper()
	h := newHarness(t, adapter)
	return h.open(t, with)
}

// spec returns the canonical interactive Spec (OnPermission nil == the chat human path
// unless a case overrides it). Grants authorize the Write tool used in scripts.
func (h *harness) spec() agentsession.Spec {
	return agentsession.Spec{
		Workspace:  "/workspace/eden",
		Routing:    assistantKey,
		Grants:     []agentsession.ToolGrant{{ID: "grant-write", Tool: "Write"}},
		Credential: secrets.Ref(credentialRef),
	}
}

// open opens a session over the harness spec (optionally mutated by `with`).
//
//nolint:ireturn // returns the agentsession.Session port the consumer holds (the contract surface).
func (h *harness) open(t *testing.T, with func(*agentsession.Spec)) agentsession.Session {
	t.Helper()
	spec := h.spec()
	if with != nil {
		with(&spec)
	}
	session, err := h.pool.Open(context.Background(), spec)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.
	return session
}

// drain reads a stream to its terminal (or ctx cancellation), returning the events in
// order. It is the test-side "drain to terminal" the engine fold performs. A stream fault
// is wrapped on the Eden errors seam so the suite branches by kind.
func drain(ctx context.Context, stream agentsession.Stream) ([]agentsession.Event, error) {
	var events []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return events, wrapStreamErr(stream)
		}
		events = append(events, event)
		if event.IsTerminal() {
			return events, wrapStreamErr(stream)
		}
	}
}

// wrapStreamErr wraps a stream's terminal fault on the Eden errors seam (nil stays nil).
func wrapStreamErr(stream agentsession.Stream) error {
	if err := stream.Err(); err != nil {
		return errors.Wrap(errors.KindUnavailable, "agentsessiontest: drain stream", err)
	}
	return nil
}

// CanonicalScript is the full-path script a conformance case drives: a message with a
// thinking block and text deltas, a granted tool start/end, a usage tick, and a clean
// terminal Result carrying the authoritative four-token ledger. It is exported so the
// black-box conformance entrypoint can build a pre-scripted Adapter.
func CanonicalScript() []agentsession.Event { return canonicalScript() }

// canonicalScript is the internal full-path script the harness and suite reuse.
func canonicalScript() []agentsession.Event {
	return []agentsession.Event{
		MessageStart("assistant"),
		ThinkingDelta("considering the request"),
		TextDelta("Hello"),
		TextDelta(", world"),
		ToolStart("call-1", "Write", "path=note.txt"),
		ToolEnd("call-1", agentsession.ToolOutcomeOK, "wrote 12 bytes", 5*time.Millisecond),
		Usage(agentsession.UsageMeter{
			Model: "fake-fable-5", Harness: "fake",
			InputTokens: 100, OutputTokens: 40, CacheReadTokens: 60, CacheCreationTokens: 20,
			CostMicros: 1500, Cumulative: true,
		}),
		MessageEnd(),
		Result(agentsession.TokenLedger{
			UsageMeter: agentsession.UsageMeter{
				Model: "fake-fable-5", Harness: "fake",
				InputTokens: 100, OutputTokens: 40, CacheReadTokens: 60, CacheCreationTokens: 20,
				CostMicros: 1500, Cumulative: true,
			},
			Turns: 1, ToolUses: 1, WallTime: 12 * time.Millisecond,
			ToolUsesByName: map[string]int32{"Write": 1},
		}, "Hello, world", "end_turn"),
	}
}
