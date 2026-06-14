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
