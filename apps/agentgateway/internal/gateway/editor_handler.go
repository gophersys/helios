package gateway

import (
	"net/http"
	"net/url"
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
)

// editor_handler.go serves the "Open in VS Code (read-only)" coordinates. The editor is a read-only
// code-server (real VS Code in the browser) serving the project's live worktree. This endpoint is
// SUBSTRATE-AGNOSTIC: it only forms the per-project URL under the configured EditorURLBase. The editor
// WORKLOAD is managed per substrate — a docker container locally (deploy/ctl.sh start_code_server), a
// code-server Deployment+Service+Ingress in kubernetes — so the same UI contract works on both; only
// the base URL (localhost vs the ingress host) differs.

// editorView is the wire DTO for GET /sessions/{id}/editor. WEB opens URL in a new tab; DESKTOP builds
// vscode://vscode-remote/ssh-remote+<sshHost><worktreePath> (else falls back to URL). No field is a
// credential — the URL carries no token, and sshHost is a host alias the user's VS Code resolves.
type editorView struct {
	URL          string `json:"url"`          // <EditorURLBase>/?folder=<worktree> — read-only VS Code in a new tab
	WorktreePath string `json:"worktreePath"` // the worktree the editor opens (the supervisor's materialized CWD)
	SSHHost      string `json:"sshHost"`      // OPTIONAL ssh-remote host for the desktop vscode:// URI; "" == web-only
}

// handleEditor serves GET /sessions/{id}/editor — the read-only VS Code coordinates for the session's
// project worktree. A composition with no EditorURLBase returns 503 (the editor is not offered, e.g. a
// deployment that does not run code-server). The worktree is resolved through the SAME seam the
// workspace file API uses (resolveWorkspaceRoot → the agent's materialized CWD), so the editor opens
// exactly the dir the right-panel file tree renders.
func (g *Gateway) handleEditor(w http.ResponseWriter, r *http.Request) {
	base := strings.TrimRight(strings.TrimSpace(g.configuration.EditorURLBase), "/")
	if base == "" {
		g.writeError(w, errors.New(errors.KindUnavailable, "gateway: editor is not configured"))
		return
	}
	root, ok := g.resolveWorkspaceRoot(orchestrator.AgentID(r.PathValue("id")))
	if !ok {
		g.writeError(w, errors.Wrap(errors.KindUnavailable, "gateway: editor",
			RequestError{Reason: "no workspace root for this session"}))
		return
	}
	g.writeJSON(w, http.StatusOK, editorView{
		URL:          base + "/?folder=" + url.QueryEscape(root),
		WorktreePath: root,
		SSHHost:      strings.TrimSpace(g.configuration.EditorSSHHost),
	})
}
