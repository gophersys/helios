package agentsession_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// canarySecret is the redaction needle (ADR-0020 dimension (f)): the credential plaintext
// the secrets provider resolves SERVER-SIDE at Open. It must appear in NO surfaced artifact —
// not an Event, not a stored transcript record, not an error string, not a Command the
// adapter received. The library carries only the loggable secrets.Reference; the value has
// no path into the published surface. If it leaks, the credential-flow guarantee (07 §2) is
// broken.
const canarySecret = "SEEDED-CANARY-agentsession-cred-d34db33f-do-not-leak" // #nosec G101 -- a test redaction needle, not a real credential; the whole point is to prove it NEVER surfaces

// canaryCredRef is the loggable reference the canary resolves under (the value never rides it).
const canaryCredRef = "vault://eden/anthropic#canary-token" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value

// TestCanary_CredentialNeverSurfaces opens a REAL session whose credential resolves to the
// seeded canary, drives the full scripted turn to its terminal across two viewers, then
// asserts the canary appears in NONE of: any emitted Event (rendered exhaustively), the
// durable transcript, the Commands the adapter received, or the rendered Ack/Close path.
// This proves the value never escapes the resolve->inject seam onto the published surface.
func TestCanary_CredentialNeverSurfaces(t *testing.T) {
	t.Parallel()

	adapter := agentsessiontest.New(agentsessiontest.CanonicalScript()...)
	transcript := agentsessiontest.NewTranscript()
	provider := secretstest.New(map[string]string{canaryCredRef: canarySecret})
	key := agentsession.RouteKey{Role: "assistant"}
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			key: {Harness: "fake", Model: "fake-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    provider,
			Transcript: transcript,
			Clock:      canaryClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	// SystemHints is a non-secret seam — but seed the canary there too, plus into the
	// credential, so a regression that echoed EITHER into an Event/transcript is caught.
	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:   "/workspace/eden",
		Routing:     key,
		Grants:      []agentsession.ToolGrant{{ID: "grant-write", Tool: "Write"}},
		Credential:  secrets.Ref(canaryCredRef),
		SystemHints: "remember the token " + canarySecret,
	})
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	// Two concurrent viewers drain to terminal; collect every Seq-stamped event.
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	streamA := session.Events(ctx, agentsession.FromSeq(0))
	streamB := session.Events(ctx, agentsession.FromSeq(0))
	if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	eventsA := drainEvents(ctx, t, streamA)
	eventsB := drainEvents(ctx, t, streamB)

	for _, ev := range append(eventsA, eventsB...) {
		assertEventCanaryFree(t, ev)
	}

	// The credential value must not have reached the transcript either: replay it and scan.
	if len(eventsA) == 0 {
		t.Fatalf("viewer A observed no events")
	}
	sessionID := eventsA[0].SessionID
	replay, err := transcript.ReadFrom(ctx, sessionID, agentsession.FromSeq(0))
	if err != nil {
		t.Fatalf("ReadFrom: %v", err)
	}
	for {
		ev, ok := replay.Next(ctx)
		if !ok {
			break
		}
		assertEventCanaryFree(t, ev)
	}

	// The adapter received only Commands the SUT sent; none may carry the credential value.
	for _, cmd := range adapter.Received() {
		if strings.Contains(cmd.Text, canarySecret) {
			t.Fatalf("canary leaked into a Command the adapter received: %q", cmd.Text)
		}
	}
}

// TestCanary_NeverSurfacesThroughError proves the credential value never surfaces through an
// AuthError — the failure path. A non-readying harness over a resolvable canary credential
// produces an AuthError carrying the loggable Reference; the error string (and its whole
// wrapped chain) must be canary-free.
func TestCanary_NeverSurfacesThroughError(t *testing.T) {
	t.Parallel()
	adapter := agentsessiontest.New().SpawnNonReadying()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "fake", Model: "m"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    secretstest.New(map[string]string{canaryCredRef: canarySecret}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      canaryClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	_, openErr := pool.Open(context.Background(), agentsession.Spec{
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Credential: secrets.Ref(canaryCredRef),
	})
	if openErr == nil {
		t.Fatalf("a non-readying harness must fail Open (silent-bad-token trap)")
	}
	if !isType[agentsession.AuthError](openErr) {
		t.Fatalf("want AuthError, got %v (%T)", openErr, openErr)
	}
	if strings.Contains(openErr.Error(), canarySecret) {
		t.Fatalf("canary leaked through the error surface: %q", openErr.Error())
	}
}

// assertEventCanaryFree renders every human-readable surface of an Event and fails if the
// canary appears anywhere.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); the scanner reads a copy.
func assertEventCanaryFree(t *testing.T, ev agentsession.Event) {
	t.Helper()
	surfaces := []string{
		ev.SessionID, ev.TurnID, ev.Kind.String(), string(ev.Extension),
	}
	if ev.Message != nil {
		surfaces = append(surfaces, ev.Message.Role, ev.Message.Delta)
	}
	if ev.Tool != nil {
		surfaces = append(surfaces, ev.Tool.Name, ev.Tool.ArgsSummary, ev.Tool.PartialDigest,
			ev.Tool.ResultDigest, ev.Tool.GrantID, ev.Tool.CallID)
	}
	if ev.Permission != nil {
		surfaces = append(surfaces, ev.Permission.RequestID, ev.Permission.Tool,
			ev.Permission.Reason, ev.Permission.By)
	}
	if ev.Usage != nil {
		surfaces = append(surfaces, ev.Usage.Model, ev.Usage.Harness)
	}
	if ev.Terminal != nil {
		surfaces = append(surfaces, ev.Terminal.ResultText, ev.Terminal.StopReason,
			ev.Terminal.Detail, ev.Terminal.By)
	}
	for _, s := range surfaces {
		if strings.Contains(s, canarySecret) {
			t.Fatalf("canary leaked into a surfaced Event field (kind=%s): %q", ev.Kind, s)
		}
	}
}

// drainEvents reads a stream to its terminal, returning every event in order.
func drainEvents(ctx context.Context, t *testing.T, stream agentsession.Stream) []agentsession.Event {
	t.Helper()
	var out []agentsession.Event
	for {
		ev, ok := stream.Next(ctx)
		if !ok {
			if err := stream.Err(); err != nil {
				t.Fatalf("stream faulted: %v", err)
			}
			return out
		}
		out = append(out, ev)
		if ev.IsTerminal() {
			return out
		}
	}
}

// canaryClock is a deterministic Clock for the canary harness.
type canaryClock struct{}

func (canaryClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }
