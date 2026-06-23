package projectcreate

import (
	"context"
	"os"
	"path/filepath"

	edenerrors "github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/forge"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/secrets"
)

// This file binds the saga's narrow consumer-defined ports (ProjectForge, TemplateSeeder) to the REAL
// libraries (forge.Forge, gitrepository) — the composition-side adapters a production root constructs
// and injects on Deps. They are the ONLY place the saga touches the library surfaces: each translates
// the saga's minimal input into the library call and maps the result/error back. A unit test of the
// saga binds a fake port instead; these adapters' own correctness is proven against the REAL substrate
// in the //go:build integration test.

// ── ProjectForge over forge.Forge ───────────────────────────────────────────────────────────────.

// ForgeAdapter binds a forge.Forge (the production githubadapter) to the saga's ProjectForge port. It
// maps CreateRepositoryInput onto forge.CreateRepoRequest and the resolved forge.Repository back onto
// the saga's RepositoryCoordinates. It owns no state beyond the wrapped forge; safe for concurrent use
// iff the wrapped forge is (the githubadapter is).
type ForgeAdapter struct {
	forge forge.Forge
}

// compile-time assertion: *ForgeAdapter binds the saga's ProjectForge port.
var _ ProjectForge = (*ForgeAdapter)(nil)

// NewForgeAdapter wraps a forge.Forge as the saga's ProjectForge. A nil forge is a wrapped KindInvalid
// (the composition root must inject a real forge). Pure: no I/O.
func NewForgeAdapter(remoteForge forge.Forge) (*ForgeAdapter, error) {
	if remoteForge == nil {
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: NewForgeAdapter requires a non-nil forge.Forge")
	}
	return &ForgeAdapter{forge: remoteForge}, nil
}

// CreateRepository creates the repository via the wrapped forge (idempotent — the githubadapter reads
// an existing repo back via GET on a 422) and maps the result onto RepositoryCoordinates. The
// credential rides the request as an opaque reference, resolved server-side by the forge.
func (a *ForgeAdapter) CreateRepository(ctx context.Context, input CreateRepositoryInput) (RepositoryCoordinates, error) {
	repository, err := a.forge.CreateRepo(ctx, forge.CreateRepoRequest{
		Owner:       input.Owner,
		Name:        input.Name,
		Private:     input.Private,
		Description: input.Description,
		Credential:  input.Credential,
	})
	if err != nil {
		return RepositoryCoordinates{}, edenerrors.Wrap(edenerrors.KindOf(err), "projectcreate: forge create repository", err)
	}
	return RepositoryCoordinates{
		Owner:         repository.Owner,
		Name:          repository.Name,
		CloneURL:      repository.CloneURL,
		DefaultBranch: repository.DefaultBranch,
	}, nil
}

// ── TemplateSeeder over gitrepository ────────────────────────────────────────────────────────────.

// seedRemoteName is the logical remote the seeder re-points from the template to the new repository.
const seedRemoteName = "origin"

// seedCommitMessage is the single seed commit's message (the flatten root commit).
const seedCommitMessage = "seed from template"

// seedAuthorName / seedAuthorEmail stamp the seed commit as the Eden PLATFORM actor (ActorPlatform — a
// system graft, never an agent run): the flatten requires a non-zero Identity, and the platform actor
// is the right principal for a template seed (gitrepository injects NO Eden-Run trailers for it).
const (
	seedAuthorName  = "Eden Platform"
	seedAuthorEmail = "platform@eden.dev"
)

// SeederConfig is the immutable input for the gitrepository-backed seeder. CheckoutRoot is the parent
// directory under which each project's template checkout is materialized (a per-project subdir, so
// concurrent seeds never collide). Required.
type SeederConfig struct {
	// CheckoutRoot is the parent directory the seeder clones each project's template into (a fresh
	// per-project subdirectory). The composition root points it at the workspace scratch area. Required.
	CheckoutRoot string
}

// SeederDeps is the injected hexagon for the seeder: the git Backend (the system-git vendor seam), the
// secrets provider (resolves the push credential server-side), and the Clock the seed commit's time is
// stamped from. They are exactly gitrepository.Deps, threaded through so the seeder builds one
// gitrepository.Repository per seed bound to that project's checkout.
type SeederDeps struct {
	// Backend executes the git operations (gitrepository.SystemGit() in production, a fake in a unit
	// test). Required.
	Backend gitrepository.Backend
	// Secrets resolves the push credential reference to a short-lived secret at the push, server-side.
	// Required for the networked clone/push.
	Secrets secrets.Provider
	// Clock stamps the seed commit's time. Required.
	Clock gitrepository.Clock
}

// Seeder binds gitrepository to the saga's TemplateSeeder port: it clones the template into a fresh
// per-project checkout, flattens its history to a single seed commit, re-points origin at the new
// repository, and pushes the seed into the unborn main (a fast-forward into an empty branch). It is the
// production seeder the composition root constructs; safe for concurrent use across distinct projects
// (each seed builds its own Repository rooted at a distinct per-project directory).
type Seeder struct {
	checkoutRoot string
	backend      gitrepository.Backend
	secrets      secrets.Provider
	clock        gitrepository.Clock
}

// compile-time assertion: *Seeder binds the saga's TemplateSeeder port.
var _ TemplateSeeder = (*Seeder)(nil)

// NewSeeder is the pure constructor for the gitrepository-backed seeder. It validates the wiring and
// returns the concrete *Seeder, doing NO I/O (the first clone happens on the first SeedRepository). A
// missing seam or an empty/relative CheckoutRoot is a wrapped KindInvalid.
//
//nolint:gocritic // SeederConfig is the frozen, copyable composition input; New takes it by value (the spine).
func NewSeeder(configuration SeederConfig, dependencies SeederDeps) (*Seeder, error) {
	switch {
	case configuration.CheckoutRoot == "":
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: SeederConfig.CheckoutRoot is required")
	case !filepath.IsAbs(configuration.CheckoutRoot):
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: SeederConfig.CheckoutRoot must be an absolute path: "+configuration.CheckoutRoot)
	case dependencies.Backend == nil:
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: SeederDeps.Backend is required (the git vendor seam)")
	case dependencies.Secrets == nil:
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: SeederDeps.Secrets is required (the push credential resolver)")
	case dependencies.Clock == nil:
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: SeederDeps.Clock is required")
	}
	return &Seeder{
		checkoutRoot: filepath.Clean(configuration.CheckoutRoot),
		backend:      dependencies.Backend,
		secrets:      dependencies.Secrets,
		clock:        dependencies.Clock,
	}, nil
}

// SeedRepository seeds the new, empty repository from the template, idempotently: clone the template
// into a fresh per-project checkout, flatten to one seed commit, re-point origin at the new repository,
// and push the seed into its unborn main. A non-fast-forward / conflict on the push means origin/main
// already carries content (the repo was already seeded by a prior run) — that is the IDEMPOTENT no-op
// path, returned as a clean success rather than an error, so a saga replay of step 2 converges.
func (s *Seeder) SeedRepository(ctx context.Context, input SeedInput) (SeedResult, error) {
	if input.RepositoryURL == "" {
		return SeedResult{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: SeedRepository requires a RepositoryURL")
	}
	if input.TemplateURL == "" {
		return SeedResult{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: SeedRepository requires a TemplateURL")
	}

	checkout, cleanup, err := s.prepareCheckout(input.ProjectID)
	if err != nil {
		return SeedResult{}, err
	}
	defer cleanup()

	// One Repository handle, rooted at the per-project checkout, drives the whole seed. New is pure; the
	// Config carries no remote yet (Clone records origin, SetRemote re-points it).
	repository, err := gitrepository.New(
		gitrepository.Config{
			Root:          checkout,
			DefaultAuthor: gitrepository.Identity{Name: seedAuthorName, Email: seedAuthorEmail, Kind: gitrepository.ActorPlatform},
		},
		gitrepository.Deps{Backend: s.backend, Secrets: s.secrets, Clock: s.clock},
	)
	if err != nil {
		return SeedResult{}, edenerrors.Wrap(edenerrors.KindInternal, "projectcreate: build seed repository handle", err)
	}

	// 1) Clone the template into the checkout (origin -> template URL). The credential authenticates the
	//    template read (the template may be private); it rides the helper seam, never argv/URL.
	cloned, err := repository.Clone(ctx, input.TemplateURL, checkout, gitrepository.CloneOptions{
		RemoteName: seedRemoteName,
		Credential: input.Credential,
	})
	if err != nil {
		return SeedResult{}, edenerrors.Wrap(edenerrors.KindOf(err), "projectcreate: clone template", err)
	}

	// 2) Flatten the template's history to ONE "seed from template" root commit (the platform actor) so
	//    the template's past does not bleed into the new repository.
	commit, err := cloned.Flatten(ctx, gitrepository.FlattenOptions{
		Message: seedCommitMessage,
		Author:  gitrepository.Identity{Name: seedAuthorName, Email: seedAuthorEmail, Kind: gitrepository.ActorPlatform},
	})
	if err != nil {
		return SeedResult{}, edenerrors.Wrap(edenerrors.KindOf(err), "projectcreate: flatten template history", err)
	}

	// 3) Re-point origin at the NEW repository (in-memory; no git process), so the push publishes the
	//    seed into the new, empty repo rather than back at the template.
	if err := cloned.SetRemote(seedRemoteName, input.RepositoryURL); err != nil {
		return SeedResult{}, edenerrors.Wrap(edenerrors.KindOf(err), "projectcreate: re-point origin at new repository", err)
	}

	// 4) Push the seed into the new repo's unborn main — a fast-forward into an empty branch. A
	//    non-fast-forward / conflict means the repo already has the seed (a prior run) -> idempotent skip.
	mainBranch, err := gitrepository.ParseBranchName(defaultSeedBranch)
	if err != nil {
		return SeedResult{}, edenerrors.Wrap(edenerrors.KindInternal, "projectcreate: parse seed branch", err)
	}
	_, err = cloned.Push(ctx, gitrepository.PushOptions{
		Remote:     seedRemoteName,
		LocalRef:   mainBranch,
		DestRef:    mainBranch,
		Credential: input.Credential,
	})
	if err != nil {
		if isAlreadySeeded(err) {
			// IDEMPOTENT: origin/main already carries the seed (a prior run pushed it). Converge.
			return SeedResult{DefaultBranch: defaultSeedBranch}, nil
		}
		return SeedResult{}, edenerrors.Wrap(edenerrors.KindOf(err), "projectcreate: push seed into new repository", err)
	}

	return SeedResult{DefaultBranch: defaultSeedBranch, CommitID: commit.String()}, nil
}

// defaultSeedBranch is the branch the seed is pushed onto (the template's flattened HEAD branch and the
// new repository's unborn main).
const defaultSeedBranch = "main"

// prepareCheckout makes a fresh, empty per-project checkout directory under CheckoutRoot and returns it
// plus a cleanup that removes the whole tree on return (the seed is published; the local checkout is
// scratch). A pre-existing directory from a crashed prior run is removed first so the clone starts
// clean (the seed is idempotent at the remote, so a discarded local checkout loses nothing).
func (s *Seeder) prepareCheckout(projectID string) (checkout string, cleanup func(), err error) {
	name := slugifyHNS1(projectID)
	if name == "" {
		name = "project"
	}
	checkout = filepath.Join(s.checkoutRoot, "seed-"+name)
	if removeErr := os.RemoveAll(checkout); removeErr != nil {
		return "", func() {}, edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: clear stale seed checkout", removeErr)
	}
	if mkdirErr := os.MkdirAll(checkout, 0o750); mkdirErr != nil {
		return "", func() {}, edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: create seed checkout dir", mkdirErr)
	}
	cleanup = func() {
		// Best-effort scratch removal; a leftover dir is reclaimed by the next run's RemoveAll. A
		// removal fault here is non-fatal (the seed already published), so it is not surfaced.
		_ = os.RemoveAll(checkout) //nolint:errcheck // best-effort scratch cleanup; the next run's RemoveAll reclaims a leftover, so a fault here is non-actionable.
	}
	return checkout, cleanup, nil
}

// isAlreadySeeded reports whether a push error is the idempotent "already seeded" signal: a
// non-fast-forward or a conflict, which means origin/main already carries content. A
// NonFastForwardError (KindConflict) is the canonical case; any KindConflict is treated the same (the
// remote rejected the seed because it is non-empty). Every other error (auth, unavailable, invalid) is
// a real fault the saga must surface.
func isAlreadySeeded(err error) bool {
	if edenerrors.IsType[*gitrepository.NonFastForwardError](err) {
		return true
	}
	return edenerrors.KindOf(err) == edenerrors.KindConflict
}

// ── WorkspaceMaterializer over gitrepository + the supervisor .claude tree ────────────────────────.

// materializeAuthorName / materializeAuthorEmail stamp the clone's local git identity (the supervisor
// stages through its slash-commands; the orchestrator commits — but a local identity keeps git happy).
const (
	materializeAuthorName  = "Eden Supervisor"
	materializeAuthorEmail = "supervisor@eden.dev"
)

// MaterializerConfig is the immutable input for the gitrepository-backed workspace materializer.
type MaterializerConfig struct {
	// WorkspaceRoot is the absolute parent directory each project's PERSISTENT supervisor working
	// directory is created under (it lives for the session, unlike the seeder's scratch). Required.
	WorkspaceRoot string
	// ManualSourceDir is the absolute path to the supervisor `.claude` operating-manual tree overlaid
	// into each workspace (libs/plugins/supervisor/template/.claude). Required.
	ManualSourceDir string
}

// MaterializerDeps is the injected hexagon for the materializer (the gitrepository seam + the credential
// resolver + the clock), exactly gitrepository.Deps threaded through.
type MaterializerDeps struct {
	// Backend executes the git clone (gitrepository.SystemGit() in production). Required.
	Backend gitrepository.Backend
	// Secrets resolves the clone credential reference server-side. Required for the networked clone.
	Secrets secrets.Provider
	// Clock stamps the repository handle. Required.
	Clock gitrepository.Clock
}

// Materializer binds gitrepository + a filesystem overlay to the saga's WorkspaceMaterializer port: it
// clones the seeded project repository into a fresh persistent per-project directory and overlays the
// supervisor's `.claude` operating manual, so the spawned Claude agent finds the repo AND its manual in
// its CWD. The production materializer the composition root constructs; safe for concurrent use across
// distinct projects (each materialization roots at a distinct per-project directory).
type Materializer struct {
	workspaceRoot   string
	manualSourceDir string
	backend         gitrepository.Backend
	secrets         secrets.Provider
	clock           gitrepository.Clock
}

// compile-time assertion: *Materializer binds the saga's WorkspaceMaterializer port.
var _ WorkspaceMaterializer = (*Materializer)(nil)

// NewMaterializer is the pure constructor for the gitrepository-backed workspace materializer. It
// validates the wiring (absolute roots, a manual source that exists) and returns the concrete
// *Materializer, doing NO networked I/O (the first clone happens on the first Materialize). It DOES stat
// the manual source so a misconfigured overlay fails at composition, not at the first launch.
//
//nolint:gocritic // MaterializerConfig is the frozen, copyable composition input; New takes it by value (the spine).
func NewMaterializer(configuration MaterializerConfig, dependencies MaterializerDeps) (*Materializer, error) {
	switch {
	case configuration.WorkspaceRoot == "" || !filepath.IsAbs(configuration.WorkspaceRoot):
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: MaterializerConfig.WorkspaceRoot must be an absolute path: "+configuration.WorkspaceRoot)
	case configuration.ManualSourceDir == "" || !filepath.IsAbs(configuration.ManualSourceDir):
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: MaterializerConfig.ManualSourceDir must be an absolute path: "+configuration.ManualSourceDir)
	case dependencies.Backend == nil:
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: MaterializerDeps.Backend is required (the git vendor seam)")
	case dependencies.Secrets == nil:
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: MaterializerDeps.Secrets is required (the clone credential resolver)")
	case dependencies.Clock == nil:
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: MaterializerDeps.Clock is required")
	}
	if info, err := os.Stat(configuration.ManualSourceDir); err != nil || !info.IsDir() {
		return nil, edenerrors.New(edenerrors.KindInvalid, "projectcreate: MaterializerConfig.ManualSourceDir is not a readable directory: "+configuration.ManualSourceDir)
	}
	return &Materializer{
		workspaceRoot:   filepath.Clean(configuration.WorkspaceRoot),
		manualSourceDir: filepath.Clean(configuration.ManualSourceDir),
		backend:         dependencies.Backend,
		secrets:         dependencies.Secrets,
		clock:           dependencies.Clock,
	}, nil
}

// Materialize clones the seeded project repository into a fresh persistent per-project directory and
// overlays the supervisor `.claude` operating manual. Idempotent: a re-run clears the prior tree and
// re-materializes (the persistent dir is the supervisor's CWD, so a stale one from a crashed run is
// replaced, never appended to).
func (m *Materializer) Materialize(ctx context.Context, input MaterializeInput) (MaterializeResult, error) {
	if input.RepositoryURL == "" {
		return MaterializeResult{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: Materialize requires a RepositoryURL")
	}
	name := slugifyHNS1(input.ProjectID)
	if name == "" {
		name = "project"
	}
	workDir := filepath.Join(m.workspaceRoot, "supervisor-"+name)
	if removeErr := os.RemoveAll(workDir); removeErr != nil {
		return MaterializeResult{}, edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: clear stale supervisor workspace", removeErr)
	}
	if mkdirErr := os.MkdirAll(workDir, 0o750); mkdirErr != nil {
		return MaterializeResult{}, edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: create supervisor workspace dir", mkdirErr)
	}

	repository, err := gitrepository.New(
		gitrepository.Config{
			Root:          workDir,
			DefaultAuthor: gitrepository.Identity{Name: materializeAuthorName, Email: materializeAuthorEmail, Kind: gitrepository.ActorPlatform},
		},
		gitrepository.Deps{Backend: m.backend, Secrets: m.secrets, Clock: m.clock},
	)
	if err != nil {
		return MaterializeResult{}, edenerrors.Wrap(edenerrors.KindInternal, "projectcreate: build supervisor workspace repository handle", err)
	}
	// Clone the SEEDED project repo (origin -> the new repository) into the supervisor's CWD.
	if _, cloneErr := repository.Clone(ctx, input.RepositoryURL, workDir, gitrepository.CloneOptions{
		RemoteName: seedRemoteName,
		Credential: input.Credential,
	}); cloneErr != nil {
		return MaterializeResult{}, edenerrors.Wrap(edenerrors.KindOf(cloneErr), "projectcreate: clone project repo into supervisor workspace", cloneErr)
	}

	// Overlay the supervisor `.claude` operating manual into <workDir>/.claude (the agent's OS). A clean
	// RemoveAll first so a `.claude` shipped in the cloned repo never collides (os.CopyFS won't
	// overwrite); CopyFS preserves the execute bit on the command/hook scripts.
	claudeDir := filepath.Join(workDir, ".claude")
	if rmErr := os.RemoveAll(claudeDir); rmErr != nil {
		return MaterializeResult{}, edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: clear stale .claude overlay", rmErr)
	}
	if overlayErr := os.CopyFS(claudeDir, os.DirFS(m.manualSourceDir)); overlayErr != nil {
		return MaterializeResult{}, edenerrors.Wrap(edenerrors.KindInternal, "projectcreate: overlay supervisor .claude manual", overlayErr)
	}

	return MaterializeResult{WorkDir: workDir}, nil
}
