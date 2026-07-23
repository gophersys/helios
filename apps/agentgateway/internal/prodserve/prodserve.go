// Package prodserve is the STATELESS PRODUCTION composition root for the FULL agentsession gateway
// surface (ADR-0022 #3, the ratified split). It wires internal/gateway.Gateway — the same handler
// set the live-local liveserve mounts (propose · projects · insight · agent-configs · sessions
// list/get · workspace) — over REAL CLUSTER substrates: a Postgres-backed orchestrator record plane
// (the durable DesiredStore), the dual-mode Vault secrets provider in token-file mode (the K8s-SA
// sidecar), a real agentsession.Pool for the ONE short propose turn, and the Postgres persistence
// stores for the dashboard/Settings surfaces.
//
// It is the deliberate sibling of internal/liveserve (REAL harness + in-process record plane over
// FAKES — a documented DEV-LOCAL convenience) and internal/stateless (the NATS→SSE bridge). Unlike
// liveserve, prodserve imports NO test fakes (no orchestratortest/agentsessiontest) — it is the
// production binary, so its dependency graph is fake-free. The STATELESS split it honors:
//
//   - POST /sessions writes DESIRED state (Config.RecordOnlyCreate) and returns — the gateway spawns
//     NO harness in-process; the separately-deployed orchestrator reconciles the record into a pod.
//   - The pod's live event/control plane (/sessions/{id}/events, /control, …) is served by the
//     internal/stateless NATS→JetStream bridge, mounted AHEAD of this handler by the command's
//     combined mux. prodserve builds only the REST/record plane; it never tails a harness.
//
// Degrade-honest (ADR-0022, the "never 404" rule): a surface whose in-pod capstone is not yet wired
// (the chat-create → pod → in-process live stream — task #38 territory) returns a CLASSIFIED status
// (503 KindUnavailable / 404 KindNotFound with its Kind), never an unknown 404. When a DSN is absent
// the dashboard stores are nil (their routes 503); the create-saga (ProjectCreator) is DELIBERATELY
// nil here — project PROVISIONING is the orchestrator's job (the gateway is stateless), so POST
// /projects persists the DRAFT project row and the orchestrator reconciles it (the documented
// pre-saga draft behavior — gateway.Deps.ProjectCreator doc).
package prodserve

import (
	"context"
	"io"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/slogadapter"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/agentgateway/internal/agentconfigpersistence"
	"github.com/gophersys/eden/apps/agentgateway/internal/auditpersistence"
	"github.com/gophersys/eden/apps/agentgateway/internal/createsteppersistence"
	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/eden/apps/agentgateway/internal/projectpersistence"
)

// Logger is the narrow structured-log seam the production composition adapts the command's logger
// onto (it mirrors gateway.Logger so the cmd does not import the gateway package for the port). A
// field is NEVER a secret — the credential seam is enforced upstream by the harness/secrets contract.
type Logger interface {
	Info(message string, fields ...any)
	Error(message string, fields ...any)
}

// Config is the immutable production-composition input (the configuration pattern: read once at the
// edge by the command, frozen). Every field is resolved from the environment BEFORE New, so this
// package reads NO env and the constructor stays pure. No field is ever a secret value — the Vault
// credential rides as an opaque, loggable secrets.Reference resolved server-side point-of-use.
type Config struct {
	// Provider is the ALREADY-BUILT secrets Mediator over the dual-mode Vault backend (token-file
	// mode in production). The command builds it once (mirroring the JWT-verifier resolution) and
	// hands it here; the agentsession Pool + the forge resolve their opaque references through it.
	// Required.
	Provider secrets.Provider

	// DatabaseURL is the Postgres DSN the record plane (the orchestrator DesiredStore) AND the
	// dashboard/Settings stores run on. Required — the production gateway is durable (unlike the
	// dev-local demo, which tolerates a missing DSN). The command resolves it from a Vault reference.
	DatabaseURL string

	// CredentialReference is the opaque vault:// reference the propose session's Spec folds; it
	// resolves server-side at agentsession.Open to the harness credential VALUE. Canonical form
	// vault://<mount>/<path>#<field> (e.g. vault://eden/production#setup-token). Required for the
	// propose surface; when empty the propose route is a 503 (Proposer nil).
	CredentialReference string

	// Harness is the adapter key the propose turn binds: "claude-code" (default) or "omp".
	Harness string
	// Model is the model id the propose turn runs under; empty folds to the account default.
	Model string
	// Workspace is the directory the propose harness turn runs in (its CWD). Required.
	Workspace string

	// Logger, when non-nil, is wired onto the gateway so requests emit redaction-safe structured lines.
	Logger Logger
}

// systemClock is the production gateway.Clock / agentsession.Clock (the wall clock; the composition
// root is the one place a real clock is read — the libraries stay pure).
type systemClock struct{}

// Now returns the current wall-clock instant.
func (systemClock) Now() time.Time { return time.Now() }

// BuildProductionGateway builds the fully-wired STATELESS production gateway.Gateway over the real
// cluster substrates. It is PURE in the gateway sense — it opens no listener and spawns no reconcile
// loop — but it DOES open the durable Postgres pool + ensure the record-plane schema at the edge (the
// composition root's startup step; the stores' New is pure). It returns the concrete *gateway.Gateway
// the command's combined mux serves, and a Close the command defers to release the owned pool. A
// misconfigured seam is a wrapped, classified error naming the field (never a value).
//
//nolint:gocritic // Config is the frozen, copyable composition input (the configuration pattern, read once at the edge); the builder takes it by value to match BuildLiveGateway.
func BuildProductionGateway(configuration Config) (*gateway.Gateway, func(context.Context) error, error) {
	if err := configuration.validate(); err != nil {
		return nil, nil, err
	}
	clock := systemClock{}
	ctx := context.Background()

	// The durable record-plane pool — OWNED here (Closed via the returned teardown). It backs the
	// orchestrator DesiredStore (the stateless record plane) AND is not shared with the per-store
	// pools (each dashboard store opens its own pool from the SAME DSN; the gateway Closes them via
	// closeStores). Building the store here lets the composition run the startup EnsureSchema so a
	// first-boot pod creates the orchestrator schema before the first /sessions write.
	recordPool, err := pgxpool.New(ctx, configuration.DatabaseURL)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindUnavailable, "prodserve: open record-plane database pool", err)
	}
	desiredStore, err := postgresstore.New(postgresstore.Config{}, postgresstore.Deps{Pool: recordPool})
	if err != nil {
		recordPool.Close()
		return nil, nil, errors.Wrap(errors.KindInternal, "prodserve: build orchestrator desired store", err)
	}
	if schemaErr := desiredStore.EnsureSchema(ctx); schemaErr != nil {
		recordPool.Close()
		return nil, nil, errors.Wrap(errors.KindUnavailable, "prodserve: ensure orchestrator schema", schemaErr)
	}

	// The record plane: a real orchestrator.Pool over the Postgres DesiredStore. Spawn writes desired
	// state and returns (StatusPending) — NO reconcile loop is started here (Start is never called),
	// so this gateway never provisions a pod. The separately-deployed orchestrator owns reconcile.
	telemetry, err := buildTelemetry(clock)
	if err != nil {
		recordPool.Close()
		return nil, nil, err
	}
	manager, err := orchestrator.New(
		orchestrator.Config{DefaultMaxConcurrent: 0}, // the ceiling is the orchestrator's concern; the gateway only records intent
		orchestrator.Deps{
			Desired:   desiredStore,
			Templates: templateStore{}, // the record plane resolves the create template; an unknown template is an honest classified NotFound
			Secrets:   configuration.Provider,
			Telemetry: orchestratorTelemetry{provider: telemetry},
			Clock:     clock,
		},
	)
	if err != nil {
		recordPool.Close()
		return nil, nil, errors.Wrap(errors.KindInternal, "prodserve: build orchestrator record plane", err)
	}

	// The live plane the propose turn opens on: a real agentsession.Pool over the claude+omp adapters
	// and the Vault-backed secrets provider. It is NOT tailed for chat here (the pod live plane rides
	// the NATS bridge) — it exists so the ONE short propose turn (POST /product/propose) runs a real
	// model call. ONE in-process transcript backs BOTH the pool (agentsession.New REQUIRES a non-nil
	// Transcript — the Seq assignment lives there; nil was the v0.1.7 crash-loop) AND the gateway's
	// post-mortem transcript route, mirroring liveserve's shared-transcript wiring.
	runLog := newTranscript()
	pool, err := buildSessionPool(&configuration, runLog, clock)
	if err != nil {
		recordPool.Close()
		return nil, nil, err
	}

	// The standing grant the propose session opens under: a conservative read-only Read (07 §3) —
	// keeps the short one-shot turn safe; propose only reasons over the prompt, it writes nothing.
	grants := []agentsession.ToolGrant{{ID: "grant-read", Tool: "Read", ReadOnly: true}}

	// The dashboard + Settings + create-saga-ledger persistence: REAL Postgres adapters (the DSN is
	// required in production, so these are always present — no 503-when-absent path here). Each opens
	// its own pool from the same DSN; the gateway Closes them on graceful shutdown (closeStores).
	projectStore, agentConfigStore, createStepStore, auditStore, err := buildPersistenceStores(ctx, configuration.DatabaseURL, clock)
	if err != nil {
		recordPool.Close()
		return nil, nil, err
	}

	gw, err := gateway.New(
		gateway.Config{
			Credential:       secrets.Ref(configuration.CredentialReference),
			Routing:          proposeRouteKey(),
			Workspace:        configuration.Workspace,
			Grants:           grants,
			RecordOnlyCreate: true, // STATELESS: POST /sessions records desired state; the orchestrator reconciles the pod
		},
		gateway.Deps{
			Manager:      manager,
			Sessions:     pool,
			Transcript:   runLog, // the SAME transcript the pool appends to — the post-mortem transcript route reads it
			Clock:        clock,
			Logger:       configuration.Logger,
			Proposer:     buildProposer(pool, &configuration, grants),
			Projects:     projectStore,
			CreateSteps:  createStepStore,
			Audit:        auditStore,
			AgentConfigs: agentConfigStore,
			// ProjectCreator is DELIBERATELY nil: project PROVISIONING (repo → seed → supervisor pod) is
			// the orchestrator's job (the gateway is stateless). POST /projects persists the DRAFT row;
			// the orchestrator reconciles it (the documented pre-saga draft behavior).
			// LiveSessions is nil: the orchestrator-opened live plane is served over NATS by the stateless
			// bridge, not through an in-process seam. The insight/workspace routes that need it degrade to
			// a classified 503 (not-available-yet) rather than a raw 404 — honest, per ADR-0022.
		},
	)
	if err != nil {
		recordPool.Close()
		return nil, nil, errors.Wrap(errors.KindInternal, "prodserve: build gateway", err)
	}

	// The teardown the command defers: drain the gateway (which Closes the per-store pools it owns),
	// then release the record-plane pool this package owns.
	teardown := func(shutdownCtx context.Context) error {
		_ = gw.Close(shutdownCtx) //nolint:errcheck // best-effort store drain; the record pool close below is the leak guarantee.
		recordPool.Close()
		return nil
	}
	return gw, teardown, nil
}

// buildSessionPool builds the agentsession.Pool the propose turn opens on: the claude + omp adapters
// over the Vault-backed secrets provider and the shared in-process transcript (REQUIRED by
// agentsession.New — the Seq assignment lives there; the v0.1.7 nil crashed the pod at boot). It
// routes the propose RouteKey to the configured harness/model.
//
//nolint:ireturn // returns the agentsession.Factory port the gateway holds (the frozen surface).
func buildSessionPool(configuration *Config, runLog agentsession.Transcript, clock systemClock) (agentsession.Factory, error) {
	claudeAdapter, err := claudeadapter.New(claudeadapter.Config{})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "prodserve: build claude adapter", err)
	}
	ompAdapter, err := ompadapter.New(ompadapter.Config{})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "prodserve: build omp adapter", err)
	}
	pool, err := agentsession.New(
		agentsession.Config{
			Routing: map[agentsession.RouteKey]agentsession.Route{
				proposeRouteKey(): {Harness: configuration.Harness, Model: configuration.Model},
			},
		},
		agentsession.Deps{
			Adapters: map[string]agentsession.Adapter{
				"claude-code": claudeAdapter,
				"omp":         ompAdapter,
			},
			Secrets:    configuration.Provider,
			Transcript: runLog,
			Clock:      clock,
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "prodserve: build agentsession pool", err)
	}
	return pool, nil
}

// buildProposer wires the propose seam: ONE real harness turn (claude-code | omp) opened on the
// shared pool under the Vault-resolved credential, or nil when no credential is configured (then the
// propose route is a classified 503, not a 404). The proposer implementation lives once in this
// package (proposer.go) so prodserve imports no test-fake-laden liveserve.
//
//nolint:ireturn // returns the gateway.Proposer port the gateway holds (the frozen surface).
func buildProposer(pool agentsession.Factory, configuration *Config, grants []agentsession.ToolGrant) gateway.Proposer {
	if configuration.CredentialReference == "" {
		return nil // no credential → propose degrades to a classified 503 (a composition without the wizard)
	}
	return &harnessProposer{
		sessions: pool,
		spec: agentsession.Spec{
			Workspace:  configuration.Workspace,
			Routing:    proposeRouteKey(),
			Grants:     grants,
			Credential: secrets.Ref(configuration.CredentialReference),
		},
		logger: configuration.Logger,
	}
}

// buildTelemetry builds the observability plane the orchestrator record plane emits onto — the
// slog adapter at PlaneAgent, discarded here (the record plane's admission/limit events are
// best-effort diagnostics; the pod's own structured logs carry the operational signal).
//
//nolint:ireturn // returns the observability.Provider port the record-plane Pool emits on (the frozen surface).
func buildTelemetry(clock systemClock) (observability.Provider, error) {
	telemetry, err := observability.New(
		observability.Config{ServiceName: "agentgateway", DefaultPlane: observability.PlaneAgent},
		observability.Deps{Exporter: slogadapter.New(io.Discard), Clock: clock},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "prodserve: build observability", err)
	}
	return telemetry, nil
}

// buildPersistenceStores builds the dashboard / Settings / create-saga-ledger Postgres stores over
// the required DSN. Each opens its own pgx pool (lazy dial); the gateway releases them via closeStores
// on graceful shutdown. It returns the gateway.Deps store PORTS as concrete adapters wired onto the
// interface fields at the call site.
func buildPersistenceStores(ctx context.Context, dsn string, clock systemClock) (
	projectStore *projectpersistence.PostgresProjectStore,
	agentConfigStore *agentconfigpersistence.PostgresAgentConfigStore,
	createStepStore *createsteppersistence.PostgresCreateStepStore,
	auditStore *auditpersistence.PostgresAuditStore,
	err error,
) {
	if projectStore, err = projectpersistence.NewPostgres(ctx, dsn, projectpersistence.WithClock(clock)); err != nil {
		return nil, nil, nil, nil, errors.Wrap(errors.KindInternal, "prodserve: build project store", err)
	}
	if agentConfigStore, err = agentconfigpersistence.NewPostgres(ctx, dsn); err != nil {
		return nil, nil, nil, nil, errors.Wrap(errors.KindInternal, "prodserve: build agent-config store", err)
	}
	if createStepStore, err = createsteppersistence.NewPostgres(ctx, dsn, createsteppersistence.WithClock(clock)); err != nil {
		return nil, nil, nil, nil, errors.Wrap(errors.KindInternal, "prodserve: build create-step store", err)
	}
	if auditStore, err = auditpersistence.NewPostgres(ctx, dsn); err != nil {
		return nil, nil, nil, nil, errors.Wrap(errors.KindInternal, "prodserve: build audit store", err)
	}
	return projectStore, agentConfigStore, createStepStore, auditStore, nil
}

// proposeRouteKey is the RouteKey the propose session opens under (matched in the pool's Routing).
func proposeRouteKey() agentsession.RouteKey {
	return agentsession.RouteKey{Role: "assistant"}
}

// validate checks the required production configuration the command resolved from the environment,
// returning a wrapped KindInvalid error naming the missing field (never echoing a value).
func (c *Config) validate() error {
	switch {
	case c.Provider == nil:
		return errors.New(errors.KindInvalid, "prodserve: Provider is required (the built secrets Mediator)")
	case c.DatabaseURL == "":
		return errors.New(errors.KindInvalid, "prodserve: DatabaseURL is required (the durable record + dashboard store)")
	case c.Workspace == "":
		return errors.New(errors.KindInvalid, "prodserve: Workspace is required (the propose harness CWD)")
	case c.Harness == "":
		return errors.New(errors.KindInvalid, "prodserve: Harness is required (claude-code|omp)")
	}
	return nil
}
