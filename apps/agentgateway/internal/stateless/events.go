package stateless

import (
	"net/http"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// routes wires the stateless surface onto a std-lib http.ServeMux (Go 1.22+ method+pattern syntax),
// EVERY route behind the edenhttp identity Middleware so an unauthenticated request never reaches a
// handler (ADR-0022 #3: behind auth even locally). The surface the B7 chat UI consumes:
//
//	GET    /sessions/{id}/events            SSE bridge (Last-Event-ID / ?from-seq=) — JetStream replay
//	POST   /sessions/{id}/control           prompt|steer|abort|stop|kill (verb in the body)
//	POST   /sessions/{id}/prompt            convenience: prompt (text in the body)
//	POST   /sessions/{id}/steer             convenience: steer
//	POST   /sessions/{id}/abort             convenience: abort
//	POST   /sessions/{id}/stop              convenience: stop (graceful)
//	POST   /sessions/{id}/kill              convenience: kill (hard)
//	GET    /healthz                         liveness (no auth — a load-balancer probe)
func (g *Gateway) routes() *http.ServeMux {
	mux := http.NewServeMux()
	middleware := g.dependencies.Spine.Middleware

	mux.Handle("GET /sessions/{id}/events", middleware(http.HandlerFunc(g.handleEvents)))
	mux.Handle("POST /sessions/{id}/control", middleware(g.controlHandler()))
	mux.Handle("POST /sessions/{id}/prompt", middleware(g.verbHandler(agentruntime.VerbPrompt)))
	mux.Handle("POST /sessions/{id}/steer", middleware(g.verbHandler(agentruntime.VerbSteer)))
	mux.Handle("POST /sessions/{id}/abort", middleware(g.verbHandler(agentruntime.VerbAbort)))
	mux.Handle("POST /sessions/{id}/stop", middleware(g.verbHandler(agentruntime.VerbStop)))
	mux.Handle("POST /sessions/{id}/kill", middleware(g.verbHandler(agentruntime.VerbKill)))

	// Liveness is the ONE unauthenticated route: a load-balancer / kubelet probe needs no identity,
	// and it reveals no session state (just "the gateway process is up").
	mux.HandleFunc("GET /healthz", g.handleHealth)

	return mux
}

// handleHealth is the liveness probe (no session state, no credential path, no auth).
func (g *Gateway) handleHealth(writer http.ResponseWriter, _ *http.Request) {
	edenhttp.WriteData(writer, http.StatusOK, map[string]string{"status": "ok"})
}

// handleEvents is the stateless NATS→SSE bridge (ADR-0022 #3): it authorizes the caller's
// sessions:read grant, resolves the resume cursor (Last-Event-ID / ?from-seq=), opens an SSE stream,
// and hands the request to the natssse.Bridge, which opens an ephemeral JetStream consumer on
// agent.{id}.events from cursor+1 and frames each agentruntime.EventEnvelope as an SSE event (id ==
// Seq). STATELESS: the bridge holds no per-session state — JetStream replay is the source of truth,
// so any replica serves any session. The request context bounds the stream; a client disconnect
// reaps the consumer + goroutine (the natssse reap invariant).
func (g *Gateway) handleEvents(writer http.ResponseWriter, request *http.Request) {
	identity, ok := edenhttp.IdentityFrom(request.Context())
	if !ok {
		edenhttp.WriteError(writer, errors.New(errors.KindUnauthenticated, "stateless: no verified identity (mount behind Middleware)"))
		return
	}
	if err := identity.Authorize(edenhttp.NewGrant(Namespace, actionRead)); err != nil {
		edenhttp.WriteError(writer, err)
		return
	}

	agentID := agentruntime.AgentID(request.PathValue("id"))
	cursor, err := edenhttp.ResolveCursor(request)
	if err != nil {
		edenhttp.WriteError(writer, err)
		return
	}

	stream, err := edenhttp.NewSSEStream(writer)
	if err != nil {
		edenhttp.WriteError(writer, err)
		return
	}

	g.logInfo("stateless: events stream opened", "agent", string(agentID), "fromSeq", cursor, "by", identity.Subject)
	if bridgeErr := g.dependencies.Bridge.Stream(request.Context(), agentID, cursor, stream); bridgeErr != nil {
		// The 200 + SSE headers are already committed (the stream opened), so the fault was reported
		// to the client as a trailing SSE comment by the bridge; here we only log it server-side.
		g.logError("stateless: events stream faulted", "agent", string(agentID), "error", bridgeErr.Error())
	}
}
