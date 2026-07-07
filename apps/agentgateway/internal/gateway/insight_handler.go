package gateway

import (
	"context"
	"net/http"
	"strings"
	"time"

	"github.com/gophersys/libs/go/codeinsight"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
)

// insight_handler.go serves the self-feeding seam: GET /projects/{id}/insight returns a
// codeinsight.Report computed over the project's REAL git worktree — per-entity static +
// behavioral metrics, logical coupling, ownership, ratings, trends, and the Views render-plan the
// @eden/visualization dashboards consume (contract docs/architecture/contracts/codeinsight.md). It
// is the producer→transport step of the "point Eden at a codebase → generate the dashboards" path:
// the analyzer walks git natively, this handler mounts it over HTTP, the frontend renders the Views.
//
// The route is PER-PROJECT because a persisted Project carries the SupervisorAgentID whose
// materialized host worktree IS the project's cloned-repo checkout — the same worktree the
// right-panel file tree and the read-only editor open. So resolution reuses the ONE seam the
// workspace/editor handlers already use: Project.SupervisorAgentID → LiveSessions.Workspace(id) →
// the on-disk repository root. No new worktree-resolution concept is introduced.
//
// Boundedness (honest, not a stub): the analyzer walks the full commit history and parses every
// source file, so a large repository is SLOW. The request is bounded by insightAnalyzeTimeout; a
// deadline surfaces as a typed KindUnavailable (503) rather than hanging the browser. There is NO
// caching and NO async job today — every request recomputes the Report synchronously. Caching (a
// Report memoized by HeadCommit, since the contract makes a Report reproducible from
// (repository, commit)) and an async compute-then-poll shape are FUTURE work, tracked against the
// contract's §6 productization path; this endpoint is the first, synchronous cut.

// insightAnalyzeTimeout bounds one insight request: the codeinsight analyzer walks the whole commit
// history and parses every source file, an unbounded amount of work on a large repository. Sixty
// seconds is a generous ceiling for the self-feeding target (the Eden libs) that still frees the
// request rather than letting a runaway analysis hold the connection open indefinitely.
const insightAnalyzeTimeout = 60 * time.Second

// handleProjectInsight serves GET /projects/{id}/insight — the codeinsight.Report for a project's
// worktree. It resolves the project row (Projects.Get), maps its SupervisorAgentID to the on-disk
// worktree through the SAME LiveSessions seam the workspace handlers use, constructs the analyzer
// over the system-git History + the Go MetricProvider (the v1 native provider — contract §4), and
// returns the assembled Report as JSON at 200.
//
// Fault arms, each a typed Kind the boundary maps without a per-route table:
//   - no ProjectStore wired          → KindUnavailable (503): the dashboard is not offered here.
//   - no such project id             → KindNotFound (404): the store maps a missing row to it.
//   - project has no resolvable worktree (no supervisor yet, or its session is not live on this
//     node) → KindUnavailable (503): the repository is not on disk to analyze.
//   - the analysis exceeds insightAnalyzeTimeout → KindUnavailable (503): the walk was too slow
//     (the deadline is surfaced as a typed unavailable, never a hang).
//   - a construction fault (a codeinsight.InvalidInputError) or a history-walk fault → the Kind the
//     library already stamped (KindInvalid / KindUnavailable), surfaced unchanged.
//
// The body carries only the Report — a redaction-safe projection (the contract forbids a
// credential or a URL-with-credentials in any field; the RepositoryRef.Identifier is a logical
// name), so no field can leak a secret.
func (g *Gateway) handleProjectInsight(w http.ResponseWriter, r *http.Request) {
	if g.dependencies.Projects == nil {
		g.writeError(w, errors.New(errors.KindUnavailable, "gateway: project persistence is not configured"))
		return
	}

	project, err := g.dependencies.Projects.Get(r.Context(), r.PathValue("id"))
	if err != nil {
		g.writeError(w, err)
		return
	}

	root, ok := g.resolveProjectWorktree(project)
	if !ok {
		g.writeError(w, errors.Wrap(errors.KindUnavailable, "gateway: project insight",
			RequestError{Reason: "no worktree is materialized for this project yet"}))
		return
	}

	report, err := g.analyzeWorktree(r.Context(), project, root)
	if err != nil {
		g.writeError(w, err)
		return
	}
	g.writeJSON(w, http.StatusOK, report)
}

// resolveProjectWorktree resolves a project's on-disk repository root: its supervisor agent's
// materialized host worktree (the cloned-repo CWD), looked up through the SAME LiveSessions seam
// resolveWorkspaceRoot uses for a session. It returns ("", false) when the project has no supervisor
// yet (a draft/creating row) or when that supervisor's session is not live on this node — the
// caller maps either to a typed KindUnavailable. Unlike the session workspace fallback, it does NOT
// fall back to the gateway's single Config.Workspace: that root is the chat harness CWD, not THIS
// project's repository, so analyzing it would report the wrong codebase.
func (g *Gateway) resolveProjectWorktree(project Project) (string, bool) {
	supervisor := strings.TrimSpace(project.SupervisorAgentID)
	if supervisor == "" || g.dependencies.LiveSessions == nil {
		return "", false
	}
	root, ok := g.dependencies.LiveSessions.Workspace(orchestrator.AgentID(supervisor))
	if !ok || strings.TrimSpace(root) == "" {
		return "", false
	}
	return root, true
}

// analyzeWorktree constructs the codeinsight analyzer over the system-git History + the native Go
// MetricProvider (the v1 provider — contract §4) and assembles one Report for root, bounded by
// insightAnalyzeTimeout. The timeout is the boundedness guarantee: a deadline is surfaced as a typed
// KindUnavailable (a slow walk frees the request, never hangs it), distinct from the library's own
// history/construction faults which arrive already Kind-stamped. The Identifier stamped into the
// Report is the project name (a logical label, never a credential — the contract forbids a secret in
// RepositoryRef).
func (g *Gateway) analyzeWorktree(ctx context.Context, project Project, root string) (*codeinsight.Report, error) {
	analyzer, err := codeinsight.New(
		codeinsight.Config{
			RepositoryPath: root,
			Identifier:     strings.TrimSpace(project.Name),
		},
		codeinsight.Deps{
			History:   codeinsight.NewSystemGitHistory(),
			Providers: []codeinsight.MetricProvider{codeinsight.NewGoMetricProvider()},
			Clock:     insightClock{now: g.dependencies.Clock.Now},
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindOf(err), "gateway: project insight: construct analyzer", err)
	}

	analyzeCtx, cancel := context.WithTimeout(ctx, insightAnalyzeTimeout)
	defer cancel()

	report, err := analyzer.Analyze(analyzeCtx)
	if err != nil {
		// A deadline (the walk was too slow) is a typed KindUnavailable — the request is freed rather
		// than hung — distinct from the library's own history/construction faults, which are already
		// Kind-stamped and surfaced unchanged.
		if errors.Is(analyzeCtx.Err(), context.DeadlineExceeded) {
			return nil, errors.Wrap(errors.KindUnavailable, "gateway: project insight",
				RequestError{Reason: "the repository analysis exceeded its time budget"})
		}
		return nil, errors.Wrap(errors.KindOf(err), "gateway: project insight: analyze", err)
	}
	return report, nil
}

// insightClock adapts the gateway's injected Clock onto codeinsight.Clock (one method), so the
// Report's AnalyzedAt is stamped from the SAME wall-clock source the rest of the gateway uses (and
// the fake in tests stays deterministic). It holds the Now function value rather than the port so
// the adapter is a thin, allocation-cheap shim.
type insightClock struct{ now func() time.Time }

// Now returns the injected clock's current time (the codeinsight.Clock method).
func (c insightClock) Now() time.Time { return c.now() }
