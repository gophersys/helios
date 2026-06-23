package projectcreate

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	"github.com/gophersys/libs/go/agentsession"
	edenerrors "github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// committransition.go is the supervisor's COMMIT-TRANSITION controller host-tool — the server-side
// half of "the agent stages, the orchestrator commits" (the supervisor's slash-commands only
// `git add`; nothing commits until this runs). The supervisor calls `eden_commit_transition` after a
// transition's slash-command staged its artifact + advanced state/fsm.json; the in-process Handler
// re-validates the FSM transition against the project's own state/fsm.json (the same legality the
// gate-commit hook enforces, but server-side and authoritative — the agent never runs `git commit`),
// commits the staged tree AS the agent, fast-forward pushes it with the forge credential, and PROJECTS
// the resulting FSM state onto the durable Project.Status the dashboard polls. One concept, one home:
// the FSM-state → Project.Status map lives here and is cited by the create saga's terminal handoff.

// SupervisorHostToolFactory builds the per-project supervisor host-tools (the controller surface) for
// a launched supervisor, closing over THIS project's materialized workspace + credentials. It is
// invoked at launch with the project + its workspace dir; nil (no factory wired) == the supervisor
// spawns with no host-tools (the pre-controller behavior). The composition root (liveserve) supplies
// the impl because the git backend, the forge credential, and the project store all live there.
type SupervisorHostToolFactory func(project gateway.Project, workspaceDir string) []agentsession.HostTool

// commitTransitionToolName is the host-tool the supervisor calls to commit a staged transition. It is
// the grant key the supervisor template must allow (the agentsession auto-allow surface).
const commitTransitionToolName = "eden_commit_transition"

// commitTransitionSchema is the MCP input schema: the single `trailer` is the `fsm: A -> B / transition
// / artifact / guard` line the transition's slash-command PRINTED; `subject` is an optional human commit
// subject (a default is synthesized from the transition when absent).
const commitTransitionSchema = `{
  "type": "object",
  "required": ["trailer"],
  "additionalProperties": false,
  "properties": {
    "trailer": {"type": "string", "description": "The fsm: A -> B / transition / artifact / guard line the transition command printed."},
    "subject": {"type": "string", "description": "Optional human commit subject; a default is synthesized from the transition when omitted."}
  }
}`

// CommitTransitionConfig is the per-project, fully-resolved input to the commit-transition tool.
type CommitTransitionConfig struct {
	// WorkspaceDir is the supervisor's materialized working directory (the cloned repo + the `.claude`
	// manual) — the worktree the tool stages, commits, and pushes from. Absolute.
	WorkspaceDir string
	// ProjectID is the durable project row id the resulting FSM state is projected onto.
	ProjectID string
	// RemoteURL is the project repository's push URL (the same origin the workspace was cloned from);
	// registered as the `origin` remote the tool fast-forward pushes to.
	RemoteURL string
	// Branch is the repository's default branch (e.g. "main"); empty falls back to "main".
	Branch string
	// ForgeCredential is the OPAQUE reference to the git push credential (the gh-token plane), resolved
	// server-side at the push — never inlined, never logged.
	ForgeCredential secrets.Reference
	// SessionID / RunID OPTIONALLY stamp the agent commit's Eden-* audit trailers.
	SessionID string
	RunID     string
}

// CommitTransitionDeps are the injected ports the tool acts through.
type CommitTransitionDeps struct {
	Backend  gitrepository.Backend // the git vendor seam (SystemGit in production)
	Secrets  secrets.Provider      // resolves ForgeCredential at the push
	Clock    gitrepository.Clock   // the commit timestamp source
	Projects gateway.ProjectStore  // the FSM-state → Project.Status projection sink
}

// commitAuthorName / commitAuthorEmail stamp the supervisor's agent commits (ActorAgent → the Eden-*
// audit trailers ride along when a session/run id is present).
const (
	commitAuthorName  = "Eden Supervisor"
	commitAuthorEmail = "supervisor@eden.gophersys.dev"
	defaultBranchName = "main"
)

// NewCommitTransitionTool builds the eden_commit_transition host-tool for one launched supervisor. It
// validates the wiring and constructs a gitrepository handle over the project's workspace; the Handler
// closes over that handle. Pure: no I/O beyond the gitrepository handle construction (the first git
// operation happens on the first call).
//
//nolint:gocritic // Config is the frozen, copyable per-project spine input; New takes it by value.
func NewCommitTransitionTool(configuration CommitTransitionConfig, dependencies CommitTransitionDeps) (agentsession.HostTool, error) {
	switch {
	case configuration.WorkspaceDir == "" || !filepath.IsAbs(configuration.WorkspaceDir):
		return agentsession.HostTool{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: CommitTransitionConfig.WorkspaceDir must be an absolute path: "+configuration.WorkspaceDir)
	case strings.TrimSpace(configuration.ProjectID) == "":
		return agentsession.HostTool{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: CommitTransitionConfig.ProjectID is required")
	case strings.TrimSpace(configuration.RemoteURL) == "":
		return agentsession.HostTool{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: CommitTransitionConfig.RemoteURL is required (the push destination)")
	case configuration.ForgeCredential.IsZero():
		return agentsession.HostTool{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: CommitTransitionConfig.ForgeCredential is required (the git push credential)")
	case dependencies.Backend == nil:
		return agentsession.HostTool{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: CommitTransitionDeps.Backend is required")
	case dependencies.Secrets == nil:
		return agentsession.HostTool{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: CommitTransitionDeps.Secrets is required")
	case dependencies.Clock == nil:
		return agentsession.HostTool{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: CommitTransitionDeps.Clock is required")
	case dependencies.Projects == nil:
		return agentsession.HostTool{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: CommitTransitionDeps.Projects is required")
	}

	repository, err := gitrepository.New(
		gitrepository.Config{
			Root:          configuration.WorkspaceDir,
			Remotes:       map[string]string{seedRemoteName: configuration.RemoteURL},
			DefaultAuthor: gitrepository.Identity{Name: commitAuthorName, Email: commitAuthorEmail, Kind: gitrepository.ActorAgent},
		},
		gitrepository.Deps{Backend: dependencies.Backend, Secrets: dependencies.Secrets, Clock: dependencies.Clock},
	)
	if err != nil {
		return agentsession.HostTool{}, edenerrors.Wrap(edenerrors.KindInternal, "projectcreate: build commit-transition repository handle", err)
	}

	branch := configuration.Branch
	if strings.TrimSpace(branch) == "" {
		branch = defaultBranchName
	}

	handler := &commitTransitionHandler{
		configuration: configuration,
		repository:    repository,
		projects:      dependencies.Projects,
		branch:        branch,
	}
	return agentsession.HostTool{
		Name:        commitTransitionToolName,
		Description: "Commit and push the transition you just staged (its slash-command ran git add + advanced state/fsm.json), then project its FSM state onto the project status. Pass the `trailer` line the command printed.",
		Schema:      []byte(commitTransitionSchema),
		Handler:     handler.handle,
	}, nil
}

// commitTransitionHandler holds the resolved per-project context the Handler closes over.
type commitTransitionHandler struct {
	configuration CommitTransitionConfig
	repository    *gitrepository.Repository
	projects      gateway.ProjectStore
	branch        string
}

// commitTransitionArgs is the decoded tool input.
type commitTransitionArgs struct {
	Trailer string `json:"trailer"`
	Subject string `json:"subject"`
}

// handle is the host-tool Handler: parse the trailer → re-validate the FSM transition against the
// project's state/fsm.json (authoritative, server-side) → stage all + commit AS the agent with the
// trailer → fast-forward push with the forge credential → project the FSM state onto Project.Status.
// A validation failure returns a typed error the model sees as a tool error (it never commits).
func (h *commitTransitionHandler) handle(ctx context.Context, raw []byte) ([]byte, error) {
	var args commitTransitionArgs
	if err := json.Unmarshal(raw, &args); err != nil {
		return nil, edenerrors.Wrap(edenerrors.KindInvalid, "eden_commit_transition: decode arguments", err)
	}
	transition, err := parseFSMTrailer(args.Trailer)
	if err != nil {
		return nil, err
	}
	if err := validateFSMTransition(h.configuration.WorkspaceDir, &transition); err != nil {
		return nil, err
	}

	if _, err := h.repository.Stage(ctx, h.configuration.WorkspaceDir, gitrepository.StageOptions{All: true}); err != nil {
		return nil, edenerrors.Wrap(edenerrors.KindOf(err), "eden_commit_transition: stage", err)
	}
	message := h.commitMessage(args.Subject, &transition)
	commit, err := h.repository.Commit(ctx, h.configuration.WorkspaceDir, message, gitrepository.Identity{
		Kind:      gitrepository.ActorAgent,
		SessionID: h.configuration.SessionID,
		RunID:     h.configuration.RunID,
		Phase:     transition.Transition,
	}, gitrepository.CommitOptions{})
	if err != nil {
		return nil, edenerrors.Wrap(edenerrors.KindOf(err), "eden_commit_transition: commit", err)
	}

	branch, err := gitrepository.ParseBranchName(h.branch)
	if err != nil {
		return nil, edenerrors.Wrap(edenerrors.KindInvalid, "eden_commit_transition: parse branch", err)
	}
	if _, err := h.repository.Push(ctx, gitrepository.PushOptions{
		Remote:     seedRemoteName,
		LocalRef:   branch,
		DestRef:    branch,
		Credential: h.configuration.ForgeCredential,
	}); err != nil {
		return nil, edenerrors.Wrap(edenerrors.KindOf(err), "eden_commit_transition: push", err)
	}

	status := projectStatusForFSMState(transition.To)
	if _, err := h.projects.UpdateStatus(ctx, h.configuration.ProjectID, gateway.ProjectStatusPatch{
		Status: stringPointer(status),
	}); err != nil {
		return nil, edenerrors.Wrap(edenerrors.KindOf(err), "eden_commit_transition: project status", err)
	}

	result, err := json.Marshal(map[string]string{
		"committed": commit.String(),
		"pushed":    "true",
		"status":    status,
		"state":     transition.To,
	})
	if err != nil {
		return nil, edenerrors.Wrap(edenerrors.KindInternal, "eden_commit_transition: encode result", err)
	}
	return result, nil
}

// commitMessage builds the commit message: a subject line (the caller's, or a synthesized default)
// followed by the canonical fsm: trailer the gate re-derives. The trailer line is the parseable
// provenance; the subject is the human summary.
func (h *commitTransitionHandler) commitMessage(subject string, transition *fsmTransition) string {
	subject = strings.TrimSpace(subject)
	if subject == "" {
		subject = "supervisor: " + transition.Transition
	}
	return subject + "\n\n" + transition.trailerLine()
}

// fsmTransition is a parsed fsm: trailer — the transition the supervisor staged.
type fsmTransition struct {
	From       string
	To         string
	Transition string
	Artifact   string
	Guard      string
}

// trailerLine renders the canonical fsm: trailer for the commit message (the inverse of parseFSMTrailer).
func (t *fsmTransition) trailerLine() string {
	return "fsm: " + t.From + " -> " + t.To + " / " + t.Transition + " / " + t.Artifact + " / " + t.Guard
}

// parseFSMTrailer parses the `fsm: A -> B / transition / artifact / guard` grammar (the same line the
// supervisor's slash-commands print and the gate-commit hook validates). It splits on the 3-character
// " / " delimiter (NOT a bare slash — the artifact segment is a path with bare slashes) into exactly
// four segments, then the states on "->". Every field must be non-empty.
func parseFSMTrailer(line string) (fsmTransition, error) {
	body := strings.TrimSpace(line)
	if !strings.HasPrefix(body, "fsm:") {
		return fsmTransition{}, edenerrors.New(edenerrors.KindInvalid, "eden_commit_transition: trailer must begin with 'fsm:'")
	}
	body = strings.TrimSpace(strings.TrimPrefix(body, "fsm:"))
	segments := strings.Split(body, " / ")
	if len(segments) != 4 {
		return fsmTransition{}, edenerrors.New(edenerrors.KindInvalid, "eden_commit_transition: trailer must be 'fsm: A -> B / transition / artifact / guard' (four ' / '-separated segments)")
	}
	states := strings.SplitN(segments[0], "->", 2)
	if len(states) != 2 {
		return fsmTransition{}, edenerrors.New(edenerrors.KindInvalid, "eden_commit_transition: trailer states must be 'A -> B'")
	}
	transition := fsmTransition{
		From:       strings.TrimSpace(states[0]),
		To:         strings.TrimSpace(states[1]),
		Transition: strings.TrimSpace(segments[1]),
		Artifact:   strings.TrimSpace(segments[2]),
		Guard:      strings.TrimSpace(segments[3]),
	}
	if transition.From == "" || transition.To == "" || transition.Transition == "" || transition.Artifact == "" || transition.Guard == "" {
		return fsmTransition{}, edenerrors.New(edenerrors.KindInvalid, "eden_commit_transition: trailer has an empty field")
	}
	return transition, nil
}

// fsmDocument is the minimal shape of the supervisor's state/fsm.json the server re-validation reads.
type fsmDocument struct {
	Transitions []fsmTransitionRow `json:"transitions"`
}

// fsmTransitionRow is one transition row in state/fsm.json (only the fields the wall reads).
type fsmTransitionRow struct {
	Transition string      `json:"transition"`
	From       []string    `json:"from"`
	To         string      `json:"to"`
	ToWhen     []fsmToWhen `json:"to_when"`
	Guard      fsmGuard    `json:"guard"`
}

// fsmToWhen is a git-predicate-selected destination branch (rule-decision / advance).
type fsmToWhen struct {
	To string `json:"to"`
}

// fsmGuard is a transition's guard (only the id the trailer must match is read here).
type fsmGuard struct {
	ID string `json:"id"`
}

// validateFSMTransition re-validates a claimed transition against the project's OWN state/fsm.json — the
// authoritative server-side wall (the agent never runs `git commit`, so the gate-commit hook never
// fires). It mirrors the hook's FSM-table checks: the transition exists, `from` is a legal source, `to`
// is a declared destination (the static `to` or one of `to_when`), and the guard id matches the
// transition's guard. (The guard's GIT predicate was already enforced by the slash-command before it
// staged; re-evaluating it against the index here is a follow-up hardening.)
func validateFSMTransition(workspaceDir string, transition *fsmTransition) error {
	raw, err := os.ReadFile(filepath.Join(workspaceDir, ".claude", "state", "fsm.json")) //nolint:gosec // workspaceDir is the platform-resolved materialized dir, not request input.
	if err != nil {
		return edenerrors.Wrap(edenerrors.KindUnavailable, "eden_commit_transition: read state/fsm.json", err)
	}
	var document fsmDocument
	if err := json.Unmarshal(raw, &document); err != nil {
		return edenerrors.Wrap(edenerrors.KindInternal, "eden_commit_transition: parse state/fsm.json", err)
	}
	for i := range document.Transitions {
		row := &document.Transitions[i]
		if row.Transition != transition.Transition {
			continue
		}
		if !containsString(row.From, transition.From) {
			return edenerrors.New(edenerrors.KindInvalid, "eden_commit_transition: '"+transition.From+"' is not a legal source for transition '"+transition.Transition+"'")
		}
		if !transitionReaches(row, transition.To) {
			return edenerrors.New(edenerrors.KindInvalid, "eden_commit_transition: '"+transition.To+"' is not a declared destination of transition '"+transition.Transition+"'")
		}
		if row.Guard.ID != transition.Guard {
			return edenerrors.New(edenerrors.KindInvalid, "eden_commit_transition: trailer guard '"+transition.Guard+"' is not transition '"+transition.Transition+"' guard '"+row.Guard.ID+"'")
		}
		return nil
	}
	return edenerrors.New(edenerrors.KindInvalid, "eden_commit_transition: unknown transition '"+transition.Transition+"' (not in state/fsm.json)")
}

// transitionReaches reports whether `to` is a declared destination of a transition row: its static `to`
// or one of its to_when branches' `to`.
func transitionReaches(row *fsmTransitionRow, to string) bool {
	if row.To != "" && row.To == to {
		return true
	}
	for i := range row.ToWhen {
		if row.ToWhen[i].To == to {
			return true
		}
	}
	return false
}

// containsString reports whether needle is in haystack.
func containsString(haystack []string, needle string) bool {
	for _, s := range haystack {
		if s == needle {
			return true
		}
	}
	return false
}

// supervisorInitialState is the FSM's start state (state/fsm.json current_state at materialization) —
// the state the saga's launch handoff projects onto the durable status. It maps to WIZARD.
const supervisorInitialState = "init"

// projectStatusForFSMState maps a supervisor FSM state onto the durable Project.Status the dashboard
// polls — the ONE home for that projection, cited by both the commit-transition tool (the push-model
// projection on every committed transition) and the create saga's launch handoff (the initial
// projection at supervisor-ready). The early lifecycle (the whole interview + planning) reads as
// `wizard`; once the supervisor is `building` work packages it reads as `building`; the terminal
// `done` keeps `building` (there is no distinct done project status yet). An unknown state falls back
// to `wizard` (the safe "still being set up" default).
func projectStatusForFSMState(state string) string {
	switch state {
	case "building", "done":
		return gateway.ProjectStatusBuilding
	default:
		// init, charter_drafted, charter_ratified, product_decomposed, decisions_open,
		// decisions_ruled, planned — the whole setup/interview/planning phase.
		return gateway.ProjectStatusWizard
	}
}
