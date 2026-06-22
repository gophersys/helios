// Package gateway is the agentsession gateway — the HTTP/SSE backend-for-frontend that
// turns the orchestrator.Manager record plane and the agentsession.Factory live plane
// into the real-time chat surface the SvelteKit browser consumes (REQ-0020..0024).
//
// It owns NO agent logic and NO harness: it is a thin, instrumented translation seam.
// Lifecycle records (spawn / list / get / stop / resume — the REQ-0022 project-scoped
// session list) flow through the injected orchestrator.Manager; the live event stream,
// the from-seq replay, and the prompt/steer/abort control channel flow through a live
// agentsession.Session the gateway opens via the injected agentsession.Factory and holds
// in an in-memory registry keyed by AgentID. This split mirrors the architecture ruling
// that the chat surface tails Events off the agentsession session, NOT off orchestrator
// (orchestrator never proxies the stream — orchestrator.md §"does NOT own").
//
// The credential is resolved server-side INSIDE agentsession.Open (it rides an opaque
// secrets.Reference on the Spec); it never enters an HTTP request/response body, an SSE
// payload, a header echoed to the client, a log line, or the transcript (REQ-0021).
//
// Constructor spine: New(configuration, dependencies) is PURE — it builds the handler and
// validates the injected ports; it opens no listener and spawns no goroutine. Serve does
// the listen. Handler returns the http.Handler so tests drive it over net/http/httptest.
//
// Concurrency: the *Gateway is safe for concurrent use. Each SSE request is an independent
// agentsession.Stream (per-session fan-out + per-cursor replay); control verbs and reads
// are serialized internally by the underlying session. The registry is mutex-guarded.
package gateway

import (
	"context"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/secrets"
)

// Clock is the minimal injected time port (mirrors agentsession.Clock / observability
// .Clock): the only wall-clock source, so New stays pure and tests stay deterministic.
type Clock interface{ Now() time.Time }

// ProjectCreator is the DB-first create-saga's drive seam: kick the ordered, resumable provisioning
// saga for one persisted project (repo -> template seed -> supervisor -> ready). It is a ONE-method
// consumer-defined port (the projectcreate.Saga binds it) the create handler calls AFTER writing the
// DRAFT row, so the row is reload-safe before any provisioning starts. Run is long-lived (it waits on
// the supervisor health heartbeat); the gateway runs it on a detached, tracked goroutine and the
// handler returns the project row immediately so the dashboard shows loading. It is OPTIONAL on Deps —
// when nil the create handler persists the project WITHOUT provisioning (the pre-saga behavior: a plain
// draft/building row), so a composition that does not run the saga is unchanged.
type ProjectCreator interface {
	// Run drives the project named by projectID through the creation saga, resumably and idempotently.
	// It returns a wrapped error on a step fault (the saga has already parked the project at FAILED with
	// the reason); the gateway logs it (the caller already returned the row to the client).
	Run(ctx context.Context, projectID string) error
}

// Logger is the narrow, redaction-safe structured-log seam the gateway emits on. It is a
// consumer-defined port (the shape of the need, not a mirror of slog): the composition
// root adapts an observability.Provider / *slog.Logger onto it. A message or field is
// NEVER a secret — the credential seam is enforced upstream by secrets.Secret being
// un-printable, and the gateway never handles a resolved value.
type Logger interface {
	Info(message string, fields ...any)
	Error(message string, fields ...any)
}

// Config is the immutable, fully-resolved gateway input (the configuration pattern:
// parsed at the edge, frozen). It reads NO env, NO clock, NO secret value — only the
// loggable secrets.Reference that names the setup-token, plus the routing/grants the
// gateway folds into each agentsession.Spec when it opens a live session.
type Config struct {
	// Credential is the OPAQUE, loggable reference to the membership setup-token. It is
	// resolved server-side inside agentsession.Open (never here, never by the gateway);
	// the value reaches only the harness process and never the browser (REQ-0021).
	Credential secrets.Reference

	// Routing selects the harness+model the opened session binds (per-phase, as data —
	// REQ-0021). It is the agentsession.RouteKey the injected Factory's routing table
	// resolves.
	Routing agentsession.RouteKey

	// Workspace is the already-provisioned workspace directory the harness runs in (S2
	// owns its lifecycle; the gateway only names it). For the chat surface this is the
	// project workspace the orchestrator provisioned.
	Workspace string

	// Grants is the standing tool allowlist AS DATA folded into the opened session's
	// Spec.Grants (07 §3). Never a secret.
	Grants []agentsession.ToolGrant

	// MaxPageSize caps the session-list page size (REQ-0022). 0 == DefaultPageSize.
	MaxPageSize int

	// WriteTimeout bounds a non-streaming response write; the SSE route is exempt (it is
	// long-lived). 0 == DefaultWriteTimeout.
	WriteTimeout time.Duration

	// FlushInterval is the SSE heartbeat cadence: a comment frame keeps proxies from
	// idling the long-lived stream and bounds delivery latency (REQ-0020 ~1s). 0 ==
	// DefaultFlushInterval.
	FlushInterval time.Duration
}

// DefaultPageSize is the session-list page size when Config.MaxPageSize is unset.
const DefaultPageSize = 50

// DefaultWriteTimeout bounds a non-streaming response write when Config.WriteTimeout is
// unset.
const DefaultWriteTimeout = 15 * time.Second

// DefaultFlushInterval is the SSE heartbeat cadence when Config.FlushInterval is unset.
const DefaultFlushInterval = 20 * time.Second

// Deps is the injected hexagon. New constructs no ports; everything the gateway touches
// arrives here or on Config.
type Deps struct {
	// Manager is the record plane: Spawn/Get/List/Stop/Resume — the REQ-0022 session list
	// and the REQ-0020 lifecycle controls. The gateway accepts the interface (the
	// orchestratortest fake or the real *orchestrator.Pool satisfy it).
	Manager orchestrator.Manager

	// Sessions is the live plane: the agentsession.Factory the gateway calls Open on to
	// obtain a live Session it tails (Events) and controls (Control). The
	// agentsessiontest scripted Adapter wired into a real *agentsession.Pool satisfies it.
	Sessions agentsession.Factory

	// Clock stamps response/log times; keeps New pure and the fake deterministic.
	Clock Clock

	// Transcript is the durable replay log read for the post-mortem transcript route
	// (REQ-0020 persisted Run, queryable AFTER the session ends — REQ-0023 reconstruct
	// from persisted events). It is the SAME Transcript the injected Factory appends to,
	// so a read after Close still serves the full ordered Run. Optional: when nil, the
	// transcript route serves a live session's replay tail only (no post-Close read).
	Transcript agentsession.Transcript

	// Logger is the redaction-safe structured-log seam; optional (a nil logger is a no-op).
	Logger Logger

	// Proposer is the create-flow wizard's AI-propose seam: it turns the user's initial prompt
	// into a ProductConfig (POST /product/propose). It is OPTIONAL — when nil the propose route is
	// a 503 (a composition that does not offer the wizard). The live root binds it to ONE real
	// claude/omp turn; the dev root binds it to a deterministic prompt-derived fake.
	Proposer Proposer

	// Projects is the persisted-Project seam the dashboard surface (GET/POST /projects) reads and
	// writes. It is OPTIONAL — when nil the /projects routes are a 503 (a composition that does not
	// offer the dashboard). The live root binds it to a real Postgres adapter; the dev root binds it
	// to an in-memory fake — the same real-vs-fake mirror the Proposer uses.
	Projects ProjectStore

	// CreateSteps is the DB-first create-saga's ledger seam: the per-step idempotency + replay record
	// the saga advances (ProjectStore is the project's durable state; this is HOW it got there). It is
	// OPTIONAL — nil in a composition that does not run the saga. Real Postgres in liveserve, in-memory
	// fake in devserve.
	CreateSteps CreateStepStore

	// Audit is the append-only audit-trail seam: every action taken on a project, newest-first with
	// cursor pagination. OPTIONAL — nil disables the trail (no action is recorded). Real Postgres in
	// liveserve, in-memory fake in devserve.
	Audit AuditStore

	// AgentConfigs is the per-agent-type user-configuration seam the Settings → Agents surface
	// (GET/PUT /agent-configs) reads and writes. OPTIONAL — when nil those routes are a 503. Real
	// Postgres adapter in liveserve, in-memory fake in devserve.
	AgentConfigs AgentConfigStore

	// ProjectCreator is the DB-first create-saga the POST /projects handler kicks (async) after writing
	// the DRAFT row. OPTIONAL — when nil, POST /projects persists the project WITHOUT provisioning (the
	// pre-saga behavior). The live root binds it to a projectcreate.Saga over real forge/git/orchestrator
	// adapters; the dev root may bind a deterministic fake or leave it nil.
	ProjectCreator ProjectCreator
}

// Gateway is the concrete http.Handler builder New returns (return-concrete). It holds
// the injected ports, the resolved configuration, and the live-session registry. Its zero
// value is unusable.
type Gateway struct {
	configuration Config
	dependencies  Deps
	registry      *registry
	mux           *http.ServeMux

	// sagas tracks the detached create-saga goroutines the create handler kicks so graceful shutdown
	// (Close/Serve) drains them — no provisioning goroutine outlives the gateway.
	sagas sync.WaitGroup
}

// New is the pure constructor spine: no I/O, no clock read, no env read, no listen, no
// goroutine. It validates the injected ports and Config and returns the concrete
// *Gateway with its routes wired. The first session Open happens only at a create
// request. It returns a wrapped ConfigError (errors.AsType, errors.KindInvalid) on a
// missing dependency or an invalid configuration.
//
//nolint:gocritic // contract: Config is the frozen, copyable gateway input (the configuration pattern); New takes it by value.
func New(configuration Config, dependencies Deps) (*Gateway, error) {
	if dependencies.Manager == nil {
		return nil, errors.Wrap(errors.KindInvalid, "gateway: New",
			ConfigError{Field: "Manager", Message: "an orchestrator.Manager is required (the record plane)"})
	}
	if dependencies.Sessions == nil {
		return nil, errors.Wrap(errors.KindInvalid, "gateway: New",
			ConfigError{Field: "Sessions", Message: "an agentsession.Factory is required (the live plane)"})
	}
	if dependencies.Clock == nil {
		return nil, errors.Wrap(errors.KindInvalid, "gateway: New",
			ConfigError{Field: "Clock", Message: "an injected Clock is required so New stays pure"})
	}
	if configuration.Credential.IsZero() {
		return nil, errors.Wrap(errors.KindInvalid, "gateway: New",
			ConfigError{Field: "Credential", Message: "a secrets.Reference for the setup-token is required (resolved server-side at Open)"})
	}
	if configuration.MaxPageSize <= 0 {
		configuration.MaxPageSize = DefaultPageSize
	}
	if configuration.WriteTimeout <= 0 {
		configuration.WriteTimeout = DefaultWriteTimeout
	}
	if configuration.FlushInterval <= 0 {
		configuration.FlushInterval = DefaultFlushInterval
	}

	g := &Gateway{
		configuration: configuration,
		dependencies:  dependencies,
		registry:      newRegistry(),
	}
	g.mux = g.routes()
	return g, nil
}

// Handler returns the gateway's http.Handler (the wired ServeMux). The SvelteKit UI
// consumes exactly this surface. Safe to mount under a prefix by the composition root.
//
//nolint:ireturn // returns the std http.Handler port the consumer mounts (the frozen surface).
func (g *Gateway) Handler() http.Handler { return g.mux }

// Serve listens on listener and serves the gateway until ctx is canceled, then performs a
// graceful shutdown (drain in-flight requests, then reap every live session so no harness
// goroutine leaks). It is the ONLY method that does I/O; New does none. Serve blocks until
// shutdown completes and returns a wrapped error on a serve fault.
func (g *Gateway) Serve(ctx context.Context, listener net.Listener) error {
	server := &http.Server{
		Handler:           g.mux,
		ReadHeaderTimeout: 10 * time.Second,
		BaseContext:       func(net.Listener) context.Context { return ctx },
	}

	serveErr := make(chan error, 1)
	go func() { serveErr <- server.Serve(listener) }()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx) //nolint:errcheck // shutdown best-effort; the registry reap below is the leak guarantee.
		g.registry.closeAll(shutdownCtx)
		g.sagas.Wait() // drain in-flight create-saga goroutines so none outlives the gateway.
		g.closeStores()
		return nil
	case err := <-serveErr:
		g.registry.closeAll(context.Background())
		g.sagas.Wait() // drain in-flight create-saga goroutines so none outlives the gateway.
		g.closeStores()
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return errors.Wrap(errors.KindUnavailable, "gateway: serve", err)
	}
}

// Close reaps every live session in the registry (idempotent) and releases any closable store
// resource. The composition root calls it when Serve was not used (e.g. a test that drove the
// Handler directly), so no harness goroutine outlives the gateway. Returns nil; per-session close
// faults are best-effort.
func (g *Gateway) Close(ctx context.Context) error {
	g.registry.closeAll(ctx)
	g.sagas.Wait() // drain in-flight create-saga goroutines so none outlives the gateway.
	g.closeStores()
	return nil
}

// closeStores releases any store dependency that owns a closable resource on graceful shutdown — the
// real Postgres adapters own a pgx pool; the in-memory fakes own nothing and are skipped (they do not
// satisfy the closer). A nil (unconfigured, optional) store is also skipped. This is what makes the
// adapters' "the caller owns Close" contract true: the gateway is that caller.
func (g *Gateway) closeStores() {
	type closer interface{ Close() }
	if projects, ok := g.dependencies.Projects.(closer); ok {
		projects.Close()
	}
	if agentConfigs, ok := g.dependencies.AgentConfigs.(closer); ok {
		agentConfigs.Close()
	}
	if createSteps, ok := g.dependencies.CreateSteps.(closer); ok {
		createSteps.Close()
	}
	if audit, ok := g.dependencies.Audit.(closer); ok {
		audit.Close()
	}
}

// kickSaga runs the create-saga for projectID on a detached, tracked goroutine and returns
// immediately — the create handler has already returned the project row, so the dashboard shows
// loading while the saga provisions. The goroutine runs under a context DETACHED from the request
// (context.WithoutCancel of the gateway's base context) so the long-lived saga (it waits on the
// supervisor heartbeat) is not canceled when the POST returns its 201. The WaitGroup makes the
// goroutine drainable by graceful shutdown. A saga fault is logged (the saga has already parked the
// project at FAILED); it never crashes the gateway.
func (g *Gateway) kickSaga(baseCtx context.Context, projectID string) {
	creator := g.dependencies.ProjectCreator
	if creator == nil {
		return
	}
	g.sagas.Add(1)
	go func() {
		defer g.sagas.Done()
		if err := creator.Run(context.WithoutCancel(baseCtx), projectID); err != nil {
			g.logError("gateway: create saga failed", "project", projectID, "error", err.Error(), "kind", errors.KindOf(err).String())
		}
	}()
}

// logInfo emits a redaction-safe info line when a Logger is wired (no-op otherwise).
func (g *Gateway) logInfo(message string, fields ...any) {
	if g.dependencies.Logger != nil {
		g.dependencies.Logger.Info(message, fields...)
	}
}

// logError emits a redaction-safe error line when a Logger is wired (no-op otherwise).
func (g *Gateway) logError(message string, fields ...any) {
	if g.dependencies.Logger != nil {
		g.dependencies.Logger.Error(message, fields...)
	}
}
