// Package stateless is the agentgateway's PRODUCTION HTTP surface (ADR-0022 #3): a STATELESS
// NATS/JetStream→SSE bridge + REST-POST control plane. It owns NO agent logic and holds NO
// per-session state — any gateway replica serves any session by JetStream durable replay:
//
//   - GET  /sessions/{id}/events  — a JetStream→SSE bridge (edenhttp/natssse): an ephemeral consumer
//     on agent.{id}.events from Last-Event-ID/from-seq, each agentruntime.EventEnvelope framed as an
//     SSE event (id == Seq). A reconnect resumes gap-free; a replica restart loses nothing.
//   - POST /sessions/{id}/control (+ /prompt|/steer|/abort|/stop|/kill) — the edenhttp 6-stage
//     pipeline publishes a typed agentruntime.ControlMessage to agent.{id}.control (the SOFT signal
//     the in-pod PID-1 sidecar subscribes and enacts).
//
// EVERY route is behind the edenhttp dev-JWT + namespace:action grant authz (ADR-0022 #3: behind
// auth even locally). The package owns only the wiring + the per-route grant policy; the bridge,
// the auth, the pipeline, and the bus protocol all live in their frozen homes (edenhttp, natssse,
// agentruntime) — one concept, one home (10 §9).
//
// It is the deliberate counterpart to internal/devserve (the in-process Pool dev path over fakes):
// the dev path stays for quick local UI testing; THIS path is what a deployed gateway runs.
package stateless

import (
	"context"
	"net/http"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/natssse"
	"github.com/gophersys/libs/go/errors"
)

// Namespace is the grant namespace every gateway route authorizes within (the "sessions" resource
// family in the namespace:action grant grammar). A caller's dev-JWT must carry sessions:<action>
// (or a wildcard covering it) to reach the route.
const Namespace = "sessions"

// The grant actions the routes require (the namespace:action vocabulary, IOTEA RBAC). Reading the
// event stream needs sessions:read; any control verb needs sessions:control.
const (
	actionRead    = "read"
	actionControl = "control"
)

// ControlPublisher is the consumer-defined port the gateway publishes a control verb through (accept
// this interface; the natscontrol adapter is the production impl, a fake binds it in tests). It is
// the SHAPE OF THE NEED — one method — not a mirror of NATS: the gateway asks only "publish this
// typed ControlMessage to the agent's control subject", and natscontrol owns the JetStream/core-NATS
// detail behind it (the agentruntime ControlSubject grammar has its home there).
type ControlPublisher interface {
	// PublishControl publishes message to agent.<message.AgentID>.control. A transport fault is a
	// typed error the pipeline maps to a status (errors.Kind → HTTP status).
	PublishControl(ctx context.Context, message agentruntime.ControlMessage) error
}

// Config is the immutable gateway input (the configuration pattern). It reads NO env, NO clock, NO
// secret value — the JWT secret reaches the spine as an already-built edenhttp.TokenVerifier on
// Deps. (Config is the idiomatic Go type name HNS-1 rule 11 exempts.)
type Config struct {
	// EventsStream is the JetStream stream the SSE bridge binds (agent.*.events); empty == the
	// agentruntime default. Surfaced so a deployment that names its stream differently can override.
	EventsStream string
}

// Deps is the injected hexagon. New constructs no ports. (Deps is the idiomatic Go type name.)
type Deps struct {
	// Spine is the edenhttp HTTP spine: the dev-JWT Middleware + the SSE heartbeat cadence. REQUIRED.
	Spine *edenhttp.Spine
	// Bridge is the JetStream→SSE bridge serving the events route. REQUIRED.
	Bridge *natssse.Bridge
	// Control publishes a control verb to the agent's control subject. REQUIRED.
	Control ControlPublisher
	// Logger is the redaction-safe structured-log seam; optional (a nil Logger is a no-op).
	Logger edenhttp.Logger
}

// Gateway is the concrete http.Handler builder New returns (return-concrete). It holds the injected
// ports + the resolved configuration. Its zero value is unusable; construct via New. Safe for
// concurrent use (it holds immutable configuration + concurrency-safe ports).
type Gateway struct {
	configuration Config
	dependencies  Deps
	mux           *http.ServeMux
}

// New is the pure constructor spine (10 §9): no I/O, no clock read, no env read, no listen, no
// goroutine. It validates the injected ports and returns the concrete *Gateway with its routes
// wired behind the edenhttp identity Middleware. A missing dependency is a wrapped ConfigError
// (errors.AsType, errors.KindInvalid).
//
//nolint:gocritic // contract: Config is the frozen, copyable gateway input (the configuration pattern); New takes it by value.
func New(configuration Config, dependencies Deps) (*Gateway, error) {
	if dependencies.Spine == nil {
		return nil, errors.Wrap(errors.KindInvalid, "stateless: New",
			edenhttp.ConfigError{Field: "Spine", Message: "an edenhttp.Spine is required (the dev-JWT auth + SSE cadence)"})
	}
	if dependencies.Bridge == nil {
		return nil, errors.Wrap(errors.KindInvalid, "stateless: New",
			edenhttp.ConfigError{Field: "Bridge", Message: "a natssse.Bridge is required (the JetStream→SSE events path)"})
	}
	if dependencies.Control == nil {
		return nil, errors.Wrap(errors.KindInvalid, "stateless: New",
			edenhttp.ConfigError{Field: "Control", Message: "a ControlPublisher is required (the agent.<id>.control path)"})
	}
	gateway := &Gateway{configuration: configuration, dependencies: dependencies}
	gateway.mux = gateway.routes()
	return gateway, nil
}

// Handler returns the gateway's http.Handler (the wired ServeMux behind the identity Middleware).
// The B7 chat UI consumes exactly this surface. Safe to mount under a prefix by the composition root.
//
//nolint:ireturn // returns the std http.Handler port the consumer mounts (the production surface).
func (g *Gateway) Handler() http.Handler { return g.mux }

// logError emits a redaction-safe error line when a Logger is wired (no-op otherwise).
func (g *Gateway) logError(message string, fields ...any) {
	if g.dependencies.Logger != nil {
		g.dependencies.Logger.Error(message, fields...)
	}
}

// logInfo emits a redaction-safe info line when a Logger is wired (no-op otherwise).
func (g *Gateway) logInfo(message string, fields ...any) {
	if g.dependencies.Logger != nil {
		g.dependencies.Logger.Info(message, fields...)
	}
}
