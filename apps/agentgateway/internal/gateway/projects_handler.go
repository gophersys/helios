package gateway

import (
	"crypto/rand"
	"crypto/sha256"
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

// handleCreateProject persists a Project from the scoped product and, when the DB-first create-saga is
// wired, kicks it (the heart of the create flow). It is RELOAD-SAFE: the project row is written FIRST
// (DB-first), so a reload after this point resumes the saga from the ledger. It normalizes the
// ProductConfig (the one definition of "valid"), derives the id (deterministic from the client token so
// a re-POST is idempotent), the name, and the initial status, persists the row, returns the stored
// projectView at 201 IMMEDIATELY (the UI shows loading), and kicks the saga asynchronously.
//
// When no saga is wired (Deps.ProjectCreator == nil), it preserves the pre-saga behavior exactly: a
// plain draft/building persist with a fresh random id, returned at 201.
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

	sagaEnabled := g.dependencies.ProjectCreator != nil

	identifier, err := g.resolveProjectID(request.ClientToken, sagaEnabled)
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	// Idempotent re-POST: when the id is derived from a client token and a row already stands, return
	// it unchanged (the same in-progress row) rather than clobbering the saga's progress. A Create that
	// upserts on id would reset the saga, so the Get-first guard is what makes a double-submit safe.
	if request.ClientToken != "" {
		if existing, getErr := g.dependencies.Projects.Get(r.Context(), identifier); getErr == nil {
			g.logInfo("gateway: project create idempotent re-post", "id", existing.ID, "status", existing.Status)
			g.writeData(w, http.StatusCreated, toProjectView(existing))
			return
		} else if !errors.IsType[*errors.Error](getErr) || errors.KindOf(getErr) != errors.KindNotFound {
			// A real store fault (not a clean "no such row") — surface it; do not silently re-create.
			g.writeEnvelopeError(w, getErr)
			return
		}
	}

	product := NormalizeProductConfig(*request.Product)
	now := g.dependencies.Clock.Now()
	sessionID := strings.TrimSpace(request.SessionID)
	name := strings.TrimSpace(request.Name)
	if name == "" {
		name = product.ProductName
	}

	// DB-FIRST: the saga writes the row at status=creating BEFORE any provisioning (reload-safe from
	// here). Without the saga, the legacy status applies (building when a session was supplied, else
	// draft) — the pre-saga behavior preserved verbatim.
	status := ProjectStatusDraft
	switch {
	case sagaEnabled:
		status = ProjectStatusCreating
	case sessionID != "":
		status = ProjectStatusBuilding
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
	// Return the row to the client BEFORE the saga runs (the UI shows loading + polls), then kick the
	// resumable saga asynchronously on a detached, tracked goroutine.
	g.writeData(w, http.StatusCreated, toProjectView(stored))
	if sagaEnabled {
		g.kickSaga(r.Context(), stored.ID)
	}
}

// resolveProjectID mints the project id for a create request. With a client token AND the saga wired,
// it is DERIVED deterministically from the token (so a re-POST resolves the same id → the idempotent
// re-post path returns the existing row). Otherwise it is a fresh random id (the pre-saga behavior). A
// rand fault on the random path is the only error.
func (g *Gateway) resolveProjectID(clientToken string, sagaEnabled bool) (string, error) {
	if sagaEnabled && strings.TrimSpace(clientToken) != "" {
		return deriveProjectID(clientToken), nil
	}
	return generateProjectID()
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

// deriveProjectID derives a DETERMINISTIC, opaque project id from the create-flow's client token: the
// same "project-" + 18-hex shape as a fresh id, but reproducible — the first 9 bytes of SHA-256(token).
// This is what makes a re-POST idempotent: the same token resolves the same id, so the handler's
// Get-first guard returns the existing in-progress row instead of starting (or clobbering) a second
// saga. The token is an opaque client value, never a credential; SHA-256 makes the id non-reversible
// and uniformly distributed (no token content leaks into the id, no collision on distinct tokens).
func deriveProjectID(clientToken string) string {
	digest := sha256.Sum256([]byte(strings.TrimSpace(clientToken)))
	return "project-" + hex.EncodeToString(digest[:9])
}
