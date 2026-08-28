package gitrepositorytest

import (
	"sort"
	"sync/atomic"

	"github.com/gophersys/libs/go/gitrepository"
)

// idCounter is a process-wide monotonic source for commit ids, so ids are globally unique
// ACROSS models (a local repo and the bare remote it pushes to). A per-model counter would
// collide once a commit is copied between models on a push, breaking ancestry queries.
var idCounter atomic.Int64

// model is the in-memory git model behind the fake Backend: a commit log, branch heads, a
// per-worktree index and working tree, and the linked-worktree registry. It is faithful
// enough to pass the SAME conformance suite as the real system-git backend — ff-only push,
// per-actor audit trailers, worktree isolation, the read surfaces — without a git binary.
//
// Concurrency: every method holds mu. The library serializes mutating verbs per worktree, so
// the model never sees a torn write; mu additionally guards the shared commit/branch state
// the library does NOT serialize across distinct worktrees (distinct worktrees share one
// commit graph and branch namespace, exactly as real git's .git store does).
type model struct {
	// commits is the content-addressed commit graph: id → commit.
	commits map[string]*commit
	// branches maps a short branch name → its tip commit id ("" for an unborn branch head).
	branches map[string]string
	// worktrees maps a worktree path → its live state (index, working tree, checked-out branch).
	worktrees map[string]*worktree
	// mainPath is the primary working tree's path (never removable via RemoveWorktree).
	mainPath string
}

// commit is one node in the in-memory commit graph.
type commit struct {
	id       string
	parent   string
	tree     map[string][]byte // path → content snapshot
	message  string
	trailers []gitrepository.AuthorTrailer
	author   string // "Name <email>"
}

// worktree is one checked-out working tree: its branch, a staged index, and the working-tree
// content. The index and working set are DISTINCT per worktree — that disjointness IS the
// swarm-isolation primitive the conformance suite proves (02 §2).
type worktree struct {
	path   string
	branch string
	// index is the staged snapshot: path → content (a deletion is recorded as a nil value).
	index map[string]*[]byte
	// working is the working-tree content: path → content. A path absent from the parent
	// commit's tree but present here and not staged is "untracked".
	working map[string][]byte
	isMain  bool
}

// newModel builds an empty model with a single unborn "main" branch and a main worktree at
// root. It is the zero state a fresh fake Backend exposes.
func newModel(root string) *model {
	m := &model{
		commits:   map[string]*commit{},
		branches:  map[string]string{"main": ""},
		worktrees: map[string]*worktree{},
		mainPath:  root,
	}
	m.worktrees[root] = &worktree{
		path:    root,
		branch:  "main",
		index:   map[string]*[]byte{},
		working: map[string][]byte{},
		isMain:  true,
	}
	return m
}

// mintID returns a fresh, globally-unique 40-hex commit id (process-wide monotonic), so an id
// copied between models on a push never collides with another model's freshly-minted id.
func (m *model) mintID() string {
	n := idCounter.Add(1)
	const hexDigits = "0123456789abcdef"
	id := make([]byte, 40)
	for i := 39; i >= 0; i-- {
		id[i] = hexDigits[n&0xf]
		n >>= 4
	}
	return string(id)
}

// headCommit returns the commit a worktree's branch points at, or nil for an unborn branch.
func (m *model) headCommit(wt *worktree) *commit {
	tip := m.branches[wt.branch]
	if tip == "" {
		return nil
	}
	return m.commits[tip]
}

// treeOf returns a copy of the tree a commit snapshots (empty for an unborn branch).
func treeOf(c *commit) map[string][]byte {
	out := map[string][]byte{}
	if c == nil {
		return out
	}
	for path, content := range c.tree {
		copied := make([]byte, len(content))
		copy(copied, content)
		out[path] = copied
	}
	return out
}

// sortedPaths returns the keys of a path map in deterministic order (status/diff stability).
func sortedPaths[V any](in map[string]V) []string {
	paths := make([]string, 0, len(in))
	for path := range in {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	return paths
}

// isAncestor reports whether ancestor is an ancestor of (or equal to) descendant in the
// commit graph — the fast-forward test the push verb enforces. The zero (unborn) ancestor is
// an ancestor of everything (a brand-new remote branch).
func (m *model) isAncestor(ancestor, descendant string) bool {
	if ancestor == "" {
		return true
	}
	for cursor := descendant; cursor != ""; {
		if cursor == ancestor {
			return true
		}
		node := m.commits[cursor]
		if node == nil {
			return false
		}
		cursor = node.parent
	}
	return false
}
