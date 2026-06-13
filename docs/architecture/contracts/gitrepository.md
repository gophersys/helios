# Contract draft — gitrepository

> Status: Draft for negotiation — Wave 3A; freezes per the ADR-0016 process · 2026-06-12 · Reconciled from independent producer/consumer drafts (09 §4 step 2). The **git-operations port** for worked repositories (C23): clone/fetch, branch + worktree (the swarm-isolation primitive, 02 §2), status/diff, stage/commit with per-actor author identity (02 §1 audit), push to an `authority_mode`-correct remote (ADR-0013), and the frontend read surfaces (branches, per-session file modifications — C23). It is a **library (S2 seam)**, not an F-family connector: it executes *local* git over a `Workspace` (02 §1) and sits beneath the F2 SCM connector (mirror push/pull, PRs, webhooks, branch protection — 05 §2). NEVER a merge engine — merges go through gates (E3, 04 §8). Freezes per the ADR-0016 freeze process; the frozen contract then lands in `libs/go/gitrepository/` and `gitrepositorytest`, and this draft moves to the attic.

## 1. Scope

`gitrepository` is the port that performs **local git operations on a worked repository** (C23):
clone (depth/auth options), fetch, branch and **worktree create/remove** (the swarm-isolation
primitive that pairs with `FileLease`, 02 §2), status/diff, stage/commit with a per-actor author
identity (the 02 §1 audit trail), push to a named remote (eden-authority or byo-authority per
ADR-0013), and the read surfaces the frontend needs (branch list, per-session file modifications —
C23).

It owns exactly five things, split across **three small interfaces** (the ≤5-method ceiling, 10 §9),
each accepted by the call-site role that drives it:

1. **Provisioning** — `Clone` (depth/auth options), `AddWorktree`/`RemoveWorktree` over an existing
   checkout. The worktree is one work package's isolated write surface (one worktree ⇄ one
   `FileLease` set ⇄ one agent, 02 §2 / 07 §3) — driven by the orchestrator/session-service.
2. **Inspection (the read surface)** — `Status`, `Diff`, `Branches`, `Worktrees` — the frontend's
   per-session file modifications + branch picker + in-flight worktree view (C23) and the engine's
   "is the worktree clean?" precondition (09 §4) — driven by the chat backend and gates.
3. **Authoring** — `Stage` + `Commit` with a caller-supplied `Author` identity (agent-run vs human,
   the audit identity), `Fetch`, `Push` to a named remote with credentials resolved via the frozen
   `secrets` port — driven by the engine.

It explicitly does **not** own (the consumer must not expect these here):

- **Merge.** There is **NEVER a custom merge engine** (the brief, E3): merges go through gates
  server-side. The surface has no `Merge`/`Rebase`/`CherryPick`/`Pull`/`Reset --hard`/`Force`.
  `Pull` is split into `Fetch` + an explicit, **fast-forward-only** branch update so a silent
  three-way merge can never happen here. A divergence surfaces as `NonFastForwardError` (carrying
  both tips) or `ConflictKind`/`ConflictError` (read-only visibility) — every one a *signal to
  escalate to a gate* (E3, 04 §8), never an input to an in-library three-way merge.
- **Remote SCM surface** — PR/MR creation, webhooks, commit status, branch protection, identity
  mapping: the **F2 SCM connector** (05 §2). This port `Push`es to a named `Remote`; what that
  remote *is* (an eden-authority host, a GitHub mirror) and what gates fire is F2/engine policy.
- **Authority / drift / remediation policy** — `authority_mode`, `enforcement_level`, `DriftEvent`
  emission and adopt/revert/fork (ADR-0013, 05 §5) are F2/engine concerns; this library is the
  mechanical `git status`/`diff`/`fetch` the drift detector *calls*.
- **Workspace/pod provisioning** — the directory a worktree lives in is provisioned by **S2 over
  `workspaceprovider`** (02 §1); this library assumes a filesystem path exists and operates within
  it. It creates no container and `RemoveWorktree` never tears down the pod.
- **Credential storage/minting** — the `secrets` port + vault (07 §2). `Clone`/`Fetch`/`Push` carry
  an opaque `secrets.Reference`, resolved server-side at the operation; the raw value never enters
  the `Config`, an argument, a log, or an `Error`.

It cites, never redefines: `Monorepo` / `Workspace` / `FileLease` / `Run` / `DriftEvent` (02 §1–2);
`eden-authority` / `byo-authority` / `enforcement_level` (ADR-0013, 05 §2 F2); `Secret` /
`Reference` (secrets.md, 07 §2); `Error` / `Kind` / `AsType` (errors.md).

## 2. Contract

> **Implementation position (the brief asks for one; §6 defends it): shell the system `git`
> binary, do NOT embed `go-git` — but behind a single injected `Backend` seam, so the choice is a
> `Deps` decision, not a contract commitment.** The brief's load-bearing operations — `git worktree
> add/remove` (the swarm primitive, with no faithful `go-git` equivalent), shallow/partial/sparse
> clone (`--depth`, `--filter=blob:none`), and the `credential.helper` short-lived-token seam — are
> mature in the binary and immature/absent in `go-git`, and shelling the same `git` the eventual
> self-hosted server, CI runners, and byo-authority hosts run gives bit-for-bit fidelity (ADR-0013).
> The `Backend` seam keeps the door open for a degenerate read-only `go-git` backend later, and lets
> the conformance suite prove the whole surface against a **real `git` binary** (ADR-0016). See §7 Q1.

```go
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
// binary; it does NOT embed go-git. The vendor seam — the ONLY place a git
// implementation is invoked — is the injected Backend in Deps. This keeps worktrees,
// shallow/partial/sparse clone, and the credential-helper short-lived-token seam
// bit-for-bit identical to the eventual self-hosted git server and to byo-authority
// host behavior (ADR-0013). The split is an implementation detail behind a port.
//
// Concurrency: a Repository is safe for concurrent READ use (Status/Diff/Branches/
// Worktrees/Resolve). Mutating verbs (Stage/Commit, branch/worktree create/remove,
// Fetch/Push) on the SAME worktree are serialized by the library onto one git
// invocation at a time. DISTINCT worktrees of one repository are independent and may
// mutate concurrently — that independence IS the swarm primitive (02 §2): disjoint
// FileLease sets map to disjoint worktrees, so concurrent agents never contend.
// Close is idempotent.
package gitrepository

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// ── Value types: identities, refs, the audit-bearing author ──────────────────

// CommitID is a full 40/64-hex object id (sha-1 or sha-256). Loggable; comparable;
// usable as a map key. The zero value is the invalid/unborn commit (a fresh branch
// with no commits). It is NEVER abbreviated in this surface — abbreviation is a UI
// concern.
type CommitID struct{ hex string }

func (c CommitID) String() string { return c.hex }
func (c CommitID) IsZero() bool   { return c.hex == "" }

// BranchName is a validated short branch name ("feature/x", not
// "refs/heads/feature/x"). ParseBranchName rejects names git would reject (no "..",
// no leading "-", no control chars — the injection surface when names reach an
// argv). Loggable; comparable.
type BranchName struct{ name string }

// ParseBranchName validates and constructs a BranchName. PURE; no I/O. Returns a
// wrapped InvalidRefError (errors.AsType) for a name git refuses.
func ParseBranchName(s string) (BranchName, error)

func (b BranchName) String() string { return b.name }
func (b BranchName) IsZero() bool   { return b.name == "" }

// Ref names a thing a fetch/push targets: a branch and the named remote it lives on.
// The per-project authority_mode (ADR-0013) decides which remote a Ref resolves
// against UPSTREAM, not here — this is a value, not a policy.
type Ref struct {
	Remote string     // the configured remote name, e.g. "eden" (authority) or "origin" (byo mirror)
	Branch BranchName
}

// Identity is the per-actor commit author/committer stamp — the load-bearing 02 §1
// distinction between an agent run and a human. It is supplied PER COMMIT (one
// repository commits as different actors over its life), never frozen at Open. Kind
// classifies the principal so the audit trail distinguishes an agent Run from a
// human WITHOUT parsing a free-text name; for an AgentRun the library injects the
// Eden-Run-ID / Eden-Session-ID / Eden-Phase commit trailers, reconciling the commit
// log with the append-only audit log (07 §7) and the Run provenance chain (03 §5).
// Name+Email are the git author identity; the Eden keys correlate. NEVER a credential.
type Identity struct {
	Name      string    // git author/committer name, e.g. "Eden Agent (implement)" or "Mateo Segura"
	Email     string    // git author/committer email
	When      time.Time // zero == Clock.Now() (deterministic in tests)
	Kind      ActorKind // Human | Agent | Platform — the audit classification (selects the trailer set)
	RunID     string    // Agent: the Run (02 §2) this commit belongs to; "" otherwise
	SessionID string    // Agent: the agentsession id; "" otherwise
	Phase     string    // Agent: the pipeline phase, e.g. "implement"; "" otherwise
}

func (i Identity) IsZero() bool { return i.Name == "" && i.Email == "" }

type ActorKind uint8

const (
	ActorHuman    ActorKind = iota // a person committed through the UI/editor (02 §1)
	ActorAgent                     // an agent Run (gets Eden-Run-ID/Session/Phase trailers)
	ActorPlatform                  // an Eden system commit (e.g. a graft); no Eden-Run trailer
)

// ── The three ports a consumer holds ──────────────────────────────────────────
// A *Repository (returned by New) implements all three; each consumer ACCEPTS the
// narrow interface its call site needs (return-concrete / accept-interface, 10 §9).
// Each interface is ≤5 methods. Worktrees are addressed by their on-disk path under
// the bound Root.

// Provisioner provisions the worked checkout and its isolated worktrees. The
// worktree is the swarm-isolation primitive: one worktree per work package, pairing
// with a disjoint FileLease set (02 §2) so concurrent agents never share a write
// surface. It does NOT provision the pod/directory (S2's job, 02 §1). Exactly 3
// methods.
type Provisioner interface {
	// Clone materializes the remote into dir from a CloneOptions (Depth/Branch/
	// Filter/Sparse/Auth). dir must already exist (S2 provisioned it). The opaque
	// Auth Reference is resolved server-side via the secrets port and fed to git
	// through the credential-helper seam — the value never enters argv, the URL, a
	// log, or the on-disk remote config (07 §2). Returns the opened *Repository at
	// the cloned HEAD. Errors: AuthError (credential rejected, carries the ref never
	// the value); UnavailableError (host unreachable — retryable).
	Clone(ctx context.Context, remote string, dir string, options CloneOptions) (*Repository, error)

	// AddWorktree materializes a NEW linked worktree (`git worktree add`) at
	// options.Path, checked out to options.Branch (created from options.Start when it
	// does not yet exist). This is THE swarm primitive: each concurrent agent gets its
	// own worktree over its disjoint FileLease set (02 §2), so there is no shared index
	// to contend and "overlapping leases are a planning error, not a merge problem"
	// holds mechanically. options.Path must be a path S2 already made writable. Returns
	// a *Repository rooted at that path. AlreadyExistsError if the worktree/branch
	// exists.
	AddWorktree(ctx context.Context, options WorktreeOptions) (*Repository, error)

	// RemoveWorktree prunes the linked worktree at path (`git worktree remove` — not a
	// bare rm; the .git/worktrees metadata must be pruned) and, when DeleteBranch,
	// deletes its branch. It does NOT delete the parent checkout or the pod (02 §1) and
	// NEVER removes the main working tree. Idempotent: an already-removed worktree is a
	// no-op, not an error. DirtyWorktreeError when uncommitted changes block removal and
	// Force is false.
	RemoveWorktree(ctx context.Context, path string, options RemoveOptions) error
}

// Inspector is the read surface — the frontend's per-session file modifications +
// branches + in-flight worktrees (C23), the engine's clean-checkout precondition
// (09 §4), and the gate's "what changed" input (04 §8). All methods are read-only,
// concurrency-safe, and touch no network. Exactly 4 methods.
type Inspector interface {
	// Status reports a worktree's working-tree state against HEAD: branch, HEAD commit,
	// ahead/behind vs upstream, clean flag, and the per-path change set — the
	// per-session file-modification rail the chat polls (C23) and the engine's
	// clean-checkout precondition (09 §4). Pure observation; never mutates the index or
	// tree.
	Status(ctx context.Context, worktree string) (Status, error)

	// Diff returns the diff for the requested DiffOptions (working-tree vs HEAD, staged
	// vs HEAD, or commit..commit — the gate's "what changed" input and the frontend's
	// diff view). NameOnly returns the cheap path list; otherwise a unified patch
	// bounded by MaxBytes (Truncated set at the cap) with binary files flagged not
	// inlined. It is the ONLY content-comparison surface — a gate DECIDES on this diff;
	// the library never resolves a conflict from it.
	Diff(ctx context.Context, options DiffOptions) (Diff, error)

	// Branches lists local (and, when IncludeRemote, remote-tracking) branches with
	// their tip, upstream, and ahead/behind — the frontend branch picker and the
	// release-cycle view (C9, C23). Read-only.
	Branches(ctx context.Context, options BranchOptions) ([]Branch, error)

	// Worktrees lists the live worktrees of the repository (path, branch, tip, whether
	// it is the main tree) — the engine's view of in-flight swarm packages and the
	// dashboard's "what is being worked" surface (C23). Read-only.
	Worktrees(ctx context.Context) ([]WorktreeInfo, error)
}

// Author authors changes and moves commits across the wire: stage, commit with a
// per-actor identity, fetch in, push out. NO merge surface (the brief): merges go
// through gates. Mutating; one worktree is written by one actor. Push is
// fast-forward-only by contract. Exactly 4 methods.
type Author interface {
	// Stage adds path specs to the index of worktree (`git add`, pathspec-scoped). It
	// accepts an explicit path set (never an implicit "all" with surprises unless
	// StageOptions.All is set) so a swarm worktree stages exactly its FileLease set
	// (02 §2). Mutating; serialized per worktree. Returns the post-stage Status for a
	// flat call site.
	Stage(ctx context.Context, worktree string, options StageOptions) (Status, error)

	// Commit records the staged index AS the given Identity (02 §1 audit: agent runs vs
	// humans). Identity is REQUIRED — a zero Identity is an InvalidRefError; every commit
	// is attributable. The library sets author AND committer from Identity, injects the
	// Eden-Run/Session/Phase trailers for ActorAgent, and returns the new CommitID. An
	// empty index with AllowEmpty=false returns NothingToCommitError (a clean no-op
	// signal, not a noisy failure). It NEVER signs with or reads a credential — commit
	// identity is attribution, not authentication.
	Commit(ctx context.Context, worktree string, message string, author Identity, options CommitOptions) (CommitID, error)

	// Fetch updates remote-tracking refs for the named remote WITHOUT touching the
	// working tree or local branches (the no-merge half of the old "pull"). Auth via
	// the opaque secrets.Reference, over the credential-helper seam. A read-only-
	// credential fetch is the drift detector's observation primitive (advisory mode,
	// ADR-0013). Returns the fetched tips.
	Fetch(ctx context.Context, options FetchOptions) (map[Ref]CommitID, error)

	// Push publishes a local branch tip to a remote Ref — to eden-authority or a
	// byo-authority mirror per ADR-0013; this port pushes, it does not decide which the
	// remote IS. It is FAST-FORWARD-ONLY by contract: a non-ff update returns
	// NonFastForwardError (carrying both tips) and the caller escalates to a gate (E3),
	// never force-pushing — there is NO Force field. Auth via the secrets seam;
	// DeniedError when the host (or a byo-authority branch-protection rule, ADR-0013)
	// rejects the ref. Returns the new tip.
	Push(ctx context.Context, options PushOptions) (PushResult, error)
}

// ── The constructor spine (10 §4) — PURE ──────────────────────────────────────

// New is the pure constructor spine: no I/O, no clock read, no env read, no process
// spawn, no binary probe, no clone. It validates Config + Deps and returns the
// concrete *Repository (which implements Provisioner + Inspector + Author). The first
// git operation happens only on the first verb call.
func New(configuration Config, dependencies Deps) (*Repository, error) { return nil, nil }

// Repository is the concrete handle returned by New — it implements Provisioner,
// Inspector, and Author. It is bound to one worked checkout root (Config.Root);
// worktrees are addressed by path under it. Safe for concurrent reads; serializes
// mutating verbs per worktree. Zero value unusable; construct via New.
type Repository struct{ /* unexported */ }

// Config is the immutable, fully-resolved input (the configuration pattern: parsed at
// the edge, frozen). It holds NO live handles and NO secret values.
type Config struct {
	// Root is the worked-checkout directory the Repository is bound to (S2 provisioned
	// it; 02 §1). Worktree paths are validated to live within Root.
	Root string

	// Remotes names the push/fetch destinations by logical name → URL, e.g.
	// {"eden": "..."} (eden-authority) or {"origin": "https://github.com/acme/app.git"}
	// (byo-authority mirror, ADR-0013). The per-project authority_mode decision is made
	// UPSTREAM and arrives as this resolved map; this library applies it, it does not
	// decide it. URLs only — credentials are a Reference at the operation, never embedded.
	Remotes map[string]string

	// DefaultAuthor is the fallback commit identity (the platform-actor) when an
	// operation supplies only a partial author; per-commit Identity overrides it.
	// Never a credential. Optional.
	DefaultAuthor Identity
}

// Deps is the injected hexagon. New constructs no ports and spawns no process.
type Deps struct {
	// Backend executes the git operations against a path (§6: the system-git impl, or a
	// fake) — the ONLY place a git implementation is invoked (the vendor seam, 05 §1
	// spirit). The library owns argument shaping, path validation, Author stamping, the
	// credential-flow, the fast-forward-only push guard, and result mapping; the Backend
	// owns ONLY running an operation against a path. Required.
	Backend Backend

	// Secrets resolves an operation's opaque Auth Reference to a short-lived Secret at
	// the moment of Clone/Fetch/Push — server-side — so the value reaches git via the
	// credential-helper seam and NEVER enters args, logs, Config, or any Error (07 §2).
	// Required for any networked operation.
	Secrets secrets.Provider

	// Clock stamps a Commit's time when Identity.When is zero; keeps New pure and the
	// fake deterministic (mirrors observability.Clock / agentsession.Clock).
	Clock Clock
}

type Clock interface{ Now() time.Time }

// ── Options & value types (plain, copyable, zero-safe) ─────────────────────────

// CloneOptions carries the depth/auth/branch/sparse knobs for Clone.
type CloneOptions struct {
	Depth      int               // 0 == full history; >0 == shallow `--depth=N` (cheap PoC clone, C2/C19)
	Branch     BranchName        // single-branch checkout; zero == the remote's default branch
	Filter     string            // partial-clone filter, e.g. "blob:none" (lazy blobs for large repos); "" == none
	Sparse     []string          // sparse-checkout path set; nil == full tree
	Auth       secrets.Reference // OPAQUE; resolved at the operation, never on argv/URL/log
	RemoteName string            // the local name for the origin remote, e.g. "eden" or "origin"
}

// WorktreeOptions creates a linked worktree (the isolation primitive, 02 §2).
type WorktreeOptions struct {
	Path   string     // the new worktree directory (the agent's CWD; S2 owns its lifecycle, 02 §1)
	Branch BranchName // the branch this worktree checks out
	Start  string     // create Branch from this revision when it does not yet exist; "" == Branch must exist
}

// RemoveOptions controls worktree pruning.
type RemoveOptions struct {
	DeleteBranch bool // also delete the worktree's branch (work-package cleanup)
	Force        bool // remove even with uncommitted changes (engine-controlled); else DirtyWorktreeError
}

// DiffOptions selects what Diff compares. Mode picks working-tree/staged/commit..commit.
type DiffOptions struct {
	Worktree string   // the worktree to diff (DiffWorkingVsHead / DiffStagedVsHead)
	Mode     DiffMode
	From, To string   // commit..commit revisions for DiffCommits; ignored otherwise
	Paths    []string // optional pathspec scoping (a worktree diffs its lease set)
	NameOnly bool     // path list only (the cheap file-modification list)
	MaxBytes int64    // bound the patch (0 == a sane default cap; never unbounded)
}

type DiffMode uint8

const (
	DiffWorkingVsHead DiffMode = iota // unstaged + staged vs HEAD (the chat's live view)
	DiffStagedVsHead                  // index vs HEAD (what a Commit would record)
	DiffCommits                       // From..To (a gate comparing a Run's branch to base)
)

// BranchOptions / StageOptions / CommitOptions / FetchOptions / PushOptions are the
// per-call inputs.
type BranchOptions struct{ IncludeRemote bool }
type StageOptions struct {
	Paths []string // explicit paths (a worktree stages exactly its FileLease set)
	All   bool     // empty Paths + All == stage all modified/untracked
}
type CommitOptions struct {
	AllowEmpty bool // permit a commit with an empty index (rare; e.g. a checkpoint/marker commit)
}
type FetchOptions struct {
	Remote string            // logical name from Config.Remotes
	Refs   []Ref             // the refs to update; nil == all configured for the remote
	Auth   secrets.Reference // OPAQUE; read-only credential for the drift-observation path
	Prune  bool              // prune deleted remote refs
}
type PushOptions struct {
	Remote   string            // logical name from Config.Remotes (eden- or byo-authority, ADR-0013)
	LocalRef BranchName        // the local branch tip to publish
	DestRef  BranchName        // the remote branch; zero == same as LocalRef
	Auth     secrets.Reference // OPAQUE; resolved at the push
	// NOTE: there is NO Force field — a non-fast-forward push returns NonFastForwardError
	// and the caller escalates to a gate (E3); force-with-lease is a governed act, never
	// a library affordance (the no-merge boundary, §6).
}

// Status is a worktree's working-tree snapshot — the gate input and the chat's
// file-modification panel (C23). A plain value; copyable; zero-safe.
type Status struct {
	Branch   BranchName   // the checked-out branch (zero == detached HEAD)
	Head     CommitID     // HEAD commit (zero == unborn branch, no commits yet)
	Upstream Ref          // the configured upstream (zero Ref == none)
	Ahead    int          // commits ahead of upstream (release-cycle view, C9)
	Behind   int          // commits behind upstream (drift signal, 05 §5)
	Clean    bool         // true == no staged, unstaged, or untracked changes
	Changes  []FileChange // per-path change set (the per-session file modifications, C23)
}

// FileChange is one path's state — the row the frontend renders per modified file.
type FileChange struct {
	Path     string     // repo-relative path (the new path for a rename)
	OldPath  string     // the prior path for a rename/copy; "" otherwise
	Status   ChangeKind // Added | Modified | Deleted | Renamed | Untracked | Conflicted
	Staged   bool       // true == change is in the index; false == working-tree only
	IsBinary bool       // binary content (the diff is a flag, not text)
}

type ChangeKind uint8

const (
	ChangeAdded ChangeKind = iota
	ChangeModified
	ChangeDeleted
	ChangeRenamed
	ChangeUntracked
	ChangeConflicted // reported for VISIBILITY (a gate sees a conflicting state); NEVER resolved here
)

// Diff is a bounded diff result — the gate's "what changed" input and the chat's diff
// view. Files are summarized; hunks are capped so a runaway generated file cannot blow
// the read surface.
type Diff struct {
	Files     []FileDiff // per-file; NameOnly populates Path + Status only
	Truncated bool       // true == MaxBytes/hunk cap hit; the frontend offers "view full" via a paged fetch
}

type FileDiff struct {
	Path                     string
	OldPath                  string     // old path on a rename
	Status                   ChangeKind
	IsBinary                 bool
	Hunks                    []Hunk     // empty for binary, NameOnly, or stat-only
	AddedLines, RemovedLines int
}

type Hunk struct {
	OldStart, OldLines, NewStart, NewLines int
	Text                                   string // the unified-diff body for this hunk (bounded)
}

// Branch is one ref with its tip — the frontend branch picker (C9, C23).
type Branch struct {
	Name          BranchName
	Tip           CommitID
	IsRemote      bool
	Upstream      Ref // zero Ref == no upstream
	Ahead, Behind int
}

// WorktreeInfo is one live worktree (Worktrees).
type WorktreeInfo struct {
	Path   string
	Branch BranchName
	Tip    CommitID
	IsMain bool // the primary working tree (never removable via RemoveWorktree)
}

// PushResult reports the pushed Ref's new tip and whether it was a no-op.
type PushResult struct {
	Ref      Ref
	Tip      CommitID // the remote's new tip
	UpToDate bool     // true == already at the local tip (a clean no-op, not a failure)
}

// ── The lower seam: Backend (the ONLY place a git implementation runs) ────────

// Backend executes git operations against a path — the §6 default SHELLS the system
// git binary, or a fake. It is THIN: the library owns path validation, argument
// shaping, Author stamping, the credential-flow (Secret.Use at the helper seam), the
// fast-forward-only push guard, and result mapping into the value types above; the
// Backend owns ONLY the raw operation. The credential-helper environment is injected
// here, by the library, confined to the child process — never Eden's env. cred is nil
// for a public/local op; when set it is the resolved, un-printable short-lived Secret
// the Backend exposes to git via a credential helper — confined to Secret.Use, never
// argv (07 §2). Exactly 5 methods.
type Backend interface {
	// Provision runs clone / worktree-add / worktree-remove (the binary surface, with
	// --depth / git worktree). cred is set only for a clone that authenticates.
	Provision(ctx context.Context, op ProvisionOp, cred *secrets.Secret) (ProvisionResult, error)

	// Inspect runs the read surface (status / diff / branches / worktrees). Pure-local;
	// no credential.
	Inspect(ctx context.Context, op InspectOp) (InspectResult, error)

	// Author runs stage / commit. The library has already validated and stamped Identity
	// (author+committer+trailers); the Backend records it. Pure-local; no credential.
	Author(ctx context.Context, op AuthorOp) (AuthorResult, error)

	// Transfer runs fetch / push (the binary network surface). cred is the resolved
	// short-lived Secret confined to Secret.Use at the credential-helper seam; the
	// library enforces fast-forward-only on push and classifies a rejection.
	Transfer(ctx context.Context, op TransferOp, cred *secrets.Secret) (TransferResult, error)

	// Capabilities declares what this Backend supports (shallow clone, linked worktrees,
	// partial clone) so the library degrades gracefully (05 §3) and the conformance suite
	// verifies the declaration is truthful (05 §6) — a Backend declaring a capability it
	// does not deliver fails the suite.
	Capabilities() Capabilities
}

// ProvisionOp / InspectOp / AuthorOp / TransferOp are the normalized, already-validated
// operation descriptors the library hands the Backend (the contract fixes the SEAM and
// the credential-confinement rule, not the Backend's internal request shape; the full
// field set lands with the implementation). They carry NO secret value — the credential
// rides the separate *secrets.Secret argument, confined to Secret.Use.
type (
	ProvisionOp struct{ /* kind + validated paths/refs/depth/filter/sparse (no secret) */ }
	InspectOp   struct{ /* kind + worktree + refs/bounds (no secret) */ }
	AuthorOp    struct{ /* kind + worktree + stamped Identity + paths/message (no secret) */ }
	TransferOp  struct{ /* kind + remote URL + refs + ff-only flag (no secret) */ }
)
type (
	ProvisionResult struct{ /* opened-repo / worktree metadata */ }
	InspectResult   struct{ /* maps to Status / Diff / []Branch / []WorktreeInfo */ }
	AuthorResult    struct{ /* the new CommitID */ }
	TransferResult  struct{ /* the moved Ref tips */ }
)

// Capabilities is the Backend's declaration (05 §3). DATA, not code.
type Capabilities struct {
	ShallowClone   bool // --depth supported
	LinkedWorktree bool // `git worktree` supported (the isolation primitive)
	PartialClone   bool // --filter partial clone supported
}

// ── Errors (typed, errors.AsType-first, aligned with errors.md) ───────────────
//
// Each is a distinct type carrying the offending ref/path/remote — NEVER a credential,
// NEVER raw stderr. The Backend/library return them wrapped with %w so callers branch
// on type across git's stderr rewordings, not by string match. Each exposes Kind() so
// the transport boundary's exhaustive switch errors.KindOf(err) classifies without
// string matching (errors.md §5; 10 §9).
type (
	// InvalidRefError reports a malformed branch name / revision (the argv-injection
	// guard rejected it) — or a zero Identity on Commit, or a worktree path outside Root.
	InvalidRefError struct{ Ref string }
	// NotFoundError reports an unknown repository dir, revision, ref, remote, or worktree.
	NotFoundError struct{ What string }
	// AlreadyExistsError reports a branch/worktree create over an existing one.
	AlreadyExistsError struct{ What string }
	// NothingToCommitError reports a Commit with an empty index and AllowEmpty=false —
	// a clean no-op signal, not a noisy failure.
	NothingToCommitError struct{}
	// NonFastForwardError reports a Push that is not a fast-forward — the signal to
	// ESCALATE TO A GATE (never to force-push or in-library merge). Carries both tips.
	NonFastForwardError struct {
		Ref           Ref
		Local, Remote CommitID
	}
	// ConflictError reports a working-tree state git considers conflicted (reported for a
	// gate's VISIBILITY; this library never resolves it).
	ConflictError struct{ Paths []string }
	// DirtyWorktreeError reports a mutating op blocked by uncommitted changes where a
	// clean tree is required (e.g. RemoveWorktree without Force).
	DirtyWorktreeError struct{ Worktree string }
	// AuthError reports a credential failure on a network verb (carries the ref, NEVER
	// the value) — the secrets/vault path (07 §2).
	AuthError struct {
		Reference secrets.Reference
		Remote    string
	}
	// DeniedError reports a host rejection (e.g. branch protection in byo-authority
	// enforced mode, ADR-0013) — distinct from an auth failure.
	DeniedError struct{ Ref Ref }
	// UnavailableError reports a transient network/host failure (retryable).
	UnavailableError struct{ Remote string }
)

func (e InvalidRefError) Error() string      { return "" }
func (e NotFoundError) Error() string        { return "" }
func (e AlreadyExistsError) Error() string   { return "" }
func (e NothingToCommitError) Error() string { return "" }
func (e NonFastForwardError) Error() string  { return "" }
func (e ConflictError) Error() string        { return "" }
func (e DirtyWorktreeError) Error() string   { return "" }
func (e AuthError) Error() string            { return "" }
func (e DeniedError) Error() string          { return "" }
func (e UnavailableError) Error() string     { return "" }

// Kind maps each error to the errors.md taxonomy (the transport boundary's switch
// target, 10 §9), so KindOf(err) classifies without string matching.
func (e InvalidRefError) Kind() errors.Kind      { return errors.KindInvalid }
func (e NotFoundError) Kind() errors.Kind        { return errors.KindNotFound }
func (e AlreadyExistsError) Kind() errors.Kind   { return errors.KindConflict }
func (e NothingToCommitError) Kind() errors.Kind { return errors.KindConflict }
func (e NonFastForwardError) Kind() errors.Kind  { return errors.KindConflict }
func (e ConflictError) Kind() errors.Kind        { return errors.KindConflict }
func (e DirtyWorktreeError) Kind() errors.Kind   { return errors.KindConflict }
func (e AuthError) Kind() errors.Kind            { return errors.KindUnauthenticated }
func (e DeniedError) Kind() errors.Kind          { return errors.KindPermission }
func (e UnavailableError) Kind() errors.Kind     { return errors.KindUnavailable }
```

### Credential flow (the seam, designed honestly — 07 §2)

Identical in shape to `agentsession`'s, because it is the same vault → `secrets.Reference` →
server-side resolve → confined-`Use` discipline, just delivered into git's `credential.helper`
protocol instead of a harness env:

```
 vault ──── bound as ──▶ secrets.Reference  ──(loggable; lives in CloneOptions/FetchOptions/PushOptions & configuration)──┐
        ▲                                                                                                                 │
        │   network verb (Clone/Fetch/Push): the library writes a git config with                                        ▼
        │   credential.helper = <eden short-lived helper>, NEVER user:pass@URL ──▶ git invokes the helper on a 401 challenge
        │                                                                                                                 │
        │   helper: Deps.Secrets.Resolve(ref) ──server-side──▶ *secrets.Secret ──▶ Secret.Use(fn): write the token into git's
        │   credential protocol on stdout ONLY  (AuthError on failure — carries the ref, never the value)                 │
        └─────────────────────────────────────────────────────────────────────────────────────────────────────────────◀─┘

 Never crosses this boundary: the raw value on argv / in the URL / in the on-disk remote config / a log / an Event / a returned value.
```

## 3. Fake

```go
// Package gitrepositorytest is the canonical public fake Backend (the testing
// pattern, 10 §4 / 08 §2) plus the conformance suite. The fake is an IN-MEMORY git
// model — worktrees, a staged index, a commit log, branch heads — so a consumer
// (orchestrator, engine, chat backend) tests its flow WITHOUT a git binary or a real
// clone; and a thin real-binary harness (NewRealRepo) backs the live arm (C23: tests
// spin up real repos). The SAME conformance suite runs the in-memory fake AND the
// real system-git Backend over NewRealRepo, proving the load-bearing invariants:
// ff-only push, never-merge, per-actor audit trailers, worktree isolation, credential-
// never-leaked.
package gitrepositorytest

import (
	"context"

	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/secrets"
)

// Backend is a deterministic in-memory gitrepository.Backend. Zero value is an empty
// repo (no commits, one "main" branch). No clock, no I/O, no subprocess. Safe for
// concurrent reads.
type Backend struct {
	// Pushed records every Transfer(push) the SUT issued — refs only, never credentials —
	// for "did the agent push ws3/x to eden?" assertions.
	Pushed []gitrepository.PushOptions
	// CredentialRefs records which secrets.Reference each networked op resolved — refs
	// ONLY, never values — for the credential-confinement guarantee.
	CredentialRefs []secrets.Reference
}

func New() *Backend { return &Backend{} }

// Seed pre-populates a branch with commits/files so a read-surface test has content.
func (b *Backend) Seed(branch string, files map[string]string) *Backend { return b }

// FailNextPush forces the next Transfer(push) to return err — pass a gitrepository
// error value, e.g. gitrepository.NonFastForwardError{...} or gitrepository.AuthError{...} —
// for the divergence-routes-to-gate and bad-credential paths.
func (b *Backend) FailNextPush(err error) *Backend { return b }

func (b *Backend) Provision(ctx context.Context, op gitrepository.ProvisionOp, cred *secrets.Secret) (gitrepository.ProvisionResult, error) {
	return gitrepository.ProvisionResult{}, nil
}
func (b *Backend) Inspect(ctx context.Context, op gitrepository.InspectOp) (gitrepository.InspectResult, error) {
	return gitrepository.InspectResult{}, nil
}
func (b *Backend) Author(ctx context.Context, op gitrepository.AuthorOp) (gitrepository.AuthorResult, error) {
	return gitrepository.AuthorResult{}, nil
}
func (b *Backend) Transfer(ctx context.Context, op gitrepository.TransferOp, cred *secrets.Secret) (gitrepository.TransferResult, error) {
	return gitrepository.TransferResult{}, nil
}
func (b *Backend) Capabilities() gitrepository.Capabilities {
	return gitrepository.Capabilities{ShallowClone: true, LinkedWorktree: true}
}

// AssertCredentialNeverInArgs fails t if canary appears in ANY recorded operation's
// argument projection — the "credential never on argv / in logs" guarantee, runnable
// (07 §2; pairs with secretstest.AssertNotLeaked over a captured log buffer). The value
// lives only inside the helper's Secret.Use frame, never on a process surface.
func (b *Backend) AssertCredentialNeverInArgs(t TestingT, canary string) {}

// NewRealRepo materializes a REAL on-disk git repository in t.TempDir() (the integration
// arm, C23: "Go tests must spin up real repos"), seeded from RepoSeed, and returns its
// dir + a real *gitrepository.Repository wired to the system git. Cleanup is registered
// on t. Used by the conformance suite's live arm and by consumers writing real-substrate
// tests — it needs only a git binary, NO running cluster.
func NewRealRepo(t TestingT, seed RepoSeed) (dir string, repository *gitrepository.Repository) {
	return "", nil
}

// RepoSeed describes an initial repository (branches, commits, an identity) for
// NewRealRepo — deterministic so a worktree-isolation or ff-only test is reproducible.
type RepoSeed struct {
	DefaultBranch string
	Commits       []SeedCommit
	Identity      gitrepository.Identity
}

type SeedCommit struct {
	Files   map[string]string
	Message string
	Branch  string
}

type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
	TempDir() string
	Cleanup(func())
}
```

## 4. Conformance suite

The suite proves any `gitrepository.Backend` (the in-memory `gitrepositorytest.Backend` or the
real system-git Backend) is substitutable and that the load-bearing invariants hold. It lives in
`gitrepositorytest` per the testing pattern (10 §4, 08 §2). The unit arm runs the fake; the live
arm (release pipelines, C23) runs the SAME suite against the real system `git` over `NewRealRepo`,
and — the two-distro-cluster claim's analogue here — passes identically against `git` ≥2.40 with
both the sha-1 and sha-256 object formats (ADR-0016: real substrates, two conformance targets).

```go
// Run drives any gitrepository.Backend through the substitutability properties.
func Run(t *testing.T, newBackend func() gitrepository.Backend)
```

Properties asserted:

- **Never a merge engine** — there is no `Merge`/`Rebase`/`CherryPick` verb in the surface (a
  reflective check); `DiffCommits` and `ChangeConflicted`/`ConflictError` are read-only —
  exercising a conflicting state surfaces it, never resolves it.
- **Fast-forward-only push** — a non-ff `Push` returns `NonFastForwardError` carrying local+remote
  tips and does NOT advance the ref; there is no `Force` field to set (a compile-time guarantee,
  asserted by the type's shape).
- **Per-actor audit identity** — `Commit` with a zero `Identity` returns `InvalidRefError`; an
  `ActorAgent` commit injects `Eden-Run-ID`/`Eden-Session-ID`/`Eden-Phase` trailers and sets
  author+committer; an `ActorHuman` commit carries none of those trailers; the returned `CommitID`
  resolves and the trailers are queryable (02 §1); `When` defaults to the injected `Clock`.
- **Worktree isolation = the swarm primitive** — two `AddWorktree`s over disjoint paths mutate,
  `Stage`, and `Commit` concurrently with no index contention and independent HEADs; `RemoveWorktree`
  prunes linked-worktree metadata (not a bare `rm`) without touching the other or the main tree, is
  idempotent, and removing a dirty worktree without `Force` returns `DirtyWorktreeError`; the main
  tree is never removable.
- **Credential never leaks** — `Clone`/`Fetch`/`Push` resolve the `secrets.Reference` via
  `Deps.Secrets` exactly once per op and feed it via the credential helper;
  `AssertCredentialNeverInArgs(canary)` holds across every recorded op (argv, Env, Dir); a bad
  credential yields `AuthError` carrying the ref and never the value; the URL never contains
  `user:pass@`.
- **Read surfaces are faithful (C23)** — `Status.Changes`, `Branches`, and `Worktrees` reproduce a
  known seeded state (per-session file modifications, branches, in-flight worktrees the frontend
  renders); `Diff` is bounded and sets `Truncated` at the cap; `Diff{NameOnly}` returns paths only;
  binary files report `IsBinary`, never inlined bytes.
- **Shallow/partial honesty** — a `CloneOptions.Depth>0` produces a shallow clone where
  `Capabilities.ShallowClone`; a Backend declaring a capability it does not deliver fails the suite
  (05 §6).
- **Typed errors, AsType-first** — unknown revision → `NotFoundError`; existing branch →
  `AlreadyExistsError`; empty index → `NothingToCommitError`; host rejection → `DeniedError` vs
  transient → `UnavailableError`; each is matched by `errors.AsType[...]`, classifies via
  `errors.KindOf` to the right `errors.Kind`, and carries the ref/path — never raw stderr or a
  credential.
- **Pure spine + deterministic clock** — `New` runs no git; a zero `Identity.When` stamps from the
  injected `Clock` so a commit's timestamps are reproducible in tests.
- **Value round-trips** — `ParseBranchName(b.String()) == b`; `CommitID` zero value reports
  invalid; an injection-shaped branch name (`"-x"`, `"a..b"`, control chars) is rejected by
  `ParseBranchName`, never reaching an argv.

## 5. Usage

```go
// ── composition root: authority_mode (ADR-0013) decides the remote, not the lib ─
func gitFor(authority project.AuthorityMode, secretsProvider secrets.Provider, root string) *gitrepository.Repository {
	remotes := map[string]string{"eden": edenAuthorityURL} // eden-authority default
	if authority == project.ByoAuthority {
		remotes = map[string]string{"origin": project.MirrorURL()} // the user's host is authoritative (ADR-0013)
	}
	repo, _ := gitrepository.New(
		gitrepository.Config{Root: root, Remotes: remotes, DefaultAuthor: edenPlatformActor},
		gitrepository.Deps{
			Backend: gitrepository.SystemGit(), // shells the system binary (§6); tests inject gitrepositorytest.Backend
			Secrets: secretsProvider,           // the frozen secrets port — opaque refs in, never values
			Clock:   wallClock,
		},
	)
	return repo // a *gitrepository.Repository, accepted downstream as Provisioner / Inspector / Author
}

// ── engine: a swarm phase fans over disjoint FileLease sets, one worktree each ──
// (02 §2: "overlapping leases are a planning error, not a merge problem" — held mechanically)
func (e *Engine) runSwarmPackage(ctx context.Context, repo gitrepository.Provisioner, pkg plan.Package) (gitrepository.CommitID, error) {
	wt, err := repo.AddWorktree(ctx, gitrepository.WorktreeOptions{
		Path:   pkg.WorktreePath, // S2 provisioned the parent dir; this carves the worktree
		Branch: pkg.Branch,       // one branch per Run (04 §8)
		Start:  "main",
	})
	if err != nil {
		return gitrepository.CommitID{}, fmt.Errorf("worktree for %s: %w", pkg.ID, err)
	}
	defer repo.RemoveWorktree(ctx, pkg.WorktreePath, gitrepository.RemoveOptions{DeleteBranch: false}) // released on completion; history survives for the gate (02 §2)

	// ... the agent runs in this worktree (agentsession over pkg.WorktreePath) and edits ONLY its lease set ...

	if _, err := wt.Stage(ctx, pkg.WorktreePath, gitrepository.StageOptions{Paths: pkg.LeasePaths()}); err != nil { // exactly the FileLease set — never "all"
		return gitrepository.CommitID{}, err
	}
	// commit AS the agent run — the audit trailers make the Run queryable (02 §1, 07 §7)
	id, err := wt.Commit(ctx, pkg.WorktreePath, pkg.CommitMessage(), gitrepository.Identity{
		Name: "Eden Agent (implement)", Email: "agent+" + pkg.RunID + "@eden.dev", Kind: gitrepository.ActorAgent,
		RunID: pkg.RunID, SessionID: pkg.SessionID, Phase: "implement",
	}, gitrepository.CommitOptions{})
	if err != nil {
		if nc := (gitrepository.NothingToCommitError{}); errors.AsType(err, &nc) {
			return gitrepository.CommitID{}, nil // a clean no-op: the agent changed nothing
		}
		return gitrepository.CommitID{}, fmt.Errorf("commit package %s: %w", pkg.ID, err)
	}
	return id, nil // the gate (E3) integrates these branches — NEVER this library
}

// ── engine: push to the project's remote, routing a non-ff to a GATE, never merging ──
func (e *Engine) publishRun(ctx context.Context, repo gitrepository.Author, run RunRef) error {
	_, err := repo.Push(ctx, gitrepository.PushOptions{
		Remote:   run.Project().Remote(),                      // eden- or byo-authority URL (ADR-0013); the lib doesn't decide which
		LocalRef: run.Branch(),
		Auth:     secrets.Ref(run.Project().PushCredentialRef()), // setup-token-style; resolved server-side at the push
	})
	if err != nil {
		var nff gitrepository.NonFastForwardError
		if errors.AsType(err, &nff) {
			return e.routeToGate(ctx, run, nff) // We NEVER merge. The remote advanced under us → a DriftEvent (05 §5); human/policy rules adopt/revert/fork
		}
		var auth gitrepository.AuthError
		if errors.AsType(err, &auth) {
			return fmt.Errorf("push %s: credential %s rejected: %w", auth.Remote, auth.Reference, err) // byo-authority bad token; ref loggable, value never was
		}
		return fmt.Errorf("push run %s: %w", run.ID(), err)
	}
	return nil
}

// ── session-service: cheap shallow clone for a fresh PoC project (C19/C2) ──────
func (s *SessionService) cloneForPoC(ctx context.Context, repo gitrepository.Provisioner, tmpl Template, dir string) (*gitrepository.Repository, error) {
	return repo.Clone(ctx, tmpl.RemoteURL(), dir, gitrepository.CloneOptions{
		Depth:  1,                                 // shallow: cheap PoC (C2)
		Branch: tmpl.Ref(),
		Auth:   secrets.Ref(tmpl.CredentialRef()), // OPAQUE; zero for a public template
	})
}

// ── chat backend: the per-session file-modification rail + branches (C23) ──────
// The SvelteKit server reads them off gitrepository — the browser never touches the
// repo (the credential boundary is server-side, like agentsession).
func (c *ChatBackend) sessionFileRail(ctx context.Context, repo gitrepository.Inspector, wt string) (FileRailView, error) {
	st, err := repo.Status(ctx, wt) // read-only; the chat's "files changed this session" panel
	if err != nil {
		return FileRailView{}, fmt.Errorf("session status: %w", err)
	}
	return FileRailView{Files: st.Changes, Clean: st.Clean, Ahead: st.Ahead}, nil // Added/Modified/Deleted per path, staged + binary flags
}

func (c *ChatBackend) branchPicker(ctx context.Context, repo gitrepository.Inspector) ([]gitrepository.Branch, error) {
	return repo.Branches(ctx, gitrepository.BranchOptions{IncludeRemote: true}) // the branch picker + release-cycle view (C9, C23)
}

// ── byo-authority advisory mode (ADR-0013): observe drift, never push ──────────
func (d *DriftDetector) observe(ctx context.Context, repo gitrepository.Author, ref gitrepository.Ref, readOnlyCred secrets.Reference) error {
	tips, err := repo.Fetch(ctx, gitrepository.FetchOptions{ // read-only credential; updates tracking refs only
		Remote: ref.Remote, Refs: []gitrepository.Ref{ref}, Auth: readOnlyCred, Prune: true,
	})
	if err != nil {
		return fmt.Errorf("fetch for drift observation: %w", err)
	}
	_ = tips // diff the observed tip vs Eden's known state → emit a DriftEvent (05 §5); advisory mode NEVER pushes
	return nil
}

// ── a gate DECIDES on a diff; it never merges ──────────────────────────────────
func (g *Gate) decide(ctx context.Context, repo gitrepository.Inspector, runBranch gitrepository.BranchName) (Verdict, error) {
	diff, err := repo.Diff(ctx, gitrepository.DiffOptions{
		Mode: gitrepository.DiffCommits, From: "main", To: runBranch.String(), MaxBytes: 1 << 20,
	})
	if err != nil {
		return Verdict{}, err
	}
	return g.policy.Evaluate(diff), nil // promote-or-not; integration of the branch is the gate's governed act, post-verdict
}
```

## 6. Design rationale

1. **Shell the system `git` binary; do NOT embed `go-git` — behind ONE injected `Backend` seam.**
   This is the position the brief asks the producer to defend, and the reconciled form takes the
   producer's "shell git" stance while keeping the consumer's `Backend` port so it is a `Deps`
   choice, not a hardcode. Reasons, ranked: (a) **worktrees are first-class only in real git** —
   `git worktree add/remove` is the exact swarm-isolation primitive (02 §2), and `go-git` has no
   worktree-administrative support; reimplementing the `.git/worktrees` bookkeeping would reinvent
   the load-bearing primitive. (b) **shallow/partial/sparse clone** (`--depth`, `--filter=blob:none`,
   sparse-checkout) are essential for the large-repo, cost-conscious posture (C2/C19) and are mature
   in git, immature/absent in `go-git`. (c) **credential-helper fidelity** — git's `credential.helper`
   is exactly the short-lived-token seam 07 §2 wants; shelling git lets the value live only inside the
   helper's `Secret.Use` frame and reach git's credential protocol on stdout, never argv/URL/config.
   (d) **bit-for-bit fidelity** with the eventual self-hosted git server, CI runners, and byo-authority
   host behavior (ADR-0013) — the same git everywhere, no "works in go-git, differs on the host"
   divergence. (e) **sha-256 object format, protocol v2, signing, hooks** track upstream for free. The
   cost — a binary dependency and stderr parsing — is contained: the binary is present in every sandbox
   image (ADR-0016), and stderr classification lives in one place (the library, not the seam). The seam
   keeps the door open for a degenerate read-only `go-git` Backend later, and lets the conformance suite
   prove the whole surface against a real `git` binary (ADR-0016). See §7 Q1.

2. **Consumer-derived, three small interfaces under the ≤5-method ceiling (10 §9), split by call-site
   role.** The producer's split (`Repository`/`Remotes`/`Worktrees`) and the consumer's split
   (`Provisioner`/`Inspector`/`Author`) describe the same surface from two axes; the reconciled form
   takes the **consumer's call-site-role split** because the call sites cluster cleanly that way: the
   orchestrator/session-service *provisions* (`Clone` + worktree lifecycle, 3 methods), the chat
   frontend and gates *inspect* (`Status`/`Diff`/`Branches`/`Worktrees`, 4 methods), the engine
   *authors* (`Stage`/`Commit`/`Fetch`/`Push`, 4 methods). Each consumer accepts only the narrow
   interface it needs; `New` returns the concrete `*Repository` implementing all three
   (accept-interface / return-concrete). The producer's `Resolve` is folded into `Status`/diff
   revisions and the gate's `DiffCommits` (the only call sites needing a revision are reads), keeping
   `Inspector` at 4. See §7 Q3.

3. **The worktree is the swarm-isolation primitive, paired with `FileLease` (02 §2).**
   `AddWorktree`/`RemoveWorktree` are first-class, not an afterthought: one worktree ⇄ one disjoint
   `FileLease` set ⇄ one agent (07 §3). The library takes NO write lock — overlapping leases are a
   *planning* error (02 §2), so concurrency safety is "concurrent reads safe; one worktree, one
   writer; distinct worktrees independent" by contract, not by mutex. `RemoveWorktree` prunes
   linked-worktree metadata (not a bare `rm`), never tears down the pod (S2's job, 02 §1), and never
   removes the main tree.

4. **NEVER a custom merge engine — the no-merge surface is structural, enforced by the *absence* of
   API.** There is no `Merge`/`Rebase`/`CherryPick`/`Reset --hard`/`Force` anywhere. `Pull` is split
   into `Fetch` (refs only, working tree untouched) so a silent three-way merge is impossible. `Push`
   is fast-forward-only with **no `Force` field** (a compile-time guarantee, asserted reflectively in
   §4). A divergence surfaces as `NonFastForwardError` (carrying both tips) or
   `ConflictError`/`ChangeConflicted` (read-only visibility) — every one a *signal to escalate to a
   gate* (E3, 04 §8). The most a gate gets from this library is `Diff(DiffCommits, base..branch)` to
   *decide* on; integration is the gate's governed act over its own machinery. This is the single most
   important boundary in the contract, and it is unforgeable because the API simply does not exist.

5. **Per-actor author identity is mandatory and audit-bearing (02 §1, 07 §7).** `Commit` requires a
   non-zero `Identity` carrying `Name`/`Email`/`Kind` (`Human`/`Agent`/`Platform`) — a zero `Identity`
   is an `InvalidRefError` — so every commit is attributable and an agent Run is distinguishable from a
   human in the history without parsing a free-text name. `Identity` is a `Commit` argument, not an
   `Open`/`Config` field, because one repository commits as many actors over its life. `ActorAgent`
   injects `Eden-Run-ID`/`Eden-Session-ID`/`Eden-Phase` trailers so the git history *is* the audit
   trail, queryable by actor, reconciling with the append-only audit log (07 §7) and the Run
   provenance chain (03 §5). It never carries or reads a credential: commit identity is attribution,
   not authentication.

6. **Credentials via the frozen `secrets` pattern, confined to a helper seam — identical to the
   agentsession credential-flow (07 §2).** Only an opaque `secrets.Reference` rides
   `CloneOptions`/`FetchOptions`/`PushOptions` — loggable, value-less. The value is resolved
   server-side at the network call via `Deps.Secrets.Resolve` and confined to the credential helper's
   `Secret.Use(fn)` frame, emitted into git's credential protocol on stdout — never argv, never the URL
   (`no user:pass@host`), never the on-disk remote config, never a log/Event/returned value. `AuthError`
   carries the ref, never the value; `AssertCredentialNeverInArgs` makes the guarantee runnable. This
   reuses, byte-for-byte, the credential-flow `agentsession` froze, and is the second real consumer of
   the resolve-at-point-of-use + helper-injection seam — confirming that shape generalizes.

7. **`authority_mode` is applied, not decided here (ADR-0013).** The per-project
   eden-authority/byo-authority decision is made upstream; it arrives as `Config.Remotes` (which named
   remote a `Ref` targets) plus the credential's scope. eden-authority pushes to `eden`; byo-authority
   pushes to the user's mirror or — in advisory mode — only `Fetch`es with a read-only credential to
   observe drift (05 §5) and never pushes. The library carries no policy branch on authority mode; the
   composition root and the `Ref`/`Config` values express it, keeping the gate-enforcement and
   data-minimization rulings (ADR-0013) in the engine where they belong.

8. **`New(Config, Deps)` is pure; read surfaces are bounded and frontend-shaped.** `New` validates the
   worked-checkout `Root`, the named `Remotes`, and the injected `Backend`/`Secrets`/`Clock` and
   returns `*Repository`; it runs no git, reads no clock, opens no connection, and probes no binary —
   the first git operation happens lazily on the first verb (mirroring `secrets.New`/`agentsession.New`).
   `Status.Changes`, `Branches`, `Worktrees`, and `Diff` are exactly the read surfaces the chat and
   dashboard need (C23); `Diff` is bounded (`Truncated` + a paged "view full" fetch) and binary-aware so
   a runaway generated file cannot blow the surface, and the values are plain copyable structs (no live
   handles) so they serialize straight onto the wire (`libs/protocols` carries the proto twins).

## 7. Open questions

| # | question / conflict | producer position | consumer position | reconciler resolution 🧩 |
|---|---|---|---|---|
| Q1 | **`go-git` vs shelling the `git` binary** — the position the brief demands. | Shell the system `git` binary for the WHOLE surface (worktrees, partial/shallow clone, credential-helper fidelity, bit-for-bit parity with the self-hosted server and byo hosts); a `gogitadapter` is at most a future degenerate read-only case, never v1. | **Hybrid**: `go-git` for the read/local surface (hermetic, no subprocess per poll, no `git` on the chat-path image), shell the binary for clone/fetch/push/worktree (mature transport, `--depth`, real `git worktree`, the credential helper). | 🧩 **Took the producer's shell-git default; kept the consumer's `Backend` seam.** The brief asks for a defended position and the producer's is the stronger one: a hybrid splits stderr-parsing and worktree-bookkeeping across two implementations and invites a "works in go-git, differs on the binary" divergence class precisely on the load-bearing primitive (worktrees) and the cost-critical path (shallow/partial clone) — exactly where `go-git` is weakest. The reconciled `Backend` is a single seam whose **default shells the system git for every verb**; the consumer's real win — that the implementation choice is a `Deps` decision provable against a real binary, not a contract commitment — is preserved, and a degenerate read-only `go-git` Backend remains a drop-in if a no-`git`-binary call path ever proves load-bearing. The hybrid is recorded, not adopted. |
| Q2 | **`Backend` seam granularity** — a thin one-method `Run(Invocation)` process seam, or a four-verb `Provision`/`Inspect`/`Author`/`Transfer` seam? | A THIN `Git` seam with exactly one method `Run(Invocation) → Output`: the library owns argv construction, parsing, the ff-only guard, trailers, worktree bookkeeping; the seam owns ONLY process invocation. | A four-verb `Backend` (`Provision`/`Inspect`/`Author`/`Transfer`) + `Capabilities()`, normalized op descriptors, so a hybrid backend can route reads to `go-git` and network to the binary. | 🧩 **Took the consumer's four-verb `Backend` + `Capabilities()` (5 methods).** Even though the default backend shells git for everything (Q1), the verb-grouped seam carries the credential-confinement rule structurally (`cred *secrets.Secret` rides only `Provision`/`Transfer`, never `Inspect`/`Author`), declares capabilities the conformance suite checks for truthfulness (05 §6, the connector-family discipline), and keeps the door open for the read-only `go-git` drop-in without a contract change. The producer's "library owns argv/parsing/ff-guard/trailers, the seam owns only the raw op" discipline is honored verbatim — it simply lands on four typed verbs instead of one stringly `Run`. The op descriptors are opaque-by-design here (the seam and the credential rule freeze; the descriptor field set lands with the implementation). |
| Q3 | **Interface split axis** — `Repository`/`Remotes`/`Worktrees` (by git-mechanism), or `Provisioner`/`Inspector`/`Author` (by call-site role)? Plus: keep a `Resolve(revision)→CommitID` verb? | Three ports by mechanism: `Repository` (Status/Diff/Stage/Commit/**Resolve**, 5), `Remotes` (Clone/Fetch/Push, 3), `Worktrees` (CreateBranch/AddWorktree/RemoveWorktree/ListBranches/ListWorktrees, 5). | Three ports by call-site role: `Provisioner` (Clone/worktree-add/remove, 3), `Inspector` (Status/Diff/Branches/Log, 4), `Author` (Stage/Commit/Fetch/Push, 4). | 🧩 **Took the consumer's call-site-role split; dropped the standalone `Resolve` verb.** The role split is what the real call sites prove: the orchestrator provisions, the chat/gates inspect, the engine authors — each accepts exactly one narrow port (the accept-interface rule pays off). The producer's mechanism split put `Stage`/`Commit` (engine) next to `Status`/`Diff` (frontend) on one port, which no consumer holds together. The producer's separate `Resolve(revision)→CommitID` is **folded**: the only call sites needing a revision→`CommitID` are reads (a gate's `DiffCommits` takes revisions directly; `Status.Head` already pins HEAD), so a standalone verb bought nothing and would push `Inspector` to 5. The producer's `CreateBranch` is likewise folded into `AddWorktree.Start` (a branch is the ref a worktree checks out) and `ListBranches`/`ListWorktrees` become `Inspector.Branches`/`Worktrees`. Net: three ports of 3/4/4 methods, no surface lost. |
| Q4 | **`Log`/history read surface** — include a `Log(ref, limit)→[]Commit`? | No `Log` verb (history is read via `Resolve` + `Diff`); the release-cycle view is not in the producer's read set. | `Log(ref, limit)→[]Commit`, newest-first, bounded — the history / release-cycle read (C9) carrying each commit's `Identity` for the audit trail. | 🧩 **Deferred `Log` from the v1 surface; recorded as the first additive extension.** It is a real C9 read, but it would push `Inspector` to 5 methods and no Wave-3A call site (the file-modification rail, the branch picker, the gate diff) needs it yet — `Status` + `Branches` + `Diff` cover the frontend's per-session and branch views. Keeping `Inspector` at 4 leaves exactly one slot for the additive `Log` when the release-cycle view (C9) lands and proves its shape, rather than freezing a speculative `[]Commit`/pagination contract now. The producer's history-via-`Diff` and the consumer's `Log` are both honored by deferral: the read exists, just not in the frozen v1 ceiling. |
| Q5 | **Commit author shape** — a dedicated `Actor{Name,Email,Kind,RunID,SessionID,Phase}`, or an `Identity{Name,Email,When,Actor}` with the Run keys carried in `Email`/`Name`? | A first-class `Actor` with explicit `RunID`/`SessionID`/`Phase` fields, so the audit trailers are queryable structurally without parsing a name. | An `Identity{Name,Email,When,Actor ActorKind}` where the Run correlation rides the synthesized `Email` (`agent+<run>@eden.dev`); `Actor` classifies the principal. | 🧩 **Took the consumer's `Identity` name + `When` field; kept the producer's explicit Run keys.** Naming it `Identity` (not `Actor`) matches the audit-stamp vocabulary and carries the consumer's `When` (zero == injected `Clock`) for deterministic tests. But the producer's explicit `RunID`/`SessionID`/`Phase` fields are **kept** over folding the Run id into the `Email` string, because the trailers must be queryable by actor *without parsing a synthesized address* (07 §7, 03 §5) — a parsed `agent+<run>@eden.dev` is a string-match audit trail, exactly what the typed-error / typed-everything discipline rejects. So `Kind ActorKind` drives the trailer set and the explicit keys populate it; the human/platform cases leave them empty. |
| Q6 | **Error taxonomy split** — does a host rejection collapse into `AuthError`, or split into `AuthError` (bad credential, `Unauthenticated`) vs `DeniedError` (host policy/branch-protection, `Permission`)? | Split: `AuthError` (`KindUnauthenticated`) for a credential failure AND a distinct `DeniedError` (`KindPermission`) for a host rejection (byo-authority branch protection, ADR-0013). | A single `AuthError` for "credential rejected"; `RemoteError` for transient/unreachable; no separate denied/permission type. | 🧩 **Took the producer's `AuthError` vs `DeniedError` split.** A byo-authority enforced-mode branch-protection rejection (ADR-0013) is a *permission* outcome the dashboard must surface differently from a *bad token* (the user fixes a token vs a branch-protection rule), and the frozen `errors` taxonomy already distinguishes `KindUnauthenticated` from `KindPermission` (errors.md Q7) precisely so the transport boundary does not lose that information. The consumer's `RemoteError` is taken (renamed `UnavailableError`, `KindUnavailable`) for the transient arm. Every error type exposes `Kind()` so `KindOf(err)` classifies at the Connect boundary without string matching (the consumer's load-bearing demand); `NonFastForwardError`/`AlreadyExistsError`/`NothingToCommitError`/`ConflictError`/`DirtyWorktreeError` all map to `KindConflict`. |
| Q7 | **`secrets`/`errors` sibling alignment** — confirm the frozen-shape siblings; does `NonFastForwardError`→`KindConflict` need a new `KindPrecondition`? | Maps onto the frozen `Kind` taxonomy; no new `Kind` needed. | Same; explicitly **rejects** a new `KindPrecondition` as taxonomy bloat — `KindConflict` already means "state/version/uniqueness conflict". | 🧩 **Aligned to the siblings as frozen; no new `Kind`.** Credentials use `secrets.Reference` (loggable) + `secrets.Secret.Use(fn)` exactly as `secrets.md` froze them; the credential helper calls `Resolve` at git's 401 challenge and emits via `Use`. Errors are typed structs inspected via `errors.AsType` with a `Kind()` method per `errors.md`; a non-fast-forward lands on `KindConflict` (the state/version-conflict arm) — a new `KindPrecondition` is rejected as bloat. **No new surface is demanded on any frozen sibling** (`secrets`/`errors`); this is the second consumer confirming both seams generalize. |
| Q8 | **`workspaceprovider` / orchestrator / F2 boundary** (adjacent, co-negotiating) — where do the directory-lifecycle, lease-disjointness, and remote-SCM boundaries land? | S2 provisions/teardowns the parent dir + pod; `gitrepository` carves/removes *worktrees within* it and never creates/deletes the dir or reaps a pod. F2 consumes *this* `Push`/`Fetch` for the wire transfer and layers host-app concerns above it. The planner guarantees non-overlapping lease sets before `AddWorktree`. | Same boundary demands, stated from the call sites: `Workspace.Path → Config.Root` handoff is `workspaceprovider`'s; F2's drift detector consumes `Inspector` (`Status.Behind`/`Diff`/`Fetch`) rather than shelling git; the orchestrator sequences `AddWorktree → session → gate → Commit → Push → RemoveWorktree`. | 🧩 **Recorded as cross-contract demands for the reconciler to route; no conflict between the drafts.** Both sides agree on every seam: (a) `workspaceprovider`/S2 owns the directory's existence and the pod; `gitrepository` owns its git state — `AddWorktree.Path` must be a path S2 already made writable, and `RemoveWorktree` prunes only git's worktree metadata. (b) The orchestrator guarantees disjoint `FileLease` sets *before* `AddWorktree` (overlap is a 02 §2 planning error); this library does not detect overlap, it provides the isolation that makes the assumption pay off. (c) F2 owns `authority_mode`/`enforcement_level`/PR-MR/webhooks/branch-protection/`DriftEvent` emission and *consumes* this library's `Push`/`Fetch`/`Inspector` for the local git and wire transfer — `DeniedError` from `Push` is where a host-app branch-protection rejection surfaces; F2 does not re-implement local git, and this library does not grow remote-SCM surface. These land on the named seams when those contracts negotiate (Wave 3A/3B), not as duplicate ownership. |
