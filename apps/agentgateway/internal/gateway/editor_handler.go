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
// project worktree. The base URL is resolved PER-AGENT (ADR-0027 §3): when EditorIngressDomain is set
// the editor is served at the host-per-agent origin "https://<id>.editor.<domain>" the substrate
// routed THIS agent's read-only editor sidecar through (mounting THIS agent's worktree); else the
// single static EditorURLBase is used. A composition with NEITHER returns 503 (the editor is not
// offered, e.g. a deployment that does not run code-server). The worktree is resolved through the SAME
// seam the workspace file API uses (resolveWorkspaceRoot → the agent's materialized CWD), so the editor
// opens exactly the dir the right-panel file tree renders.
func (g *Gateway) handleEditor(w http.ResponseWriter, r *http.Request) {
	id := orchestrator.AgentID(r.PathValue("id"))
	base := g.editorBaseFor(id)
	if base == "" {
		g.writeError(w, errors.New(errors.KindUnavailable, "gateway: editor is not configured"))
		return
	}
	root, ok := g.resolveWorkspaceRoot(id)
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

// editorBaseFor resolves the read-only editor's base URL for session id, trailing-slash trimmed:
// PREFERRING the per-agent host-per-agent origin "https://<id>.editor.<EditorIngressDomain>" (ADR-0027
// §3 — each agent's own read-only editor) when EditorIngressDomain is configured, else falling back to
// the single static EditorURLBase. Returns "" when neither is configured (the 503 path). The <id> is
// sanitized to a DNS label so it forms a valid host, matching the substrate's own host derivation.
func (g *Gateway) editorBaseFor(id orchestrator.AgentID) string {
	if domain := strings.Trim(strings.TrimSpace(g.configuration.EditorIngressDomain), "."); domain != "" {
		if label := editorHostLabel(string(id)); label != "" {
			return "https://" + label + ".editor." + domain
		}
	}
	return strings.TrimRight(strings.TrimSpace(g.configuration.EditorURLBase), "/")
}

// editorHostLabel renders an agent id as an RFC-1123 DNS label (lowercase [a-z0-9-], trimmed of
// leading/trailing dashes) so "<label>.editor.<domain>" is a valid host — the same sanitization the
// kubernetesadapter applies to the workspace name, so the gateway's derived host matches the
// substrate's routed editor host exactly. Returns "" for an id that sanitizes to nothing.
func editorHostLabel(id string) string {
	var b strings.Builder
	prevDash := false
	for _, r := range strings.ToLower(id) {
		switch {
		case (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9'):
			b.WriteRune(r)
			prevDash = false
		default:
			if !prevDash {
				b.WriteByte('-')
				prevDash = true
			}
		}
	}
	return strings.Trim(b.String(), "-")
}
