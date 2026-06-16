package gateway

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/errors"
)

// projects_handler holds the dashboard's persisted-Project surface: create (the create-flow's "Build
// it" persists the scoped product), list (the dashboard grid), and get-one. Each route is enveloped
// (the edenhttp {data, errors, kind} shape, like POST /product/propose) and 503s when no ProjectStore
// is wired (the Projects dep is OPTIONAL). The credential is never on a Project — the ProductConfig is
// the redaction-safe spec.

// handleCreateProject persists a Project from the scoped product. It normalizes the ProductConfig
// (the one definition of "valid"), stamps the id + timestamps (so both store adapters share one id
// semantics), derives the name + status, and returns the stored projectView at 201.
func (g *Gateway) handleCreateProject(w http.ResponseWriter, r *http.Request) {
	if g.dependencies.Projects == nil {
		g.writeEnvelopeError(w, errors.New(errors.KindUnavailable, "gateway: project persistence is not configured"))
		return
	}

	var request createProjectRequest
	if err := decodeJSON(r, &request); err != nil {
		g.writeEnvelopeError(w, err)
		return
	}
	if request.Product == nil {
		g.writeEnvelopeError(w, errors.Wrap(errors.KindInvalid, "gateway: create project",
			RequestError{Reason: "product is required"}))
		return
	}

	identifier, err := generateProjectID()
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	product := NormalizeProductConfig(*request.Product)
	now := g.dependencies.Clock.Now()
	sessionID := strings.TrimSpace(request.SessionID)
	status := ProjectStatusDraft
	if sessionID != "" {
		status = ProjectStatusBuilding
	}
	name := strings.TrimSpace(request.Name)
	if name == "" {
		name = product.ProductName
	}

	project := Project{
		ID:        identifier,
		Name:      name,
		Idea:      strings.TrimSpace(request.Idea),
		Product:   product,
		Status:    status,
		SessionID: sessionID,
		CreatedAt: now,
		UpdatedAt: now,
	}

	stored, err := g.dependencies.Projects.Create(r.Context(), project)
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	g.logInfo("gateway: project created", "id", stored.ID, "name", stored.Name, "status", stored.Status)
	g.writeData(w, http.StatusCreated, toProjectView(stored))
}

// handleListProjects returns the newest page of projects (the dashboard grid), wrapped in the data
// envelope. The page size is clamped to the gateway's MaxPageSize.
func (g *Gateway) handleListProjects(w http.ResponseWriter, r *http.Request) {
	if g.dependencies.Projects == nil {
		g.writeEnvelopeError(w, errors.New(errors.KindUnavailable, "gateway: project persistence is not configured"))
		return
	}

	page, err := g.dependencies.Projects.List(r.Context(), g.projectFilter(r))
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	views := make([]projectView, 0, len(page.Projects))
	for i := range page.Projects {
		views = append(views, toProjectView(page.Projects[i]))
	}
	g.writeData(w, http.StatusOK, listProjectsResponse{Projects: views, Next: page.Next})
}

// handleGetProject returns one Project by id (a 404 envelope when absent — the store maps a missing
// row to KindNotFound).
func (g *Gateway) handleGetProject(w http.ResponseWriter, r *http.Request) {
	if g.dependencies.Projects == nil {
		g.writeEnvelopeError(w, errors.New(errors.KindUnavailable, "gateway: project persistence is not configured"))
		return
	}

	project, err := g.dependencies.Projects.Get(r.Context(), r.PathValue("id"))
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}
	g.writeData(w, http.StatusOK, toProjectView(project))
}

// projectFilter reads the list query (limit, cursor) into a ProjectFilter, defaulting and clamping
// the page size to the gateway's MaxPageSize.
func (g *Gateway) projectFilter(r *http.Request) ProjectFilter {
	query := r.URL.Query()
	limit := g.configuration.MaxPageSize
	if raw := strings.TrimSpace(query.Get("limit")); raw != "" {
		if parsed, parseErr := strconv.Atoi(raw); parseErr == nil && parsed > 0 {
			limit = parsed
		}
	}
	if limit > g.configuration.MaxPageSize {
		limit = g.configuration.MaxPageSize
	}
	return ProjectFilter{Limit: limit, Cursor: strings.TrimSpace(query.Get("cursor"))}
}

// generateProjectID mints an opaque, collision-resistant project id ("project-" + 18 hex chars from
// a cryptographic source). A rand fault is the only error path (surfaced as KindInternal).
func generateProjectID() (string, error) {
	var raw [9]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return "", errors.Wrap(errors.KindInternal, "gateway: generate project id", err)
	}
	return "project-" + hex.EncodeToString(raw[:]), nil
}
