// Package gitrepositorytest is the canonical public fake Backend (the testing pattern,
// 10 §4 / 08 §2) plus the conformance suite. The fake is an IN-MEMORY git model — worktrees,
// a staged index, a commit log, branch heads — so a consumer (orchestrator, engine, chat
// backend) tests its flow WITHOUT a git binary or a real clone; and a thin real-binary
// harness (NewRealRepo) backs the live arm (C23: tests spin up real repos). The SAME
// conformance suite (Run) drives the in-memory fake AND the real system-git Backend over
// NewRealRepo, proving the load-bearing invariants: ff-only push, never-merge, per-actor
// audit trailers, worktree isolation, credential-never-leaked.
package gitrepositorytest

import (
	"context"
	"strings"
	"sync"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/secrets"
)

// Backend is a deterministic in-memory gitrepository.Backend. Zero value is an empty repo (no
// commits, one "main" branch). No clock, no I/O, no subprocess. Safe for concurrent reads;
// mutating verbs are serialized by the library per worktree, and the model's own mutex guards
// the shared commit/branch state.
type Backend struct {
	// Pushed records every Transfer(push) the SUT issued — refs only, never credentials — for
	// "did the agent push ws3/x to eden?" assertions.
	Pushed []gitrepository.PushOptions
	// CredentialRefs records which secrets.Reference each networked op resolved — refs ONLY,
	// never values — for the credential-confinement guarantee.
	CredentialRefs []secrets.Reference

	mu sync.Mutex
	// model is the local repository's in-memory git model, created lazily on first use so the
	// zero Backend is usable and the Root binds to the library's Config.Root.
	model *model
	// remotes is the shared bare-remote registry: remote URL → its in-memory model. A push
	// fast-forwards the remote's branch; a fetch reads its tips. Distinct Backends sharing a
	// remote URL share the same remote model (a real bare origin).
	remotes map[string]*model
	// canaryArgs records a projection of every op's argument surface (the descriptor fields
	// that would become argv/env/dir) so AssertCredentialNeverInArgs can prove a credential
	// canary never reached a process surface.
	canaryArgs []string
	// failNextPush, when non-nil, forces the next Transfer(push) to return it.
	failNextPush error
}

// compile-time assertion: *Backend implements gitrepository.Backend.
var _ gitrepository.Backend = (*Backend)(nil)

// New returns a fresh in-memory fake Backend.
func New() *Backend {
	return &Backend{remotes: map[string]*model{}}
}

// Seed pre-populates the local repository's "main" branch with one commit containing files so
// a read-surface test has content. Fluent.
func (b *Backend) Seed(branch string, files map[string]string) *Backend {
	b.mu.Lock()
	defer b.mu.Unlock()
	m := b.ensureModel("")
	tree := map[string][]byte{}
	for path, content := range files {
		tree[path] = []byte(content)
	}
	id := m.mintID()
	parent := m.branches[branch]
	m.commits[id] = &commit{
		id:      id,
		parent:  parent,
		tree:    tree,
		message: "seed",
		author:  "Seed <seed@eden.dev>",
	}
	m.branches[branch] = id
	// Refresh the main worktree's working tree to the seeded content if it is on this branch.
	if wt, ok := m.worktrees[m.mainPath]; ok && wt.branch == branch {
		wt.working = treeOf(m.commits[id])
	}
	return b
}

// SetWorkingFile places content at path in the working tree of the worktree rooted at
// worktree — the in-memory analog of a real editor/agent writing a file before Stage. It is
// the seam the conformance suite uses to seed a working-tree change for the fake arm (the real
// arm writes to disk). worktree "" addresses the main tree.
func (b *Backend) SetWorkingFile(worktree, path, content string) {
	b.mu.Lock()
	defer b.mu.Unlock()
	m := b.ensureModel("")
	target := worktree
	if target == "" {
		target = m.mainPath
	}
	wt := m.worktrees[target]
	if wt == nil {
		return
	}
	wt.working[path] = []byte(content)
}

// FailNextPush forces the next Transfer(push) to return err — pass a gitrepository error
// value, e.g. gitrepository.NonFastForwardError{...} or gitrepository.AuthError{...} — for
// the divergence-routes-to-gate and bad-credential paths. Fluent.
func (b *Backend) FailNextPush(err error) *Backend {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.failNextPush = err
	return b
}

// ensureModel lazily creates the local model bound to root (the library's Config.Root, passed
// on the first op). A subsequent op with the same root reuses it; a clone creates the
// destination's model on demand. Caller holds b.mu.
func (b *Backend) ensureModel(root string) *model {
	if b.model == nil {
		if root == "" {
			root = "/in-memory"
		}
		b.model = newModel(root)
	}
	return b.model
}

// recordArgs appends an op's argument projection to canaryArgs (the surface a real backend
// would place on argv/env/dir), so AssertCredentialNeverInArgs can scan it. A credential
// value is NEVER among these fields — it rides the separate *secrets.Secret, confined to
// Secret.Use — so a canary appearing here would be a real leak.
func (b *Backend) recordArgs(parts ...string) {
	for _, part := range parts {
		if part != "" {
			b.canaryArgs = append(b.canaryArgs, part)
		}
	}
}

// Capabilities declares the in-memory backend's surface. It declares shallow + linked
// worktrees (the operations it models) and NOT partial clone, so the shallow/partial-honesty
// conformance case is exercised: a capability declared is delivered, one not declared is
// rejected by the library before reaching the backend.
func (b *Backend) Capabilities() gitrepository.Capabilities {
	return gitrepository.Capabilities{ShallowClone: true, LinkedWorktree: true, PartialClone: false}
}

// AssertCredentialNeverInArgs fails t if canary appears in ANY recorded operation's argument
// projection — the "credential never on argv / in logs" guarantee, runnable (07 §2; pairs
// with secretstest.AssertNotLeaked over a captured log buffer). The value lives only inside
// the helper's Secret.Use frame, never on a process surface.
func (b *Backend) AssertCredentialNeverInArgs(t TestingT, canary string) {
	t.Helper()
	b.mu.Lock()
	defer b.mu.Unlock()
	if canary == "" {
		return
	}
	for _, arg := range b.canaryArgs {
		if strings.Contains(arg, canary) {
			t.Errorf("credential canary leaked: %q appears in a recorded operation argument", canary)
			return
		}
	}
}

// TestingT is the minimal testing surface the fake needs (satisfied by *testing.T).
type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
	TempDir() string
	Cleanup(func())
}

// contextDone reports a canceled/expired context so the fake honors cancellation like the
// real backend (the library already short-circuits, but a direct Backend call must too). It
// maps ctx.Err() through the errors model so the result classifies (KindCanceled/KindDeadline).
func contextDone(ctx context.Context) error {
	if err := errors.FromContext(ctx); err != nil {
		return err
	}
	return nil
}
