package agentsession_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// fixedClock is a deterministic agentsession.Clock for the library unit tests.
type fixedClock struct{}

func (fixedClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// memTranscript is a minimal in-memory transcript for the library unit tests (the
// public agentsessiontest.Transcript is the canonical one; this keeps these tests in the
// library's own black-box package without importing the harness).
type memTranscript struct {
	events map[string][]agentsession.Event
}

func newMemTranscript() *memTranscript {
	return &memTranscript{events: make(map[string][]agentsession.Event)}
}

//nolint:gocritic // contract §2: Transcript.Append takes the Event value (the immutable record; the fake mirrors the frozen seam).
func (m *memTranscript) Append(_ context.Context, event agentsession.Event) (uint64, error) {
	existing := m.events[event.SessionID]
	seq := uint64(len(existing)) + 1
	event.Seq = seq
	m.events[event.SessionID] = append(existing, event)
	return seq, nil
}

//nolint:ireturn // contract §2: Transcript.ReadFrom returns the Stream port (the frozen replay seam).
func (m *memTranscript) ReadFrom(_ context.Context, sessionID string, from agentsession.Cursor) (agentsession.Stream, error) {
	stored := m.events[sessionID]
	start := int(from)
	if start < 0 {
		start = 0
	}
	var snapshot []agentsession.Event
	if start < len(stored) {
		snapshot = make([]agentsession.Event, len(stored)-start)
		copy(snapshot, stored[start:])
	}
	return &memStream{events: snapshot}, nil
}

type memStream struct {
	events []agentsession.Event
	index  int
}

func (s *memStream) Next(context.Context) (agentsession.Event, bool) {
	if s.index >= len(s.events) {
		return agentsession.Event{}, false
	}
	event := s.events[s.index]
	s.index++
	return event, true
}

func (s *memStream) Err() error { return nil }

// nonReadyingAdapter spawns a conn that closes its event channel WITHOUT ever emitting a
// Ready transition — the silent-bad-token trap the library must convert to AuthError.
type nonReadyingAdapter struct{}

func (nonReadyingAdapter) Manifest() agentsession.CapabilityManifest {
	return agentsession.CapabilityManifest{}
}

//nolint:ireturn // contract §2: Adapter.Spawn returns the HarnessConn port (the frozen lower seam).
func (nonReadyingAdapter) Spawn(context.Context, agentsession.Spec, agentsession.Route, agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	conn := &nonReadyingConn{events: make(chan agentsession.Event)}
	close(conn.events) // the harness exits immediately, confirming nothing
	return conn, nil
}

type nonReadyingConn struct{ events chan agentsession.Event }

func (c *nonReadyingConn) Events() <-chan agentsession.Event                { return c.events }
func (c *nonReadyingConn) Send(context.Context, agentsession.Command) error { return nil }
func (c *nonReadyingConn) Close(context.Context) error                      { return nil }

// TestOpen_SilentBadToken_ConvertsToAuthError proves the GENUINE pump path: a harness
// whose event channel closes before any Ready handshake converts to AuthError at Open
// (the silent-bad-token trap), NOT trusted as success. The AuthError carries the
// Reference, never the value.
func TestOpen_SilentBadToken_ConvertsToAuthError(t *testing.T) {
	t.Parallel()
	const ref = "vault://eden/anthropic#setup-token"
	const canary = "S3CR3T-do-not-leak"
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "fake", Model: "m"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": nonReadyingAdapter{}},
			Secrets:    secretstest.New(map[string]string{ref: canary}),
			Transcript: newMemTranscript(),
			Clock:      fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	_, openErr := pool.Open(context.Background(), agentsession.Spec{
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Credential: secrets.Ref(ref),
	})
	authErr, ok := errors.AsType[agentsession.AuthError](openErr)
	if !ok {
		t.Fatalf("silent-bad-token must convert to AuthError, got %v (%T)", openErr, openErr)
	}
	if errors.KindOf(openErr) != errors.KindUnauthenticated {
		t.Errorf("AuthError must classify Unauthenticated, got %v", errors.KindOf(openErr))
	}
	if authErr.Reference.String() != ref {
		t.Errorf("AuthError must carry the Reference %q, got %q", ref, authErr.Reference.String())
	}
	if got := openErr.Error(); strings.Contains(got, canary) {
		t.Errorf("AuthError leaked the credential value: %q", got)
	}
}

// TestOpen_MissingCredentialRef_AuthError proves a zero credential reference is an
// AuthError before any spawn.
func TestOpen_MissingCredentialRef_AuthError(t *testing.T) {
	t.Parallel()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "fake", Model: "m"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": nonReadyingAdapter{}},
			Secrets:    secretstest.New(nil),
			Transcript: newMemTranscript(),
			Clock:      fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	_, openErr := pool.Open(context.Background(), agentsession.Spec{Routing: agentsession.RouteKey{Role: "assistant"}})
	if !isType[agentsession.AuthError](openErr) {
		t.Fatalf("a zero credential reference must be AuthError, got %v (%T)", openErr, openErr)
	}
}

// isType reports whether err's chain carries a *E (the single typed-error inspection
// idiom, keeping the blank-position discard in ONE place).
func isType[E error](err error) bool {
	_, ok := errors.AsType[E](err)
	return ok
}

// TestNew_RejectsMissingDependencies proves the pure constructor validates Deps.
func TestNew_RejectsMissingDependencies(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name         string
		dependencies agentsession.Deps
	}{
		{"no adapters", agentsession.Deps{Secrets: secretstest.New(nil), Transcript: newMemTranscript(), Clock: fixedClock{}}},
		{"nil secrets", agentsession.Deps{Adapters: map[string]agentsession.Adapter{"f": nonReadyingAdapter{}}, Transcript: newMemTranscript(), Clock: fixedClock{}}},
		{"nil transcript", agentsession.Deps{Adapters: map[string]agentsession.Adapter{"f": nonReadyingAdapter{}}, Secrets: secretstest.New(nil), Clock: fixedClock{}}},
		{"nil clock", agentsession.Deps{Adapters: map[string]agentsession.Adapter{"f": nonReadyingAdapter{}}, Secrets: secretstest.New(nil), Transcript: newMemTranscript()}},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			_, err := agentsession.New(agentsession.Config{}, testCase.dependencies)
			if !isType[agentsession.ConfigError](err) {
				t.Fatalf("New(%s) must be ConfigError, got %v (%T)", testCase.name, err, err)
			}
			if errors.KindOf(err) != errors.KindInvalid {
				t.Errorf("ConfigError must classify Invalid, got %v", errors.KindOf(err))
			}
		})
	}
}
