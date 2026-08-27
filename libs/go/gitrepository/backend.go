package gitrepository

import (
	"context"

	"github.com/gophersys/libs/go/secrets"
)

// Backend executes git operations against a path — the §6 default SHELLS the system git
// binary (SystemGit), or a fake (gitrepositorytest.Backend). It is THIN: the library owns
// path validation, argument shaping, Author stamping, the credential-flow (Secret.Use at
// the helper seam), the fast-forward-only push guard, and result mapping into the value
// types above; the Backend owns ONLY the raw operation. The credential-helper environment
// is injected here, by the library, confined to the child process — never Eden's env. cred
// is nil for a public/local op; when set it is the resolved, un-printable short-lived
// Secret the Backend exposes to git via a credential helper — confined to Secret.Use, never
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
	// short-lived Secret confined to Secret.Use at the credential-helper seam; the library
	// enforces fast-forward-only on push and classifies a rejection.
	Transfer(ctx context.Context, op TransferOp, cred *secrets.Secret) (TransferResult, error)

	// Capabilities declares what this Backend supports (shallow clone, linked worktrees,
	// partial clone) so the library degrades gracefully (05 §3) and the conformance suite
	// verifies the declaration is truthful (05 §6) — a Backend declaring a capability it
	// does not deliver fails the suite.
	Capabilities() Capabilities
}

// Capabilities is the Backend's declaration (05 §3). DATA, not code.
type Capabilities struct {
	// ShallowClone reports that --depth is supported.
	ShallowClone bool
	// LinkedWorktree reports that `git worktree` is supported (the isolation primitive).
	LinkedWorktree bool
	// PartialClone reports that --filter partial clone is supported.
	PartialClone bool
}

// ── Normalized operation descriptors ──────────────────────────────────────────
// The library hands the Backend already-validated descriptors (the contract fixes the
// SEAM and the credential-confinement rule, not the Backend's internal request shape).
// They carry NO secret value — the credential rides the separate *secrets.Secret argument,
// confined to Secret.Use. Each carries a Kind discriminator so a Backend dispatches without
// a string match.

// ProvisionKind discriminates a ProvisionOp.
type ProvisionKind uint8

const (
	// ProvisionClone materializes a remote into a directory.
	ProvisionClone ProvisionKind = iota
	// ProvisionAddWorktree creates a linked worktree.
	ProvisionAddWorktree
	// ProvisionRemoveWorktree prunes a linked worktree.
	ProvisionRemoveWorktree
	// ProvisionFlattenHistory drops the worked checkout's commit history and replaces the
	// checked-out branch with a SINGLE root commit snapshotting the current tree (the
	// template-copy seed: `clone template` → flatten → `push` into an empty new repo). It
	// rewrites no remote — the flattened branch is published by an ordinary fast-forward Push
	// into an unborn destination, so the ff-only contract is preserved (the seed IS the first
	// commit on the new origin).
	ProvisionFlattenHistory
)

// ProvisionOp is the validated clone / worktree-add / worktree-remove descriptor (no secret).
type ProvisionOp struct {
	// Kind selects clone / add-worktree / remove-worktree.
	Kind ProvisionKind
	// Root is the worked-checkout directory the op runs against (the bound Repository root).
	Root string
	// RemoteURL is the resolved clone source (ProvisionClone); never carries credentials.
	RemoteURL string
	// RemoteName is the local origin remote name for a clone.
	RemoteName string
	// Dir is the target directory: the clone destination or the new worktree path.
	Dir string
	// Branch is the branch to check out (clone single-branch / worktree branch).
	Branch string
	// Start is the start revision when a worktree's branch must be created.
	Start string
	// Depth is the shallow-clone depth (0 == full).
	Depth int
	// Filter is the partial-clone filter ("" == none).
	Filter string
	// Sparse is the sparse-checkout path set (nil == full tree).
	Sparse []string
	// CreateBranch is true when a worktree's branch does not yet exist and must be created from Start.
	CreateBranch bool
	// DeleteBranch removes the worktree's branch on remove.
	DeleteBranch bool
	// Force removes a dirty worktree.
	Force bool

	// The fields below are populated ONLY for ProvisionFlattenHistory — the single seed commit
	// the flatten records. They mirror the AuthorOp commit-stamp surface (the library stamps the
	// identity once; the seam records it) because a flatten is a checkout-level history rewrite,
	// not a stage/commit of a working change.

	// Message is the seed commit message (ProvisionFlattenHistory).
	Message string
	// AuthorName / AuthorEmail are the stamped author+committer identity for the seed commit.
	AuthorName  string
	AuthorEmail string
	// When is the resolved seed-commit time (Identity.When, or Clock.Now() — already resolved).
	When string
	// Trailers are the queryable Eden-* trailers for an ActorAgent seed commit.
	Trailers []AuthorTrailer
}

// InspectKind discriminates an InspectOp.
type InspectKind uint8

const (
	// InspectStatus reads a worktree's working-tree status.
	InspectStatus InspectKind = iota
	// InspectDiff reads a bounded diff.
	InspectDiff
	// InspectBranches lists branches.
	InspectBranches
	// InspectWorktrees lists worktrees.
	InspectWorktrees
)

// InspectOp is the validated read-surface descriptor (no secret).
type InspectOp struct {
	// Kind selects status / diff / branches / worktrees.
	Kind InspectKind
	// Root is the worked-checkout directory.
	Root string
	// Worktree is the worktree to inspect (status / working-tree diff).
	Worktree string
	// DiffMode selects the diff comparison axis.
	DiffMode DiffMode
	// From and To are the revisions for DiffCommits.
	From string
	To   string
	// Paths optionally scopes a diff.
	Paths []string
	// NameOnly requests the path list only.
	NameOnly bool
	// MaxBytes bounds a diff (always > 0 by the time it reaches the Backend).
	MaxBytes int64
	// IncludeRemote also lists remote-tracking branches.
	IncludeRemote bool
}

// AuthorKind discriminates an AuthorOp.
type AuthorKind uint8

const (
	// AuthorStage adds paths to the index.
	AuthorStage AuthorKind = iota
	// AuthorCommit records the index as an Identity.
	AuthorCommit
)

// AuthorTrailer is one queryable commit trailer ("Eden-Run-ID: …") the library injects for
// an ActorAgent commit. It is structured, not a parsed name, so the audit trail is
// queryable by actor without string-parsing an address (07 §7).
type AuthorTrailer struct {
	// Key is the trailer token, e.g. "Eden-Run-ID".
	Key string
	// Value is the trailer value, e.g. the Run id.
	Value string
}

// AuthorOp is the validated stage / commit descriptor with the already-stamped Identity
// (no secret).
type AuthorOp struct {
	// Kind selects stage / commit.
	Kind AuthorKind
	// Root is the worked-checkout directory.
	Root string
	// Worktree is the worktree the op writes.
	Worktree string
	// Paths is the explicit stage set.
	Paths []string
	// All stages every modified/untracked path.
	All bool
	// Message is the commit message.
	Message string
	// AuthorName / AuthorEmail are the stamped author+committer identity.
	AuthorName  string
	AuthorEmail string
	// When is the resolved commit time (Identity.When, or Clock.Now() — already resolved).
	When string
	// Trailers are the queryable Eden-* trailers for an ActorAgent commit.
	Trailers []AuthorTrailer
	// AllowEmpty permits an empty-index commit.
	AllowEmpty bool
}

// TransferKind discriminates a TransferOp.
type TransferKind uint8

const (
	// TransferFetch updates remote-tracking refs.
	TransferFetch TransferKind = iota
	// TransferPush publishes a local tip (fast-forward-only).
	TransferPush
)

// TransferOp is the validated fetch / push descriptor (no secret). The credential rides
// the separate *secrets.Secret argument to Transfer, never this struct.
type TransferOp struct {
	// Kind selects fetch / push.
	Kind TransferKind
	// Root is the worked-checkout directory.
	Root string
	// Remote is the logical remote name.
	Remote string
	// RemoteURL is the resolved remote URL (never carries credentials).
	RemoteURL string
	// Refs are the refs to fetch (nil == all configured).
	Refs []Ref
	// LocalRef / DestRef are the push source and destination branch names.
	LocalRef string
	DestRef  string
	// Prune removes deleted remote refs on a fetch.
	Prune bool
	// FastForwardOnly is always true for a push (the contract guard); declared on the seam
	// so a Backend cannot silently force-push.
	FastForwardOnly bool
	// HasCredential reports whether a cred is supplied (the Backend installs the helper seam).
	HasCredential bool
}

// Backend result types.

// ProvisionResult is the opened-repo / worktree metadata a Provision returns.
type ProvisionResult struct {
	// Head is the HEAD commit after a clone / worktree-add (zero == unborn).
	Head CommitID
	// Branch is the checked-out branch after the op.
	Branch BranchName
}

// InspectResult maps to Status / Diff / []Branch / []WorktreeInfo. Exactly one field is
// populated, selected by the InspectOp.Kind.
type InspectResult struct {
	// Status is populated for InspectStatus.
	Status Status
	// Diff is populated for InspectDiff.
	Diff Diff
	// Branches is populated for InspectBranches.
	Branches []Branch
	// Worktrees is populated for InspectWorktrees.
	Worktrees []WorktreeInfo
}

// AuthorResult is the new CommitID a commit produces (and the post-op Status a stage
// returns).
type AuthorResult struct {
	// Commit is the new commit id (AuthorCommit).
	Commit CommitID
	// Status is the post-op working-tree status (AuthorStage, and AuthorCommit for callers).
	Status Status
}

// TransferResult is the moved Ref tips.
type TransferResult struct {
	// Tips are the fetched/pushed ref tips.
	Tips map[Ref]CommitID
	// UpToDate reports a push that was already at the remote tip (a clean no-op).
	UpToDate bool
}
