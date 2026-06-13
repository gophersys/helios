package gitrepositorytest

import (
	"bytes"
	"context"

	"github.com/gophersys/libs/go/gitrepository"
)

// Author runs stage / commit against the in-memory model. The library has already validated
// and stamped Identity (author+committer+trailers); the fake records it. Pure-local; no
// credential.
//
//nolint:gocritic // contract §2/§3: the Backend interface takes the op descriptor by value (the frozen seam); the fake mirrors it.
func (b *Backend) Author(ctx context.Context, op gitrepository.AuthorOp) (gitrepository.AuthorResult, error) {
	if err := contextDone(ctx); err != nil {
		return gitrepository.AuthorResult{}, err
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	m := b.ensureModel(op.Root)

	switch op.Kind {
	case gitrepository.AuthorStage:
		result, err := b.stage(m, &op)
		return result, gitrepository.WrapError(err) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	case gitrepository.AuthorCommit:
		result, err := b.commit(m, &op)
		return result, gitrepository.WrapError(err) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	default:
		return gitrepository.AuthorResult{}, gitrepository.WrapError(&gitrepository.NotFoundError{What: "unknown author kind"}) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	}
}

// stage adds the requested paths (or All) to the worktree's index, then returns the post-stage
// Status. Staging exactly the requested paths is what makes a swarm worktree stage exactly its
// FileLease set (02 §2).
func (b *Backend) stage(m *model, op *gitrepository.AuthorOp) (gitrepository.AuthorResult, error) {
	wt := m.worktrees[op.Worktree]
	if wt == nil {
		return gitrepository.AuthorResult{}, &gitrepository.NotFoundError{What: "worktree " + op.Worktree}
	}
	head := treeOf(m.headCommit(wt))

	paths := op.Paths
	if op.All && len(paths) == 0 {
		paths = changedPaths(wt, head)
	}
	for _, path := range paths {
		if content, present := wt.working[path]; present {
			snapshot := make([]byte, len(content))
			copy(snapshot, content)
			wt.index[path] = &snapshot
		} else if _, inHead := head[path]; inHead {
			// A path removed from the working tree but present in HEAD stages as a deletion.
			wt.index[path] = nil
		}
	}
	return gitrepository.AuthorResult{Status: m.status(op.Worktree)}, nil
}

// changedPaths is the set of working-tree paths differing from HEAD plus HEAD paths removed
// from the working tree — the universe `git add -A` would stage.
func changedPaths(wt *worktree, head map[string][]byte) []string {
	seen := map[string]struct{}{}
	for path, content := range wt.working {
		prior, ok := head[path]
		if !ok || !bytes.Equal(prior, content) {
			seen[path] = struct{}{}
		}
	}
	for path := range head {
		if _, present := wt.working[path]; !present {
			seen[path] = struct{}{}
		}
	}
	return sortedPaths(seen)
}

// commit records the staged index as a new commit AS the stamped Identity, advancing the
// worktree's branch head. An empty index with AllowEmpty=false is NothingToCommitError. The
// new commit carries the Eden-* trailers verbatim so they are queryable (the audit trail).
func (b *Backend) commit(m *model, op *gitrepository.AuthorOp) (gitrepository.AuthorResult, error) {
	wt := m.worktrees[op.Worktree]
	if wt == nil {
		return gitrepository.AuthorResult{}, &gitrepository.NotFoundError{What: "worktree " + op.Worktree}
	}
	if len(wt.index) == 0 && !op.AllowEmpty {
		return gitrepository.AuthorResult{}, &gitrepository.NothingToCommitError{}
	}

	tree := treeOf(m.headCommit(wt))
	for path, staged := range wt.index {
		if staged == nil {
			delete(tree, path)
			continue
		}
		tree[path] = *staged
	}

	id := m.mintID()
	m.commits[id] = &commit{
		id:       id,
		parent:   m.branches[wt.branch],
		tree:     tree,
		message:  op.Message,
		trailers: op.Trailers,
		author:   op.AuthorName + " <" + op.AuthorEmail + ">",
	}
	m.branches[wt.branch] = id
	// The commit clears the index; the working tree now matches the new HEAD for the committed
	// paths (uncommitted working-tree edits, if any, persist).
	wt.index = map[string]*[]byte{}

	return gitrepository.AuthorResult{Commit: gitrepository.CommitIDFromHex(id)}, nil
}
