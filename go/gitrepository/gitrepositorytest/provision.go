package gitrepositorytest

import (
	"bytes"
	"context"

	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/secrets"
)

// Provision runs clone / worktree-add / worktree-remove against the in-memory model. cred is
// set only for a clone that authenticates; the fake records the resolution (CredentialRefs)
// but the value never reaches an argument projection.
//
//nolint:gocritic // contract §2/§3: the Backend interface takes the op descriptor by value (the frozen seam); the fake mirrors it.
func (b *Backend) Provision(ctx context.Context, op gitrepository.ProvisionOp, cred *secrets.Secret) (gitrepository.ProvisionResult, error) {
	if err := contextDone(ctx); err != nil {
		return gitrepository.ProvisionResult{}, err
	}
	b.mu.Lock()
	defer b.mu.Unlock()

	switch op.Kind {
	case gitrepository.ProvisionClone:
		result, err := b.clone(&op, cred)
		return result, gitrepository.WrapError(err) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	case gitrepository.ProvisionAddWorktree:
		result, err := b.addWorktree(&op)
		return result, gitrepository.WrapError(err) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	case gitrepository.ProvisionRemoveWorktree:
		return gitrepository.ProvisionResult{}, gitrepository.WrapError(b.removeWorktree(&op)) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	default:
		return gitrepository.ProvisionResult{}, gitrepository.WrapError(&gitrepository.NotFoundError{What: "unknown provision kind"}) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	}
}

// clone materializes a fresh model at op.Dir seeded from the source remote's model (registered
// under op.RemoteURL), honoring shallow depth as a metadata flag. The credential, when set,
// is consumed via Secret.Use so the no-leak path is exercised; the value never touches args.
func (b *Backend) clone(op *gitrepository.ProvisionOp, cred *secrets.Secret) (gitrepository.ProvisionResult, error) {
	b.recordArgs(op.RemoteURL, op.Dir, op.Branch, op.RemoteName, op.Filter)
	consumeCredential(cred)

	source := b.remotes[op.RemoteURL]
	dest := newModel(op.Dir)
	if source != nil {
		// Copy the source's branch heads + commit graph into the clone.
		for id, c := range source.commits {
			dest.commits[id] = c
		}
		for name, tip := range source.branches {
			dest.branches[name] = tip
		}
		// Check out the requested branch (or "main") into the main worktree.
		branch := op.Branch
		if branch == "" {
			branch = "main"
		}
		if _, ok := dest.branches[branch]; ok {
			wt := dest.worktrees[dest.mainPath]
			wt.branch = branch
			wt.working = treeOf(dest.headCommit(wt))
		}
	}
	b.model = dest

	wt := dest.worktrees[dest.mainPath]
	head := dest.headCommit(wt)
	return gitrepository.ProvisionResult{
		Head:   commitID(head),
		Branch: mustBranch(wt.branch),
	}, nil
}

// addWorktree creates a NEW linked worktree at op.Dir on op.Branch, creating the branch from
// op.Start when CreateBranch. Its index and working tree are DISTINCT from every other
// worktree — the isolation primitive (02 §2). AlreadyExistsError if the path or branch exists.
func (b *Backend) addWorktree(op *gitrepository.ProvisionOp) (gitrepository.ProvisionResult, error) {
	m := b.ensureModel(op.Root)
	if _, exists := m.worktrees[op.Dir]; exists {
		return gitrepository.ProvisionResult{}, &gitrepository.AlreadyExistsError{What: "worktree " + op.Dir}
	}

	tip := ""
	if op.CreateBranch {
		if _, exists := m.branches[op.Branch]; exists {
			return gitrepository.ProvisionResult{}, &gitrepository.AlreadyExistsError{What: "branch " + op.Branch}
		}
		start, err := m.resolveStart(op.Start)
		if err != nil {
			return gitrepository.ProvisionResult{}, err
		}
		tip = start
		m.branches[op.Branch] = tip
	} else {
		existing, ok := m.branches[op.Branch]
		if !ok {
			return gitrepository.ProvisionResult{}, &gitrepository.NotFoundError{What: "branch " + op.Branch}
		}
		tip = existing
	}

	wt := &worktree{
		path:    op.Dir,
		branch:  op.Branch,
		index:   map[string]*[]byte{},
		working: treeOf(m.commits[tip]),
	}
	m.worktrees[op.Dir] = wt
	return gitrepository.ProvisionResult{
		Head:   commitID(m.commits[tip]),
		Branch: mustBranch(op.Branch),
	}, nil
}

// resolveStart resolves a worktree start revision to a commit id. It accepts a branch name or
// a commit id; an unknown revision is a NotFoundError. An empty/"HEAD" start resolves to the
// main worktree's current tip.
func (m *model) resolveStart(start string) (string, error) {
	if start == "" || start == "HEAD" {
		main := m.worktrees[m.mainPath]
		if main == nil {
			return "", nil
		}
		return m.branches[main.branch], nil
	}
	if tip, ok := m.branches[start]; ok {
		return tip, nil
	}
	if _, ok := m.commits[start]; ok {
		return start, nil
	}
	return "", &gitrepository.NotFoundError{What: "revision " + start}
}

// removeWorktree prunes the linked worktree at op.Dir (idempotent: an absent worktree is a
// no-op). A dirty worktree without Force is a DirtyWorktreeError; the main tree is never
// removable (the library guards this, defense-in-depth here too).
func (b *Backend) removeWorktree(op *gitrepository.ProvisionOp) error {
	m := b.ensureModel(op.Root)
	wt, ok := m.worktrees[op.Dir]
	if !ok {
		return nil // idempotent no-op
	}
	if wt.isMain || op.Dir == m.mainPath {
		return &gitrepository.InvalidRefError{Ref: "cannot remove the main working tree"}
	}
	if !op.Force && m.worktreeDirty(wt) {
		return &gitrepository.DirtyWorktreeError{Worktree: op.Dir}
	}
	delete(m.worktrees, op.Dir)
	if op.DeleteBranch {
		delete(m.branches, wt.branch)
	}
	return nil
}

// worktreeDirty reports whether a worktree has staged, unstaged, or untracked changes vs its
// branch tip.
func (m *model) worktreeDirty(wt *worktree) bool {
	if len(wt.index) > 0 {
		return true
	}
	head := treeOf(m.headCommit(wt))
	if len(wt.working) != len(head) {
		return true
	}
	for path, content := range wt.working {
		prior, ok := head[path]
		if !ok || !bytes.Equal(prior, content) {
			return true
		}
	}
	return false
}

// consumeCredential exercises Secret.Use so the credential path is realized exactly like the
// real backend (resolve → Use → never an arg). It discards the bytes; the model needs no
// authentication. A nil cred (public/local op) is a no-op.
func consumeCredential(cred *secrets.Secret) {
	if cred == nil {
		return
	}
	// The model needs no authentication; Use is invoked only to exercise the resolve→Use path
	// (the credential never becomes an argument). A Use error (an already-zeroized secret) is not
	// actionable here — the fake's job is to prove the value never leaks, not to authenticate.
	_ = cred.Use(func(_ []byte) error { return nil }) //nolint:errcheck // see comment: Use is exercised for the no-leak path; its error is unactionable in the fake.
}

// commitID maps a model commit to a gitrepository.CommitID (zero for a nil/unborn commit).
func commitID(c *commit) gitrepository.CommitID {
	if c == nil {
		return gitrepository.CommitID{}
	}
	return gitrepository.CommitIDFromHex(c.id)
}

// mustBranch parses a branch name the model itself produced (already validated). The zero
// BranchName covers the impossible malformed case rather than panicking.
func mustBranch(name string) gitrepository.BranchName {
	parsed, err := gitrepository.ParseBranchName(name)
	if err != nil {
		return gitrepository.BranchName{}
	}
	return parsed
}
