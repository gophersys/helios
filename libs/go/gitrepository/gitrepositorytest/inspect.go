package gitrepositorytest

import (
	"bytes"
	"context"
	"fmt"
	"strings"

	"github.com/gophersys/libs/go/gitrepository"
)

// Inspect runs the read surface (status / diff / branches / worktrees) against the in-memory
// model. Pure-local; no credential.
//
//nolint:gocritic // contract §2/§3: the Backend interface takes the op descriptor by value (the frozen seam); the fake mirrors it.
func (b *Backend) Inspect(ctx context.Context, op gitrepository.InspectOp) (gitrepository.InspectResult, error) {
	if err := contextDone(ctx); err != nil {
		return gitrepository.InspectResult{}, err
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	m := b.ensureModel(op.Root)

	switch op.Kind {
	case gitrepository.InspectStatus:
		return gitrepository.InspectResult{Status: m.status(op.Worktree)}, nil
	case gitrepository.InspectDiff:
		diff, err := m.diff(&op)
		return gitrepository.InspectResult{Diff: diff}, gitrepository.WrapError(err) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	case gitrepository.InspectBranches:
		return gitrepository.InspectResult{Branches: m.branchList(op.IncludeRemote)}, nil
	case gitrepository.InspectWorktrees:
		return gitrepository.InspectResult{Worktrees: m.worktreeList()}, nil
	default:
		return gitrepository.InspectResult{}, gitrepository.WrapError(&gitrepository.NotFoundError{What: "unknown inspect kind"}) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	}
}

// status computes a worktree's working-tree status vs its branch tip: branch, HEAD, clean
// flag, and the per-path change set (the chat's file-modification rail, C23).
func (m *model) status(path string) gitrepository.Status {
	wt := m.worktrees[path]
	if wt == nil {
		return gitrepository.Status{Clean: true}
	}
	head := treeOf(m.headCommit(wt))
	status := gitrepository.Status{
		Branch: mustBranch(wt.branch),
		Head:   commitID(m.headCommit(wt)),
		Clean:  true,
	}

	// Staged changes (index vs HEAD).
	for _, path := range sortedPaths(wt.index) {
		staged := wt.index[path]
		kind := gitrepository.ChangeModified
		if _, inHead := head[path]; !inHead {
			kind = gitrepository.ChangeAdded
		}
		if staged == nil {
			kind = gitrepository.ChangeDeleted
		}
		status.Changes = append(status.Changes, gitrepository.FileChange{
			Path:     path,
			Status:   kind,
			Staged:   true,
			IsBinary: staged != nil && isBinary(*staged),
		})
		status.Clean = false
	}

	// Working-tree changes vs HEAD that are NOT staged: modified/added/untracked/deleted.
	for _, path := range sortedPaths(wt.working) {
		if _, staged := wt.index[path]; staged {
			continue
		}
		content := wt.working[path]
		prior, inHead := head[path]
		switch {
		case !inHead:
			status.Changes = append(status.Changes, gitrepository.FileChange{
				Path: path, Status: gitrepository.ChangeUntracked, IsBinary: isBinary(content),
			})
			status.Clean = false
		case !bytes.Equal(prior, content):
			status.Changes = append(status.Changes, gitrepository.FileChange{
				Path: path, Status: gitrepository.ChangeModified, IsBinary: isBinary(content),
			})
			status.Clean = false
		}
	}

	// Deletions in the working tree (present in HEAD, absent from working, not staged).
	for _, path := range sortedPaths(head) {
		if _, present := wt.working[path]; present {
			continue
		}
		if _, staged := wt.index[path]; staged {
			continue
		}
		status.Changes = append(status.Changes, gitrepository.FileChange{
			Path: path, Status: gitrepository.ChangeDeleted,
		})
		status.Clean = false
	}
	return status
}

// diff computes a bounded Diff for the requested mode. The fake produces a faithful unified-
// diff body for text and flags binary files without inlining bytes; NameOnly returns paths.
func (m *model) diff(op *gitrepository.InspectOp) (gitrepository.Diff, error) {
	from, to, err := m.diffTrees(op)
	if err != nil {
		return gitrepository.Diff{}, err
	}

	var files []gitrepository.FileDiff
	var size int64
	truncated := false
	for _, path := range unionPaths(from, to) {
		if len(op.Paths) > 0 && !pathMatches(path, op.Paths) {
			continue
		}
		before, hadBefore := from[path]
		after, hadAfter := to[path]
		if hadBefore && hadAfter && bytes.Equal(before, after) {
			continue
		}
		fileDiff, consumed, hit := buildFileDiff(path, before, after, hadBefore, hadAfter, op.NameOnly, op.MaxBytes, size)
		if hit {
			truncated = true
		}
		size += consumed
		files = append(files, fileDiff)
	}
	return gitrepository.Diff{Files: files, Truncated: truncated}, nil
}

// buildFileDiff constructs one path's FileDiff, returning the bytes its hunk consumed and
// whether the MaxBytes cap was hit (NameOnly and binary files carry no hunk).
func buildFileDiff(path string, before, after []byte, hadBefore, hadAfter, nameOnly bool, maxBytes, used int64) (gitrepository.FileDiff, int64, bool) {
	fileDiff := gitrepository.FileDiff{Path: path, Status: diffStatus(hadBefore, hadAfter)}
	if isBinary(before) || isBinary(after) {
		fileDiff.IsBinary = true
	}
	if nameOnly || fileDiff.IsBinary {
		return fileDiff, 0, false
	}
	hunk, added, removed := unifiedHunk(before, after)
	if int64(len(hunk.Text))+used > maxBytes {
		return fileDiff, 0, true
	}
	fileDiff.Hunks = []gitrepository.Hunk{hunk}
	fileDiff.AddedLines = added
	fileDiff.RemovedLines = removed
	return fileDiff, int64(len(hunk.Text)), false
}

// diffStatus classifies a path's change from its presence in the before/after trees.
func diffStatus(hadBefore, hadAfter bool) gitrepository.ChangeKind {
	switch {
	case !hadBefore:
		return gitrepository.ChangeAdded
	case !hadAfter:
		return gitrepository.ChangeDeleted
	default:
		return gitrepository.ChangeModified
	}
}

// diffTrees resolves the (from, to) content snapshots a Diff compares for each mode.
func (m *model) diffTrees(op *gitrepository.InspectOp) (from, to map[string][]byte, err error) {
	switch op.DiffMode {
	case gitrepository.DiffWorkingVsHead:
		wt := m.worktrees[op.Worktree]
		if wt == nil {
			return nil, nil, &gitrepository.NotFoundError{What: "worktree " + op.Worktree}
		}
		return treeOf(m.headCommit(wt)), wt.working, nil
	case gitrepository.DiffStagedVsHead:
		wt := m.worktrees[op.Worktree]
		if wt == nil {
			return nil, nil, &gitrepository.NotFoundError{What: "worktree " + op.Worktree}
		}
		return treeOf(m.headCommit(wt)), m.stagedTree(wt), nil
	case gitrepository.DiffCommits:
		fromTree, ferr := m.treeAtRevision(op.From)
		if ferr != nil {
			return nil, nil, ferr
		}
		toTree, terr := m.treeAtRevision(op.To)
		if terr != nil {
			return nil, nil, terr
		}
		return fromTree, toTree, nil
	default:
		return nil, nil, &gitrepository.InvalidRefError{Ref: "unknown diff mode"}
	}
}

// stagedTree overlays a worktree's index onto its HEAD tree (what a Commit would record).
func (m *model) stagedTree(wt *worktree) map[string][]byte {
	tree := treeOf(m.headCommit(wt))
	for path, staged := range wt.index {
		if staged == nil {
			delete(tree, path)
			continue
		}
		tree[path] = *staged
	}
	return tree
}

// treeAtRevision resolves a branch name or commit id to its tree snapshot.
func (m *model) treeAtRevision(rev string) (map[string][]byte, error) {
	if tip, ok := m.branches[rev]; ok {
		return treeOf(m.commits[tip]), nil
	}
	if c, ok := m.commits[rev]; ok {
		return treeOf(c), nil
	}
	return nil, &gitrepository.NotFoundError{What: "revision " + rev}
}

// branchList enumerates local (and optionally remote-tracking) branches with their tip.
func (m *model) branchList(includeRemote bool) []gitrepository.Branch {
	var branches []gitrepository.Branch
	for _, name := range sortedPaths(m.branches) {
		tip := m.branches[name]
		if tip == "" {
			continue // an unborn branch has no tip to list
		}
		branches = append(branches, gitrepository.Branch{
			Name: mustBranch(name),
			Tip:  gitrepository.CommitIDFromHex(tip),
		})
	}
	_ = includeRemote // the in-memory model has no remote-tracking refs to surface
	return branches
}

// worktreeList enumerates the live worktrees (path, branch, tip, isMain).
func (m *model) worktreeList() []gitrepository.WorktreeInfo {
	var infos []gitrepository.WorktreeInfo
	for _, path := range sortedPaths(m.worktrees) {
		wt := m.worktrees[path]
		infos = append(infos, gitrepository.WorktreeInfo{
			Path:   wt.path,
			Branch: mustBranch(wt.branch),
			Tip:    commitID(m.headCommit(wt)),
			IsMain: wt.isMain,
		})
	}
	return infos
}

// isBinary reports whether content looks binary (contains a NUL byte) — the heuristic git
// itself uses to decide between an inlined patch and a "Binary files differ" line.
func isBinary(content []byte) bool {
	for _, c := range content {
		if c == 0 {
			return true
		}
	}
	return false
}

// unionPaths returns the sorted union of two trees' paths.
func unionPaths(a, b map[string][]byte) []string {
	seen := map[string]struct{}{}
	for path := range a {
		seen[path] = struct{}{}
	}
	for path := range b {
		seen[path] = struct{}{}
	}
	return sortedPaths(seen)
}

// pathMatches reports whether path is covered by any pathspec (exact or directory prefix).
func pathMatches(path string, specs []string) bool {
	for _, spec := range specs {
		if path == spec || strings.HasPrefix(path, strings.TrimSuffix(spec, "/")+"/") {
			return true
		}
	}
	return false
}

// unifiedHunk builds a single faithful unified-diff hunk for a text change (a whole-file
// replace is sufficient for the conformance suite's bounded-diff and content assertions).
func unifiedHunk(before, after []byte) (hunk gitrepository.Hunk, added, removed int) {
	beforeLines := splitKeep(string(before))
	afterLines := splitKeep(string(after))
	var body strings.Builder
	fmt.Fprintf(&body, "@@ -1,%d +1,%d @@\n", len(beforeLines), len(afterLines))
	for _, line := range beforeLines {
		body.WriteString("-" + line + "\n")
		removed++
	}
	for _, line := range afterLines {
		body.WriteString("+" + line + "\n")
		added++
	}
	return gitrepository.Hunk{
		OldStart: 1, OldLines: len(beforeLines),
		NewStart: 1, NewLines: len(afterLines),
		Text: body.String(),
	}, added, removed
}

// splitKeep splits text into lines, dropping a single trailing empty element so a file with a
// terminal newline does not yield a phantom empty line.
func splitKeep(text string) []string {
	if text == "" {
		return nil
	}
	lines := strings.Split(text, "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	return lines
}
