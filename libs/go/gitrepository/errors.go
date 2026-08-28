package gitrepository

import (
	"strconv"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// The error taxonomy is a set of distinct types, each carrying the offending
// ref/path/remote — NEVER a credential, NEVER raw stderr — and each mapping to a stable
// errors.Kind so the transport boundary needs no per-port table (errors.md §5, 10 §9).
// Inspected via errors.AsType; classified via errors.KindOf after the library wraps them
// with wrapKind. The Backend/library return them wrapped with %w so callers branch on
// type across git's stderr rewordings, not by string match.

type (
	// InvalidRefError reports a malformed branch name / revision (the argv-injection guard
	// rejected it) — or a zero Identity on Commit, or a worktree path outside Root.
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
		Ref    Ref
		Local  CommitID
		Remote CommitID
	}

	// ConflictError reports a working-tree state git considers conflicted (reported for a
	// gate's VISIBILITY; this library never resolves it).
	ConflictError struct{ Paths []string }

	// DirtyWorktreeError reports a mutating op blocked by uncommitted changes where a clean
	// tree is required (e.g. RemoveWorktree without Force).
	DirtyWorktreeError struct{ Worktree string }

	// AuthError reports a credential failure on a network verb (carries the ref, NEVER the
	// value) — the secrets/vault path (07 §2).
	AuthError struct {
		Reference secrets.Reference
		Remote    string
	}

	// DeniedError reports a host rejection (e.g. branch protection in byo-authority enforced
	// mode, ADR-0013) — distinct from an auth failure.
	DeniedError struct{ Ref Ref }

	// UnavailableError reports a transient network/host failure (retryable).
	UnavailableError struct{ Remote string }
)

// Error renders an operator-safe message; none of these ever interpolates a secret value
// (a Reference's canonical form is loggable by design, the value is not present).

func (e *InvalidRefError) Error() string {
	return "gitrepository: invalid ref " + strconv.Quote(e.Ref)
}

func (e *NotFoundError) Error() string {
	return "gitrepository: not found: " + strconv.Quote(e.What)
}

func (e *AlreadyExistsError) Error() string {
	return "gitrepository: already exists: " + strconv.Quote(e.What)
}

func (e *NothingToCommitError) Error() string {
	return "gitrepository: nothing to commit (empty index)"
}

func (e *NonFastForwardError) Error() string {
	return "gitrepository: non-fast-forward push to " + strconv.Quote(e.Ref.Remote+"/"+e.Ref.Branch.String()) +
		" (local " + strconv.Quote(e.Local.String()) + ", remote " + strconv.Quote(e.Remote.String()) + ")"
}

func (e *ConflictError) Error() string {
	return "gitrepository: working tree has " + strconv.Itoa(len(e.Paths)) + " conflicted path(s)"
}

func (e *DirtyWorktreeError) Error() string {
	return "gitrepository: worktree " + strconv.Quote(e.Worktree) + " has uncommitted changes"
}

func (e *AuthError) Error() string {
	msg := "gitrepository: credential rejected for remote " + strconv.Quote(e.Remote)
	if !e.Reference.IsZero() {
		msg += " (reference " + strconv.Quote(e.Reference.String()) + ")"
	}
	return msg
}

func (e *DeniedError) Error() string {
	return "gitrepository: remote rejected ref " + strconv.Quote(e.Ref.Remote+"/"+e.Ref.Branch.String())
}

func (e *UnavailableError) Error() string {
	return "gitrepository: remote " + strconv.Quote(e.Remote) + " unavailable"
}

// Each error exposes Kind() mapping it to the errors.md taxonomy (10 §9). This method is the
// SINGLE home for the type→Kind mapping: kindOf below reads it through the kindCarrier seam
// rather than re-deriving a parallel switch, so KindOf(err) classifies without string
// matching (contract §2 Kind table) and the mapping cannot drift between two declarations.

// Kind reports the stable errors.Kind for an InvalidRefError.
func (e *InvalidRefError) Kind() errors.Kind { return errors.KindInvalid }

// Kind reports the stable errors.Kind for a NotFoundError.
func (e *NotFoundError) Kind() errors.Kind { return errors.KindNotFound }

// Kind reports the stable errors.Kind for an AlreadyExistsError.
func (e *AlreadyExistsError) Kind() errors.Kind { return errors.KindConflict }

// Kind reports the stable errors.Kind for a NothingToCommitError.
func (e *NothingToCommitError) Kind() errors.Kind { return errors.KindConflict }

// Kind reports the stable errors.Kind for a NonFastForwardError.
func (e *NonFastForwardError) Kind() errors.Kind { return errors.KindConflict }

// Kind reports the stable errors.Kind for a ConflictError.
func (e *ConflictError) Kind() errors.Kind { return errors.KindConflict }

// Kind reports the stable errors.Kind for a DirtyWorktreeError.
func (e *DirtyWorktreeError) Kind() errors.Kind { return errors.KindConflict }

// Kind reports the stable errors.Kind for an AuthError.
func (e *AuthError) Kind() errors.Kind { return errors.KindUnauthenticated }

// Kind reports the stable errors.Kind for a DeniedError.
func (e *DeniedError) Kind() errors.Kind { return errors.KindPermission }

// Kind reports the stable errors.Kind for an UnavailableError.
func (e *UnavailableError) Kind() errors.Kind { return errors.KindUnavailable }

// WrapError wraps a typed gitrepository error with its stable errors.Kind so a Backend (the
// in-memory fake or any third-party Backend) returns errors that classify via errors.KindOf
// without the library re-parsing them. It is the seam a Backend uses to return a typed,
// already-classified error; the library's own backend uses the private wrapKind, which is
// identical. A nil error stays nil; an already-wrapped error keeps its Kind.
func WrapError(err error) error {
	if err == nil {
		return nil
	}
	return errors.Wrap(kindOf(err), err.Error(), err)
}

// kindCarrier is the classification seam: a typed error that carries its own stable
// errors.Kind via the Kind() method declared above. Every gitrepository error type
// implements it (the data IS its classification, contract §2 Kind table), so kindOf reads
// the carrier instead of re-deriving a parallel table — ONE home for the Kind mapping.
type kindCarrier interface{ Kind() errors.Kind }

// kindOf is the TOTAL classifier the library wraps with (wrapKind), so the transport
// boundary reads errors.KindOf without a gitrepository-specific table. It reads the
// error's OWN Kind() method (the single source of truth, defined per type above); a
// non-carrier error is KindUnknown.
//
// kindOf is only ever called by wrapKind/WrapError on a freshly-minted, UNWRAPPED
// gitrepository error the library is about to wrap; classification of an already-WRAPPED
// chain is errors.KindOf (which walks the chain). Reading the carrier on the unwrapped
// leaf keeps the Kind declared ONCE — there is no second switch to drift from the methods.
//
//nolint:errorlint // kindOf classifies an unwrapped leaf the library just minted; the wrapped-chain path is errors.KindOf via errors.AsType.
func kindOf(err error) errors.Kind {
	if carrier, ok := err.(kindCarrier); ok {
		return carrier.Kind()
	}
	return errors.KindUnknown
}

// wrapKind wraps a typed gitrepository error with its stable errors.Kind so the transport
// boundary maps it without a per-port table (10 §9). Returns nil for a nil error (the
// happy path reads linearly).
func wrapKind(err error) error {
	if err == nil {
		return nil
	}
	return errors.Wrap(kindOf(err), err.Error(), err)
}
