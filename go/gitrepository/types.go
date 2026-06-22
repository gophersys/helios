package gitrepository

import (
	"strings"
	"time"

	"github.com/gophersys/libs/go/secrets"
)

// CommitID is a full 40/64-hex object id (sha-1 or sha-256). Loggable; comparable;
// usable as a map key. The zero value is the invalid/unborn commit (a fresh branch
// with no commits). It is NEVER abbreviated in this surface — abbreviation is a UI
// concern.
type CommitID struct{ hex string }

// String returns the full hex object id ("" for the zero value).
func (c CommitID) String() string { return c.hex }

// IsZero reports whether c is the invalid/unborn commit.
func (c CommitID) IsZero() bool { return c.hex == "" }

// CommitIDFromHex constructs a CommitID from a hex object id a Backend resolved (the
// system-git binary's rev-parse output, or a fake's model id). It is the constructor a
// Backend implementation uses to produce a CommitID — a CommitID never originates from
// untrusted input, only from git output. A non-hex or wrong-length value yields the zero
// CommitID, which IsZero reports.
func CommitIDFromHex(hex string) CommitID {
	hex = strings.TrimSpace(hex)
	if !isObjectHex(hex) {
		return CommitID{}
	}
	return CommitID{hex: strings.ToLower(hex)}
}

// commitIDFromHex is the internal alias the library's own backend uses.
func commitIDFromHex(hex string) CommitID { return CommitIDFromHex(hex) }

// isObjectHex reports whether s is a full sha-1 (40) or sha-256 (64) lowercase/upper
// hex object id — the only two lengths git emits for a resolved object.
func isObjectHex(s string) bool {
	if len(s) != objectHexSHA1 && len(s) != objectHexSHA256 {
		return false
	}
	for _, r := range s {
		switch {
		case r >= '0' && r <= '9':
		case r >= 'a' && r <= 'f':
		case r >= 'A' && r <= 'F':
		default:
			return false
		}
	}
	return true
}

const (
	objectHexSHA1   = 40
	objectHexSHA256 = 64
)

// BranchName is a validated short branch name ("feature/x", not
// "refs/heads/feature/x"). ParseBranchName rejects names git would reject (no "..",
// no leading "-", no control chars — the injection surface when names reach an
// argv). Loggable; comparable.
type BranchName struct{ name string }

// String returns the short branch name ("" for the zero value).
func (b BranchName) String() string { return b.name }

// IsZero reports whether b is the empty/unset branch name.
func (b BranchName) IsZero() bool { return b.name == "" }

// Ref names a thing a fetch/push targets: a branch and the named remote it lives on.
// The per-project authority_mode (ADR-0013) decides which remote a Ref resolves
// against UPSTREAM, not here — this is a value, not a policy.
type Ref struct {
	// Remote is the configured remote name, e.g. "eden" (authority) or "origin"
	// (byo mirror). It is a logical key into Config.Remotes, never a URL.
	Remote string
	// Branch is the short branch name this Ref points at.
	Branch BranchName
}

// IsZero reports whether r carries neither a remote nor a branch.
func (r Ref) IsZero() bool { return r.Remote == "" && r.Branch.IsZero() }

// Identity is the per-actor commit author/committer stamp — the load-bearing 02 §1
// distinction between an agent run and a human. It is supplied PER COMMIT (one
// repository commits as different actors over its life), never frozen at New. Kind
// classifies the principal so the audit trail distinguishes an agent Run from a
// human WITHOUT parsing a free-text name; for an AgentRun the library injects the
// Eden-Run-ID / Eden-Session-ID / Eden-Phase commit trailers, reconciling the commit
// log with the append-only audit log (07 §7) and the Run provenance chain (03 §5).
// Name+Email are the git author identity; the Eden keys correlate. NEVER a credential.
type Identity struct {
	// Name is the git author/committer name, e.g. "Eden Agent (implement)".
	Name string
	// Email is the git author/committer email.
	Email string
	// When is the commit time; the zero value means Clock.Now() (deterministic in tests).
	When time.Time
	// Kind classifies the principal (Human | Agent | Platform) and selects the trailer set.
	Kind ActorKind
	// RunID is the Run (02 §2) this commit belongs to for ActorAgent; "" otherwise.
	RunID string
	// SessionID is the agentsession id for ActorAgent; "" otherwise.
	SessionID string
	// Phase is the pipeline phase (e.g. "implement") for ActorAgent; "" otherwise.
	Phase string
}

// IsZero reports whether i carries no author identity at all.
//
//nolint:gocritic // contract §2: Identity.IsZero has a value receiver (a plain copyable audit-stamp predicate; the frozen surface).
func (i Identity) IsZero() bool { return i.Name == "" && i.Email == "" }

// ActorKind classifies the principal behind a commit so the audit trail distinguishes
// an agent Run from a human without parsing a free-text name.
type ActorKind uint8

const (
	// ActorHuman is a person who committed through the UI/editor (02 §1).
	ActorHuman ActorKind = iota
	// ActorAgent is an agent Run (gets Eden-Run-ID/Session/Phase trailers).
	ActorAgent
	// ActorPlatform is an Eden system commit (e.g. a graft); no Eden-Run trailer.
	ActorPlatform
)

// Options and value types (plain, copyable, zero-safe).

// CloneOptions carries the depth/auth/branch/sparse knobs for Clone.
type CloneOptions struct {
	// Depth is 0 for full history, or >0 for a shallow `--depth=N` clone (cheap PoC, C2/C19).
	Depth int
	// Branch requests a single-branch checkout; the zero value means the remote's default branch.
	Branch BranchName
	// Filter is a partial-clone filter, e.g. "blob:none" (lazy blobs); "" means none.
	Filter string
	// Sparse is the sparse-checkout path set; nil means the full tree.
	Sparse []string
	// Credential is the OPAQUE credential reference, resolved at the operation, never on argv/URL/log.
	Credential secrets.Reference
	// RemoteName is the local name for the origin remote, e.g. "eden" or "origin".
	RemoteName string
}

// WorktreeOptions creates a linked worktree (the isolation primitive, 02 §2).
type WorktreeOptions struct {
	// Path is the new worktree directory (the agent's CWD; S2 owns its lifecycle, 02 §1).
	Path string
	// Branch is the branch this worktree checks out.
	Branch BranchName
	// Start creates Branch from this revision when it does not yet exist; "" means Branch must exist.
	Start string
}

// RemoveOptions controls worktree pruning.
type RemoveOptions struct {
	// DeleteBranch also deletes the worktree's branch (work-package cleanup).
	DeleteBranch bool
	// Force removes even with uncommitted changes (engine-controlled); else DirtyWorktreeError.
	Force bool
}

// DiffMode selects what Diff compares.
type DiffMode uint8

const (
	// DiffWorkingVsHead diffs unstaged + staged vs HEAD (the chat's live view).
	DiffWorkingVsHead DiffMode = iota
	// DiffStagedVsHead diffs the index vs HEAD (what a Commit would record).
	DiffStagedVsHead
	// DiffCommits diffs From..To (a gate comparing a Run's branch to base).
	DiffCommits
)

// DiffOptions selects what Diff compares. Mode picks working-tree/staged/commit..commit.
type DiffOptions struct {
	// Worktree is the worktree to diff (DiffWorkingVsHead / DiffStagedVsHead).
	Worktree string
	// Mode selects the comparison axis.
	Mode DiffMode
	// From is the base revision for DiffCommits; ignored otherwise.
	From string
	// To is the target revision for DiffCommits; ignored otherwise.
	To string
	// Paths optionally scopes the diff (a worktree diffs its lease set).
	Paths []string
	// NameOnly returns the cheap path list only (the file-modification list).
	NameOnly bool
	// MaxBytes bounds the patch (0 means a sane default cap; never unbounded).
	MaxBytes int64
}

// BranchOptions selects which branches Branches reports.
type BranchOptions struct {
	// IncludeRemote also lists remote-tracking branches.
	IncludeRemote bool
}

// StageOptions selects which paths Stage adds to the index.
type StageOptions struct {
	// Paths is the explicit path set (a worktree stages exactly its FileLease set).
	Paths []string
	// All, with empty Paths, stages every modified and untracked path.
	All bool
}

// CommitOptions controls Commit.
type CommitOptions struct {
	// AllowEmpty permits a commit with an empty index (rare; e.g. a checkpoint/marker commit).
	AllowEmpty bool
}

// FlattenOptions controls Flatten — the template-copy seed (clone template → drop its history
// → push into the NEW, empty repository). The flatten replaces the checked-out branch with a
// SINGLE root commit snapshotting the current working tree, so the cloned-from template's
// history does not bleed into the new repository. The push that publishes it is an ordinary
// fast-forward into an unborn destination branch, so the ff-only Push contract is preserved.
type FlattenOptions struct {
	// Message is the seed commit message, e.g. "seed from template". Required — a flatten is an
	// attributable act like any other commit.
	Message string
	// Author stamps the single seed commit (author+committer), exactly as Commit's Identity does.
	// REQUIRED — a zero Identity (after the Config.DefaultAuthor fallback) is an InvalidRefError.
	Author Identity
}

// FetchOptions selects what Fetch updates.
type FetchOptions struct {
	// Remote is the logical name from Config.Remotes.
	Remote string
	// Refs are the refs to update; nil means all configured for the remote.
	Refs []Ref
	// Credential is the OPAQUE read-only credential for the drift-observation path.
	Credential secrets.Reference
	// Prune removes deleted remote refs.
	Prune bool
}

// PushOptions selects what Push publishes. There is NO Force field — a non-fast-forward
// push returns NonFastForwardError and the caller escalates to a gate (E3); force-with-lease
// is a governed act, never a library affordance (the no-merge boundary, §6).
type PushOptions struct {
	// Remote is the logical name from Config.Remotes (eden- or byo-authority, ADR-0013).
	Remote string
	// LocalRef is the local branch tip to publish.
	LocalRef BranchName
	// DestRef is the remote branch; the zero value means the same as LocalRef.
	DestRef BranchName
	// Credential is the OPAQUE credential, resolved at the push.
	Credential secrets.Reference
}

// ChangeKind classifies one path's working-tree state.
type ChangeKind uint8

const (
	// ChangeAdded is a newly tracked path.
	ChangeAdded ChangeKind = iota
	// ChangeModified is a content change to a tracked path.
	ChangeModified
	// ChangeDeleted is a removed tracked path.
	ChangeDeleted
	// ChangeRenamed is a path moved from OldPath.
	ChangeRenamed
	// ChangeUntracked is a path git does not yet track.
	ChangeUntracked
	// ChangeConflicted is reported for VISIBILITY (a gate sees a conflicting state); NEVER resolved here.
	ChangeConflicted
)

// String renders a ChangeKind for diagnostics.
func (c ChangeKind) String() string {
	switch c {
	case ChangeAdded:
		return "added"
	case ChangeModified:
		return "modified"
	case ChangeDeleted:
		return "deleted"
	case ChangeRenamed:
		return "renamed"
	case ChangeUntracked:
		return "untracked"
	case ChangeConflicted:
		return "conflicted"
	default:
		return "unknown"
	}
}

// FileChange is one path's state — the row the frontend renders per modified file.
type FileChange struct {
	// Path is the repo-relative path (the new path for a rename).
	Path string
	// OldPath is the prior path for a rename/copy; "" otherwise.
	OldPath string
	// Status classifies the change.
	Status ChangeKind
	// Staged is true when the change is in the index; false when working-tree only.
	Staged bool
	// IsBinary is true for binary content (the diff is a flag, not text).
	IsBinary bool
}

// Status is a worktree's working-tree snapshot — the gate input and the chat's
// file-modification panel (C23). A plain value; copyable; zero-safe.
type Status struct {
	// Branch is the checked-out branch (zero means detached HEAD).
	Branch BranchName
	// Head is the HEAD commit (zero means an unborn branch, no commits yet).
	Head CommitID
	// Upstream is the configured upstream (zero Ref means none).
	Upstream Ref
	// Ahead is the number of commits ahead of upstream (release-cycle view, C9).
	Ahead int
	// Behind is the number of commits behind upstream (drift signal, 05 §5).
	Behind int
	// Clean is true when there are no staged, unstaged, or untracked changes.
	Clean bool
	// Changes is the per-path change set (the per-session file modifications, C23).
	Changes []FileChange
}

// Hunk is one unified-diff hunk, bounded so a runaway file cannot blow the read surface.
type Hunk struct {
	// OldStart is the 1-based start line in the old file.
	OldStart int
	// OldLines is the line count in the old file.
	OldLines int
	// NewStart is the 1-based start line in the new file.
	NewStart int
	// NewLines is the line count in the new file.
	NewLines int
	// Text is the unified-diff body for this hunk (bounded).
	Text string
}

// FileDiff is one path's diff — Path + Status only for NameOnly.
type FileDiff struct {
	// Path is the repo-relative path (the new path on a rename).
	Path string
	// OldPath is the old path on a rename.
	OldPath string
	// Status classifies the change.
	Status ChangeKind
	// IsBinary is true for binary content (Hunks is empty, never inlined bytes).
	IsBinary bool
	// Hunks is the diff body; empty for binary, NameOnly, or stat-only.
	Hunks []Hunk
	// AddedLines is the count of added lines.
	AddedLines int
	// RemovedLines is the count of removed lines.
	RemovedLines int
}

// Diff is a bounded diff result — the gate's "what changed" input and the chat's diff
// view. Files are summarized; hunks are capped so a runaway generated file cannot blow
// the read surface.
type Diff struct {
	// Files is the per-file diff; NameOnly populates Path + Status only.
	Files []FileDiff
	// Truncated is true when the MaxBytes/hunk cap was hit; the frontend offers "view full".
	Truncated bool
}

// Branch is one ref with its tip — the frontend branch picker (C9, C23).
type Branch struct {
	// Name is the branch's short name.
	Name BranchName
	// Tip is the branch's HEAD commit.
	Tip CommitID
	// IsRemote is true for a remote-tracking branch.
	IsRemote bool
	// Upstream is the configured upstream (zero Ref means no upstream).
	Upstream Ref
	// Ahead is the count of commits ahead of upstream.
	Ahead int
	// Behind is the count of commits behind upstream.
	Behind int
}

// WorktreeInfo is one live worktree (Worktrees).
type WorktreeInfo struct {
	// Path is the worktree's on-disk directory.
	Path string
	// Branch is the branch the worktree has checked out.
	Branch BranchName
	// Tip is the worktree's HEAD commit.
	Tip CommitID
	// IsMain is true for the primary working tree (never removable via RemoveWorktree).
	IsMain bool
}

// PushResult reports the pushed Ref's new tip and whether it was a no-op.
type PushResult struct {
	// Ref is the remote ref that was pushed.
	Ref Ref
	// Tip is the remote's new tip.
	Tip CommitID
	// UpToDate is true when the remote was already at the local tip (a clean no-op).
	UpToDate bool
}
