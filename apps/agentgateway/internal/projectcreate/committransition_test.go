package projectcreate_test

import (
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/eden/apps/agentgateway/internal/projectcreate"
)

// commitClock is a real wall clock for the commit-transition tests (the integration-tagged realClock is
// in a different build lane; this stays unit-lane local).
type commitClock struct{}

func (commitClock) Now() time.Time { return time.Now() }

// runGit runs `git -C dir <args>` and returns its combined output, failing the test on error (a local,
// unit-lane git helper distinct from the integration lane's gitOutput).
func runGit(t *testing.T, dir string, args ...string) string {
	t.Helper()
	out, err := exec.Command("git", append([]string{"-C", dir}, args...)...).CombinedOutput() //nolint:gosec // fixed argv (git + a test-controlled dir + literal flags); no user input.
	if err != nil {
		t.Fatalf("git %v in %s: %v\n%s", args, dir, err, out)
	}
	return string(out)
}

// fsmFixture is a minimal state/fsm.json covering a static-`to` transition (propose-questionnaire),
// another static one (plan), and a `to_when` transition (advance) — enough to exercise every
// destination-resolution path of the server-side wall.
const fsmFixture = `{
  "current_state": "init",
  "transitions": [
    {"transition": "propose-questionnaire", "from": ["init"], "to": "init", "guard": {"id": "charter-not-ratified"}},
    {"transition": "plan", "from": ["decisions_ruled", "product_decomposed"], "to": "planned", "guard": {"id": "no-open-fork"}},
    {"transition": "advance", "from": ["planned", "building"], "to_when": [{"to": "done"}, {"to": "building"}], "guard": {"id": "plan-exists"}}
  ]
}`

// TestParseFSMTrailer proves the fsm: trailer grammar parser accepts the canonical line a transition
// command prints and rejects every malformed shape (the artifact's bare slashes must NOT be split on).
func TestParseFSMTrailer(t *testing.T) {
	t.Parallel()
	good := "fsm: init -> init / propose-questionnaire / init/product/questionnaire/ / charter-not-ratified"
	transition, err := projectcreate.ParseFSMTrailerForTest(good)
	if err != nil {
		t.Fatalf("valid trailer rejected: %v", err)
	}
	if transition.From != "init" || transition.To != "init" || transition.Transition != "propose-questionnaire" ||
		transition.Artifact != "init/product/questionnaire/" || transition.Guard != "charter-not-ratified" {
		t.Fatalf("parsed fields wrong: %+v", transition)
	}

	for _, bad := range []string{
		"",
		"propose-questionnaire", // no fsm: prefix
		"fsm: init -> init / propose-questionnaire / artifact",                // 3 segments
		"fsm: init / propose-questionnaire / artifact / guard",                // states missing ->
		"fsm: init -> init / propose-questionnaire /  / charter-not-ratified", // empty artifact
		"fsm: init -> init / propose-questionnaire / a / b / c",               // 5 segments
	} {
		if _, err := projectcreate.ParseFSMTrailerForTest(bad); err == nil {
			t.Errorf("malformed trailer %q must be rejected", bad)
		}
	}
}

// TestProjectStatusForFSMState proves the one-home FSM-state -> Project.Status projection: the whole
// setup/interview/planning phase reads as wizard; building/done read as building; an unknown state is
// the safe wizard default.
func TestProjectStatusForFSMState(t *testing.T) {
	t.Parallel()
	wizard := []string{"init", "charter_drafted", "charter_ratified", "product_decomposed", "decisions_open", "decisions_ruled", "planned", "bogus"}
	for _, state := range wizard {
		if got := projectcreate.ProjectStatusForFSMStateForTest(state); got != gateway.ProjectStatusWizard {
			t.Errorf("state %q -> %q, want %q", state, got, gateway.ProjectStatusWizard)
		}
	}
	for _, state := range []string{"building", "done"} {
		if got := projectcreate.ProjectStatusForFSMStateForTest(state); got != gateway.ProjectStatusBuilding {
			t.Errorf("state %q -> %q, want %q", state, got, gateway.ProjectStatusBuilding)
		}
	}
}

// TestValidateFSMTransition proves the server-side FSM-table wall against a real state/fsm.json: a legal
// transition passes; an unknown transition, an illegal `from`, an undeclared `to`, and a mismatched
// guard each fail. The to_when destination (advance -> done|building) is accepted.
func TestValidateFSMTransition(t *testing.T) {
	t.Parallel()
	workDir := t.TempDir()
	writeFixtureFSM(t, workDir)

	if err := projectcreate.ValidateFSMTransitionForTest(workDir, "init", "init", "propose-questionnaire", "init/product/questionnaire/", "charter-not-ratified"); err != nil {
		t.Fatalf("legal transition rejected: %v", err)
	}
	if err := projectcreate.ValidateFSMTransitionForTest(workDir, "planned", "done", "advance", "state/fsm.json", "plan-exists"); err != nil {
		t.Fatalf("legal to_when transition rejected: %v", err)
	}
	bad := []struct {
		name                                  string
		from, to, transition, artifact, guard string
	}{
		{"unknown transition", "init", "init", "nope", "a", "g"},
		{"illegal from", "building", "init", "propose-questionnaire", "a", "charter-not-ratified"},
		{"undeclared to", "init", "planned", "propose-questionnaire", "a", "charter-not-ratified"},
		{"mismatched guard", "init", "init", "propose-questionnaire", "a", "wrong-guard"},
	}
	for _, c := range bad {
		if err := projectcreate.ValidateFSMTransitionForTest(workDir, c.from, c.to, c.transition, c.artifact, c.guard); err == nil {
			t.Errorf("%s: must be rejected", c.name)
		}
	}
}

// TestCommitTransitionTool_HappyPath proves the eden_commit_transition host-tool end-to-end on REAL git:
// given a worktree with a staged transition, the tool re-validates, commits AS the agent, fast-forward
// pushes to a real (local bare) remote, and projects the FSM state onto Project.Status. No mocks: real
// `git` via SystemGit, a real bare remote, the fake project projects as the projection sink.
func TestCommitTransitionTool_HappyPath(t *testing.T) {
	t.Parallel()
	if _, err := exec.LookPath("git"); err != nil {
		t.Skip("git not on PATH; the commit-transition real-git test is skipped")
	}
	const projectID = "project-commit-test"
	bareDir, workDir := setupCommitWorktree(t)

	// A staged transition: a new questionnaire file + the (self-loop) fsm.json, as the slash-command
	// would have left them. The tool's Stage(All) picks up the untracked file.
	writeFile(t, filepath.Join(workDir, "init", "product", "questionnaire", "01-scope.md"), "What is in scope?")

	projects := newFakeProjectStore(commitClock{})
	if _, err := projects.Create(context.Background(), gateway.Project{ID: projectID, Status: gateway.ProjectStatusSupervisorReady}); err != nil {
		t.Fatalf("seed project: %v", err)
	}
	const credentialRef = "gh://token"
	provider := secretstest.New(map[string]string{credentialRef: "unused-for-local-remote"})

	tool, err := projectcreate.NewCommitTransitionTool(
		projectcreate.CommitTransitionConfig{
			WorkspaceDir:    workDir,
			ProjectID:       projectID,
			RemoteURL:       bareDir,
			Branch:          "main",
			ForgeCredential: secrets.Ref(credentialRef),
		},
		projectcreate.CommitTransitionDeps{
			Backend:  gitrepository.SystemGit(),
			Secrets:  provider,
			Clock:    commitClock{},
			Projects: projects,
		},
	)
	if err != nil {
		t.Fatalf("NewCommitTransitionTool: %v", err)
	}
	if tool.Name != "eden_commit_transition" || tool.Handler == nil {
		t.Fatalf("host-tool shape wrong: %+v", tool)
	}

	trailer := `{"trailer":"fsm: init -> init / propose-questionnaire / init/product/questionnaire/ / charter-not-ratified"}`
	result, err := tool.Handler(context.Background(), []byte(trailer))
	if err != nil {
		t.Fatalf("commit-transition handler: %v", err)
	}
	var decoded map[string]string
	if err := json.Unmarshal(result, &decoded); err != nil {
		t.Fatalf("decode result %q: %v", result, err)
	}
	if decoded["pushed"] != "true" || decoded["status"] != gateway.ProjectStatusWizard || decoded["committed"] == "" {
		t.Fatalf("result wrong: %v", decoded)
	}

	// The projection landed in the project store.
	stored, err := projects.Get(context.Background(), projectID)
	if err != nil {
		t.Fatalf("get project: %v", err)
	}
	if stored.Status != gateway.ProjectStatusWizard {
		t.Errorf("project status = %q, want wizard", stored.Status)
	}

	assertCommittedAndPushed(t, workDir, bareDir)
}

// assertCommittedAndPushed proves the transition really landed on the worktree HEAD (named + carrying
// the fsm: trailer) and fast-forwarded the bare remote's main to the same commit.
func assertCommittedAndPushed(t *testing.T, workDir, bareDir string) {
	t.Helper()
	headSubject := strings.TrimSpace(runGit(t, workDir, "log", "-1", "--pretty=%s"))
	if !strings.Contains(headSubject, "propose-questionnaire") {
		t.Errorf("HEAD subject %q does not name the transition", headSubject)
	}
	if !strings.Contains(runGit(t, workDir, "log", "-1", "--pretty=%B"), "fsm: init -> init / propose-questionnaire") {
		t.Errorf("commit message missing the fsm: trailer")
	}
	localHead := strings.TrimSpace(runGit(t, workDir, "rev-parse", "HEAD"))
	remoteHead := strings.TrimSpace(runGit(t, bareDir, "rev-parse", "main"))
	if localHead != remoteHead {
		t.Errorf("push did not fast-forward the remote: local %s != remote %s", localHead, remoteHead)
	}
}

// setupCommitWorktree builds a real git worktree with a state/fsm.json + an initial commit, wired to a
// real local BARE remote named origin (the seed remote the tool pushes to). Returns (bareDir, workDir).
func setupCommitWorktree(t *testing.T) (bareDir, workDir string) {
	t.Helper()
	bareDir = t.TempDir()
	runGit(t, bareDir, "init", "--bare", "--initial-branch=main")

	workDir = t.TempDir()
	runGit(t, workDir, "init", "--initial-branch=main")
	runGit(t, workDir, "config", "user.email", "seed@eden.test")
	runGit(t, workDir, "config", "user.name", "Seed")
	runGit(t, workDir, "remote", "add", "origin", bareDir)
	writeFixtureFSM(t, workDir)
	writeFile(t, filepath.Join(workDir, "README.md"), "# project")
	runGit(t, workDir, "add", "-A")
	runGit(t, workDir, "commit", "-m", "seed")
	runGit(t, workDir, "push", "origin", "main")
	return bareDir, workDir
}

// writeFixtureFSM writes the fsm fixture to <workDir>/.claude/state/fsm.json.
func writeFixtureFSM(t *testing.T, workDir string) {
	t.Helper()
	writeFile(t, filepath.Join(workDir, ".claude", "state", "fsm.json"), fsmFixture)
}

// writeFile writes content to path, creating parent dirs.
func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
		t.Fatalf("mkdir %s: %v", filepath.Dir(path), err)
	}
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}
