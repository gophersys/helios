package agentruntime

import (
	"context"
	"strings"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// This file implements the founder-ratified Eden permission ADVISOR (2026-06-15) as the
// agentsession.PermissionAdvisor port. agentsession CALLS this port on an out-of-grant request
// (autonomous, or on a chat timeout) and CLAMPS the returned verdict by the data-derived risk
// class — the prompt-injection wall lives in agentsession, not here, so this impl never needs to
// re-implement it (it MAY pass the rationale through). agentsession stays pure (it does NOT spawn
// agents); this impl lives in the runtime BECAUSE the runtime can spawn agentsession sessions.
//
// To adjudicate, Advise opens a SEPARATE, short-lived "reviewer" agentsession (a reasoning role)
// with:
//
//   - NO out-of-grant tools — empty Grants AND a synchronous default-DENY OnPermission, so the
//     reviewer can only reason + answer: it can NEVER itself trigger a recursive permission
//     request (no advisor recursion, no human wait, no runaway tool use).
//   - MAX THINKING enabled — the reviewer's route/model thinking level is dialed up via the
//     reviewer Spec so the verdict is well-reasoned (the route is configured by the composition
//     root; the SystemHints additionally request maximal deliberation).
//   - A BOUNDED budget — a wall-clock deadline AND a token/cost ceiling on the reviewer session,
//     so adjudication can neither hang nor run away. On a reviewer error/timeout/malformed verdict
//     the advisor FAILS SAFE to deny.
//
// The reviewer is prompted from the AdviceContext (the request tool+args+reason + the session
// goal/role/phase + the standing grants + the recent-transcript snippet + the security posture)
// and asked for a structured verdict {allow|deny, scope once|session, rationale}. Advise parses
// that verdict into an agentsession.Decision and audit-logs the decision + rationale via the
// observability seam (every AI-made permission decision is explainable).

// AdvisorConfig is the immutable, fully-resolved input for the permission advisor (the
// configuration pattern: parsed at the edge, frozen here). It holds NO live handles and NO secret
// VALUES — only a loggable secrets.Reference and the reviewer's bounds. It is DATA.
type AdvisorConfig struct {
	// ReviewerRoute selects the reviewer harness+model the Factory resolves (agentconfiguration's
	// "right agent for the right phase"). It SHOULD route to a strong reasoning model with max
	// thinking; the composition root owns that binding. The zero RouteKey is rejected by NewAdvisor.
	ReviewerRoute agentsession.RouteKey

	// ReviewerWorkspace is the already-provisioned workspace dir the reviewer session runs in (the
	// harness CWD). It MAY be a read-only scratch dir — the reviewer has no write grants. Required.
	ReviewerWorkspace string

	// ReviewerCredential is the OPAQUE credential reference the reviewer session resolves
	// server-side (never the value). Required: the reviewer is a real harness session.
	ReviewerCredential secrets.Reference

	// WallClock bounds the reviewer adjudication end-to-end (Open→Prompt→drain). Zero ==
	// DefaultAdvisorWallClock. The reviewer session also receives this as its Budget.MaxWall, and
	// the Advise ctx is additionally bounded by it, so a wedged reviewer is a deny, never a hang.
	WallClock time.Duration

	// MaxCostMicros is the reviewer session's hard cost ceiling (Budget.MaxCostMicros), so a
	// runaway reviewer is Aborted by the agentsession budget authority. Zero == DefaultAdvisorCost.
	MaxCostMicros int64

	// MaxTurns caps the reviewer's turns (Budget.MaxTurns); a one-shot adjudication needs few.
	// Zero == DefaultAdvisorTurns.
	MaxTurns int32
}

// AdvisorDeps is the injected hexagon for the advisor. NewAdvisor constructs no port.
type AdvisorDeps struct {
	// Sessions is the agentsession Factory the advisor opens the REVIEWER session through (the same
	// in-process Factory the runtime already wires). Required.
	Sessions agentsession.Factory

	// Observer is the telemetry/audit seam every reviewer decision + rationale is logged onto, so
	// an AI-made permission decision is explainable after the fact. Required.
	Observer Observer

	// Clock is the advisor's only time source (it stamps no wall clock itself beyond the ctx
	// deadline the Factory honors). Required so the advisor stays pure and deterministic in tests.
	Clock Clock
}

// Advisor default bounds (the configuration pattern: a zero field selects the default, never an
// implicit surprise). The reviewer is a one-shot, low-cost reasoning turn.
const (
	// DefaultAdvisorWallClock bounds one adjudication end-to-end when WallClock is zero.
	DefaultAdvisorWallClock = 60 * time.Second
	// DefaultAdvisorCost is the reviewer session's cost ceiling (micro-units) when MaxCostMicros is zero.
	DefaultAdvisorCost int64 = 50_000
	// DefaultAdvisorTurns caps the reviewer turns when MaxTurns is zero (a one-shot adjudication).
	DefaultAdvisorTurns int32 = 2
)

// reviewerSystemHints instructs the reviewer to deliberate maximally and answer in the exact
// structured form the parser reads. It is NOT a secret and carries no agent prose verbatim into a
// trust position — the wall is enforced by the risk-class clamp in agentsession regardless.
const reviewerSystemHints = "You are an Eden permission REVIEWER. Think maximally and carefully. " +
	"You adjudicate ONE out-of-grant tool request for a working agent. You have NO tools yourself; " +
	"you only reason and answer. Respond with EXACTLY three lines and nothing else:\n" +
	"VERDICT: allow|deny\n" +
	"SCOPE: once|session\n" +
	"RATIONALE: <one concise sentence, no secrets>"

// verdict-frame markers the reviewer is asked to emit and the parser reads. Kept as constants so
// the prompt instruction and the parser cannot drift.
const (
	verdictMarker   = "verdict:"
	scopeMarker     = "scope:"
	rationaleMarker = "rationale:"
)

// Advisor is the constructed permission advisor (the concrete return of NewAdvisor — accept the
// ports, return the concrete type, 10 §9). Its zero value is unusable; build it via NewAdvisor and
// inject it as agentsession.Deps.Advisor. It is safe for concurrent Advise calls (each opens its
// own short-lived reviewer session; the Advisor holds no per-call mutable state).
type Advisor struct {
	configuration AdvisorConfig
	sessions      agentsession.Factory
	observer      Observer
	clock         Clock
}

// NewAdvisor constructs an Advisor from its Config and Deps. It is PURE: it validates the
// invariants (a present ReviewerRoute/Workspace/Credential, every required port non-nil) and wires
// the ports — no I/O, no clock read, no harness spawn (that happens per-Advise). It returns a typed
// ConfigError (KindInvalid) on a violated invariant, so the composition root fails fast and loud.
//
//nolint:gocritic // contract: AdvisorConfig is the frozen, copyable input (the configuration pattern); the constructor spine takes it by value.
func NewAdvisor(configuration AdvisorConfig, dependencies AdvisorDeps) (*Advisor, error) {
	if (configuration.ReviewerRoute == agentsession.RouteKey{}) {
		return nil, newConfigError("AdvisorConfig.ReviewerRoute is required")
	}
	if configuration.ReviewerWorkspace == "" {
		return nil, newConfigError("AdvisorConfig.ReviewerWorkspace is required")
	}
	if configuration.ReviewerCredential.IsZero() {
		return nil, newConfigError("AdvisorConfig.ReviewerCredential is required")
	}
	if dependencies.Sessions == nil {
		return nil, newConfigError("AdvisorDeps.Sessions (agentsession.Factory) is required")
	}
	if dependencies.Observer == nil {
		return nil, newConfigError("AdvisorDeps.Observer is required")
	}
	if dependencies.Clock == nil {
		return nil, newConfigError("AdvisorDeps.Clock is required")
	}
	return &Advisor{
		configuration: configuration,
		sessions:      dependencies.Sessions,
		observer:      dependencies.Observer,
		clock:         dependencies.Clock,
	}, nil
}

// compile-time assertion: *Advisor is an agentsession.PermissionAdvisor (the frozen port).
var _ agentsession.PermissionAdvisor = (*Advisor)(nil)

// Advise adjudicates ONE out-of-grant request by opening a bounded, tool-less reviewer session,
// prompting it from the AdviceContext, and parsing its structured verdict into a Decision. It is
// FAIL-SAFE: a reviewer Open/Prompt/drain error, a deadline, or a malformed/empty verdict all map
// to a DENY (never an allow, never an indefinite block — the ctx the caller passes additionally
// bounds the whole call). The returned Decision is still subject to the risk-class clamp in
// agentsession; this impl does not re-implement the wall, but it passes the rationale through.
//
//nolint:gocritic // PermissionRequest/AdviceContext are agentsession's frozen copyable value records (§2); the port takes them by value.
func (a *Advisor) Advise(ctx context.Context, request agentsession.PermissionRequest, advice agentsession.AdviceContext) (agentsession.Decision, error) {
	// Bound the whole adjudication by the wall-clock budget AND the caller's ctx, whichever is
	// tighter. A wedged reviewer can therefore never hang the resolution chain.
	adjudicateCtx, cancel := context.WithTimeout(ctx, a.wallClock())
	defer cancel()

	decision, err := a.adjudicate(adjudicateCtx, request, &advice)
	if err != nil {
		// FAIL SAFE: any reviewer fault is a deny. The error is audit-logged (not swallowed) and a
		// deny Decision is returned so the chain proceeds (and the clamp in agentsession is moot on
		// a deny). We return a nil error so the caller treats this as a decided deny, not a transport
		// fault that would re-route — the deny IS the decision.
		a.observer.Logf(ctx, "agentruntime advisor: agent reviewer failed for tool=%q request=%q: %v (failing safe to deny)",
			request.Tool, request.RequestID, err)
		return denyDecision("advisor reviewer error; failed safe to deny"), nil
	}

	a.observer.Logf(ctx, "agentruntime advisor: decision tool=%q request=%q allow=%t scope=%s by=%q rationale=%q",
		request.Tool, request.RequestID, decision.Allow, decision.Scope, decision.By, decision.Rationale)
	return decision, nil
}

// adjudicate opens the reviewer session, prompts it, drains its reply, and parses the verdict. It
// returns an error on any reviewer fault (Open/Prompt/drain/empty reply) so Advise fails safe; a
// MALFORMED non-empty reply is NOT an error — it parses to a deny (the safe default verdict),
// because a reviewer that answered but garbled its frame is a decided deny, not a transport fault.
func (a *Advisor) adjudicate(ctx context.Context, request agentsession.PermissionRequest, advice *agentsession.AdviceContext) (agentsession.Decision, error) {
	session, err := a.sessions.Open(ctx, a.reviewerSpec())
	if err != nil {
		return agentsession.Decision{}, errors.Wrap(errors.KindUnavailable, "agentruntime advisor: open reviewer session", err)
	}
	defer func() {
		// Reap the reviewer session, bounded so the cleanup cannot hang past the budget.
		closeCtx, closeCancel := context.WithTimeout(context.WithoutCancel(ctx), reviewerCloseTimeout)
		defer closeCancel()
		_ = session.Close(closeCtx) //nolint:errcheck // best-effort reviewer reap; the verdict is the actionable outcome.
	}()

	if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: buildReviewerPrompt(&request, advice)}); err != nil {
		return agentsession.Decision{}, errors.Wrap(errors.KindUnavailable, "agentruntime advisor: prompt reviewer", err)
	}

	reply, err := drainReviewerReply(ctx, session)
	if err != nil {
		return agentsession.Decision{}, err
	}
	if strings.TrimSpace(reply) == "" {
		return agentsession.Decision{}, errors.New(errors.KindInternal, "agentruntime advisor: reviewer returned an empty verdict")
	}
	return parseVerdict(reply), nil
}

// reviewerSpec builds the reviewer session Spec: NO grants and a synchronous default-DENY
// OnPermission (so the reviewer can NEVER trigger a recursive out-of-grant request — it has no
// tools AND any attempt is denied in-process, no advisor recursion, no human wait), a bounded
// Budget (wall-clock + cost + turns), the reviewer route, and max-thinking SystemHints. The
// reviewer carries the configured opaque credential reference, resolved server-side (never a value
// here). PermissionResolution stays the safe default; OnPermission short-circuits it to deny.
func (a *Advisor) reviewerSpec() agentsession.Spec {
	return agentsession.Spec{
		Workspace:   a.configuration.ReviewerWorkspace,
		Routing:     a.configuration.ReviewerRoute,
		Grants:      nil, // NO out-of-grant tools: the reviewer only reasons and answers
		Credential:  a.configuration.ReviewerCredential,
		SystemHints: reviewerSystemHints,
		Budget: agentsession.Budget{
			MaxCostMicros: a.maxCostMicros(),
			MaxTurns:      a.maxTurns(),
			MaxWall:       a.wallClock(),
		},
		// Default-DENY any tool the reviewer somehow tries: a synchronous, clean-room policy that
		// returns deny for EVERY request, so the reviewer cannot escalate to an advisor or a human
		// and cannot run a tool. This is the "no out-of-grant tools" guarantee made un-bypassable.
		OnPermission: denyAllPolicy,
	}
}

// denyAllPolicy is the reviewer's synchronous permission policy: deny EVERY request. It guarantees
// the reviewer session can never acquire a tool outside its (empty) grants — no recursion, no
// human wait, no runaway. It is a clean-room policy (not influenced by agent prose).
//
//nolint:gocritic // PermissionRequest is agentsession's frozen copyable value record (§2); the policy reads it by value.
func denyAllPolicy(_ agentsession.PermissionRequest) agentsession.Decision {
	return agentsession.Decision{
		Allow:     false,
		By:        "policy:reviewer-no-tools",
		Scope:     agentsession.ScopeOnce,
		Rationale: "the permission reviewer has no tools; every out-of-grant request is denied",
	}
}

// wallClock returns the configured adjudication bound or the default.
func (a *Advisor) wallClock() time.Duration {
	if a.configuration.WallClock > 0 {
		return a.configuration.WallClock
	}
	return DefaultAdvisorWallClock
}

// maxCostMicros returns the configured reviewer cost ceiling or the default.
func (a *Advisor) maxCostMicros() int64 {
	if a.configuration.MaxCostMicros > 0 {
		return a.configuration.MaxCostMicros
	}
	return DefaultAdvisorCost
}

// maxTurns returns the configured reviewer turn cap or the default.
func (a *Advisor) maxTurns() int32 {
	if a.configuration.MaxTurns > 0 {
		return a.configuration.MaxTurns
	}
	return DefaultAdvisorTurns
}

// reviewerCloseTimeout bounds the reviewer session reap so the deferred Close cannot hang the
// adjudication past its budget on a wedged harness.
const reviewerCloseTimeout = 5 * time.Second

// drainReviewerReply reads the reviewer session's Event stream from Seq 0 to its terminal (or the
// ctx deadline), accumulating the assistant text. The terminal Result's ResultText is preferred
// when present (the authoritative final text); otherwise the concatenated text deltas are used. A
// stream fault or a non-Result terminal (Failed/Aborted) is an error so Advise fails safe.
func drainReviewerReply(ctx context.Context, session agentsession.Session) (string, error) {
	stream := session.Events(ctx, agentsession.FromSeq(0))
	var deltas strings.Builder
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			if err := stream.Err(); err != nil {
				return "", errors.Wrap(errors.KindUnavailable, "agentruntime advisor: drain reviewer stream", err)
			}
			// The stream ended without a terminal we could classify (ctx deadline mid-drain): the
			// accumulated deltas are all we have; treat an empty accumulation as a fault.
			if deltas.Len() == 0 {
				return "", errors.New(errors.KindDeadline, "agentruntime advisor: reviewer stream ended before a verdict")
			}
			return deltas.String(), nil
		}
		switch event.Kind {
		case agentsession.EventTextDelta:
			if event.Message != nil {
				deltas.WriteString(event.Message.Delta)
			}
		case agentsession.EventResult:
			if event.Terminal != nil && strings.TrimSpace(event.Terminal.ResultText) != "" {
				return event.Terminal.ResultText, nil
			}
			return deltas.String(), nil
		case agentsession.EventFailed, agentsession.EventAborted:
			return "", errors.New(errors.KindUnavailable, "agentruntime advisor: reviewer session ended without a clean result")
		default:
			// thinking/message/usage/permission frames are not part of the verdict text.
		}
	}
}

// buildReviewerPrompt assembles the adjudication prompt from the request + AdviceContext: the
// tool+args+reason being requested, the session goal/role/phase, the standing grants, the recent
// transcript snippet, the security posture, and the data-derived risk class. It carries only
// redacted, loggable context — never a secret value (the AdviceContext is built secret-free by
// agentsession). The instruction to answer in the structured frame lives in the reviewer Spec's
// SystemHints; this prompt is the case material. Both inputs are passed by pointer (the
// AdviceContext is heavy) and read-only.
func buildReviewerPrompt(request *agentsession.PermissionRequest, advice *agentsession.AdviceContext) string {
	var b strings.Builder
	b.WriteString("Adjudicate this out-of-grant tool request.\n\n")
	b.WriteString("REQUESTED TOOL: ")
	b.WriteString(request.Tool)
	b.WriteByte('\n')
	if args := strings.TrimSpace(string(request.Input)); args != "" {
		b.WriteString("REQUESTED ARGUMENTS: ")
		b.WriteString(args)
		b.WriteByte('\n')
	}
	if request.Reason != "" {
		b.WriteString("AGENT'S STATED REASON: ")
		b.WriteString(request.Reason)
		b.WriteByte('\n')
	}
	b.WriteString("RISK CLASS (data-derived, authoritative): ")
	b.WriteString(advice.Risk.String())
	b.WriteByte('\n')
	if advice.SessionGoal != "" {
		b.WriteString("SESSION GOAL: ")
		b.WriteString(advice.SessionGoal)
		b.WriteByte('\n')
	}
	if advice.Role != "" || advice.Phase != "" {
		b.WriteString("AGENT ROLE/PHASE: ")
		b.WriteString(advice.Role)
		b.WriteByte('/')
		b.WriteString(advice.Phase)
		b.WriteByte('\n')
	}
	if advice.SecurityPosture != "" {
		b.WriteString("SECURITY POSTURE: ")
		b.WriteString(advice.SecurityPosture)
		b.WriteByte('\n')
	}
	if len(advice.Grants) > 0 {
		b.WriteString("STANDING GRANTS: ")
		b.WriteString(renderGrants(advice.Grants))
		b.WriteByte('\n')
	}
	if snippet := strings.TrimSpace(advice.RecentTranscript); snippet != "" {
		b.WriteString("RECENT TRANSCRIPT (redacted):\n")
		b.WriteString(snippet)
		b.WriteByte('\n')
	}
	b.WriteString("\nNote: a HIGH-risk request is destructive/irreversible/egress/credential-bearing; ")
	b.WriteString("prefer deny or escalation for it. Answer in the required three-line frame.")
	return b.String()
}

// renderGrants renders the standing grant set as a compact, loggable string for the prompt (no
// secrets — grants are allowlist DATA). Each grant is "Tool(scope,scope)" or just "Tool".
func renderGrants(grants []agentsession.ToolGrant) string {
	parts := make([]string, 0, len(grants))
	for i := range grants {
		grant := &grants[i]
		if len(grant.Scopes) == 0 {
			parts = append(parts, grant.Tool)
			continue
		}
		parts = append(parts, grant.Tool+"("+strings.Join(grant.Scopes, ",")+")")
	}
	return strings.Join(parts, ", ")
}

// parseVerdict parses the reviewer's structured three-line frame into a Decision. It is TOLERANT
// of surrounding prose and case but DEFAULTS SAFE: an absent/garbled VERDICT line yields a DENY,
// an absent SCOPE yields ScopeOnce, an absent RATIONALE yields a recorded placeholder. The By stamp
// is "advisor:reviewer-agent" so the audit chain attributes the decision to the AI reviewer. A
// returned ALLOW is still subject to the risk-class clamp in agentsession (the wall is enforced
// there, not trusted here).
func parseVerdict(reply string) agentsession.Decision {
	allow := false
	scope := agentsession.ScopeOnce
	rationale := ""
	for _, raw := range strings.Split(reply, "\n") {
		line := strings.TrimSpace(raw)
		lower := strings.ToLower(line)
		switch {
		case strings.HasPrefix(lower, verdictMarker):
			value := strings.TrimSpace(line[len(verdictMarker):])
			// Only an explicit "allow" allows; anything else (including "deny", garbage, or empty)
			// is a deny — the safe default. firstWord is empty for an empty value (→ deny).
			allow = strings.EqualFold(firstWord(value), "allow")
		case strings.HasPrefix(lower, scopeMarker):
			value := strings.ToLower(strings.TrimSpace(line[len(scopeMarker):]))
			if strings.HasPrefix(value, "session") {
				scope = agentsession.ScopeSession
			}
		case strings.HasPrefix(lower, rationaleMarker):
			rationale = strings.TrimSpace(line[len(rationaleMarker):])
		default:
			// surrounding prose the reviewer may have added — ignored.
		}
	}
	if rationale == "" {
		rationale = "advisor reviewer returned no explicit rationale"
	}
	if !allow {
		// A deny ignores scope (a deny is terminal-for-this-request regardless of scope).
		return agentsession.Decision{
			Allow:     false,
			By:        advisorBy,
			Scope:     agentsession.ScopeOnce,
			Rationale: rationale,
		}
	}
	return agentsession.Decision{
		Allow:     true,
		By:        advisorBy,
		Scope:     scope,
		Rationale: rationale,
	}
}

// firstWord returns the first whitespace-delimited word of s, or "" when s is blank — so an empty
// VERDICT value safely yields a deny (never a panic on an empty Fields slice).
func firstWord(s string) string {
	fields := strings.Fields(s)
	if len(fields) == 0 {
		return ""
	}
	return fields[0]
}

// advisorBy is the audit identity stamp on every advisor-made Decision ("advisor:<name>", per the
// agentsession Decision contract). It attributes the verdict to the AI reviewer in the transcript.
const advisorBy = "advisor:reviewer-agent"

// denyDecision builds a fail-safe deny carrying the given rationale and the advisor By stamp.
func denyDecision(rationale string) agentsession.Decision {
	return agentsession.Decision{
		Allow:     false,
		By:        advisorBy,
		Scope:     agentsession.ScopeOnce,
		Rationale: rationale,
	}
}
