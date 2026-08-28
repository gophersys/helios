package gitrepository

import (
	"context"
)

// trailer keys for the per-actor audit trail (02 §1, 07 §7). They make the commit log
// queryable by actor WITHOUT parsing a free-text name.
const (
	trailerRunID     = "Eden-Run-ID"
	trailerSessionID = "Eden-Session-ID"
	trailerPhase     = "Eden-Phase"
)

// commitTimeLayout is the git author-date format the library stamps (RFC2822-ish; git
// accepts strict ISO-8601 too). We use the strict ISO form with an explicit offset so a
// deterministic Clock produces a reproducible commit timestamp.
const commitTimeLayout = "2006-01-02T15:04:05-07:00"

// Stage adds the requested paths to the index of worktree. Mutating; serialized per
// worktree. Returns the post-stage Status.
func (r *Repository) Stage(ctx context.Context, worktree string, options StageOptions) (Status, error) {
	if err := contextErr(ctx); err != nil {
		return Status{}, err
	}
	path, err := r.validateWorktree(worktree)
	if err != nil {
		return Status{}, err
	}
	if len(options.Paths) == 0 && !options.All {
		return Status{}, wrapKind(&InvalidRefError{Ref: "Stage requires explicit Paths or All"})
	}
	for _, p := range options.Paths {
		if p == "" || p == "--" {
			return Status{}, wrapKind(&InvalidRefError{Ref: "invalid stage pathspec"})
		}
	}

	lock := r.worktreeLock(path)
	lock.Lock()
	defer lock.Unlock()

	result, err := r.backend.Author(ctx, AuthorOp{
		Kind:     AuthorStage,
		Root:     r.root,
		Worktree: path,
		Paths:    options.Paths,
		All:      options.All,
	})
	if err != nil {
		return Status{}, wrapBackend(err)
	}
	return result.Status, nil
}

// Commit records the staged index AS the given Identity. Identity is REQUIRED — a zero
// Identity is an InvalidRefError; every commit is attributable. The library stamps
// author+committer, injects the Eden-* trailers for ActorAgent, resolves the commit time
// from the Clock when Identity.When is zero, and returns the new CommitID.
//
//nolint:gocritic // contract §2: Commit takes the Author Identity by value (the frozen surface; Identity is a plain copyable audit stamp).
func (r *Repository) Commit(ctx context.Context, worktree, message string, author Identity, options CommitOptions) (CommitID, error) {
	if err := contextErr(ctx); err != nil {
		return CommitID{}, err
	}
	path, err := r.validateWorktree(worktree)
	if err != nil {
		return CommitID{}, err
	}

	resolved := r.resolveAuthor(&author)
	if resolved.IsZero() {
		return CommitID{}, wrapKind(&InvalidRefError{Ref: "Commit requires a non-zero Identity (Name+Email)"})
	}
	if message == "" {
		return CommitID{}, wrapKind(&InvalidRefError{Ref: "Commit requires a non-empty message"})
	}

	when := resolved.When
	if when.IsZero() {
		when = r.clock.Now()
	}

	op := AuthorOp{
		Kind:        AuthorCommit,
		Root:        r.root,
		Worktree:    path,
		Message:     message,
		AuthorName:  resolved.Name,
		AuthorEmail: resolved.Email,
		When:        when.Format(commitTimeLayout),
		Trailers:    auditTrailers(&resolved),
		AllowEmpty:  options.AllowEmpty,
	}

	lock := r.worktreeLock(path)
	lock.Lock()
	defer lock.Unlock()

	result, err := r.backend.Author(ctx, op)
	if err != nil {
		return CommitID{}, wrapBackend(err)
	}
	return result.Commit, nil
}

// resolveAuthor merges a per-commit Identity over Config.DefaultAuthor: a missing Name/Email
// on the per-commit identity falls back to the platform-actor default, while Kind and the
// Eden keys come from the per-commit identity (one repository commits as many actors).
func (r *Repository) resolveAuthor(author *Identity) Identity {
	resolved := *author
	if resolved.Name == "" {
		resolved.Name = r.defaultAuthor.Name
	}
	if resolved.Email == "" {
		resolved.Email = r.defaultAuthor.Email
	}
	return resolved
}

// auditTrailers builds the queryable Eden-* trailer set for an ActorAgent commit. A human
// or platform commit carries NONE of those trailers (the contract's per-actor audit
// distinction). Empty keys are omitted so a partially-populated agent identity does not emit
// a blank trailer.
func auditTrailers(identity *Identity) []AuthorTrailer {
	if identity.Kind != ActorAgent {
		return nil
	}
	var trailers []AuthorTrailer
	if identity.RunID != "" {
		trailers = append(trailers, AuthorTrailer{Key: trailerRunID, Value: identity.RunID})
	}
	if identity.SessionID != "" {
		trailers = append(trailers, AuthorTrailer{Key: trailerSessionID, Value: identity.SessionID})
	}
	if identity.Phase != "" {
		trailers = append(trailers, AuthorTrailer{Key: trailerPhase, Value: identity.Phase})
	}
	return trailers
}

// Fetch updates remote-tracking refs for the named remote WITHOUT touching the working tree
// or local branches. Credential via the opaque secrets.Reference, resolved at the operation.
func (r *Repository) Fetch(ctx context.Context, options FetchOptions) (map[Ref]CommitID, error) {
	if err := contextErr(ctx); err != nil {
		return nil, err
	}
	url, err := r.resolveRemote(options.Remote)
	if err != nil {
		return nil, err
	}
	for _, ref := range options.Refs {
		if ref.Branch.IsZero() {
			return nil, wrapKind(&InvalidRefError{Ref: "fetch ref has an empty branch"})
		}
	}

	credential, err := r.resolveCredential(ctx, options.Credential, options.Remote)
	if err != nil {
		return nil, err
	}
	defer zeroize(credential)

	result, err := r.backend.Transfer(ctx, TransferOp{
		Kind:          TransferFetch,
		Root:          r.root,
		Remote:        options.Remote,
		RemoteURL:     url,
		Refs:          options.Refs,
		Prune:         options.Prune,
		HasCredential: credential != nil,
	}, credential)
	if err != nil {
		return nil, wrapBackend(err)
	}
	return result.Tips, nil
}

// Push publishes a local branch tip to a remote Ref. FAST-FORWARD-ONLY by contract: a
// non-ff update returns NonFastForwardError (carrying both tips). There is NO Force field.
func (r *Repository) Push(ctx context.Context, options PushOptions) (PushResult, error) {
	if err := contextErr(ctx); err != nil {
		return PushResult{}, err
	}
	url, err := r.resolveRemote(options.Remote)
	if err != nil {
		return PushResult{}, err
	}
	if options.LocalRef.IsZero() {
		return PushResult{}, wrapKind(&InvalidRefError{Ref: "push requires a LocalRef"})
	}
	dest := options.DestRef
	if dest.IsZero() {
		dest = options.LocalRef
	}

	credential, err := r.resolveCredential(ctx, options.Credential, options.Remote)
	if err != nil {
		return PushResult{}, err
	}
	defer zeroize(credential)

	result, err := r.backend.Transfer(ctx, TransferOp{
		Kind:            TransferPush,
		Root:            r.root,
		Remote:          options.Remote,
		RemoteURL:       url,
		LocalRef:        options.LocalRef.String(),
		DestRef:         dest.String(),
		FastForwardOnly: true, // the contract guard: a Backend MUST NOT force-push.
		HasCredential:   credential != nil,
	}, credential)
	if err != nil {
		return PushResult{}, wrapBackend(err)
	}

	pushedRef := Ref{Remote: options.Remote, Branch: dest}
	return PushResult{
		Ref:      pushedRef,
		Tip:      result.Tips[pushedRef],
		UpToDate: result.UpToDate,
	}, nil
}
