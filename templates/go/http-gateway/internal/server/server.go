// Package server is the http-gateway's assembled HTTP surface: the pure constructor that builds the
// edenhttp spine (the dev-JWT identity gate) and mounts the health probes + the v1 routes behind its
// authentication Middleware. The composition root (cmd/gateway) wires this; the package owns no I/O
// — New is pure (10 §4), so the server is fakeable and the composition root is the only place wiring
// is chosen.
package server

import (
	"context"
	"net/http"
	"time"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/secrets"

	apiv1 "github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/server/healthcheck"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/server/identity"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/server/middleware"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/server/runtime"
)

// jwtSecretResolveTimeout bounds the one secret resolution New performs at startup.
const jwtSecretResolveTimeout = 10 * time.Second

// Config is the immutable, fully-resolved server input (the configuration pattern). It reads NO env
// and NO clock of its own — every value arrives from the composition root. (Config is the idiomatic
// Go type name HNS-1 rule 11 exempts; a package named `config` would not be.)
type Config struct {
	// JWTSecretRef is the secrets Reference the JWT signing key resolves from at startup.
	JWTSecretRef secrets.Reference
	// HeartbeatInterval is the SSE keepalive cadence the edenhttp spine schedules on (0 → default).
	HeartbeatInterval time.Duration
	// Substrate is the detected deployment substrate, recorded on the server for telemetry/branching.
	Substrate runtime.Substrate
	// RateLimit is the per-client request budget the outer middleware enforces. The zero value (Limit
	// 0) disables limiting, so a server is unlimited unless the composition root opts in.
	RateLimit middleware.RateLimitConfig
}

// Deps is the injected hexagon: the narrow ports the server depends on. New consumes ports; it
// constructs none. (Deps is the idiomatic Go type name HNS-1 rule 11 exempts.)
type Deps struct {
	// Secrets is the redaction port the server resolves the JWT signing key through. REQUIRED.
	Secrets secrets.Provider
	// Observability is the structured-Event stream the server logs on. REQUIRED.
	Observability observability.Provider
	// ReadinessProbes are the dependency probes the readiness handler checks (the Postgres pool, a
	// secrets backend). Empty → the probe-only/no-DB boot: readiness answers 200 with nothing to be
	// unready for. The composition root supplies the real probes once persistence is wired.
	ReadinessProbes []healthcheck.Probe
	// Resources is the typed CRUD surface the persisted `resource` routes call (the consumer-defined
	// resource.Persistence port; *persistence.Resources satisfies it). Nil → the resource routes are
	// not mounted (the no-DB boot serves only the no-persistence `ping` reference).
	Resources resource.Persistence
}

// Server is the concrete value New returns (return-concrete): it owns the assembled http.Handler the
// composition root serves. Its zero value is unusable; construct via New. Safe for concurrent use
// (it holds an immutable handler tree).
type Server struct {
	handler http.Handler
}

// New is the pure constructor spine (10 §9): it validates Deps, resolves the JWT signing secret once
// (the ONE blocking step, bounded), builds the edenhttp dev-JWT verifier + spine, and mounts the
// health probes (public) + the v1 routes (behind the spine's authentication Middleware). It returns
// a wrapped error on a missing dependency or an unresolvable secret.
func New(configuration Config, dependencies Deps) (*Server, error) {
	if dependencies.Secrets == nil {
		return nil, errors.New(errors.KindInvalid, "server: New requires Deps.Secrets")
	}
	if dependencies.Observability == nil {
		return nil, errors.New(errors.KindInvalid, "server: New requires Deps.Observability")
	}

	resolveCtx, cancel := context.WithTimeout(context.Background(), jwtSecretResolveTimeout)
	defer cancel()
	verifier, err := identity.NewVerifier(resolveCtx, dependencies.Secrets, configuration.JWTSecretRef)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "server: build identity verifier", err)
	}

	spine, err := edenhttp.New(
		edenhttp.Config{HeartbeatInterval: configuration.HeartbeatInterval},
		edenhttp.Deps{
			Verifier: verifier,
			Clock:    systemClock{},
			Logger:   middleware.ObservabilityLogger{Provider: dependencies.Observability},
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "server: build edenhttp spine", err)
	}

	handler := route(configuration, spine, dependencies)
	return &Server{handler: handler}, nil
}

// Handler returns the assembled http.Handler the composition root serves. It is the server's only
// exported surface besides New (accept-interfaces, return-concrete — the consumer gets a usable
// http.Handler, not another port).
func (s *Server) Handler() http.Handler { return s.handler }

// route builds the handler tree, layered outside-in:
//
//	requestid+span  ─┐  (every request: correlation id + an observability Scope)
//	rate limit       ├─ the server-wide outer middleware, wrapping BOTH the probes and /v1.
//	mux             ─┘
//	  ├─ GET /healthz/live   — PUBLIC liveness (the kubelet probes pre-identity).
//	  ├─ GET /healthz/ready  — PUBLIC readiness (probes the injected dependencies → 503 until up).
//	  └─ /v1/  → spine.Middleware → apiMux  — the authenticated API: the spine authenticates FIRST,
//	            then each route's declarative Required Grant authorizes. The gateway is behind auth
//	            even locally (ADR-0022 #3); authorization is the Required field, not a middleware.
//
// The probes sit OUTSIDE the auth spine (a kubelet has no token) but INSIDE the request-id/rate-limit
// outer middleware (so every request, probe or API, is correlated and budgeted).
func route(configuration Config, spine *edenhttp.Spine, dependencies Deps) http.Handler {
	mux := http.NewServeMux()

	// Public liveness/readiness probes (no auth — the kubelet probes pre-identity). Readiness checks
	// the injected dependency probes and returns 503 naming any that are down.
	mux.Handle("GET /healthz/live", healthcheck.Live())
	mux.Handle("GET /healthz/ready", healthcheck.Ready(dependencies.ReadinessProbes...))

	// The authenticated v1 API. v1.Mount registers every resource's 5-file routes onto a sub-mux,
	// each carrying its declarative Required Grant; the whole tree sits behind the spine Middleware.
	apiMux := http.NewServeMux()
	apiv1.Mount(apiMux, apiv1.Deps{
		Observability: dependencies.Observability,
		Resources:     dependencies.Resources,
	})
	mux.Handle("/v1/", http.StripPrefix("/v1", spine.Middleware(apiMux)))

	// Outer, server-wide middleware (applied to the WHOLE mux): request-id + OTel span first so a
	// rejected (rate-limited) request is still correlated, then the per-client rate limit.
	requestID := middleware.RequestID(dependencies.Observability)
	rateLimit := middleware.RateLimit(configuration.RateLimit)
	return requestID(rateLimit(mux))
}

// systemClock is the server's edenhttp.Clock. New stays pure by injecting it rather than reading the
// wall clock inside the libraries; the app is the one place a real clock is read (10 §4).
type systemClock struct{}

// Now returns the current wall-clock instant.
func (systemClock) Now() time.Time { return time.Now() }
