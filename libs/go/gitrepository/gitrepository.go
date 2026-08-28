// Package gitrepository performs local git operations on a WORKED repository
// (02 §1 Monorepo / Workspace): clone (depth/auth), fetch, branch + worktree
// create/remove (the swarm-isolation primitive pairing with FileLease, 02 §2),
// status/diff, stage/commit with a per-actor Author identity (the audit trail,
// 02 §1), and push to a named Remote (eden-authority | byo-authority, ADR-0013).
// It exposes the read surfaces the chat frontend needs (branches, per-session
// file modifications — C23).
//
// Module: github.com/gophersys/libs/go/gitrepository  (go 1.26)
//
// It is PLUMBING (an S2 seam), not the F2 SCM connector (05 §2): it never creates
// PRs, manages webhooks/branch-protection, decides authority_mode/enforcement_level,
// emits DriftEvents, or remediates drift — those are F2/engine concerns it serves.
// There is NEVER a custom merge engine: no Merge/Rebase/CherryPick/Pull; merges go
// through gates server-side (the brief, E3). Pull is split into Fetch + a
// fast-forward-only push so a silent three-way merge cannot happen here.
//
// It does NOT own: pod/workspace provisioning (S2 over workspaceprovider, 02 §1 —
// RemoveWorktree never tears down a pod); credential storage/minting (secrets port
// + vault, 07 §2 — Clone/Fetch/Push carry an opaque secrets.Reference, resolved at
// the operation, never the value in args/logs/Config/Error).
//
// IMPLEMENTATION POSITION (§6 / §7 Q1): the default Backend SHELLS the system git
// binary (SystemGit); it does NOT embed go-git. The vendor seam — the ONLY place a
// git implementation is invoked — is the injected Backend in Deps. This keeps
// worktrees, shallow/partial/sparse clone, and the credential-helper short-lived-token
// seam bit-for-bit identical to the eventual self-hosted git server and to
// byo-authority host behavior (ADR-0013). The split is an implementation detail behind
// a port.
//
// Concurrency: a Repository is safe for concurrent READ use (Status/Diff/Branches/
// Worktrees). Mutating verbs (Stage/Commit, branch/worktree create/remove, Fetch/Push)
// on the SAME worktree are serialized by the library onto one git invocation at a time.
// DISTINCT worktrees of one repository are independent and may mutate concurrently —
// that independence IS the swarm primitive (02 §2): disjoint FileLease sets map to
// disjoint worktrees, so concurrent agents never contend.
package gitrepository

import (
	"context"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// Provisioner provisions the worked checkout and its isolated worktrees. The worktree is
// the swarm-isolation primitive: one worktree per work package, pairing with a disjoint
// FileLease set (02 §2) so concurrent agents never share a write surface. It does NOT
// provision the pod/directory (S2's job, 02 §1). Exactly 3 methods.
type Provisioner interface {
	// Clone materializes the remote into dir from a CloneOptions (Depth/Branch/Filter/
	// Sparse/Credential). dir must already exist (S2 provisioned it). The opaque Credential
	// Reference is resolved server-side via the secrets port and fed to git through the
	// credential-helper seam — the value never enters argv, the URL, a log, or the on-disk
	// remote config (07 §2). Returns the opened *Repository at the cloned HEAD.
	Clone(ctx context.Context, remote, dir string, options CloneOptions) (*Repository, error)

	// AddWorktree materializes a NEW linked worktree (`git worktree add`) at options.Path,
	// checked out to options.Branch (created from options.Start when it does not yet exist).
	// This is THE swarm primitive: each concurrent agent gets its own worktree over its
	// disjoint FileLease set (02 §2). options.Path must be a path S2 already made writable.
	// Returns a *Repository rooted at that path. AlreadyExistsError if the worktree/branch
	// exists.
	AddWorktree(ctx context.Context, options WorktreeOptions) (*Repository, error)

	// RemoveWorktree prunes the linked worktree at path (`git worktree remove` — not a bare
	// rm; the .git/worktrees metadata must be pruned) and, when DeleteBranch, deletes its
	// branch. It does NOT delete the parent checkout or the pod (02 §1) and NEVER removes
	// the main working tree. Idempotent: an already-removed worktree is a no-op, not an
	// error. DirtyWorktreeError when uncommitted changes block removal and Force is false.
	RemoveWorktree(ctx context.Context, path string, options RemoveOptions) error
}

// Inspector is the read surface — the frontend's per-session file modifications + branches
// + in-flight worktrees (C23), the engine's clean-checkout precondition (09 §4), and the
// gate's "what changed" input (04 §8). All methods are read-only, concurrency-safe, and
// touch no network. Exactly 4 methods.
type Inspector interface {
	// Status reports a worktree's working-tree state against HEAD: branch, HEAD commit,
	// ahead/behind vs upstream, clean flag, and the per-path change set. Pure observation;
	// never mutates the index or tree.
	Status(ctx context.Context, worktree string) (Status, error)

	// Diff returns the diff for the requested DiffOptions (working-tree vs HEAD, staged vs
	// HEAD, or commit..commit). NameOnly returns the cheap path list; otherwise a unified
	// patch bounded by MaxBytes (Truncated set at the cap) with binary files flagged not
	// inlined. It is the ONLY content-comparison surface — a gate DECIDES on this diff; the
	// library never resolves a conflict from it.
	Diff(ctx context.Context, options DiffOptions) (Diff, error)

	// Branches lists local (and, when IncludeRemote, remote-tracking) branches with their
	// tip, upstream, and ahead/behind. Read-only.
	Branches(ctx context.Context, options BranchOptions) ([]Branch, error)

	// Worktrees lists the live worktrees of the repository (path, branch, tip, whether it is
	// the main tree). Read-only.
	Worktrees(ctx context.Context) ([]WorktreeInfo, error)
}

// Author authors changes and moves commits across the wire: stage, commit with a per-actor
// identity, fetch in, push out. NO merge surface (the brief): merges go through gates.
// Mutating; one worktree is written by one actor. Push is fast-forward-only by contract.
// Exactly 4 methods.
type Author interface {
	// Stage adds path specs to the index of worktree (`git add`, pathspec-scoped). It
	// accepts an explicit path set (never an implicit "all" with surprises unless
	// StageOptions.All is set) so a swarm worktree stages exactly its FileLease set (02 §2).
	// Mutating; serialized per worktree. Returns the post-stage Status.
	Stage(ctx context.Context, worktree string, options StageOptions) (Status, error)

	// Commit records the staged index AS the given Identity (02 §1 audit). Identity is
	// REQUIRED — a zero Identity is an InvalidRefError; every commit is attributable. The
	// library sets author AND committer from Identity, injects the Eden-Run/Session/Phase
	// trailers for ActorAgent, and returns the new CommitID. An empty index with
	// AllowEmpty=false returns NothingToCommitError. It NEVER signs with or reads a
	// credential — commit identity is attribution, not authentication.
	Commit(ctx context.Context, worktree, message string, author Identity, options CommitOptions) (CommitID, error)

	// Fetch updates remote-tracking refs for the named remote WITHOUT touching the working
	// tree or local branches (the no-merge half of the old "pull"). Credential via the opaque
	// secrets.Reference, over the credential-helper seam. Returns the fetched tips.
	Fetch(ctx context.Context, options FetchOptions) (map[Ref]CommitID, error)

	// Push publishes a local branch tip to a remote Ref. It is FAST-FORWARD-ONLY by
	// contract: a non-ff update returns NonFastForwardError (carrying both tips) and the
	// caller escalates to a gate (E3), never force-pushing — there is NO Force field. Credential
	// via the secrets seam; DeniedError when the host (or a byo-authority branch-protection
	// rule, ADR-0013) rejects the ref. Returns the new tip.
	Push(ctx context.Context, options PushOptions) (PushResult, error)
}

// Clock stamps a Commit's time when Identity.When is zero; keeps New pure and the fake
// deterministic (mirrors observability.Clock / agentsession.Clock).
type Clock interface{ Now() time.Time }

// Config is the immutable, fully-resolved input (the configuration pattern: parsed at the
// edge, frozen). It holds NO live handles and NO secret values.
type Config struct {
	// Root is the worked-checkout directory the Repository is bound to (S2 provisioned it;
	// 02 §1). Worktree paths are validated to live within Root.
	Root string

	// Remotes names the push/fetch destinations by logical name → URL, e.g. {"eden": "…"}
	// (eden-authority) or {"origin": "https://github.com/acme/app.git"} (byo-authority
	// mirror, ADR-0013). URLs only — credentials are a Reference at the operation, never
	// embedded.
	Remotes map[string]string

	// DefaultAuthor is the fallback commit identity (the platform-actor) when an operation
	// supplies only a partial author; per-commit Identity overrides it. Never a credential.
	// Optional.
	DefaultAuthor Identity
}

// Deps is the injected hexagon. New constructs no ports and spawns no process.
type Deps struct {
	// Backend executes the git operations against a path (§6: the system-git impl, or a
	// fake) — the ONLY place a git implementation is invoked (the vendor seam). The library
	// owns argument shaping, path validation, Author stamping, the credential-flow, the
	// fast-forward-only push guard, and result mapping; the Backend owns ONLY running an
	// operation against a path. Required.
	Backend Backend

	// Secrets resolves an operation's opaque Credential Reference to a short-lived Secret at the
	// moment of Clone/Fetch/Push — server-side — so the value reaches git via the
	// credential-helper seam and NEVER enters args, logs, Config, or any Error (07 §2).
	// Required for any networked operation.
	Secrets secrets.Provider

	// Clock stamps a Commit's time when Identity.When is zero; keeps New pure and the fake
	// deterministic. Required.
	Clock Clock
}

// Repository is the concrete handle returned by New — it implements Provisioner, Inspector,
// and Author. It is bound to one worked checkout root (Config.Root); worktrees are addressed
// by path under it. Safe for concurrent reads; serializes mutating verbs per worktree. Zero
// value unusable; construct via New.
type Repository struct {
	root          string
	remotes       map[string]string
	defaultAuthor Identity
	backend       Backend
	secrets       secrets.Provider
	clock         Clock

	// locks serializes mutating verbs PER worktree path: one git invocation at a time on the
	// same worktree, while distinct worktrees mutate independently (the swarm primitive,
	// 02 §2). Concurrent reads take no lock.
	mu    sync.Mutex
	locks map[string]*sync.Mutex
}

// compile-time assertion: *Repository implements all three consumer ports.
var (
	_ Provisioner = (*Repository)(nil)
	_ Inspector   = (*Repository)(nil)
	_ Author      = (*Repository)(nil)
)

// New is the pure constructor spine: no I/O, no clock read, no env read, no process spawn,
// no binary probe, no clone. It validates Config + Deps and returns the concrete
// *Repository (which implements Provisioner + Inspector + Author). The first git operation
// happens only on the first verb call.
//
//nolint:gocritic // contract §2 / 10 §4: New(configuration, dependencies) is the canon spine; Config/Deps pass by value (the frozen, copyable inputs).
func New(configuration Config, dependencies Deps) (*Repository, error) {
	if strings.TrimSpace(configuration.Root) == "" {
		return nil, wrapKind(&InvalidRefError{Ref: "configuration.Root must not be empty"})
	}
	if !filepath.IsAbs(configuration.Root) {
		return nil, wrapKind(&InvalidRefError{Ref: "configuration.Root must be an absolute path: " + configuration.Root})
	}
	if dependencies.Backend == nil {
		return nil, wrapKind(&InvalidRefError{Ref: "dependencies.Backend is required"})
	}
	if dependencies.Clock == nil {
		return nil, wrapKind(&InvalidRefError{Ref: "dependencies.Clock is required"})
	}
	for name, url := range configuration.Remotes {
		if !validRemoteName(name) {
			return nil, wrapKind(&InvalidRefError{Ref: "invalid remote name: " + name})
		}
		if strings.TrimSpace(url) == "" {
			return nil, wrapKind(&InvalidRefError{Ref: "remote " + name + " has an empty URL"})
		}
		if strings.ContainsAny(url, " \t\n") {
			return nil, wrapKind(&InvalidRefError{Ref: "remote " + name + " URL contains whitespace"})
		}
	}

	remotes := make(map[string]string, len(configuration.Remotes))
	for name, url := range configuration.Remotes {
		remotes[name] = url
	}

	return &Repository{
		root:          filepath.Clean(configuration.Root),
		remotes:       remotes,
		defaultAuthor: configuration.DefaultAuthor,
		backend:       dependencies.Backend,
		secrets:       dependencies.Secrets,
		clock:         dependencies.Clock,
		locks:         make(map[string]*sync.Mutex),
	}, nil
}

// Root reports the worked-checkout directory this Repository is bound to.
func (r *Repository) Root() string { return r.root }

// Capabilities reports the injected Backend's declared capabilities (05 §3).
func (r *Repository) Capabilities() Capabilities { return r.backend.Capabilities() }

// worktreeLock returns the per-worktree serialization mutex, creating it on first use. The
// lock keyed on the cleaned path is the "one worktree, one writer" guard; distinct paths get
// distinct locks so distinct worktrees mutate concurrently (the swarm primitive).
func (r *Repository) worktreeLock(path string) *sync.Mutex {
	key := filepath.Clean(path)
	r.mu.Lock()
	defer r.mu.Unlock()
	lock, ok := r.locks[key]
	if !ok {
		lock = &sync.Mutex{}
		r.locks[key] = lock
	}
	return lock
}

// validateWorktree confirms path is the Root or a directory under it — the argv/path-escape
// guard (a worktree must live within the bound checkout, never "../etc"). An empty path
// means the Root itself.
func (r *Repository) validateWorktree(path string) (string, error) {
	if strings.TrimSpace(path) == "" {
		return r.root, nil
	}
	if !filepath.IsAbs(path) {
		return "", wrapKind(&InvalidRefError{Ref: "worktree path must be absolute: " + path})
	}
	clean := filepath.Clean(path)
	if clean == r.root {
		return clean, nil
	}
	relative, err := filepath.Rel(r.root, clean)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return "", wrapKind(&InvalidRefError{Ref: "worktree path escapes Root: " + path})
	}
	return clean, nil
}

// resolveRemote maps a logical remote name to its configured URL, or a NotFoundError. It reads
// the remote map under r.mu so a concurrent SetRemote (which re-points origin for a
// template-copy push) never races the read.
func (r *Repository) resolveRemote(name string) (string, error) {
	if !validRemoteName(name) {
		return "", wrapKind(&InvalidRefError{Ref: "invalid remote name: " + name})
	}
	r.mu.Lock()
	url, ok := r.remotes[name]
	r.mu.Unlock()
	if !ok {
		return "", wrapKind(&NotFoundError{What: "remote " + name})
	}
	return url, nil
}

// resolveCredential resolves an opaque Credential Reference to a short-lived Secret at the moment
// of a network op — server-side, so the value reaches git only via the credential-helper
// seam (07 §2). A zero Reference is a public/local op (no credential). It returns a nil
// Secret for the public case, never (nil, nil) ambiguity for a real reference.
func (r *Repository) resolveCredential(ctx context.Context, reference secrets.Reference, remote string) (*secrets.Secret, error) {
	if reference.IsZero() {
		return nil, nil //nolint:nilnil // a zero Reference is the public/local op: no credential, no error — the documented two-state return.
	}
	if r.secrets == nil {
		return nil, wrapKind(&AuthError{Reference: reference, Remote: remote})
	}
	secret, err := r.secrets.Resolve(ctx, reference)
	if err != nil {
		// The underlying secrets error is preserved in the chain; the gitrepository-typed
		// AuthError carries the ref (loggable), never the value, and classifies the boundary.
		return nil, errors.Wrap(errors.KindUnauthenticated, (&AuthError{Reference: reference, Remote: remote}).Error(), err)
	}
	return secret, nil
}
