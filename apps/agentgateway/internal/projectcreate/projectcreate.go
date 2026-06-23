// Package projectcreate is the DB-first, resumable project-creation SAGA — the heart of the
// dashboard's "create a project" flow. It drives one fresh project from a persisted DRAFT row to a
// live, supervisor-ready workspace through an ORDERED, IDEMPOTENT, RESUMABLE sequence of steps:
//
//  1. provision_repo     forge.CreateRepo(owner, slug, private)            -> repo coordinates
//  2. seed_template      gitrepository: clone gophersys/template, flatten,  -> seeded origin/main
//     re-point origin at the new repo, push the seed
//  3. launch_supervisor  orchestrator.Spawn(supervisor, local-docker)      -> workspace + agent
//  4. supervisor_ready   wait on the orchestrator health heartbeat (Get)   -> status flips to wizard
//
// DURABILITY (the "DB-first" discipline): the project row is written FIRST (status=creating) by the
// handler before the saga runs, so the flow is reload-safe from the very start. Each step then writes
// a gateway.CreateStep ledger row (status=pending) BEFORE doing its work and Advances it to done
// AFTER — the idempotency key is (projectUUID, step). On a reload the saga reads the ledger, finds the
// last done step, and resumes the next; an already-done step is a no-op. project.status is the
// user-visible projection of "where the saga is" (the dashboard's loading stepper reads it); the
// ledger is the machine truth the saga replays against. On any step fault the saga parks the project
// at status=failed with the human reason (LastError) and the machine step (SagaStep); a Retry
// re-enters at SagaStep.
//
// CONCERNS IT DOES NOT OWN: it never resolves a credential value (the gh PAT rides an opaque
// secrets.Reference into forge/gitrepository, resolved server-side); it never creates the GitHub repo,
// runs git, or spawns a container itself — it ORCHESTRATES the existing ports (forge.Forge,
// gitrepository, orchestrator.Manager) and records the outcome. It defines no new contract type that
// already has a home: it CITES gateway.Project / gateway.CreateStep / gateway.ProjectStatusPatch.
package projectcreate

import (
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// Clock is the minimal injected time port (mirrors gateway.Clock / gitrepository.Clock): the only
// wall-clock source the saga reads, so New stays pure and a test drives deterministic timestamps.
type Clock interface{ Now() time.Time }

// Logger is the narrow, redaction-safe structured-log seam the saga emits its step transitions on. It
// is OPTIONAL (a nil Logger is a no-op). A message or field is NEVER a secret — the saga only ever
// holds an opaque secrets.Reference, never a resolved value.
type Logger interface {
	Info(message string, fields ...any)
	Error(message string, fields ...any)
}

// Config is the immutable, fully-resolved saga input (the configuration pattern: resolved at the edge
// by the composition root, frozen here). It holds NO live handle and NO secret VALUE — only the
// loggable references and coordinates the saga folds into each step. New reads none of it lazily;
// everything is decided once at construction.
type Config struct {
	// RepositoryOwner is the GitHub account/organization every project repository is created under
	// (e.g. "MateoSegura"). Required: an empty owner is a wrapped KindInvalid at New.
	RepositoryOwner string

	// PrivateRepository requests a private repository on forge.CreateRepo; false creates a public one.
	PrivateRepository bool

	// ForgeCredential is the OPAQUE, loggable reference to the GitHub PAT (the gh-token) the forge and
	// the git push authenticate with. It is resolved server-side at the operation by the injected
	// secrets.Provider those ports hold — never by the saga, never into a log or an error. Required.
	ForgeCredential secrets.Reference

	// SupervisorCredential is the OPAQUE reference to the SUPERVISOR HARNESS credential (the Claude
	// setup/OAuth token), distinct from ForgeCredential: the launch step folds it into the supervisor
	// Spawn, where the orchestrator resolves it server-side into the claude child env
	// (CLAUDE_CODE_OAUTH_TOKEN) at agentsession.Open. The git-plane (forge create + template push) and
	// the harness-auth plane carry SEPARATE credentials — a real Claude supervisor authenticates with a
	// Claude token, not the gh-token. Required.
	SupervisorCredential secrets.Reference

	// TemplateRepositoryURL is the clone URL of the seed template (gophersys/template). Required: the
	// seed step clones it, flattens it, and pushes it into the fresh repository.
	TemplateRepositoryURL string

	// TemplateReference is the loggable template identity recorded on the project (Project.TemplateRef),
	// e.g. "gophersys/template@main". Free text; never a credential. Optional (defaults to the URL).
	TemplateReference string

	// SupervisorTemplate names the immutable orchestrator AgentTemplate the launch step spawns the
	// project's supervisor from (orchestratorservice.supervisorTemplateRef — {Name:"supervisor",
	// Version:"0.1.0"}). Required: a zero ref is rejected at New.
	SupervisorTemplate orchestrator.TemplateRef

	// SupervisorCluster is the cluster the supervisor workspace is provisioned on (ADR-0012). The zero
	// ClusterRef resolves to the orchestrator's Config.DefaultCluster (local-docker for the v0 service),
	// so the common path leaves it empty.
	SupervisorCluster orchestrator.ClusterRef

	// OrganizationID scopes the supervisor's tenancy (orchestrator.Tenancy.OrganizationID, 07 §6). The
	// project id is the per-project half; this is the org half. Required.
	OrganizationID string

	// SupervisorReadyTimeout bounds how long step 4 waits for the supervisor health heartbeat to report
	// ready before the saga parks the project at failed. Zero == the parent context bounds it.
	SupervisorReadyTimeout time.Duration

	// SupervisorPollInterval is the cadence step 4 re-Gets the agent record while waiting for ready.
	// Zero == DefaultSupervisorPollInterval.
	SupervisorPollInterval time.Duration
}

// DefaultSupervisorPollInterval is the step-4 readiness poll cadence when Config.SupervisorPollInterval
// is unset.
const DefaultSupervisorPollInterval = 2 * time.Second

// Deps is the injected hexagon (accept interfaces; New constructs nothing). Every port the saga drives
// arrives here; the saga owns only the ORDER and the ledger discipline, never an adapter.
type Deps struct {
	// Projects is the durable project row's store (the user-visible projection the dashboard polls).
	// The saga reads the row to resume and patches its status + saga scratch through it. Required.
	Projects gateway.ProjectStore

	// Steps is the per-step idempotency + replay ledger (the machine truth the saga replays against).
	// Required: the saga writes a pending row before each step and advances it to done/failed after.
	Steps gateway.CreateStepStore

	// Forge creates the project's GitHub repository (step 1), idempotently. Required.
	Forge ProjectForge

	// Seeder clones the seed template, flattens it, re-points origin at the new repository, and pushes
	// the seed (step 2), idempotently. Required.
	Seeder TemplateSeeder

	// Supervisor is the orchestrator record plane: Spawn launches the supervisor workspace (step 3) and
	// Get observes its readiness (step 4). The real *orchestratorservice.Service (an orchestrator.Manager)
	// satisfies it. Required.
	Supervisor orchestrator.Manager

	// Materializer OPTIONALLY prepares the supervisor's working directory before launch (step 3): clone
	// the seeded project repo + overlay the `.claude` operating manual, returning a host path threaded
	// into SpawnRequest.Workspace. When nil the supervisor spawns with no workspace override (a bare CWD —
	// the stub-substrate integration lane). The real *Materializer satisfies it.
	Materializer WorkspaceMaterializer

	// Clock stamps the saga's timestamps; keeps New pure and a test deterministic. Required.
	Clock Clock

	// Logger is the redaction-safe structured-log seam; optional (a nil Logger is a no-op).
	Logger Logger
}

// Saga is the concrete project-creation saga New returns (return-concrete). It holds the frozen Config
// and the injected ports and drives one project through the ordered, resumable step sequence. Safe for
// concurrent use across DISTINCT projects (each step's idempotency key is project-scoped and the stores
// serialize their own writes); a single project should be driven by one Run at a time. Zero value
// unusable — construct via New.
type Saga struct {
	configuration Config
	dependencies  Deps
}

// New is the pure constructor spine New(configuration, dependencies) -> (*Saga, error): it validates
// the wiring and returns the concrete *Saga, doing NO I/O — no repository create, no clone, no spawn,
// no clock read (the first effect happens only on the first Run). It returns a wrapped KindInvalid
// naming the missing seam (never echoing a value) so a misconfigured saga fails at composition, not at
// the first step.
//
//nolint:gocritic,cyclop // Config is the frozen, copyable composition input (the configuration pattern); New takes it by value. The validation is a flat required-field guard, not branching complexity.
func New(configuration Config, dependencies Deps) (*Saga, error) {
	switch {
	case dependencies.Projects == nil:
		return nil, errors.New(errors.KindInvalid, "projectcreate: Deps.Projects is required (the durable project row store)")
	case dependencies.Steps == nil:
		return nil, errors.New(errors.KindInvalid, "projectcreate: Deps.Steps is required (the saga step ledger)")
	case dependencies.Forge == nil:
		return nil, errors.New(errors.KindInvalid, "projectcreate: Deps.Forge is required (the repository-create port)")
	case dependencies.Seeder == nil:
		return nil, errors.New(errors.KindInvalid, "projectcreate: Deps.Seeder is required (the template-seed port)")
	case dependencies.Supervisor == nil:
		return nil, errors.New(errors.KindInvalid, "projectcreate: Deps.Supervisor is required (the orchestrator record plane)")
	case dependencies.Clock == nil:
		return nil, errors.New(errors.KindInvalid, "projectcreate: Deps.Clock is required so New stays pure")
	case configuration.RepositoryOwner == "":
		return nil, errors.New(errors.KindInvalid, "projectcreate: Config.RepositoryOwner is required (the GitHub account repos are created under)")
	case configuration.ForgeCredential.IsZero():
		return nil, errors.New(errors.KindInvalid, "projectcreate: Config.ForgeCredential is required (the opaque gh-token reference)")
	case configuration.SupervisorCredential.IsZero():
		return nil, errors.New(errors.KindInvalid, "projectcreate: Config.SupervisorCredential is required (the opaque Claude harness token reference for the supervisor Spawn)")
	case configuration.TemplateRepositoryURL == "":
		return nil, errors.New(errors.KindInvalid, "projectcreate: Config.TemplateRepositoryURL is required (the seed template clone URL)")
	case configuration.SupervisorTemplate.IsZero():
		return nil, errors.New(errors.KindInvalid, "projectcreate: Config.SupervisorTemplate is required (the supervisor AgentTemplate ref)")
	case configuration.OrganizationID == "":
		return nil, errors.New(errors.KindInvalid, "projectcreate: Config.OrganizationID is required (the supervisor tenancy org key)")
	}

	if configuration.SupervisorPollInterval <= 0 {
		configuration.SupervisorPollInterval = DefaultSupervisorPollInterval
	}
	if configuration.TemplateReference == "" {
		configuration.TemplateReference = configuration.TemplateRepositoryURL
	}

	return &Saga{configuration: configuration, dependencies: dependencies}, nil
}

// logInfo emits a redaction-safe info line when a Logger is wired (no-op otherwise).
func (s *Saga) logInfo(message string, fields ...any) {
	if s.dependencies.Logger != nil {
		s.dependencies.Logger.Info(message, fields...)
	}
}

// logError emits a redaction-safe error line when a Logger is wired (no-op otherwise).
func (s *Saga) logError(message string, fields ...any) {
	if s.dependencies.Logger != nil {
		s.dependencies.Logger.Error(message, fields...)
	}
}
