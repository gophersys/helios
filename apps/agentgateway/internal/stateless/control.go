package stateless

import (
	"context"
	"net/http"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// controlBody is the JSON body of POST /sessions/{id}/control: the verb the caller wants the in-pod
// sidecar to enact and the optional text (prompt/steer payload; empty for abort/stop/kill). It is
// the redaction-safe wire DTO — no credential rides here (a credential reaches the harness via the
// agentsession/secrets seam, never a control message).
type controlBody struct {
	Verb string `json:"verb"`           // "prompt" | "steer" | "abort" | "stop" | "kill"
	Text string `json:"text,omitempty"` // prompt/steer message; empty for abort/stop/kill
}

// verbBody is the JSON body of the convenience verb routes (POST /sessions/{id}/prompt etc.): only
// the text, since the route fixes the verb.
type verbBody struct {
	Text string `json:"text,omitempty"`
}

// controlInput is the parsed control intent the pipeline executes: the agent id (from the {id} path),
// the typed verb, and the text. The Parse stage assembles it from the path value + the JSON body, so
// the Execute stage has everything it needs without touching the raw request.
type controlInput struct {
	agentID agentruntime.AgentID
	verb    agentruntime.ControlVerb
	text    string
}

// controlAck is the success body of every control route: the verb that was published to the agent's
// control subject, so the UI confirms the SOFT signal was accepted (delivery to the sidecar is
// asynchronous; the resulting events arrive on the SSE stream).
type controlAck struct {
	Agent     string `json:"agent"`
	Verb      string `json:"verb"`
	Published bool   `json:"published"`
}

// controlHandler builds the 6-stage edenhttp pipeline for POST /sessions/{id}/control: parse the
// {id} path + verb/text body into a controlInput, authorize the sessions:control grant, then publish
// the typed agentruntime.ControlMessage to agent.{id}.control. The verb comes from the BODY here (the
// generic control route); the convenience routes use verbHandler with a fixed verb.
func (g *Gateway) controlHandler() http.Handler {
	return edenhttp.Handler[controlInput, controlAck]{
		Parse: func(request *http.Request) (controlInput, error) {
			var body controlBody
			if err := edenhttp.DecodeJSONBody(request, &body); err != nil {
				return controlInput{}, errors.Wrap(errors.KindOf(err), "stateless: parse control body", err)
			}
			verb, ok := parseVerb(body.Verb)
			if !ok {
				return controlInput{}, errors.Wrap(errors.KindInvalid, "stateless: control",
					edenhttp.RequestError{Reason: "verb must be one of prompt|steer|abort|stop|kill"})
			}
			return controlInput{agentID: pathAgentID(request), verb: verb, text: body.Text}, nil
		},
		Required: edenhttp.NewGrant(Namespace, actionControl),
		Execute:  g.executePublish,
		Logger:   g.dependencies.Logger,
	}
}

// verbHandler builds the pipeline for a convenience verb route (POST /sessions/{id}/prompt etc.): the
// verb is FIXED by the route, so the body carries only the optional text. It authorizes the same
// sessions:control grant and publishes the same typed message.
func (g *Gateway) verbHandler(verb agentruntime.ControlVerb) http.Handler {
	return edenhttp.Handler[controlInput, controlAck]{
		Parse: func(request *http.Request) (controlInput, error) {
			body := verbBody{}
			// The verb routes accept an OPTIONAL body (abort/stop/kill carry none); tolerate an empty
			// body rather than requiring "{}", so a curl with no payload still aborts/stops/kills.
			if request.ContentLength != 0 {
				if err := edenhttp.DecodeJSONBody(request, &body); err != nil {
					return controlInput{}, errors.Wrap(errors.KindOf(err), "stateless: parse verb body", err)
				}
			}
			return controlInput{agentID: pathAgentID(request), verb: verb, text: body.Text}, nil
		},
		Required: edenhttp.NewGrant(Namespace, actionControl),
		Execute:  g.executePublish,
		Logger:   g.dependencies.Logger,
	}
}

// executePublish is the shared Execute stage: it builds the typed agentruntime.ControlMessage
// (stamping the audit `By` from the authenticated subject) and publishes it to agent.{id}.control
// through the injected port. A missing agent id is a 400; a publish fault is the typed error the
// pipeline maps to a status.
func (g *Gateway) executePublish(ctx context.Context, identity edenhttp.Identity, input controlInput) (controlAck, error) {
	if input.agentID == "" {
		return controlAck{}, errors.Wrap(errors.KindInvalid, "stateless: control",
			edenhttp.RequestError{Reason: "missing session id in path"})
	}
	message := agentruntime.ControlMessage{
		AgentID: input.agentID,
		Verb:    input.verb,
		Text:    input.text,
		By:      identity.Subject, // the audit identity (the authenticated caller).
	}
	if err := g.dependencies.Control.PublishControl(ctx, message); err != nil {
		return controlAck{}, errors.Wrap(errors.KindOf(err), "stateless: publish control", err)
	}
	g.logInfo("stateless: control published", "agent", string(input.agentID), "verb", input.verb.String(), "by", identity.Subject)
	return controlAck{Agent: string(input.agentID), Verb: input.verb.String(), Published: true}, nil
}

// pathAgentID reads the {id} path value off the request (the route wildcard).
func pathAgentID(request *http.Request) agentruntime.AgentID {
	return agentruntime.AgentID(request.PathValue("id"))
}

// parseVerb maps a wire verb token onto the typed agentruntime.ControlVerb. Unknown → ok=false.
func parseVerb(token string) (agentruntime.ControlVerb, bool) {
	switch token {
	case "prompt":
		return agentruntime.VerbPrompt, true
	case "steer":
		return agentruntime.VerbSteer, true
	case "abort":
		return agentruntime.VerbAbort, true
	case "stop":
		return agentruntime.VerbStop, true
	case "kill":
		return agentruntime.VerbKill, true
	default:
		return 0, false
	}
}
