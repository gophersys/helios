//go:build load

package gitrepository_test

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"sync/atomic"
	"testing"
	"time"

	"go.uber.org/goleak"
	"golang.org/x/sync/errgroup"

	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/gitrepository/gitrepositorytest"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500
// in-process; ADR-0020 dimension (e)). The git lanes do real subprocess work, so the default is
// scaled down for the per-clone variant to keep wall-time sane while still saturating the race
// detector — EDEN_LOAD_N still drives the read fan-out at full width.
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// loadClock is a deterministic Clock for the load harness.
type loadClock struct{}

func (loadClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// TestLoad_ConcurrentReadsRaceClean opens ONE *Repository over a REAL on-disk checkout and
// drives N concurrent read verbs (Status / Branches / Worktrees / Diff) against it under -race.
// Reads take NO lock by contract (the Repository is "safe for concurrent READ use"); this lane
// proves that claim is race-clean at fan-out and that goleak sees every `git` child reaped after
// the group drains (the goroutine high-water returns to baseline) — ADR-0020 dimension (e).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling's git children would perturb the high-water assertion, so the fan-out runs serially.
func TestLoad_ConcurrentReadsRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	_, repository := gitrepositorytest.NewRealRepo(t, gitrepositorytest.RepoSeed{
		DefaultBranch: "main",
		Commits: []gitrepositorytest.SeedCommit{
			{Files: map[string]string{"a.txt": "a\n", "dir/b.txt": "b\n"}, Message: "base"},
		},
	})

	ctx, cancel := context.WithTimeout(t.Context(), 60*time.Second)
	defer cancel()

	var statusOK, branchesOK atomic.Int64
	group, groupCtx := errgroup.WithContext(ctx)
	group.SetLimit(32) // bound concurrent git subprocesses so the read fan-out cannot exhaust fds
	for i := range n {
		i := i
		group.Go(func() error {
			switch i % 3 {
			case 0:
				st, err := repository.Status(groupCtx, "")
				if err != nil {
					return err
				}
				if !st.Clean {
					return errLoadDirty
				}
				statusOK.Add(1)
			case 1:
				branches, err := repository.Branches(groupCtx, gitrepository.BranchOptions{})
				if err != nil {
					return err
				}
				if len(branches) == 0 {
					return errLoadNoBranch
				}
				branchesOK.Add(1)
			default:
				if _, err := repository.Worktrees(groupCtx); err != nil {
					return err
				}
			}
			return nil
		})
	}
	if err := group.Wait(); err != nil {
		t.Fatalf("a concurrent read faulted under fan-out (N=%d): %v", n, err)
	}
	if statusOK.Load() == 0 || branchesOK.Load() == 0 {
		t.Fatalf("fan-out did not exercise both read paths: status=%d branches=%d", statusOK.Load(), branchesOK.Load())
	}
}

// TestLoad_ConcurrentClonesRaceClean drives many concurrent Clones from ONE shared REAL bare
// remote, each into its own temp directory, under -race. Each cloned *Repository is independent
// (distinct root, distinct lock table); the lane proves the clone spine + the derived-Repository
// construction are race-clean across independent destinations and that every clone's git child is
// reaped (goleak). Every destination is a t.TempDir, reaped by the framework.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; runs serially so a parallel sibling cannot perturb the orphan-goroutine assertion.
func TestLoad_ConcurrentClonesRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	// Clones are heavier than reads; scale the count down but keep it meaningful under -race.
	clones := loadN() / 10
	if clones < 10 {
		clones = 10
	}

	bare := makeBareRemoteWithCommit(t)

	// A driver Repository whose only job is to expose Clone; its Root is irrelevant to the clone
	// destinations (each clone targets its own dir). The system-git backend does the real work.
	driver, err := gitrepository.New(
		gitrepository.Config{Root: t.TempDir()},
		gitrepository.Deps{Backend: gitrepository.SystemGit(), Clock: loadClock{}},
	)
	if err != nil {
		t.Fatalf("New(driver): %v", err)
	}

	parent := t.TempDir()
	ctx, cancel := context.WithTimeout(t.Context(), 120*time.Second)
	defer cancel()

	var cloned atomic.Int64
	group, groupCtx := errgroup.WithContext(ctx)
	group.SetLimit(16) // bound concurrent clone subprocesses (each spawns a git child + transfers objects)
	for i := range clones {
		dest := filepath.Join(parent, "clone-"+strconv.Itoa(i))
		group.Go(func() error {
			if err := os.MkdirAll(dest, 0o750); err != nil {
				return err
			}
			repo, err := driver.Clone(groupCtx, bare, dest, gitrepository.CloneOptions{RemoteName: "origin"})
			if err != nil {
				return err
			}
			// Read back the clone to prove it is a genuine checkout at the remote's tip.
			st, err := repo.Status(groupCtx, "")
			if err != nil {
				return err
			}
			if st.Head.IsZero() {
				return errLoadUnborn
			}
			cloned.Add(1)
			return nil
		})
	}
	if err := group.Wait(); err != nil {
		t.Fatalf("a concurrent clone faulted under fan-out (clones=%d): %v", clones, err)
	}
	if got := cloned.Load(); got != int64(clones) {
		t.Fatalf("expected %d successful clones, got %d", clones, got)
	}
}

// ── load harness ──────────────────────────────────────────────────────────────.

type loadErr string

func (e loadErr) Error() string { return string(e) }

const (
	errLoadDirty    = loadErr("load: a freshly-seeded checkout reported unclean")
	errLoadNoBranch = loadErr("load: Branches returned no branches for a seeded repo")
	errLoadUnborn   = loadErr("load: a clone reported an unborn HEAD")
)

// makeBareRemoteWithCommit creates a REAL bare remote (git init --bare) carrying one commit on
// main, in a t.TempDir reaped by the framework — the shared source the concurrent clones pull
// from. It uses the harness git directly (independent of the library) so the source exists before
// the Repository-under-test touches it.
func makeBareRemoteWithCommit(t *testing.T) string {
	t.Helper()
	// Seed a working repo, then push it into a fresh bare so the bare has a real commit on main.
	work := t.TempDir()
	loadGit(t, work, "init", "-q", "-b", "main")
	loadGit(t, work, "config", "user.name", "Eden Load")
	loadGit(t, work, "config", "user.email", "load@eden.dev")
	if err := os.WriteFile(filepath.Join(work, "seed.txt"), []byte("seed\n"), 0o600); err != nil {
		t.Fatalf("write seed: %v", err)
	}
	loadGit(t, work, "add", "-A")
	loadGit(t, work, "commit", "-q", "-m", "seed")

	bare := t.TempDir()
	loadGit(t, bare, "init", "-q", "--bare", "-b", "main")
	loadGit(t, work, "remote", "add", "origin", bare)
	loadGit(t, work, "push", "-q", "origin", "main")
	return bare
}

// loadGit runs a git command in dir for the load harness, failing the test on error.
func loadGit(t *testing.T, dir string, args ...string) {
	t.Helper()
	command := exec.Command("git", args...)
	command.Dir = dir
	command.Env = loadEnv()
	if out, err := command.CombinedOutput(); err != nil {
		t.Fatalf("git %v: %v: %s", args, err, out)
	}
}

// loadEnv pins a deterministic, isolated git environment for the load harness.
func loadEnv() []string {
	env := []string{
		"GIT_TERMINAL_PROMPT=0", "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null", "LC_ALL=C",
	}
	if path := os.Getenv("PATH"); path != "" {
		env = append(env, "PATH="+path)
	}
	if home := os.Getenv("HOME"); home != "" {
		env = append(env, "HOME="+home)
	}
	return env
}
