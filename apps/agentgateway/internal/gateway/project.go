package gateway

import (
	"context"
	"time"
)

// This file is the persisted-Project contract: the Project value, the ProjectStore port (the
// consumer-defined persistence seam), and the wire DTOs the dashboard exchanges. A Project is the
// DURABLE form of a create-flow scope — what the wizard proposes and the user builds. It carries the
// originating idea, the proposed ProductConfig (kind/stack/services/capabilities), a lifecycle
// status, the build session it spawned (when any), and timestamps. No field is a credential: the
// ProductConfig is the redaction-safe spec (the setup-token rides the gateway's secrets.Reference,
// resolved at Open, never this value).

// Project is a first-class, persisted thing a user is building with Eden. A build session references
// it by id (createSessionRequest.ProjectID → Tenant.ProjectID). The Product is normalized
// (NormalizeProductConfig) before persistence so a stored Project is always a complete spec.
//
// Beyond the originating idea + ProductConfig, a Project carries the DB-first create-saga's durable
// scratch: where the repository landed (GitHubOwner/GitHubRepo/RepoURL/DefaultBranch), which template
// seeded it (TemplateRef), the provisioned workspace + supervisor it spawned (WorkspaceHandle,
// SupervisorAgentID, SessionRef), how far the saga advanced (SagaStep), and the last fault that
// stalled it (LastError). None of these is a credential — RepoURL is the public clone URL, the
// handles are opaque record-plane identifiers, and the saga resolves any secret server-side at use.
// Every field is JSON-omitempty so a pre-saga Project (draft) and a forward-compatible field never
// break a stored row (the record is JSONB; see projectpersistence).
type Project struct {
	ID                string        `json:"id"`
	Name              string        `json:"name"`
	Idea              string        `json:"idea"`
	Product           ProductConfig `json:"product"`
	Status            string        `json:"status"`
	SessionID         string        `json:"sessionId,omitempty"`
	GitHubOwner       string        `json:"githubOwner,omitempty"`
	GitHubRepo        string        `json:"githubRepo,omitempty"`
	RepoURL           string        `json:"repoUrl,omitempty"`
	DefaultBranch     string        `json:"defaultBranch,omitempty"`
	TemplateRef       string        `json:"templateRef,omitempty"`
	WorkspaceHandle   string        `json:"workspaceHandle,omitempty"`
	SupervisorAgentID string        `json:"supervisorAgentId,omitempty"`
	SessionRef        string        `json:"sessionRef,omitempty"`
	LastError         string        `json:"lastError,omitempty"`
	SagaStep          string        `json:"sagaStep,omitempty"`
	CreatedAt         time.Time     `json:"createdAt"`
	UpdatedAt         time.Time     `json:"updatedAt"`
}

// The closed Project lifecycle status set. A project starts a DRAFT (scoped but not yet building); the
// DB-first create-saga then walks it through the provisioning states (creating → provisioning the
// repository → seeding the template → launching the supervisor → supervisor ready → wizard) into
// BUILDING, or parks it at FAILED when a saga step faults. The original DRAFT and BUILDING tokens are
// preserved verbatim so existing rows and the create handler keep working; the set widens only via a
// contract revision (this IS that revision).
const (
	ProjectStatusDraft               = "draft"
	ProjectStatusCreating            = "creating"
	ProjectStatusProvisioningRepo    = "provisioning_repo"
	ProjectStatusSeedingTemplate     = "seeding_template"
	ProjectStatusLaunchingSupervisor = "launching_supervisor"
	ProjectStatusSupervisorReady     = "supervisor_ready"
	ProjectStatusWizard              = "wizard"
	ProjectStatusBuilding            = "building"
	ProjectStatusFailed              = "failed"
)

// projectStatuses is the closed set of legal Project.Status tokens, in saga order (draft, then the
// provisioning walk, then the terminal building/failed). It backs ValidProjectStatus so a status
// patch cannot write a token outside the contract.
var projectStatuses = map[string]struct{}{
	ProjectStatusDraft:               {},
	ProjectStatusCreating:            {},
	ProjectStatusProvisioningRepo:    {},
	ProjectStatusSeedingTemplate:     {},
	ProjectStatusLaunchingSupervisor: {},
	ProjectStatusSupervisorReady:     {},
	ProjectStatusWizard:              {},
	ProjectStatusBuilding:            {},
	ProjectStatusFailed:              {},
}

// ValidProjectStatus reports whether status is a member of the closed Project lifecycle set. The
// status-patch path (ProjectStore.UpdateStatus) rejects any other token with a wrapped KindInvalid so
// a typo or a stale client can never write an off-contract status into a row.
func ValidProjectStatus(status string) bool {
	_, ok := projectStatuses[status]
	return ok
}

// ProjectFilter bounds a list query: a page Limit (clamped to the gateway's MaxPageSize) and an
// opaque Cursor (the seq boundary returned as a prior page's Next). The zero value lists the newest
// page.
type ProjectFilter struct {
	Limit  int
	Cursor string
}

// ProjectPage is one page of projects, newest first, plus the opaque Next cursor (empty when the
// page is the last).
type ProjectPage struct {
	Projects []Project
	Next     string
}

// ProjectStore is the persisted-Project port: the consumer-defined seam the gateway persists
// projects through. A real Postgres adapter backs it in liveserve; an in-memory fake backs it in
// devserve — the same real-vs-fake mirror the Proposer uses. It is OPTIONAL on Deps: when nil the
// /projects routes are a 503 (a composition that does not offer the dashboard).
//
// Create persists a fully-formed Project (the handler stamps id + timestamps so both adapters share
// one id semantics) and returns the stored copy. Get returns a wrapped KindNotFound when absent.
// List returns the newest page matching filter. UpdateStatus is the saga's mutation seam: a
// read-modify-write of one row's status + saga scratch (the JSONB record), returning the stored copy
// (a wrapped KindNotFound when the id is absent, KindInvalid when the patch names an off-contract
// status). The surface stays at four methods (the 5-method ceiling, 10 §9).
type ProjectStore interface {
	Create(ctx context.Context, project Project) (Project, error)
	Get(ctx context.Context, id string) (Project, error)
	List(ctx context.Context, filter ProjectFilter) (ProjectPage, error)
	UpdateStatus(ctx context.Context, id string, patch ProjectStatusPatch) (Project, error)
}

// ProjectStatusPatch is the saga's read-modify-write payload for ProjectStore.UpdateStatus: a partial
// mutation of one Project's status + saga scratch. A nil pointer field is "leave unchanged"; a
// non-nil pointer to the empty string is "clear this field" (the saga clears LastError once a stalled
// step recovers). Status, when set, must be a member of the closed lifecycle set (ValidProjectStatus)
// — the adapter rejects an off-contract token before it writes. The store always re-stamps UpdatedAt
// from the injected Clock; CreatedAt and the id are immutable and never patched.
type ProjectStatusPatch struct {
	Status            *string
	SagaStep          *string
	LastError         *string
	GitHubOwner       *string
	GitHubRepo        *string
	RepoURL           *string
	DefaultBranch     *string
	TemplateRef       *string
	WorkspaceHandle   *string
	SupervisorAgentID *string
	SessionRef        *string
	SessionID         *string
}

// ApplyTo folds the patch onto a Project value (the read-modify step both store adapters share), so
// the merge rule lives ONCE here, not re-spelled per adapter. It mutates the passed Project in place:
// each non-nil field overwrites, a nil field is left untouched. The caller re-stamps UpdatedAt and
// persists the result. It does NOT validate Status — the adapter validates via ValidProjectStatus
// before calling ApplyTo so an off-contract token never reaches a row.
//
//nolint:gocyclo,cyclop // a flat field-by-field merge of a closed patch struct; the cyclomatic count is the field count, not branching complexity — splitting it would only scatter the one merge rule.
func (p *ProjectStatusPatch) ApplyTo(project *Project) {
	if p.Status != nil {
		project.Status = *p.Status
	}
	if p.SagaStep != nil {
		project.SagaStep = *p.SagaStep
	}
	if p.LastError != nil {
		project.LastError = *p.LastError
	}
	if p.GitHubOwner != nil {
		project.GitHubOwner = *p.GitHubOwner
	}
	if p.GitHubRepo != nil {
		project.GitHubRepo = *p.GitHubRepo
	}
	if p.RepoURL != nil {
		project.RepoURL = *p.RepoURL
	}
	if p.DefaultBranch != nil {
		project.DefaultBranch = *p.DefaultBranch
	}
	if p.TemplateRef != nil {
		project.TemplateRef = *p.TemplateRef
	}
	if p.WorkspaceHandle != nil {
		project.WorkspaceHandle = *p.WorkspaceHandle
	}
	if p.SupervisorAgentID != nil {
		project.SupervisorAgentID = *p.SupervisorAgentID
	}
	if p.SessionRef != nil {
		project.SessionRef = *p.SessionRef
	}
	if p.SessionID != nil {
		project.SessionID = *p.SessionID
	}
}

// ── wire DTOs ──────────────────────────────────────────────────────────────────.

// createProjectRequest is the body of POST /projects: the create-flow's "Build it" persists the
// scoped product as a Project. Name defaults from the product's productName; Status defaults to
// BUILDING when a SessionID is supplied (Build-it always spawns a session), DRAFT otherwise.
type createProjectRequest struct {
	Name      string         `json:"name,omitempty"`
	Idea      string         `json:"idea,omitempty"`
	Product   *ProductConfig `json:"product"`
	SessionID string         `json:"sessionId,omitempty"`
}

// projectView is the JSON projection of a Project for the dashboard: the fields a ProjectCard reads
// (name/kind/status/harness/stacks), with the originating idea and timestamps. The stack is
// flattened (languages + frameworks) and the services listed, both derived from the stored
// ProductConfig — never a credential.
//
// The saga-scratch fields (repo coordinates, the saga step, the last fault) are surfaced
// omitempty so a build-progress UI can render the saga's advance WITHOUT a wire break: a pre-saga
// draft omits them entirely, exactly as today's dashboard sees. RepoURL is the public clone URL and
// the handles are opaque record-plane ids — no credential exists on this projection by construction.
type projectView struct {
	ID                string    `json:"id"`
	Name              string    `json:"name"`
	Idea              string    `json:"idea,omitempty"`
	Kind              string    `json:"kind"`
	Status            string    `json:"status"`
	Harness           string    `json:"harness"`
	Stacks            []string  `json:"stacks"`
	Services          []string  `json:"services"`
	SessionID         string    `json:"sessionId,omitempty"`
	GitHubOwner       string    `json:"githubOwner,omitempty"`
	GitHubRepo        string    `json:"githubRepo,omitempty"`
	RepoURL           string    `json:"repoUrl,omitempty"`
	DefaultBranch     string    `json:"defaultBranch,omitempty"`
	TemplateRef       string    `json:"templateRef,omitempty"`
	SupervisorAgentID string    `json:"supervisorAgentId,omitempty"`
	SagaStep          string    `json:"sagaStep,omitempty"`
	LastError         string    `json:"lastError,omitempty"`
	CreatedAt         time.Time `json:"createdAt"`
	UpdatedAt         time.Time `json:"updatedAt"`
}

// listProjectsResponse is the body of GET /projects (wrapped in the edenhttp data envelope): a page
// of projects, newest first, plus the opaque next cursor.
type listProjectsResponse struct {
	Projects []projectView `json:"projects"`
	Next     string        `json:"next,omitempty"`
}

// toProjectView projects a Project onto its wire DTO, flattening the stored ProductConfig into the
// dashboard's read model (no credential field exists on the projection, so a leak is impossible by
// construction).
//
//nolint:gocritic // Project is the copyable persisted record; the projector reads it by value.
func toProjectView(project Project) projectView {
	stacks := make([]string, 0, len(project.Product.Stack.Languages)+len(project.Product.Stack.Frameworks))
	stacks = append(stacks, project.Product.Stack.Languages...)
	stacks = append(stacks, project.Product.Stack.Frameworks...)
	services := project.Product.Services
	if services == nil {
		services = []string{}
	}
	return projectView{
		ID:                project.ID,
		Name:              project.Name,
		Idea:              project.Idea,
		Kind:              project.Product.ProductKind,
		Status:            project.Status,
		Harness:           project.Product.Capabilities.Harness,
		Stacks:            stacks,
		Services:          services,
		SessionID:         project.SessionID,
		GitHubOwner:       project.GitHubOwner,
		GitHubRepo:        project.GitHubRepo,
		RepoURL:           project.RepoURL,
		DefaultBranch:     project.DefaultBranch,
		TemplateRef:       project.TemplateRef,
		SupervisorAgentID: project.SupervisorAgentID,
		SagaStep:          project.SagaStep,
		LastError:         project.LastError,
		CreatedAt:         project.CreatedAt,
		UpdatedAt:         project.UpdatedAt,
	}
}
