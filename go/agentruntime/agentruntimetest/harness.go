package agentruntimetest

import (
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// fixedSessionTime is the deterministic instant the agentsession harness clock returns.
var fixedSessionTime = time.Date(2026, time.June, 14, 12, 0, 0, 0, time.UTC)

// AgentID is the canonical agent id the harness builds a sidecar for.
const AgentID agentruntime.AgentID = "agent-test-1"

// SeededCanary is the credential plaintext seeded behind the harness's secrets provider so the
// no-leak property has a concrete needle: it is resolved server-side by agentsession yet must appear
// in NO published envelope/heartbeat/control message, no log, and no error.
const SeededCanary = "ARTM-S3CR3T-setup-token-do-not-leak"

// credentialRef is the loggable secrets.Reference the canary resolves under (the value never rides
// it).
const credentialRef = "vault://eden/anthropic#setup-token" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value

// routeKey/route bind the scripted fake harness as an interactive assistant session.
var (
	routeKey = agentsession.RouteKey{Role: "assistant"}
	route    = agentsession.Route{Harness: "fake", Model: "fake-fable-5"}
)

// NewSessions builds a REAL agentsession.Pool (a genuine Factory, NOT a mock) over the agentsessiontest
// scripted fake adapter carrying the given event script, a real in-memory Transcript (so Seq is real),
// and a seeded secrets provider. The sidecar Opens a real session through this — the agentsession
// state machine, Seq ordering, and credential seam are exercised for real; only the harness SUBPROCESS
// is the deterministic scripted fake (the real-subprocess + real-NATS arm is the integration lane).
//
//nolint:ireturn // returns the agentsession.Factory port the sidecar holds (the frozen surface).
func NewSessions(t *testing.T, script ...agentsession.Event) agentsession.Factory {
	t.Helper()
	adapter := agentsessiontest.New(script...)
	provider := secretstest.New(map[string]string{credentialRef: SeededCanary})
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{routeKey: route}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    provider,
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      sessionClock{},
		},
	)
	if err != nil {
		t.Fatalf("construct agentsession.Pool: %v", err)
	}
	return pool
}

// NewSessionsNoT builds the same REAL agentsession.Pool as NewSessions but WITHOUT a *testing.T (for
// the load/lifecycle builders that run outside a per-case T). A construction failure panics — it is a
// programmer error in a test builder, surfaced loudly, never a silent skip.
//
//nolint:ireturn // returns the agentsession.Factory port the sidecar holds (the frozen surface).
func NewSessionsNoT(script ...agentsession.Event) agentsession.Factory {
	adapter := agentsessiontest.New(script...)
	provider := secretstest.New(map[string]string{credentialRef: SeededCanary})
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{routeKey: route}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    provider,
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      sessionClock{},
		},
	)
	if err != nil {
		panic(err)
	}
	return pool
}

// Spec returns the canonical agentsession.Spec the sidecar Config carries (interactive assistant over
// the fake harness, with a Write grant and the opaque canary Reference).
func Spec() agentsession.Spec {
	return agentsession.Spec{
		Workspace:  "/workspace/eden",
		Routing:    routeKey,
		Grants:     []agentsession.ToolGrant{{ID: "grant-write", Tool: "Write"}},
		Credential: secrets.Ref(credentialRef),
	}
}

// Config returns the canonical sidecar Config (the canonical AgentID + Spec). `with` may mutate it
// (e.g. set InitialPrompt or shrink the heartbeat for a fast test).
func Config(with func(*agentruntime.Config)) agentruntime.Config {
	configuration := agentruntime.Config{AgentID: AgentID, Spec: Spec()}
	if with != nil {
		with(&configuration)
	}
	return configuration
}

// NewRuntime constructs a Runtime over the canonical Config + a fresh FakeBus/FakeObserver/FixedClock
// and a real agentsession.Factory carrying the script. It returns the runtime plus the fake bus +
// observer so the test asserts over what was published and drives control verbs. `with` may mutate the
// Config before construction.
func NewRuntime(t *testing.T, with func(*agentruntime.Config), script ...agentsession.Event) (*agentruntime.Runtime, *FakeBus, *FakeObserver) {
	t.Helper()
	bus := NewFakeBus()
	observer := NewFakeObserver()
	runtime, err := agentruntime.New(Config(with), agentruntime.Deps{
		Sessions: NewSessions(t, script...),
		Bus:      bus,
		Observer: observer,
		Clock:    FixedClock{},
	})
	if err != nil {
		t.Fatalf("construct agentruntime.Runtime: %v", err)
	}
	return runtime, bus, observer
}

// CanonicalScript is the full-path harness script the sidecar pumps: a message with thinking + text
// deltas, a granted tool start/end, a usage tick, and a clean terminal Result carrying the
// four-token ledger. It is the agentsessiontest canonical script, re-exported so the sidecar tests
// drive the same proven full path.
func CanonicalScript() []agentsession.Event { return agentsessiontest.CanonicalScript() }

// sessionClock is a deterministic agentsession.Clock for the harness pool.
type sessionClock struct{}

// Now returns a fixed instant matching the agentsessiontest harness clock.
func (sessionClock) Now() time.Time { return fixedSessionTime }
