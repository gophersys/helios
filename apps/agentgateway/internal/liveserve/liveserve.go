// Package liveserve is the LIVE-LOCAL composition root for the agentsession gateway: it wires
// the full internal/gateway.Gateway over a REAL agentsession.Pool driving a REAL harness CLI
// (claude-code or omp) whose credential is resolved server-side from the REAL local Vault
// (secrets/vaultadapter, ModeUserpass — ADR-0022 #1), behind the EXACT REST+SSE surface the B7
// chat UI already calls. It is the Milestone-B B8 single-process demo path (ADR-0022 #2): one
// binary, no NATS, no pods — the harness runs in-process as an os/exec subprocess, and the
// gateway tails its normalized agentsession.Event stream over SSE.
//
// It is the deliberate sibling of internal/devserve (the in-memory FAKE path) and cmd/agentgateway
// (the STATELESS NATS→SSE production path):
//
//   - devserve  — fake scripted harness + fake secrets; zero external substrate (fast UI dev).
//   - liveserve — REAL harness + REAL Vault; in-process record plane (the live-local demo). ← here
//   - cmd/agentgateway — stateless NATS→SSE bridge over real agent-runtime pods (production).
//
// The RECORD plane (Spawn/list/get/stop — admission + tenancy) is the in-process
// orchestratortest.Manager: it is a real orchestrator.Pool over in-memory fakes, so a create
// request is admitted and recorded WITHOUT a real container/pod (the demo needs no orchestrator-
// provisioned pod — agentsession runs the harness in-process). The LIVE plane the UI streams off
// is the REAL agentsession.Pool injected as Deps.Sessions; the gateway opens its own live Session
// there, folding the gateway's opaque Vault Reference into the Spec, and agentsession.Open
// resolves it server-side. The credential VALUE never reaches the browser, a log, or any record
// (REQ-0021): it crosses only into the harness child env (CLAUDE_CODE_OAUTH_TOKEN), via Secret.Use.
//
// This package imports orchestratortest exactly as devserve does — it is a documented DEV-LOCAL
// convenience entrypoint, not the production command (cmd/agentgateway imports no fakes).
package liveserve

import (
	"context"
	"io"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/forge/githubadapter"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/slogadapter"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"

	"github.com/gophersys/eden/apps/agentgateway/internal/agentconfigpersistence"
	"github.com/gophersys/eden/apps/agentgateway/internal/auditpersistence"
	"github.com/gophersys/eden/apps/agentgateway/internal/connectorcredential"
	"github.com/gophersys/eden/apps/agentgateway/internal/createsteppersistence"
	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/eden/apps/agentgateway/internal/orchestratorservice"
	"github.com/gophersys/eden/apps/agentgateway/internal/projectcreate"
	"github.com/gophersys/eden/apps/agentgateway/internal/projectpersistence"
)

// Logger is the narrow structured-log seam the live composition adapts the command's logger onto
// (it mirrors gateway.Logger so the cmd does not import the gateway package for the port). A field
// is NEVER a secret — the credential seam is enforced upstream by the harness/secrets contract.
type Logger interface {
	Info(message string, fields ...any)
	Error(message string, fields ...any)
}

// Config is the immutable live-composition input (the configuration pattern: read once at the
// edge, frozen). Every field is resolved by the command from the environment BEFORE New, so this
// package reads NO env and the constructor stays pure. No field is ever a secret value — the Vault
// credential rides as an opaque, loggable secrets.Reference resolved server-side at Open.
type Config struct {
	// VaultAddress is the Vault API address (e.g. http://127.0.0.1:8200). Required.
	VaultAddress string
	// VaultUsername / VaultPassword are the userpass bootstrap credential (ModeUserpass, the local
	// path). VaultPassword is kept off every loggable surface; it lives only in this struct and the
	// adapter's login call body. Required.
	VaultUsername string
	VaultPassword string
	// CredentialReference is the opaque vault:// Reference the gateway folds into every opened
	// session's Spec. Resolved server-side at agentsession.Open to the harness credential VALUE.
	// Canonical form: vault://<mount>/<path>#<key> (e.g. vault://eden/development#setup-token).
	CredentialReference string
	// Harness is the adapter key the live route binds: "claude-code" (default) or "omp".
	Harness string
	// Model is the model id reported on the route (surfaced in usage/ledger projections); empty is
	// fine for claude (it uses its account default).
	Model string
	// Workspace is the directory the harness CLI runs in (its CWD). Required; the command provisions
	// a real local directory (the demo needs no orchestrator-provisioned pod workspace).
	Workspace string
	// DatabaseDSN is the Postgres connection string the dashboard's persisted-Project store runs on
	// (e.g. postgres://eden:eden@host:5432/eden?sslmode=disable). OPTIONAL: when empty the /projects
	// routes are a 503 (a composition without a database). The pool is lazy — a missing database does
	// not fail construction; the schema is ensured on the first /projects request.
	DatabaseDSN string

	// ── The create-saga seam (OPTIONAL): when DatabaseDSN AND all of the fields below are set, the
	// live gateway wires the DB-first project-creation saga (real GitHub repo → template seed → a REAL
	// Claude supervisor on real docker) as gateway.Deps.ProjectCreator, and POST /projects provisions a
	// project end-to-end. When any is empty the saga is NOT wired (the handler keeps the pre-saga draft
	// behavior). The supervisor's harness credential is the SAME claude token as CredentialReference. ──

	// RepositoryOwner is the GitHub account new project repositories are created under (e.g. MateoSegura).
	RepositoryOwner string
	// ForgeCredentialReference is the opaque vault:// reference to the GitHub PAT (the gh-token) the
	// forge + git push authenticate with — DISTINCT from CredentialReference (the claude token).
	ForgeCredentialReference string
	// TemplateRepositoryURL is the clone URL of the seed template the saga flattens into each new repo
	// (e.g. https://github.com/gophersys/template.git).
	TemplateRepositoryURL string
	// OrganizationID is the supervisor tenancy org key (mapped to a stable UUID by the saga).
	OrganizationID string
	// SeedCheckoutRoot is the ABSOLUTE parent directory the seeder clones each project's template into
	// (the command ensures it exists). Required when the saga is wired.
	SeedCheckoutRoot string
	// SupervisorWorkspaceRoot is the ABSOLUTE parent directory each project's PERSISTENT supervisor
	// working directory (clone + the overlaid `.claude` manual) is materialized under. Required when the
	// saga is wired (the command ensures it exists).
	SupervisorWorkspaceRoot string
	// SupervisorManualSourceDir is the ABSOLUTE path to the supervisor `.claude` operating-manual tree
	// the materializer overlays into each workspace (libs/plugins/supervisor/template/.claude). Required
	// when the saga is wired.
	SupervisorManualSourceDir string

	// ── The connector-credential seam (OPTIONAL, ADR-0029 §4 / A3): when ConnectorsDatabaseDSN is set,
	// the gateway binds the "eden" scheme (platformconnectoradapter) so a session can CONSUME a
	// user-uploaded connector, and derives the supervisor's harness credential from the project's owning
	// org (a `claude-api` connector → eden://connector/<id>, else the platform CredentialReference). When
	// empty, every session gets CredentialReference exactly as today — the fallback is never regressed. ──

	// ConnectorsDatabaseDSN is the resolved DSN of the platformgateway connectors database (distinct from
	// DatabaseDSN, the record plane). Empty ⇒ no connector resolution (the platform fallback for every
	// session). The value is resolved point-of-use at the edge, never logged.
	ConnectorsDatabaseDSN string
	// ConnectorsKEKReference is the opaque vault:// reference the envelope KEK resolves from (the SAME
	// reference the platformgateway connectors domain seals under, e.g. vault://eden/production#connectors-kek).
	// Required when ConnectorsDatabaseDSN is set.
	ConnectorsKEKReference string
	// ConnectorsKEKVersion is the KEK generation stamp (>= 1; defaults to 1 when unset).
	ConnectorsKEKVersion int
	// ConnectorsOrganizationID is the platformgateway organization UUID the supervisor's credential is
	// derived against (the org that owns the connectors). Empty ⇒ the platform fallback (no org to
	// resolve a connector for). A non-UUID value degrades to the fallback (never a hard failure).
	ConnectorsOrganizationID string

	// Logger, when non-nil, is wired onto the gateway so live requests emit structured lines.
	Logger Logger
}

// systemClock is the production gateway.Clock / agentsession.Clock (the wall clock; the
// composition root is the one place a real clock is read — the libraries stay pure).
type systemClock struct{}

// Now returns the current wall-clock instant.
func (systemClock) Now() time.Time { return time.Now() }

// BuildLiveGateway builds a fully wired, runnable gateway.Gateway over the REAL harness + REAL
// Vault. It is PURE in the gateway sense — it opens no listener and spawns no goroutine (the
// caller's Serve does the I/O) — but it does construct the real ports (the Vault adapter dials
// nothing until the first Open; the harness spawns nothing until the first session). It returns
// the concrete *gateway.Gateway the caller serves; the SECOND return is the create-saga's
// orchestrator (nil unless the saga is wired) whose reconcile LOOP the caller must Start/Close
// (the one goroutine this composition needs — owned by the command, not this pure builder), and a
// wrapped error if any seam is misconfigured.
//
//nolint:gocritic // Config is the frozen, copyable composition input (the configuration pattern, read once at the edge); the builder takes it by value to match BuildDevGateway.
func BuildLiveGateway(configuration Config) (*gateway.Gateway, *orchestratorservice.Service, error) {
	if err := configuration.validate(); err != nil {
		return nil, nil, err
	}
	clock := systemClock{}

	// The credential plane: the secrets Mediator over the REAL Vault backend (userpass, "vault" scheme)
	// AND — when a connectors DSN is configured — the platformconnectoradapter ("eden" scheme, ADR-0029
	// §4). agentsession.Open resolves the opaque Reference through this, server-side, into the harness
	// child env — the value never reaches this package's surface. The Deriver picks the supervisor's
	// credential from the project's owning org (a claude-api connector → eden://connector/<id>, else the
	// platform CredentialReference); connectorClose releases the owned connectors pool.
	provider, connectorDeriver, connectorClose, err := buildSecretsAndConnectors(&configuration)
	if err != nil {
		return nil, nil, err
	}
	// The connectors pool is process-lifetime (the gateway/saga resolve through it for the process's
	// life); a runnable-lifetime resource has no teardown seam in this builder, so it rides the process.
	// A degraded (no-DSN) seam's Close is a no-op. Referenced here so the linter sees the seam is owned.
	_ = connectorClose

	// The durable Run log: ONE in-process Transcript injected into BOTH the Pool (where the harness
	// stream is appended + the Seq assigned) AND the gateway (the post-mortem transcript route), so a
	// read after the live session is reaped still serves the full ordered Run (REQ-0020).
	runLog := newTranscript()

	// The live plane: a REAL agentsession.Pool whose Adapter is the REAL harness CLI (claude-code |
	// omp), the Vault-backed secrets provider, the shared in-memory Transcript, and the system clock.
	claudeAdapter, err := claudeadapter.New(claudeadapter.Config{})
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build claude adapter", err)
	}
	ompAdapter, err := ompadapter.New(ompadapter.Config{})
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build omp adapter", err)
	}
	pool, err := agentsession.New(
		agentsession.Config{
			// ONE pool, both routes: the chat assistant AND the supervisor controller. The
			// orchestratorservice opens the supervisor session through this SAME pool (Deps.Sessions),
			// so the supervisor is reachable on the gateway's registry like any other session.
			Routing: map[agentsession.RouteKey]agentsession.Route{
				liveRouteKey():                           {Harness: configuration.Harness, Model: configuration.Model},
				orchestratorservice.SupervisorRouteKey(): {Harness: "claude-code", Model: "opus"},
			},
		},
		agentsession.Deps{
			Adapters: map[string]agentsession.Adapter{
				"claude-code": claudeAdapter,
				"omp":         ompAdapter,
			},
			Secrets:    provider,
			Transcript: runLog,
			Clock:      clock,
		},
	)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build agentsession pool", err)
	}

	// The record plane: a real orchestrator.Pool over in-memory fakes, seeded with the default
	// template so a create request's Spawn is admitted and recorded (no real pod is provisioned —
	// the live harness runs in-process via the Pool above).
	manager := orchestratortest.New(orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()))

	// The standing grant the live gateway opens both the chat session AND the propose session
	// under: a conservative read-only Read (the demo agent may Read but not Write/Bash without an
	// explicit per-call permission, 07 §3) — keeps an unattended live agent safe.
	grants := []agentsession.ToolGrant{{ID: "grant-read", Tool: "Read", ReadOnly: true}}

	// The dashboard + Settings + create-saga persistence: REAL Postgres adapters when a DSN is
	// configured (the pools are lazy — no dial here), nil otherwise (those routes/saga then 503/absent).
	projectStore, agentConfigStore, createStepStore, auditStore, err := buildPersistenceStores(configuration.DatabaseDSN, clock)
	if err != nil {
		return nil, nil, err
	}

	// ── The create-saga (OPTIONAL): when the database AND the forge/template fields are configured,
	// wire the DB-first project-creation saga as the gateway's ProjectCreator. Its Supervisor is a REAL
	// orchestratorservice.Service (real docker workspace + a REAL Claude supervisor session); the caller
	// Starts/Closes its reconcile loop (the returned *Service). The CHAT record plane stays the
	// in-process fake above — only project PROVISIONING goes through the real orchestrator. ──
	var (
		projectCreator    gateway.ProjectCreator
		supervisorService *orchestratorservice.Service
		liveSessions      gateway.LiveSessions // nil interface unless the saga's orchestrator is built (avoid the typed-nil trap)
	)
	if configuration.createSagaConfigured() {
		saga, service, sagaErr := buildCreateSaga(&configuration, provider, connectorDeriver, pool, projectStore, createStepStore, clock)
		if sagaErr != nil {
			return nil, nil, sagaErr
		}
		projectCreator = saga
		supervisorService = service
		liveSessions = service // the same orchestrator the saga spawns the supervisor through resolves its live session
	}

	gw, err := gateway.New(
		gateway.Config{
			Credential:          secrets.Ref(configuration.CredentialReference),
			Routing:             liveRouteKey(),
			Workspace:           configuration.Workspace,
			Grants:              grants,
			OnPermission:        alwaysAllowPermission,
			EditorURLBase:       os.Getenv("EDEN_EDITOR_URL_BASE"),
			EditorSSHHost:       os.Getenv("EDEN_EDITOR_SSH_HOST"),
			EditorIngressDomain: os.Getenv("EDEN_EDITOR_INGRESS_DOMAIN"),
		},
		gateway.Deps{
			Manager:    manager,
			Sessions:   pool,
			Transcript: runLog,
			Clock:      clock,
			Logger:     configuration.Logger,
			// The create-flow wizard's propose seam: ONE real harness turn (claude-code | omp)
			// instructed to return ONLY ProductConfig JSON, opened on the SAME live Pool the chat
			// streams off (the harness under the Vault-resolved credential). A parse failure falls
			// back to the gateway's sane defaults; only an Open/stream fault surfaces as an error.
			Proposer: &harnessProposer{
				sessions: pool,
				spec: agentsession.Spec{
					Workspace:  configuration.Workspace,
					Routing:    liveRouteKey(),
					Grants:     grants,
					Credential: secrets.Ref(configuration.CredentialReference),
				},
				logger: configuration.Logger,
			},
			// The dashboard's persisted-Project seam: the real Postgres store (or nil → /projects 503).
			Projects: projectStore,
			// The create-saga ledger + append-only audit trail seams: the real Postgres stores (or nil
			// when no DSN — the saga then runs without a durable ledger/trail).
			CreateSteps: createStepStore,
			Audit:       auditStore,
			// The Settings → Agents config seam: the real Postgres store (or nil → /agent-configs 503).
			AgentConfigs: agentConfigStore,
			// The DB-first create-saga the POST /projects handler kicks async (or nil → the pre-saga
			// draft behavior when the saga seam is not configured).
			ProjectCreator: projectCreator,
			// The orchestrator's live plane: resolves the supervisor's open session so the gateway's
			// /sessions/{id} routes (control/events/resolve) reach the controller (nil when no saga).
			LiveSessions: liveSessions,
		},
	)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build gateway", err)
	}
	return gw, supervisorService, nil
}

// buildCreateSaga constructs the DB-first project-creation saga and the REAL orchestratorservice.Service
// its supervisor spawns through. The orchestrator runs the supervisor on real docker with the REAL
// claude binary pinned to the Opus alias (--model opus, the standing Opus directive — never the
// account default, which can drift to Sonnet); the saga's two credential planes are the gh-token
// (ForgeCredentialReference) and the claude token (CredentialReference). The caller Starts/Closes the
// returned Service's reconcile loop. The pool is process-lifetime (released on exit; the Service.Close
// stops the loop first).
// deriveSupervisorCredential picks the supervisor session's harness credential (ADR-0029 §4 / A3): the
// project owning-org's `claude-api` connector (eden://connector/<id>) when one exists, else the platform
// CredentialReference. It maps ConnectorsOrganizationID (the platformgateway org UUID) to the derivation;
// an empty or unparsable org id, or the absence of a connector, all yield the fallback — the fallback is
// never regressed. The deriver's own nil-pool path already degrades to the fallback, so this only adds
// the org-id parse guard.
func deriveSupervisorCredential(ctx context.Context, deriver *connectorcredential.Deriver, configuration *Config) secrets.Reference {
	fallback := secrets.Ref(configuration.CredentialReference)
	if deriver == nil || configuration.ConnectorsOrganizationID == "" {
		return fallback
	}
	organizationID, err := uuid.Parse(configuration.ConnectorsOrganizationID)
	if err != nil {
		// A non-UUID org id names no platformgateway org — degrade to the platform credential.
		return fallback
	}
	return deriver.DeriveClaudeCredential(ctx, organizationID)
}

func buildCreateSaga(
	configuration *Config, provider secrets.Provider, connectorDeriver *connectorcredential.Deriver,
	sessions agentsession.Factory,
	projectStore gateway.ProjectStore, stepStore gateway.CreateStepStore, clock systemClock,
) (*projectcreate.Saga, *orchestratorservice.Service, error) {
	ctx := context.Background()

	// The orchestrator's desired-state pool + schema (the composition root's startup step; New is pure).
	pool, err := pgxpool.New(ctx, configuration.DatabaseDSN)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindUnavailable, "liveserve: open orchestrator database pool", err)
	}
	desiredStore, err := postgresstore.New(postgresstore.Config{}, postgresstore.Deps{Pool: pool})
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build orchestrator desired store", err)
	}
	if schemaErr := desiredStore.EnsureSchema(ctx); schemaErr != nil {
		return nil, nil, errors.Wrap(errors.KindUnavailable, "liveserve: ensure orchestrator schema", schemaErr)
	}

	// The telemetry plane the orchestrator emits onto (discarded in the live-local demo).
	telemetry, err := observability.New(
		observability.Config{ServiceName: "agentgateway-live-orchestrator", DefaultPlane: observability.PlaneAgent},
		observability.Deps{Exporter: slogadapter.New(io.Discard), Clock: clock},
	)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build orchestrator observability", err)
	}

	// EDEN_SUPERVISOR_INPOD=1 selects the IN-POD supervisor template variant (ADR-0022 §4): the built-in
	// supervisor store compiles a WORKLOAD-POD sandbox (agent-runtime PID-1, the in-pod clone-on-boot
	// path) instead of the host-side Materializer + Ready-then-Run workspace. DEFAULT OFF — the existing
	// host-side template + the live demo path are byte-IDENTICAL when unset (this is purely additive,
	// flag-gated; the in-pod end-to-end run is NOT yet proven — it needs the k3d network-join + a real
	// in-pod claude turn, deferred). The same EDEN_NATS_URL the rest of the live process dials is the
	// bus the in-pod sidecar dials.
	supervisorInPod := os.Getenv("EDEN_SUPERVISOR_INPOD") == "1"
	// The REAL orchestratorservice on docker: a real workspace + a REAL Claude supervisor session.
	service, err := orchestratorservice.New(
		orchestratorservice.Config{
			DefaultMaxConcurrent: 4,
			ReconcileInterval:    2 * time.Second,
			ProvisionTimeout:     4 * time.Minute,
			LabelNamespace:       "eden-live",
			SupervisorInPod:      supervisorInPod,
			SupervisorNATSURL:    os.Getenv("EDEN_NATS_URL"),
		},
		orchestratorservice.Deps{
			DatabasePool:  pool,
			Secrets:       provider,
			Observability: telemetry,
			Sessions:      sessions, // the gateway's ONE shared pool (carries the Transcript) — the supervisor opens through it
		},
	)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build orchestrator service", err)
	}

	// The forge (real GitHub REST) + the gitrepository template seeder (real system-git).
	connector, err := githubadapter.New(
		githubadapter.Config{UserAgent: "eden-agentgateway-live"},
		githubadapter.Deps{HTTP: &http.Client{Timeout: 30 * time.Second}, Secrets: provider},
	)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build forge connector", err)
	}
	forgeAdapter, err := projectcreate.NewForgeAdapter(connector)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build forge adapter", err)
	}
	seeder, err := projectcreate.NewSeeder(
		projectcreate.SeederConfig{CheckoutRoot: configuration.SeedCheckoutRoot},
		projectcreate.SeederDeps{Backend: gitrepository.SystemGit(), Secrets: provider, Clock: clock},
	)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build template seeder", err)
	}

	// The workspace materializer: clone the seeded repo + overlay the supervisor `.claude` operating
	// manual so the spawned Claude agent finds its brain (the repo + its instructions) in its CWD.
	materializer, err := projectcreate.NewMaterializer(
		projectcreate.MaterializerConfig{
			WorkspaceRoot:   configuration.SupervisorWorkspaceRoot,
			ManualSourceDir: configuration.SupervisorManualSourceDir,
		},
		projectcreate.MaterializerDeps{Backend: gitrepository.SystemGit(), Secrets: provider, Clock: clock},
	)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindOf(err), "liveserve: build workspace materializer", err)
	}

	organizationID := configuration.OrganizationID
	if organizationID == "" {
		organizationID = "eden"
	}

	// The supervisor's harness credential, DERIVED from the project's owning org (ADR-0029 §4 / A3): a
	// `claude-api` connector the org uploaded → eden://connector/<id> (resolved by the "eden" adapter
	// bound above), else the platform CredentialReference — the fallback is NEVER regressed. The org key
	// is the platformgateway organization UUID (ConnectorsOrganizationID); an empty/unparsable value or
	// no connector both derive the fallback. The reference is loggable; the value is resolved server-side
	// at agentsession.Open and never reaches this surface.
	supervisorCredential := deriveSupervisorCredential(ctx, connectorDeriver, configuration)

	// The supervisor's controller host-tools, built PER launched project over its materialized workspace
	// + the forge push credential: the eden_commit_transition tool the supervisor calls to commit+push a
	// staged transition and project its FSM state onto Project.Status. The git backend, the credential,
	// and the project store all live here at the composition root. A construction fault (only reachable on
	// an invalid per-project input — guarded upstream) logs and degrades the launch to no host-tools
	// rather than failing the spawn.
	//
	// DEFAULT ON (opt out with EDEN_SUPERVISOR_HOST_TOOLS=0): the supervisor commits its OWN transitions
	// through this host-tool — the controller model, git is the supervisor's truth, it acts through
	// eden_commit_transition; Postgres is the projection. PROVEN live end-to-end: a real Opus supervisor
	// calls the tool, the Handler validates the FSM transition against state/fsm.json, stages+commits with
	// the fsm: trailer, ff-pushes with the forge credential, and projects the FSM state onto Project.Status.
	// The SDK-MCP round-trip that once blocked this was fixed in claudeadapter (84afe0e): array-form
	// sdkMcpServers + answering the CLI-driven notifications/initialized so client.connect() completes.
	forgeCredential := secrets.Ref(configuration.ForgeCredentialReference)
	var supervisorHostTools projectcreate.SupervisorHostToolFactory
	if os.Getenv("EDEN_SUPERVISOR_HOST_TOOLS") != "0" {
		supervisorHostTools = func(project gateway.Project, workspaceDir string) []agentsession.HostTool {
			tool, toolErr := projectcreate.NewCommitTransitionTool(
				projectcreate.CommitTransitionConfig{
					WorkspaceDir:    workspaceDir,
					ProjectID:       project.ID,
					RemoteURL:       project.RepoURL,
					Branch:          project.DefaultBranch,
					ForgeCredential: forgeCredential,
					SessionID:       project.SessionID,
				},
				projectcreate.CommitTransitionDeps{
					Backend:  gitrepository.SystemGit(),
					Secrets:  provider,
					Clock:    clock,
					Projects: projectStore,
				},
			)
			if toolErr != nil {
				slog.Error("liveserve: build supervisor commit-transition tool", "project", project.ID, "error", toolErr)
				return nil
			}
			return []agentsession.HostTool{tool}
		}
	}

	saga, err := projectcreate.New(
		projectcreate.Config{
			RepositoryOwner:        configuration.RepositoryOwner,
			PrivateRepository:      true,
			ForgeCredential:        forgeCredential,
			SupervisorCredential:   supervisorCredential,
			TemplateRepositoryURL:  configuration.TemplateRepositoryURL,
			TemplateReference:      configuration.TemplateRepositoryURL,
			SupervisorTemplate:     orchestrator.TemplateRef{Name: "supervisor", Version: "0.1.0"},
			OrganizationID:         organizationID,
			SupervisorReadyTimeout: 5 * time.Minute,
			SupervisorPollInterval: 2 * time.Second,
			OnPermission:           alwaysAllowPermission,
		},
		projectcreate.Deps{
			Projects:            projectStore,
			Steps:               stepStore,
			Forge:               forgeAdapter,
			Seeder:              seeder,
			Supervisor:          service,
			Materializer:        materializer,
			SupervisorHostTools: supervisorHostTools,
			Clock:               clock,
		},
	)
	if err != nil {
		return nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build create saga", err)
	}
	return saga, service, nil
}

// buildSecretsAndConnectors builds the secrets Mediator over the REAL Vault backend (userpass, "vault"
// scheme) AND — when a connectors DSN is configured — the platformconnectoradapter under the "eden"
// scheme (ADR-0029 §4), returning the org→credential Deriver and a Close for the owned connectors pool.
// The "eden" adapter resolves its KEK through the SAME Vault backend (a direct provider, so the KEK
// path is the existing vault:// seam). When no connectors DSN is configured the "eden" scheme is not
// bound and the Deriver is fallback-only — every session gets CredentialReference exactly as today.
func buildSecretsAndConnectors(configuration *Config) (secrets.Provider, *connectorcredential.Deriver, func(), error) {
	vault, err := vaultadapter.New(
		vaultadapter.Config{Address: configuration.VaultAddress, Mode: vaultadapter.ModeUserpass},
		vaultadapter.Deps{Username: configuration.VaultUsername, Password: configuration.VaultPassword},
	)
	if err != nil {
		return nil, nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build vault backend", err)
	}

	// The connector seam resolves its KEK through the Vault backend directly (the KEK is a vault://
	// reference), so it is built BEFORE the mediator and its adapter joins the mediator's resolver table.
	var kekRef secrets.Reference
	if configuration.ConnectorsKEKReference != "" {
		kekRef = secrets.Ref(configuration.ConnectorsKEKReference)
	}
	seam, err := connectorcredential.Build(
		context.Background(),
		connectorcredential.Config{
			ConnectorsDSN: configuration.ConnectorsDatabaseDSN,
			KEK:           kekRef,
			KEKVersion:    configuration.ConnectorsKEKVersion,
			Fallback:      secrets.Ref(configuration.CredentialReference),
		},
		connectorcredential.Deps{Secrets: vault},
	)
	if err != nil {
		return nil, nil, nil, errors.Wrap(errors.KindOf(err), "liveserve: build connector-credential seam", err)
	}

	resolvers := map[string]secrets.Provider{"vault": vault}
	if seam.Adapter != nil {
		resolvers["eden"] = seam.Adapter // ADR-0029 §4: eden://connector/<id> routes to the connector adapter
	}
	mediator, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: resolvers},
	)
	if err != nil {
		seam.Close()
		return nil, nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build secrets mediator", err)
	}
	return mediator, seam.Deriver, seam.Close, nil
}

// DefaultCreateTemplate exposes the template Name/Version a create request must name so the seeded
// record plane's Spawn resolves the default template. The dev frontend (or a smoke test) posts
// these on POST /sessions (the UI's DEV_TENANCY names exactly this template).
func DefaultCreateTemplate() (name, version string) {
	template := orchestratortest.DefaultTemplate()
	return template.Ref.Name, template.Ref.Version
}

// liveRouteKey is the RouteKey the live gateway opens its session under (matched in the Pool's
// Routing). The gateway opens its OWN session on the live plane, independent of the orchestrator
// template's routing.
func liveRouteKey() agentsession.RouteKey {
	return agentsession.RouteKey{Role: "assistant"}
}

// alwaysAllowPermission is the project-level "always allow" permission policy the live composition
// injects by DEFAULT (the global option, default ON) into every spawned session — the chat sessions
// (gateway.Config.OnPermission) and the supervisor (projectcreate.Config.OnPermission → the fold).
// It auto-resolves EVERY out-of-grant tool request with an allow, so a live agent never stalls on a
// permission prompt and the human-resolve round-trip (with its 5-minute timeout, the source of the
// "unknown or already-resolved" 404) is never armed. This only removes the EDEN-side prompt: the agent's
// in-container settings.json allowlist + its PreToolUse/gate-tool hooks remain the independent wall, so
// auto-allowing at the agentsession layer is safe. A composition that wants the human-prompt chain back
// simply passes nil (the field is the option's seam).
func alwaysAllowPermission(_ agentsession.PermissionRequest) agentsession.Decision {
	return agentsession.Decision{Allow: true, By: "policy:always-allow", Scope: agentsession.ScopeOnce}
}

// createSagaConfigured reports whether every field the create-saga needs is set, so POST /projects
// provisions a project end-to-end. When false the create handler keeps the pre-saga draft behavior.
func (c *Config) createSagaConfigured() bool {
	return c.DatabaseDSN != "" && c.RepositoryOwner != "" && c.ForgeCredentialReference != "" &&
		c.TemplateRepositoryURL != "" && c.SeedCheckoutRoot != "" &&
		c.SupervisorWorkspaceRoot != "" && c.SupervisorManualSourceDir != ""
}

// buildPersistenceStores builds the dashboard / Settings / create-saga Postgres stores when a DSN is
// configured (each nil when no DSN — the dependent routes/saga then 503/absent). The pools are lazy
// (no dial here); the gateway releases them via closeStores on graceful shutdown. It returns the
// gateway.Deps store PORTS as interfaces ON PURPOSE: the no-DSN case must yield TRUE nil interfaces (a
// concrete typed-nil would read as a present store → 500 instead of 503). The composition root wires
// ports — the inverse of accept-interfaces/return-concrete.
//
//nolint:ireturn // composition root wires the store ports; true-nil interfaces are required (see doc).
func buildPersistenceStores(dsn string, clock systemClock) (
	projectStore gateway.ProjectStore, agentConfigStore gateway.AgentConfigStore,
	createStepStore gateway.CreateStepStore, auditStore gateway.AuditStore, err error,
) {
	if dsn == "" {
		return nil, nil, nil, nil, nil
	}
	if projectStore, err = projectpersistence.NewPostgres(context.Background(), dsn, projectpersistence.WithClock(clock)); err != nil {
		return nil, nil, nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build project store", err)
	}
	if agentConfigStore, err = agentconfigpersistence.NewPostgres(context.Background(), dsn); err != nil {
		return nil, nil, nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build agent-config store", err)
	}
	if createStepStore, err = createsteppersistence.NewPostgres(context.Background(), dsn, createsteppersistence.WithClock(clock)); err != nil {
		return nil, nil, nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build create-step store", err)
	}
	if auditStore, err = auditpersistence.NewPostgres(context.Background(), dsn); err != nil {
		return nil, nil, nil, nil, errors.Wrap(errors.KindInternal, "liveserve: build audit store", err)
	}
	return projectStore, agentConfigStore, createStepStore, auditStore, nil
}

// validate checks the required configuration the command resolved from the environment, returning
// a wrapped KindInvalid error naming the missing field (never echoing a value).
func (c *Config) validate() error {
	switch {
	case c.VaultAddress == "":
		return errors.New(errors.KindInvalid, "liveserve: VaultAddress is required")
	case c.VaultUsername == "":
		return errors.New(errors.KindInvalid, "liveserve: VaultUsername is required")
	case c.VaultPassword == "":
		return errors.New(errors.KindInvalid, "liveserve: VaultPassword is required (the userpass bootstrap)")
	case c.CredentialReference == "":
		return errors.New(errors.KindInvalid, "liveserve: CredentialReference is required (the opaque vault:// ref)")
	case c.Workspace == "":
		return errors.New(errors.KindInvalid, "liveserve: Workspace is required (the harness CWD)")
	case c.Harness == "":
		return errors.New(errors.KindInvalid, "liveserve: Harness is required (claude-code|omp)")
	}
	return nil
}
