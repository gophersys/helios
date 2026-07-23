package gateway

import (
	"encoding/json"
	"net/http"

	"github.com/gophersys/libs/go/errors"
)

// routes wires the gateway's HTTP surface onto a std-lib http.ServeMux, using the Go 1.22+
// method+pattern syntax (no third-party router needed — net/http alone resolves
// method-scoped path patterns with typed wildcards). The surface the SvelteKit UI consumes:
//
//	POST   /sessions                         create/spawn a session  -> { id }
//	GET    /sessions                         list (project-scoped, paginated) -> REQ-0022
//	GET    /sessions/{id}                    get one session record   -> REQ-0020
//	POST   /sessions/{id}/stop               stop (record terminal intent)
//	POST   /sessions/{id}/resume             resume (re-attach from seq)
//	POST   /sessions/{id}/control            prompt | steer | abort   -> REQ-0020 mid-stream
//	POST   /sessions/{id}/permissions/{requestId}  resolve a pending permission (allow|deny + scope) -> ADR-0025
//	GET    /sessions/{id}/events             SSE stream (Last-Event-ID / ?from-seq=) -> REQ-0023/0024
//	GET    /sessions/{id}/transcript         persisted Run, queryable after end -> REQ-0020/0023
//	GET    /sessions/{id}/workspace          REAL files the agent produced under its workspace root
//	GET    /sessions/{id}/workspace/file     CONTENT of one workspace file (?path=, traversal-safe, 1 MiB cap)
//	GET    /sessions/{id}/editor             read-only "Open in VS Code" coordinates for the session -> ADR-0027
//	POST   /product/propose                  AI-propose a ProductConfig from the prompt (wizard step 1)
//	POST   /projects                         persist a Project from the scoped product (Build it)
//	GET    /projects                         list persisted projects (the dashboard grid)
//	GET    /projects/{id}                    get one persisted project
//	GET    /projects/{id}/insight            codeinsight Report over the project's worktree (self-feeding)
//	GET    /agent-configs                    list the saved per-agent-type configurations (Settings)
//	PUT    /agent-configs/{agentType}        upsert one agent type's configuration
//	GET    /connectors                       list the caller's connectors (Settings → Connectors; never a value)
//	POST   /connectors                       connect a provider (the credential crosses ONCE) -> write-only
//	DELETE /connectors/{id}                  disconnect (revoke) a connector
//	GET    /healthz                          liveness
func (g *Gateway) routes() *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("POST /product/propose", g.handleProductPropose)
	mux.HandleFunc("POST /projects", g.handleCreateProject)
	mux.HandleFunc("GET /projects", g.handleListProjects)
	mux.HandleFunc("GET /projects/{id}", g.handleGetProject)
	mux.HandleFunc("GET /projects/{id}/insight", g.handleProjectInsight)
	mux.HandleFunc("GET /agent-configs", g.handleListAgentConfigs)
	mux.HandleFunc("PUT /agent-configs/{agentType}", g.handlePutAgentConfig)
	mux.HandleFunc("GET /connectors", g.handleListConnectors)
	mux.HandleFunc("POST /connectors", g.handleCreateConnector)
	mux.HandleFunc("DELETE /connectors/{id}", g.handleDeleteConnector)
	mux.HandleFunc("POST /sessions", g.handleCreateSession)
	mux.HandleFunc("GET /sessions", g.handleListSessions)
	mux.HandleFunc("GET /sessions/{id}", g.handleGetSession)
	mux.HandleFunc("POST /sessions/{id}/stop", g.handleStopSession)
	mux.HandleFunc("POST /sessions/{id}/resume", g.handleResumeSession)
	mux.HandleFunc("POST /sessions/{id}/control", g.handleControl)
	mux.HandleFunc("POST /sessions/{id}/permissions/{requestId}", g.handleResolvePermission)
	mux.HandleFunc("GET /sessions/{id}/events", g.handleEvents)
	mux.HandleFunc("GET /sessions/{id}/transcript", g.handleTranscript)
	mux.HandleFunc("GET /sessions/{id}/workspace", g.handleWorkspace)
	mux.HandleFunc("GET /sessions/{id}/workspace/file", g.handleWorkspaceFile)
	mux.HandleFunc("GET /sessions/{id}/editor", g.handleEditor)
	mux.HandleFunc("GET /healthz", g.handleHealth)

	return mux
}

// handleHealth is the liveness probe (no session state, no credential path).
func (g *Gateway) handleHealth(w http.ResponseWriter, _ *http.Request) {
	g.writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// writeJSON writes a value as JSON with the given status. A pre-write encode fault is
// surfaced as a 500 (the header is not yet committed at that point); a post-header encode
// fault is unrecoverable and logged. The body NEVER carries a credential — every DTO is a
// redaction-safe projection.
func (g *Gateway) writeJSON(w http.ResponseWriter, status int, body any) {
	encoded, err := json.Marshal(body)
	if err != nil {
		// Encoding a known-safe DTO should never fail; treat it as an internal fault and
		// emit the redaction-safe envelope (header not yet sent).
		g.writeError(w, errors.Wrap(errors.KindInternal, "gateway: encode response", err))
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write(encoded) //nolint:errcheck // the header is committed; a write fault here is a dropped client connection, nothing to act on.
}
