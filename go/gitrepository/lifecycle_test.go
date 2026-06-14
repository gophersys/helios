//go:build lifecycle

package gitrepository_test

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/gitrepository/gitrepositorytest"
)

// TestLifecycle_WorktreeDoubleRemoveIdempotentNoOrphans is the full-object-lifecycle
// conformance (ADR-0020 dimension (c)) for the gitrepository closeable handle: a REAL linked
// worktree — the swarm-isolation primitive (02 §2). AddWorktree materializes an on-disk
// worktree (the owned resource); RemoveWorktree is its idempotent Close (a second remove of an
// already-pruned worktree is a no-op, not an error); CountOwned reports the number of live
// LINKED worktrees (the main tree is never owned/removable). The driver asserts construct → use
// → first Close → SECOND Close is a no-op → CountOwned()==0 (the worktree was pruned exactly
// once, no orphan .git/worktrees metadata). The orphan-GOROUTINE half is asserted by the
// surrounding goleak.VerifyNone — the system-git backend must reap every `git` child it spawned.
// Tagged `//go:build lifecycle` so the heavy on-disk double-remove drive stays out of the fast
// unit run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling's git children would make it flaky, so the lifecycle/leak probe runs serially.
func TestLifecycle_WorktreeDoubleRemoveIdempotentNoOrphans(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c): every git child reaped

	report := &tReport{t: t}
	harness := &tHarness{t: t, ctx: context.Background()}
	libtesting.AssertLifecycle(context.Background(), harness, report, newWorktreeProbe(t))
}

// worktreeProbe is the testing.LifecycleProbe binding for a REAL linked worktree. Its "owned
// resource" is the on-disk linked worktree: AddWorktree creates it, RemoveWorktree prunes it
// (idempotently), and CountOwned reads the live non-main worktree count straight from
// `git worktree list`. After the double-Remove, CountOwned must read zero.
type worktreeProbe struct {
	repository *gitrepository.Repository // the main checkout that owns the worktree
	path       string                    // the linked worktree's on-disk path
}

// newWorktreeProbe returns a testing.LifecycleFactory that, per run, seeds a REAL on-disk repo
// (one base commit) over the system-git backend and yields a fresh worktree probe. It closes
// over the outer *testing.T only to register the TempDir reap; the probe itself drives the
// frozen lifecycle seam.
func newWorktreeProbe(t *testing.T) libtesting.LifecycleFactory {
	//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
	return func(ctx context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
		dir, repository := gitrepositorytest.NewRealRepo(t, gitrepositorytest.RepoSeed{
			DefaultBranch: "main",
			Commits: []gitrepositorytest.SeedCommit{
				{Files: map[string]string{"base.txt": "base\n"}, Message: "base"},
			},
		})
		if repository == nil {
			return nil, nil, errProbeSetup
		}

		path := filepath.Join(dir, "wt-lifecycle")
		branch, err := gitrepository.ParseBranchName("feature/lifecycle")
		if err != nil {
			return nil, nil, err
		}
		if _, err := repository.AddWorktree(ctx, gitrepository.WorktreeOptions{Path: path, Branch: branch, Start: "main"}); err != nil {
			return nil, nil, err
		}

		probe := &worktreeProbe{repository: repository, path: path}
		// Teardown is a final best-effort prune so a failed assertion never leaks the worktree dir.
		teardown := func() {
			_ = probe.repository.RemoveWorktree(context.Background(), probe.path, gitrepository.RemoveOptions{Force: true, DeleteBranch: true}) //nolint:errcheck // best-effort final reap; the assertions own the real Remove checks.
		}
		return probe, teardown, nil
	}
}

// errProbeSetup signals a harness construction failure to AssertLifecycle.
var errProbeSetup = lifecycleError("lifecycle: NewRealRepo returned a nil repository")

type lifecycleError string

func (e lifecycleError) Error() string { return string(e) }

// Use exercises the live worktree once: write a file, stage it, and commit it as an agent — the
// full author plane over the isolated worktree, proving it is a genuine, writable checkout
// before Close.
func (p *worktreeProbe) Use(ctx context.Context) error {
	file := filepath.Join(p.path, "work.go")
	if err := os.WriteFile(file, []byte("package work\n"), 0o600); err != nil {
		return err
	}
	if _, err := p.repository.Stage(ctx, p.path, gitrepository.StageOptions{Paths: []string{"work.go"}}); err != nil {
		return err
	}
	_, err := p.repository.Commit(ctx, p.path, "feat: lifecycle work",
		gitrepository.Identity{
			Name: "Eden Agent", Email: "agent@eden.dev", Kind: gitrepository.ActorAgent,
			RunID: "run-lifecycle", SessionID: "sess-lifecycle", Phase: "implement",
		}, gitrepository.CommitOptions{})
	return err //nolint:wrapcheck // the probe surfaces the library error verbatim to AssertLifecycle's Report.
}

// Close prunes the linked worktree. RemoveWorktree is idempotent by contract, so the driver's
// SECOND call must also return nil (the double-close invariant).
func (p *worktreeProbe) Close(ctx context.Context) error {
	return p.repository.RemoveWorktree(ctx, p.path, gitrepository.RemoveOptions{DeleteBranch: true}) //nolint:wrapcheck // surfaced verbatim to the lifecycle Report.
}

// CountOwned reports how many LINKED (non-main) worktrees are still live on disk, read straight
// from the real `git worktree list` via the Worktrees read surface. After Close it must be zero:
// the worktree was pruned exactly once with no orphan .git/worktrees metadata.
func (p *worktreeProbe) CountOwned(ctx context.Context) (int, error) {
	worktrees, err := p.repository.Worktrees(ctx)
	if err != nil {
		return 0, err //nolint:wrapcheck // surfaced verbatim to the lifecycle Report.
	}
	owned := 0
	for _, wt := range worktrees {
		if !wt.IsMain {
			owned++
		}
	}
	return owned, nil
}

// ── *testing.T adapters for the testing.Harness / testing.Report ports ────────────────.

// tReport adapts *testing.T to the testing.Report sink AssertLifecycle reports into.
type tReport struct{ t *testing.T }

func (r *tReport) Errorf(format string, args ...any) { r.t.Errorf(format, args...) }
func (r *tReport) Fatalf(format string, args ...any) { r.t.Fatalf(format, args...) }
func (r *tReport) Skipf(format string, args ...any)  { r.t.Skipf(format, args...) }

// tHarness adapts *testing.T's lifecycle needs to the testing.Harness port. Only Cleanup and
// Context are exercised by AssertLifecycle; the deterministic-source accessors are part of the
// frozen 5-method port and are never called on this path. Cleanup delegates to *testing.T.Cleanup
// so teardown runs (LIFO) at test end even if an assertion fails mid-run.
type tHarness struct {
	t   *testing.T
	ctx context.Context
}

//nolint:ireturn // contract §2: Harness.Clock returns the Clock port; unused on the lifecycle path.
func (*tHarness) Clock() libtesting.Clock { return nil }

//nolint:ireturn // contract §2: Harness.RandomSource returns the RandomSource port; unused here.
func (*tHarness) RandomSource() libtesting.RandomSource { return nil }

func (*tHarness) Has(string) bool { return false }

func (h *tHarness) Context() context.Context { return h.ctx }

func (h *tHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }
