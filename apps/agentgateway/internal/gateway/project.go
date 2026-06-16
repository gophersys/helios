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
type Project struct {
	ID        string        `json:"id"`
	Name      string        `json:"name"`
	Idea      string        `json:"idea"`
	Product   ProductConfig `json:"product"`
	Status    string        `json:"status"`
	SessionID string        `json:"sessionId,omitempty"`
	CreatedAt time.Time     `json:"createdAt"`
	UpdatedAt time.Time     `json:"updatedAt"`
}

// The closed Project lifecycle status set. A project starts a DRAFT (scoped but not yet building) or
// BUILDING (a build session was spawned with it). The set is intentionally small; it widens only via
// a contract revision.
const (
	ProjectStatusDraft    = "draft"
	ProjectStatusBuilding = "building"
)

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
// List returns the newest page matching filter.
type ProjectStore interface {
	Create(ctx context.Context, project Project) (Project, error)
	Get(ctx context.Context, id string) (Project, error)
	List(ctx context.Context, filter ProjectFilter) (ProjectPage, error)
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
type projectView struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Idea      string    `json:"idea,omitempty"`
	Kind      string    `json:"kind"`
	Status    string    `json:"status"`
	Harness   string    `json:"harness"`
	Stacks    []string  `json:"stacks"`
	Services  []string  `json:"services"`
	SessionID string    `json:"sessionId,omitempty"`
	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
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
		ID:        project.ID,
		Name:      project.Name,
		Idea:      project.Idea,
		Kind:      project.Product.ProductKind,
		Status:    project.Status,
		Harness:   project.Product.Capabilities.Harness,
		Stacks:    stacks,
		Services:  services,
		SessionID: project.SessionID,
		CreatedAt: project.CreatedAt,
		UpdatedAt: project.UpdatedAt,
	}
}
