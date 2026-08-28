package agentruntime_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// The advisor unit suite proves the agentruntime PermissionAdvisor impl maps a reviewer's
// structured verdict to the right agentsession.Decision, FAILS SAFE to deny on a malformed/empty
// reply or a reviewer fault, and opens the reviewer session with NO out-of-grant tools + a bounded
// budget (no recursion, no runaway). It drives the FAKE scripted agentsessiontest harness through a
// recording Factory that captures the exact Spec the advisor opened the reviewer with — so the
// security invariants (empty grants, deny-all policy, bounded budget) are asserted on real data,
// not narrated.

// reviewerRoute is the route the reviewer session resolves through. The recording pool registers it.
var reviewerRoute = agentsession.RouteKey{Role: "reviewer", Phase: "review"}

// reviewerCredentialRef is the loggable opaque reference the reviewer credential resolves under.
const reviewerCredentialRef = "vault://eden/anthropic#reviewer-token" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value

// recordingFactory wraps a REAL agentsession.Pool (a genuine Factory over the scripted fake
// adapter) and records every Spec the advisor opened a reviewer session with, so a test asserts the
// reviewer's no-tools + bounded-budget invariants on the actual opened Spec. It also lets a test
// force Open to fail (the reviewer-fault fail-safe arm).
type recordingFactory struct {
	inner    agentsession.Factory
	openErr  error
	mu       chan struct{} // a 1-buffered channel used as a mutex (no extra import)
	openedAt []agentsession.Spec
}

// newRecordingFactory builds a recording factory over a real Pool whose scripted fake reviewer
// replies with the given events (the reviewer's text + terminal). The reviewer route + a seeded
// provider are registered so Open resolves and the credential reference is honored.
func newRecordingFactory(t *testing.T, reviewerScript ...agentsession.Event) *recordingFactory {
	t.Helper()
	adapter := agentsessiontest.New(reviewerScript...)
	provider := secretstest.New(map[string]string{reviewerCredentialRef: "REVIEWER-TOKEN-do-not-leak"})
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			reviewerRoute: {Harness: "fake", Model: "fake-fable-5-max-thinking"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    provider,
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      fixedSessionClock{},
		},
	)
	if err != nil {
		t.Fatalf("construct reviewer Pool: %v", err)
	}
	f := &recordingFactory{inner: pool, mu: make(chan struct{}, 1)}
	f.mu <- struct{}{}
	return f
}

// Open records the Spec, then delegates to the real Pool (or returns the forced error).
//
//nolint:gocritic,ireturn // contract §2/§3: Spec is the frozen copyable input and Open returns the Session port (the frozen surface).
func (f *recordingFactory) Open(ctx context.Context, spec agentsession.Spec) (agentsession.Session, error) {
	<-f.mu
	f.openedAt = append(f.openedAt, spec)
	openErr := f.openErr
	f.mu <- struct{}{}
	if openErr != nil {
		return nil, openErr
	}
	return f.inner.Open(ctx, spec)
}

// opened returns a copy of every Spec the advisor opened a reviewer with.
func (f *recordingFactory) opened() []agentsession.Spec {
	<-f.mu
	out := make([]agentsession.Spec, len(f.openedAt))
	copy(out, f.openedAt)
	f.mu <- struct{}{}
	return out
}

// fixedSessionClock is a deterministic agentsession.Clock for the reviewer Pool.
type fixedSessionClock struct{}

func (fixedSessionClock) Now() time.Time {
	return time.Date(2026, time.June, 15, 12, 0, 0, 0, time.UTC)
}

// newAdvisor builds an Advisor over the recording factory + a fake observer (the audit seam).
func newAdvisor(t *testing.T, factory agentsession.Factory) (*agentruntime.Advisor, *agentruntimetest.FakeObserver) {
	t.Helper()
	observer := agentruntimetest.NewFakeObserver()
	advisor, err := agentruntime.NewAdvisor(
		agentruntime.AdvisorConfig{
			ReviewerRoute:      reviewerRoute,
			ReviewerWorkspace:  "/workspace/reviewer",
			ReviewerCredential: secrets.Ref(reviewerCredentialRef),
			WallClock:          5 * time.Second,
			MaxCostMicros:      40_000,
			MaxTurns:           2,
		},
		agentruntime.AdvisorDeps{
			Sessions: factory,
			Observer: observer,
			Clock:    agentruntimetest.FixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("NewAdvisor: %v", err)
	}
	return advisor, observer
}

// reviewerReplyScript builds the scripted reviewer harness reply: a thinking block, the structured
// three-line verdict as the terminal Result text, so drainReviewerReply reads the ResultText.
func reviewerReplyScript(verdictText string) []agentsession.Event {
	return []agentsession.Event{
		agentsessiontest.MessageStart("assistant"),
		agentsessiontest.ThinkingDelta("weighing the request against the session goal"),
		agentsessiontest.TextDelta(verdictText),
		agentsessiontest.MessageEnd(),
		agentsessiontest.Result(agentsession.TokenLedger{
			UsageMeter: agentsession.UsageMeter{Model: "fake-fable-5-max-thinking", Harness: "fake", CostMicros: 1200, Cumulative: true},
			Turns:      1,
		}, verdictText, "end_turn"),
	}
}

// sampleRequest/sampleAdvice are a concrete low-risk out-of-grant request + its advice bundle.
func sampleRequest() agentsession.PermissionRequest {
	return agentsession.PermissionRequest{
		RequestID: "req-1",
		Tool:      "Read",
		Input:     []byte("path=docs/architecture/README.md"),
		Reason:    "needs to read the architecture doc to plan the change",
	}
}

func sampleAdvice() agentsession.AdviceContext {
	return agentsession.AdviceContext{
		SessionGoal:      "implement the kernel build plan",
		Role:             "implementer",
		Phase:            "implement",
		Grants:           []agentsession.ToolGrant{{ID: "g-write", Tool: "Write"}},
		RecentTranscript: "assistant: I will read the README first",
		SecurityPosture:  "sandboxed-with-standing-grants",
		Risk:             agentsession.RiskLow,
	}
}

// TestAdvisor_MapsStructuredAllowVerdict proves the advisor parses a well-formed allow verdict into
// the right Decision: Allow=true, ScopeSession, the rationale carried through, By=advisor:<name>.
func TestAdvisor_MapsStructuredAllowVerdict(t *testing.T) {
	t.Parallel()
	verdict := "VERDICT: allow\nSCOPE: session\nRATIONALE: reading a doc is read-only and in the spirit of the implement goal"
	factory := newRecordingFactory(t, reviewerReplyScript(verdict)...)
	advisor, observer := newAdvisor(t, factory)

	decision, err := advisor.Advise(context.Background(), sampleRequest(), sampleAdvice())
	if err != nil {
		t.Fatalf("Advise returned an error: %v", err)
	}
	if !decision.Allow {
		t.Errorf("decision.Allow = false, want true (the reviewer voted allow)")
	}
	if decision.Scope != agentsession.ScopeSession {
		t.Errorf("decision.Scope = %s, want session", decision.Scope)
	}
	if !strings.Contains(decision.By, "advisor:") {
		t.Errorf("decision.By = %q, want an advisor:<name> stamp", decision.By)
	}
	if !strings.Contains(decision.Rationale, "read-only") {
		t.Errorf("decision.Rationale = %q, want the reviewer's reasoning carried through", decision.Rationale)
	}
	// The decision + rationale must be audit-logged (every AI-made decision is explainable).
	if !logContains(observer, "decision") || !logContains(observer, "req-1") {
		t.Errorf("the advisor decision was not audit-logged via the observer seam")
	}
}

// logContains reports whether any audit-log line recorded on the observer contains substr.
func logContains(observer *agentruntimetest.FakeObserver, substr string) bool {
	for _, line := range observer.Logs() {
		if strings.Contains(line, substr) {
			return true
		}
	}
	return false
}

// TestAdvisor_MapsStructuredDenyVerdict proves a deny verdict maps to a deny Decision (scope is
// forced to once on a deny — a deny is terminal-for-this-request regardless of scope).
func TestAdvisor_MapsStructuredDenyVerdict(t *testing.T) {
	t.Parallel()
	verdict := "VERDICT: deny\nSCOPE: session\nRATIONALE: out of scope for this session"
	factory := newRecordingFactory(t, reviewerReplyScript(verdict)...)
	advisor, _ := newAdvisor(t, factory)

	decision, err := advisor.Advise(context.Background(), sampleRequest(), sampleAdvice())
	if err != nil {
		t.Fatalf("Advise: %v", err)
	}
	if decision.Allow {
		t.Errorf("decision.Allow = true, want false (the reviewer voted deny)")
	}
	if decision.Scope != agentsession.ScopeOnce {
		t.Errorf("a deny must carry ScopeOnce, got %s", decision.Scope)
	}
}

// TestAdvisor_MalformedVerdictFailsSafeToDeny proves a non-empty but GARBLED reply (no parseable
// VERDICT line) defaults safe to a DENY — the reviewer answered but did not say allow, so it is a
// deny, never a silent allow.
func TestAdvisor_MalformedVerdictFailsSafeToDeny(t *testing.T) {
	t.Parallel()
	factory := newRecordingFactory(t, reviewerReplyScript("I'm not sure, it depends on the situation honestly.")...)
	advisor, _ := newAdvisor(t, factory)

	decision, err := advisor.Advise(context.Background(), sampleRequest(), sampleAdvice())
	if err != nil {
		t.Fatalf("Advise should not error on a malformed verdict (it is a decided deny): %v", err)
	}
	if decision.Allow {
		t.Fatalf("a malformed verdict MUST fail safe to deny, got allow")
	}
}

// TestAdvisor_EmptyReplyFailsSafeToDeny proves an EMPTY reviewer reply (no text, terminal with no
// result text) fails safe to a deny.
func TestAdvisor_EmptyReplyFailsSafeToDeny(t *testing.T) {
	t.Parallel()
	// A reviewer that reaches a clean terminal but emitted NO text and NO result text.
	emptyScript := []agentsession.Event{
		agentsessiontest.MessageStart("assistant"),
		agentsessiontest.MessageEnd(),
		agentsessiontest.Result(agentsession.TokenLedger{
			UsageMeter: agentsession.UsageMeter{Harness: "fake", Cumulative: true}, Turns: 1,
		}, "", "end_turn"),
	}
	factory := newRecordingFactory(t, emptyScript...)
	advisor, _ := newAdvisor(t, factory)

	decision, err := advisor.Advise(context.Background(), sampleRequest(), sampleAdvice())
	if err != nil {
		t.Fatalf("Advise should fail safe to deny (no error) on an empty reply: %v", err)
	}
	if decision.Allow {
		t.Fatalf("an empty reviewer reply MUST fail safe to deny, got allow")
	}
}

// TestAdvisor_ReviewerOpenFailureFailsSafeToDeny proves that when the reviewer session cannot even
// be opened (a harness fault), the advisor fails safe to a deny (never an allow, never a hang).
func TestAdvisor_ReviewerOpenFailureFailsSafeToDeny(t *testing.T) {
	t.Parallel()
	factory := newRecordingFactory(t, reviewerReplyScript("VERDICT: allow\nSCOPE: once\nRATIONALE: x")...)
	factory.openErr = errors.New(errors.KindUnavailable, "reviewer harness unavailable")
	advisor, observer := newAdvisor(t, factory)

	decision, err := advisor.Advise(context.Background(), sampleRequest(), sampleAdvice())
	if err != nil {
		t.Fatalf("Advise should fail safe (no error) on a reviewer Open failure: %v", err)
	}
	if decision.Allow {
		t.Fatalf("a reviewer Open failure MUST fail safe to deny, got allow")
	}
	if !logContains(observer, "failing safe to deny") {
		t.Errorf("the reviewer failure was not audit-logged")
	}
}

// TestAdvisor_OpensReviewerWithNoToolsAndBoundedBudget is the SECURITY invariant: the reviewer
// session is opened with NO out-of-grant tools (empty Grants) AND a deny-all OnPermission policy
// (so it can never trigger a recursive permission request — no recursion) AND a bounded budget
// (wall-clock + cost + turns — no runaway). These are asserted on the EXACT Spec the advisor opened.
func TestAdvisor_OpensReviewerWithNoToolsAndBoundedBudget(t *testing.T) {
	t.Parallel()
	factory := newRecordingFactory(t, reviewerReplyScript("VERDICT: allow\nSCOPE: once\nRATIONALE: ok")...)
	advisor, _ := newAdvisor(t, factory)

	if _, err := advisor.Advise(context.Background(), sampleRequest(), sampleAdvice()); err != nil {
		t.Fatalf("Advise: %v", err)
	}

	opened := factory.opened()
	if len(opened) != 1 {
		t.Fatalf("the advisor opened %d reviewer sessions, want exactly 1 (one-shot adjudication)", len(opened))
	}
	spec := opened[0]

	// NO out-of-grant tools: empty standing grants.
	if len(spec.Grants) != 0 {
		t.Errorf("the reviewer Spec carries %d grants, want 0 (no out-of-grant tools)", len(spec.Grants))
	}
	if len(spec.HostTools) != 0 {
		t.Errorf("the reviewer Spec carries %d host tools, want 0", len(spec.HostTools))
	}
	// The deny-all policy: any tool the reviewer tries is denied (no recursion, no human wait).
	if spec.OnPermission == nil {
		t.Fatalf("the reviewer Spec has no OnPermission policy: the reviewer could trigger a recursive permission request")
	}
	if got := spec.OnPermission(agentsession.PermissionRequest{Tool: "Bash"}); got.Allow {
		t.Errorf("the reviewer OnPermission allowed a tool: it MUST deny every request (no recursion)")
	}
	// BOUNDED budget: a wall-clock AND a cost ceiling AND a turn cap, so adjudication cannot run away.
	if spec.Budget.MaxWall <= 0 {
		t.Errorf("the reviewer Spec has no wall-clock budget: adjudication could hang")
	}
	if spec.Budget.MaxCostMicros <= 0 {
		t.Errorf("the reviewer Spec has no cost ceiling: adjudication could run away")
	}
	if spec.Budget.MaxTurns <= 0 {
		t.Errorf("the reviewer Spec has no turn cap: adjudication could loop")
	}
	// MAX THINKING is requested via the reviewer SystemHints (a reasoning posture, not a tool).
	if !strings.Contains(strings.ToLower(spec.SystemHints), "think") {
		t.Errorf("the reviewer Spec does not request max thinking via SystemHints: %q", spec.SystemHints)
	}
}

// TestAdvisor_RejectsIncompleteConfig proves NewAdvisor fails fast on a missing invariant (the
// pure constructor spine: validate config + deps, no I/O).
func TestAdvisor_RejectsIncompleteConfig(t *testing.T) {
	t.Parallel()
	factory := newRecordingFactory(t)
	cases := []struct {
		name      string
		mutate    func(*agentruntime.AdvisorConfig)
		nilFactor bool
	}{
		{name: "no route", mutate: func(c *agentruntime.AdvisorConfig) { c.ReviewerRoute = agentsession.RouteKey{} }},
		{name: "no workspace", mutate: func(c *agentruntime.AdvisorConfig) { c.ReviewerWorkspace = "" }},
		{name: "no credential", mutate: func(c *agentruntime.AdvisorConfig) { c.ReviewerCredential = secrets.Reference{} }},
		{name: "nil sessions", nilFactor: true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			configuration := agentruntime.AdvisorConfig{
				ReviewerRoute:      reviewerRoute,
				ReviewerWorkspace:  "/workspace/reviewer",
				ReviewerCredential: secrets.Ref(reviewerCredentialRef),
			}
			if tc.mutate != nil {
				tc.mutate(&configuration)
			}
			dependencies := agentruntime.AdvisorDeps{
				Sessions: factory,
				Observer: agentruntimetest.NewFakeObserver(),
				Clock:    agentruntimetest.FixedClock{},
			}
			if tc.nilFactor {
				dependencies.Sessions = nil
			}
			if _, err := agentruntime.NewAdvisor(configuration, dependencies); err == nil {
				t.Fatalf("NewAdvisor(%s) returned nil error, want a ConfigError", tc.name)
			} else if errors.KindOf(err) != errors.KindInvalid {
				t.Errorf("NewAdvisor(%s) error kind = %v, want KindInvalid", tc.name, errors.KindOf(err))
			}
		})
	}
}
