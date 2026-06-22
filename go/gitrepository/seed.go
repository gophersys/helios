package gitrepository

import (
	"context"
)

// SetRemote re-points (or adds) a logical remote name to url IN MEMORY — it mutates only this
// Repository's logical name → URL map (Config.Remotes), the same map Fetch/Push resolve a Ref
// against. It runs NO git process and touches no on-disk remote config: the system-git backend
// fetches/pushes by URL (the credential rides the helper seam, never the stored remote), so the
// logical map is the only thing a transfer reads.
//
// It is the template-copy primitive's first half: `Clone` the template (origin → template URL),
// then `SetRemote("origin", <newRepoURL>)` so the subsequent `Push` publishes into the NEW,
// empty repository rather than back at the template. PURE validation, identical to New's remote
// checks (non-empty, no whitespace, legal logical name); a malformed name/url is an
// InvalidRefError. Concurrency-safe: the write is serialized with resolveRemote under r.mu.
func (r *Repository) SetRemote(name, url string) error {
	if !validRemoteName(name) {
		return wrapKind(&InvalidRefError{Ref: "invalid remote name: " + name})
	}
	switch {
	case url == "":
		return wrapKind(&InvalidRefError{Ref: "remote " + name + " has an empty URL"})
	case containsAnyWhitespace(url):
		return wrapKind(&InvalidRefError{Ref: "remote " + name + " URL contains whitespace"})
	}
	r.mu.Lock()
	r.remotes[name] = url
	r.mu.Unlock()
	return nil
}

// snapshotRemotes returns a copy of the logical remote map under r.mu, so a derived Repository
// (a clone or a worktree) never aliases the parent's map AND never reads it while a concurrent
// SetRemote re-points an entry.
func (r *Repository) snapshotRemotes() map[string]string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return cloneRemotes(r.remotes)
}

// Flatten drops the worked checkout's commit history and replaces the checked-out branch with a
// SINGLE root commit that snapshots the current working tree — the template-copy seed. After
// `Clone`-ing a template, the clone still carries the template's full history; Flatten collapses
// it to one "seed from template" commit so the template's past does not bleed into the new
// repository. The single seed commit is then published by an ordinary Push into the new origin's
// UNBORN branch — a clean first push — so the fast-forward-only Push contract is preserved
// (there is no force-push and no remote rewrite: the seed IS the first commit on the new origin).
//
// Identity is REQUIRED (after the Config.DefaultAuthor fallback, exactly like Commit) — a zero
// Identity is an InvalidRefError, and an empty Message is rejected. The library stamps
// author+committer and injects the Eden-* audit trailers for an ActorAgent, resolving the commit
// time from the Clock when Identity.When is zero. Mutating; serialized on the Root checkout.
// Returns the new seed CommitID.
//
//nolint:gocritic // contract §2: Flatten takes FlattenOptions by value (a plain copyable seed descriptor; the frozen surface).
func (r *Repository) Flatten(ctx context.Context, options FlattenOptions) (CommitID, error) {
	if err := contextErr(ctx); err != nil {
		return CommitID{}, err
	}

	resolved := r.resolveAuthor(&options.Author)
	if resolved.IsZero() {
		return CommitID{}, wrapKind(&InvalidRefError{Ref: "Flatten requires a non-zero Identity (Name+Email)"})
	}
	if options.Message == "" {
		return CommitID{}, wrapKind(&InvalidRefError{Ref: "Flatten requires a non-empty message"})
	}

	when := resolved.When
	if when.IsZero() {
		when = r.clock.Now()
	}

	op := ProvisionOp{
		Kind:        ProvisionFlattenHistory,
		Root:        r.root,
		Dir:         r.root,
		Message:     options.Message,
		AuthorName:  resolved.Name,
		AuthorEmail: resolved.Email,
		When:        when.Format(commitTimeLayout),
		Trailers:    auditTrailers(&resolved),
	}

	lock := r.worktreeLock(r.root)
	lock.Lock()
	defer lock.Unlock()

	result, err := r.backend.Provision(ctx, op, nil)
	if err != nil {
		return CommitID{}, wrapBackend(err)
	}
	return result.Head, nil
}

// containsAnyWhitespace reports whether s carries a space, tab, or newline — the same remote-URL
// guard New applies (a whitespace-bearing URL would split on an argv).
func containsAnyWhitespace(s string) bool {
	for _, r := range s {
		if r == ' ' || r == '\t' || r == '\n' {
			return true
		}
	}
	return false
}
