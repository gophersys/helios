package gateway

import (
	"context"
	"net/http"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
)

// handleControl is the control channel (REQ-0020 prompt/steer/abort mid-session). It
// resolves the live session from the registry and issues the normalized Command against it;
// the resulting events stream back on every SSE subscriber's Events tail (the control verb
// returns only the Ack — the admitted Seq — so the UI correlates them). prompt is valid
// when Ready/AwaitingInput, steer interjects into a Running turn (CapSteer), abort cancels
// the in-flight turn — the session enforces the state machine and returns a typed StateError
// (KindConflict → 409) or UnsupportedError (KindInvalid → 400) out of phase.
func (g *Gateway) handleControl(w http.ResponseWriter, r *http.Request) {
	id := orchestrator.AgentID(r.PathValue("id"))

	var request controlRequest
	if err := decodeJSON(r, &request); err != nil {
		g.writeError(w, err)
		return
	}

	command, err := toCommand(&request)
	if err != nil {
		g.writeError(w, err)
		return
	}

	session, ok := g.registry.lookup(id)
	if !ok {
		g.writeError(w, errors.Wrap(errors.KindNotFound, "gateway: control",
			RequestError{Reason: "no live session for id " + string(id)}))
		return
	}

	// The control verb's RESULTING TURN streams asynchronously to every SSE subscriber and so
	// OUTLIVES this request; admit it under a context DETACHED from the request (context.
	// WithoutCancel) so a real async harness keeps streaming after this POST returns its Ack —
	// the same request-lifetime decoupling handleCreateSession applies to the opening prompt.
	ack, err := session.Control(context.WithoutCancel(r.Context()), command)
	if err != nil {
		g.writeError(w, err)
		return
	}
	g.logInfo("gateway: control admitted", "agent", string(id), "command", request.Command, "seq", ack.Seq)
	g.writeJSON(w, http.StatusOK, controlResponse{AdmittedSeq: ack.Seq})
}

// toCommand maps the wire control verb onto the normalized agentsession.Command. An
// unknown verb is a typed RequestError (KindInvalid → 400).
func toCommand(request *controlRequest) (agentsession.Command, error) {
	switch request.Command {
	case "prompt":
		return agentsession.Command{Kind: agentsession.CommandPrompt, Text: request.Text}, nil
	case "steer":
		return agentsession.Command{Kind: agentsession.CommandSteer, Text: request.Text}, nil
	case "abort":
		return agentsession.Command{Kind: agentsession.CommandAbort}, nil
	default:
		return agentsession.Command{}, errors.Wrap(errors.KindInvalid, "gateway: control",
			RequestError{Reason: "command must be one of prompt|steer|abort"})
	}
}

// handleResolvePermission is the permission-resolve path (ADR-0025). It answers a pending
// out-of-grant EventPermissionRequest the SSE stream surfaced: the client POSTs the human's
// verdict to /sessions/{id}/permissions/{requestId}, and the gateway forwards it to the live
// session via Session.Resolve — the session's OWN method, DISTINCT from the prompt/steer/abort
// Command verbs (Resolve is not a turn-taking command; it answers a gate). The resulting
// EventPermissionResolved arrives on every SSE subscriber's tail, so the UI correlates it by
// the admitted Seq. The session enforces first-decision-wins on the RequestID: an unknown or
// already-resolved id is an UnknownPermissionError (KindNotFound → 404); a verdict the policy
// wall refuses is a KindPermission fault (→ 403).
func (g *Gateway) handleResolvePermission(w http.ResponseWriter, r *http.Request) {
	id := orchestrator.AgentID(r.PathValue("id"))
	requestID := r.PathValue("requestId")
	if requestID == "" {
		g.writeError(w, errors.Wrap(errors.KindInvalid, "gateway: resolve permission",
			RequestError{Reason: "requestId path segment is required"}))
		return
	}

	var request resolveRequest
	if err := decodeJSON(r, &request); err != nil {
		g.writeError(w, err)
		return
	}

	decision, err := toDecision(&request)
	if err != nil {
		g.writeError(w, err)
		return
	}

	session, ok := g.registry.lookup(id)
	if !ok {
		g.writeError(w, errors.Wrap(errors.KindNotFound, "gateway: resolve permission",
			RequestError{Reason: "no live session for id " + string(id)}))
		return
	}

	// The PermissionResolved record streams asynchronously to every SSE subscriber and so
	// OUTLIVES this request; forward the decision under a context DETACHED from the request
	// (context.WithoutCancel) so a real async harness keeps emitting after this POST returns
	// its Ack — the same request-lifetime decoupling handleControl applies to a control verb.
	ack, err := session.Resolve(context.WithoutCancel(r.Context()), requestID, decision)
	if err != nil {
		// UnknownPermissionError (already-resolved / unknown id) maps to 404 via KindNotFound;
		// a verdict refused by the policy wall maps to 403 via KindPermission — both flow
		// through the shared Kind→status table (errors_http.go), so no special-casing here.
		g.writeError(w, err)
		return
	}
	g.logInfo("gateway: permission resolved", "agent", string(id), "request", requestID,
		"verdict", request.Verdict, "scope", decision.Scope.String(), "by", decision.By, "seq", ack.Seq)
	g.writeJSON(w, http.StatusOK, resolveResponse{AdmittedSeq: ack.Seq})
}

// toDecision maps the wire resolve request onto the agentsession.Decision the session's
// Resolve method consumes. The verdict drives Allow; the scope bounds an allow to this
// request only (the safe default) or the running session; By is stamped "human:<principal>"
// (the ADR-0025 audit identity for a human-driven resolve), defaulting to "human:anonymous"
// when the client omits it. An unknown verdict or scope is a typed RequestError (KindInvalid
// → 400) — the boundary rejects a malformed answer rather than guessing.
func toDecision(request *resolveRequest) (agentsession.Decision, error) {
	var allow bool
	switch request.Verdict {
	case "allow":
		allow = true
	case "deny":
		allow = false
	default:
		return agentsession.Decision{}, errors.Wrap(errors.KindInvalid, "gateway: resolve permission",
			RequestError{Reason: "verdict must be one of allow|deny"})
	}

	scope, err := toDecisionScope(request.Scope)
	if err != nil {
		return agentsession.Decision{}, err
	}

	principal := request.By
	if principal == "" {
		principal = "anonymous"
	}
	return agentsession.Decision{
		Allow: allow,
		Scope: scope,
		By:    "human:" + principal,
	}, nil
}

// toDecisionScope maps the wire scope token onto the agentsession.DecisionScope. An empty
// scope is the safe default (ScopeOnce — authorize this request only); "session" widens the
// running session's in-memory grant set. An unknown token is a typed RequestError (→ 400).
func toDecisionScope(scope string) (agentsession.DecisionScope, error) {
	switch scope {
	case "", "once":
		return agentsession.ScopeOnce, nil
	case "session":
		return agentsession.ScopeSession, nil
	default:
		return agentsession.ScopeOnce, errors.Wrap(errors.KindInvalid, "gateway: resolve permission",
			RequestError{Reason: "scope must be one of once|session"})
	}
}
