package composition

import (
	"context"
	"os"
	"path/filepath"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/secrets"
)

// workdir.go is the in-pod clone-on-boot seam — the in-pod analog of the host-side
// projectcreate.Materializer (apps/agentgateway/internal/projectcreate/adapters.go). When the pod is
// the supervisor workload (EDEN_WORKDIR_REPO set), the agent-runtime PID-1 binary clones the seeded
// project repository INTO the pod, overlays the supervisor `.claude` operating manual baked into the
// image, and commits the overlay so the harness starts on a CLEAN tree — exactly what the host-side
// Materializer does, performed IN the pod instead. The pod dogfoods ghcr.io/gophersys/base, which
// carries the system git binary and the pinned claude, so the clone runs locally to the workspace.
//
// EVERYTHING here is GATED on a non-empty EDEN_WORKDIR_REPO. The existing assistant/probe boot — and
// the live host-side demo, whose supervisor template leaves WorkdirRepo unset — never sets it, so the
// existing boot path is byte-unchanged: prepareWorkdir is a no-op that returns the env Workspace
// verbatim when EDEN_WORKDIR_REPO is empty.

// Workdir-clone env keys. These ride the Sandbox.Env (the orchestrator folds WorkdirRepo into them on
// the in-pod path; see libs/go/orchestrator/fold.go). They are NON-secret: the credential travels as
// an OPAQUE secrets.Reference (EDEN_WORKDIR_REPO_CRED), resolved server-side by the same Vault-backed
// Mediator the harness credential uses — the value never enters the env.
const (
	envWorkdirRepo       = "EDEN_WORKDIR_REPO"      // the clone URL of the seeded project repo; "" == no in-pod clone (the existing boot)
	envWorkdirRepoRef    = "EDEN_WORKDIR_REPO_CRED" // the OPAQUE clone-credential reference (a secrets.Reference); resolved server-side
	envWorkdirRepoBranch = "EDEN_WORKDIR_REPO_REF"  // optional branch/tag to check out; "" == the remote's default branch
)

// supervisorManualSourceDir is the BAKED image path the supervisor `.claude` operating manual is
// overlaid FROM. The agent-runtime.Dockerfile COPYs libs/plugins/supervisor/template/.claude here.
// Cross-module go:embed is impossible (the manual lives in the libs submodule, not this app's module),
// so the manual is a baked filesystem path the binary reads at boot — the in-pod analog of the
// host-side Materializer's MaterializerConfig.ManualSourceDir. Overridable via EDEN_SUPERVISOR_MANUAL_DIR
// for the test/integration substrate (a fixture overlay), defaulting to the baked path otherwise.
const supervisorManualSourceDir = "/opt/eden/supervisor-manual"

// envSupervisorManualDir overrides supervisorManualSourceDir (the baked path) — the test/integration
// seam points it at a fixture tree so the clone-on-boot path is provable without the baked image layer.
const envSupervisorManualDir = "EDEN_SUPERVISOR_MANUAL_DIR"

// inPodCloneRemoteName is the local origin name the in-pod clone records (mirrors the host-side
// Materializer's seedRemoteName: the supervisor pushes a transition back to this origin).
const inPodCloneRemoteName = "origin"

// Workdir-overlay git identity + commit message. Mirror the host-side Materializer verbatim (one
// behavior, two call sites): the overlay is a LOCAL bootstrap commit by the Eden PLATFORM actor
// (ActorPlatform — no Eden-Run trailer, no fsm: trailer, so it never trips the supervisor's
// gate-commit hook, which only fires for the agent's own claude-driven commits). The platform, not
// the agent, grafts the operating manual; the supervisor's first transition push publishes it.
const (
	workdirAuthorName          = "Eden Supervisor"
	workdirAuthorEmail         = "supervisor@eden.dev"
	workdirManualCommitMessage = "chore: provision supervisor operating manual (.claude)"
)

// workdirCloner clones the in-pod workspace. It holds the SAME secrets Mediator the harness
// credential resolves through (built once in build) so the clone credential and the harness credential
// share one server-side resolution seam — the value never crosses into this struct. Zero value
// unusable; construct via newWorkdirCloner.
type workdirCloner struct {
	manualSourceDir string
	secrets         secrets.Provider
	backend         gitrepository.Backend
	clock           gitrepository.Clock
}

// newWorkdirCloner constructs the in-pod cloner. PURE: no I/O, no clone — the first git process spawns
// on prepareWorkdir. It binds the production system-git Backend (the pod carries the git binary) and
// the system clock; the secrets Mediator is injected (the SAME one the session factory uses).
func newWorkdirCloner(secretsProvider secrets.Provider) *workdirCloner {
	manualDir := os.Getenv(envSupervisorManualDir)
	if manualDir == "" {
		manualDir = supervisorManualSourceDir
	}
	return &workdirCloner{
		manualSourceDir: manualDir,
		secrets:         secretsProvider,
		backend:         gitrepository.SystemGit(),
		clock:           systemClock{},
	}
}

// prepareWorkdir is the in-pod clone-on-boot entry. When environment.WorkdirRepo is EMPTY it is a
// NO-OP that returns environment.Workspace verbatim — the existing assistant/probe boot is byte-
// unchanged (this is the additive guard). When EDEN_WORKDIR_REPO is set it clones the seeded repo into
// a fresh per-agent directory under the workspace root, overlays the baked supervisor `.claude`
// manual, commits the overlay (ActorPlatform, clean tree), and returns that directory as the harness
// CWD. It mirrors the host-side Materializer.Materialize structure exactly (one behavior, two homes).
func (c *workdirCloner) prepareWorkdir(ctx context.Context, environment *Environment) (string, error) {
	if environment.WorkdirRepo == "" {
		return environment.Workspace, nil // the existing boot: no in-pod clone, the env Workspace verbatim.
	}

	workDir, err := c.cloneTargetDir(environment)
	if err != nil {
		return "", err
	}
	if removeErr := os.RemoveAll(workDir); removeErr != nil {
		return "", errors.Wrap(errors.KindUnavailable, "agent-runtime: clear stale in-pod workspace", removeErr)
	}
	if mkdirErr := os.MkdirAll(workDir, 0o750); mkdirErr != nil {
		return "", errors.Wrap(errors.KindUnavailable, "agent-runtime: create in-pod workspace dir", mkdirErr)
	}

	repository, err := gitrepository.New(
		gitrepository.Config{
			Root:          workDir,
			DefaultAuthor: gitrepository.Identity{Name: workdirAuthorName, Email: workdirAuthorEmail, Kind: gitrepository.ActorPlatform},
		},
		gitrepository.Deps{Backend: c.backend, Secrets: c.secrets, Clock: c.clock},
	)
	if err != nil {
		return "", errors.Wrap(errors.KindInternal, "agent-runtime: build in-pod workspace repository handle", err)
	}

	// 1) Clone the SEEDED project repo (origin -> the project repository) into the supervisor's CWD.
	//    The credential is the OPAQUE EDEN_WORKDIR_REPO_CRED reference; gitrepository resolves it
	//    server-side at the clone (confined to the credential-helper seam — never on argv/log).
	branch, parseErr := parseWorkdirBranch(environment.WorkdirRepoRef)
	if parseErr != nil {
		return "", parseErr
	}
	if _, cloneErr := repository.Clone(ctx, environment.WorkdirRepo, workDir, gitrepository.CloneOptions{
		RemoteName: inPodCloneRemoteName,
		Branch:     branch,
		Credential: c.credentialRef(environment),
	}); cloneErr != nil {
		return "", errors.Wrap(errors.KindOf(cloneErr), "agent-runtime: clone project repo into in-pod workspace", cloneErr)
	}

	// 2) Overlay the supervisor `.claude` operating manual into <workDir>/.claude (the agent's OS). A
	//    clean RemoveAll first so a `.claude` shipped in the cloned repo never collides (os.CopyFS won't
	//    overwrite); CopyFS preserves the execute bit on the command/hook scripts.
	claudeDir := filepath.Join(workDir, ".claude")
	if rmErr := os.RemoveAll(claudeDir); rmErr != nil {
		return "", errors.Wrap(errors.KindUnavailable, "agent-runtime: clear stale .claude overlay", rmErr)
	}
	if overlayErr := os.CopyFS(claudeDir, os.DirFS(c.manualSourceDir)); overlayErr != nil {
		return "", errors.Wrap(errors.KindInternal, "agent-runtime: overlay supervisor .claude manual", overlayErr)
	}

	// 3) Commit the `.claude` overlay so the supervisor starts on a CLEAN working tree (its protocol
	//    REFUSES to run an FSM transition against a dirty tree). A LOCAL bootstrap commit (ActorPlatform,
	//    no fsm: trailer, so it never trips the gate-commit hook); the supervisor's first transition push
	//    publishes it. Mirror the host-side Materializer's stage-then-commit verbatim.
	if _, stageErr := repository.Stage(ctx, workDir, gitrepository.StageOptions{All: true}); stageErr != nil {
		return "", errors.Wrap(errors.KindOf(stageErr), "agent-runtime: stage supervisor .claude overlay", stageErr)
	}
	if _, commitErr := repository.Commit(ctx, workDir, workdirManualCommitMessage,
		gitrepository.Identity{Name: workdirAuthorName, Email: workdirAuthorEmail, Kind: gitrepository.ActorPlatform},
		gitrepository.CommitOptions{}); commitErr != nil {
		return "", errors.Wrap(errors.KindOf(commitErr), "agent-runtime: commit supervisor .claude overlay", commitErr)
	}

	return workDir, nil
}

// cloneTargetDir derives the absolute per-agent clone directory under the workspace root. The root is
// environment.Workspace when set (the provisioned workspace mount), else the conventional /workspace;
// the clone lands in a `supervisor-<agentID>` child so a re-boot of the same agent re-materializes a
// known path (idempotent — RemoveAll clears a stale tree from a crashed run).
func (c *workdirCloner) cloneTargetDir(environment *Environment) (string, error) {
	root := environment.Workspace
	if root == "" {
		root = defaultInPodWorkspaceRoot
	}
	if !filepath.IsAbs(root) {
		return "", errors.New(errors.KindInvalid, "agent-runtime: EDEN_WORKSPACE must be an absolute path for the in-pod clone: "+root)
	}
	name := environment.AgentID
	if name == "" {
		name = "supervisor"
	}
	return filepath.Join(filepath.Clean(root), "supervisor-"+name), nil
}

// credentialRef builds the OPAQUE clone-credential reference from EDEN_WORKDIR_REPO_CRED. An empty
// reference is the zero secrets.Reference (a public/unauthenticated clone — gitrepository skips the
// credential-helper seam); a non-empty one is parsed via secrets.Ref so a malformed reference fails
// loudly at boot rather than silently cloning anonymously.
func (c *workdirCloner) credentialRef(environment *Environment) secrets.Reference {
	if environment.WorkdirRepoCred == "" {
		return secrets.Reference{}
	}
	return secrets.Ref(environment.WorkdirRepoCred)
}

// parseWorkdirBranch maps the optional EDEN_WORKDIR_REPO_REF onto a gitrepository.BranchName. Empty
// yields the zero BranchName (the remote's default branch — the common case).
func parseWorkdirBranch(ref string) (gitrepository.BranchName, error) {
	if ref == "" {
		return gitrepository.BranchName{}, nil
	}
	branch, err := gitrepository.ParseBranchName(ref)
	if err != nil {
		return gitrepository.BranchName{}, errors.Wrap(errors.KindInvalid, "agent-runtime: parse EDEN_WORKDIR_REPO_REF", err)
	}
	return branch, nil
}

// defaultInPodWorkspaceRoot is the conventional workspace root the in-pod clone roots under when
// EDEN_WORKSPACE is unset (the agent-runtime.Dockerfile WORKDIR; the base image provisions here).
const defaultInPodWorkspaceRoot = "/workspace"
