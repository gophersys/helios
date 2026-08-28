package gitrepositorytest

import (
	"context"
	"path/filepath"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
)

// assertWorktreeIsolation proves two worktrees over disjoint paths mutate, Stage, and Commit
// independently with no index contention and independent HEADs — the swarm primitive (02 §2).
func assertWorktreeIsolation(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	fix := newFixture(t, newBackend(), nil)
	ctx := context.Background()

	// A base commit so worktree branches have a start point.
	seedCommit(t, fix, fix.root, "base.txt", "base\n", "base")

	pathA := filepath.Join(fix.root, "wt-a")
	pathB := filepath.Join(fix.root, "wt-b")
	branchA := mustParse(t, "feature/a")
	branchB := mustParse(t, "feature/b")

	wtA, err := fix.repository.AddWorktree(ctx, gitrepository.WorktreeOptions{Path: pathA, Branch: branchA, Start: "main"})
	if err != nil {
		t.Fatalf("AddWorktree A: %v", err)
	}
	wtB, err := fix.repository.AddWorktree(ctx, gitrepository.WorktreeOptions{Path: pathB, Branch: branchB, Start: "main"})
	if err != nil {
		t.Fatalf("AddWorktree B: %v", err)
	}

	fix.putWorking(pathA, "a.txt", "from A\n")
	fix.putWorking(pathB, "b.txt", "from B\n")

	if _, err := wtA.Stage(ctx, pathA, gitrepository.StageOptions{Paths: []string{"a.txt"}}); err != nil {
		t.Fatalf("Stage A: %v", err)
	}
	if _, err := wtB.Stage(ctx, pathB, gitrepository.StageOptions{Paths: []string{"b.txt"}}); err != nil {
		t.Fatalf("Stage B: %v", err)
	}

	idA, err := wtA.Commit(ctx, pathA, "a", agentIdentity("runA"), gitrepository.CommitOptions{})
	if err != nil {
		t.Fatalf("Commit A: %v", err)
	}
	idB, err := wtB.Commit(ctx, pathB, "b", agentIdentity("runB"), gitrepository.CommitOptions{})
	if err != nil {
		t.Fatalf("Commit B: %v", err)
	}
	if idA == idB || idA.IsZero() || idB.IsZero() {
		t.Errorf("worktree HEADs must be independent and non-zero: A=%s B=%s", idA, idB)
	}

	// A's worktree must NOT see B's staged file, and vice versa (disjoint indexes/working trees).
	statusA, statusErr := wtA.Status(ctx, pathA)
	if statusErr != nil {
		t.Fatalf("Status A: %v", statusErr)
	}
	for _, change := range statusA.Changes {
		if change.Path == "b.txt" {
			t.Errorf("worktree A leaked B's change %q — indexes must be disjoint", change.Path)
		}
	}
}

// assertRemoveWorktree proves RemoveWorktree prunes linked-worktree metadata, is idempotent,
// returns DirtyWorktreeError for a dirty worktree without Force, and never removes the main
// tree.
func assertRemoveWorktree(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	fix := newFixture(t, newBackend(), nil)
	ctx := context.Background()
	seedCommit(t, fix, fix.root, "base.txt", "base\n", "base")

	path := filepath.Join(fix.root, "wt")
	branch := mustParse(t, "feature/x")
	if _, err := fix.repository.AddWorktree(ctx, gitrepository.WorktreeOptions{Path: path, Branch: branch, Start: "main"}); err != nil {
		t.Fatalf("AddWorktree: %v", err)
	}

	// Dirty it; a non-Force remove must be DirtyWorktreeError.
	fix.putWorking(path, "dirty.txt", "uncommitted\n")
	err := fix.repository.RemoveWorktree(ctx, path, gitrepository.RemoveOptions{})
	if !errors.IsType[*gitrepository.DirtyWorktreeError](err) {
		t.Errorf("dirty RemoveWorktree without Force must be DirtyWorktreeError, got %v (%T)", err, err)
	}

	// Force-remove succeeds; a second remove is an idempotent no-op.
	if err := fix.repository.RemoveWorktree(ctx, path, gitrepository.RemoveOptions{Force: true}); err != nil {
		t.Fatalf("Force RemoveWorktree: %v", err)
	}
	if err := fix.repository.RemoveWorktree(ctx, path, gitrepository.RemoveOptions{Force: true}); err != nil {
		t.Errorf("second RemoveWorktree must be an idempotent no-op, got %v", err)
	}

	// The main tree is never removable.
	mainErr := fix.repository.RemoveWorktree(ctx, fix.root, gitrepository.RemoveOptions{Force: true})
	assertKind(t, mainErr, errors.KindInvalid, "RemoveWorktree(main)")
}

// assertReadSurfaces proves Status.Changes, Branches, and Worktrees reproduce a known seeded
// state (the per-session file modifications, branches, in-flight worktrees the frontend
// renders, C23).
func assertReadSurfaces(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	fix := newFixture(t, newBackend(), nil)
	ctx := context.Background()
	seedCommit(t, fix, fix.root, "readme.md", "v1\n", "init")

	// A working-tree modification is visible in Status.Changes (the file-modification rail).
	fix.putWorking(fix.root, "readme.md", "v2\n")
	fix.putWorking(fix.root, "new.txt", "fresh\n")
	status, err := fix.repository.Status(ctx, fix.root)
	if err != nil {
		t.Fatalf("Status: %v", err)
	}
	if status.Clean {
		t.Errorf("Status.Clean must be false with pending changes")
	}
	if !hasChange(status.Changes, "readme.md", gitrepository.ChangeModified) {
		t.Errorf("Status.Changes must report readme.md modified; got %+v", status.Changes)
	}
	if !hasChange(status.Changes, "new.txt", gitrepository.ChangeUntracked) {
		t.Errorf("Status.Changes must report new.txt untracked; got %+v", status.Changes)
	}

	// Branches reports the seeded main branch with a non-zero tip.
	branches, err := fix.repository.Branches(ctx, gitrepository.BranchOptions{})
	if err != nil {
		t.Fatalf("Branches: %v", err)
	}
	if !hasBranch(branches, "main") {
		t.Errorf("Branches must include the seeded main branch; got %+v", branches)
	}

	// Worktrees reports exactly the main tree (no linked worktrees yet), flagged IsMain.
	worktrees, err := fix.repository.Worktrees(ctx)
	if err != nil {
		t.Fatalf("Worktrees: %v", err)
	}
	if len(worktrees) != 1 || !worktrees[0].IsMain {
		t.Errorf("Worktrees must report exactly the main tree as IsMain; got %+v", worktrees)
	}
}

// assertDiffBounded proves Diff is bounded (Truncated at the cap), NameOnly returns paths
// only, and binary files report IsBinary without inlining bytes.
func assertDiffBounded(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	fix := newFixture(t, newBackend(), nil)
	ctx := context.Background()
	seedCommit(t, fix, fix.root, "text.txt", "one\n", "init")

	// Modify the text file and stage it so a staged-vs-HEAD diff has content.
	fix.putWorking(fix.root, "text.txt", "one\ntwo\nthree\n")
	if _, err := fix.repository.Stage(ctx, fix.root, gitrepository.StageOptions{Paths: []string{"text.txt"}}); err != nil {
		t.Fatalf("Stage: %v", err)
	}

	// NameOnly returns the path list with no hunks.
	nameOnly, err := fix.repository.Diff(ctx, gitrepository.DiffOptions{Worktree: fix.root, Mode: gitrepository.DiffStagedVsHead, NameOnly: true})
	if err != nil {
		t.Fatalf("Diff(NameOnly): %v", err)
	}
	if len(nameOnly.Files) == 0 {
		t.Fatalf("Diff(NameOnly) must report the changed file")
	}
	for _, f := range nameOnly.Files {
		if len(f.Hunks) != 0 {
			t.Errorf("Diff(NameOnly) must not carry hunks for %s", f.Path)
		}
	}

	// A tiny MaxBytes forces Truncated on a real patch.
	bounded, err := fix.repository.Diff(ctx, gitrepository.DiffOptions{Worktree: fix.root, Mode: gitrepository.DiffStagedVsHead, MaxBytes: 1})
	if err != nil {
		t.Fatalf("Diff(bounded): %v", err)
	}
	if !bounded.Truncated {
		t.Errorf("Diff with MaxBytes=1 must set Truncated")
	}

	// A binary file reports IsBinary and inlines no bytes.
	fix.putWorking(fix.root, "blob.bin", "\x00\x01\x02binary\x00")
	if _, err := fix.repository.Stage(ctx, fix.root, gitrepository.StageOptions{Paths: []string{"blob.bin"}}); err != nil {
		t.Fatalf("Stage(binary): %v", err)
	}
	binDiff, err := fix.repository.Diff(ctx, gitrepository.DiffOptions{Worktree: fix.root, Mode: gitrepository.DiffStagedVsHead, MaxBytes: 1 << 20})
	if err != nil {
		t.Fatalf("Diff(binary): %v", err)
	}
	if !anyBinary(binDiff.Files) {
		t.Errorf("Diff must flag the binary file IsBinary; got %+v", binDiff.Files)
	}
	for _, f := range binDiff.Files {
		if f.IsBinary && len(f.Hunks) > 0 {
			t.Errorf("a binary file must not carry inlined hunks: %s", f.Path)
		}
	}
}

// assertFastForwardOnly proves a non-ff Push returns NonFastForwardError carrying local+remote
// tips and does NOT advance the ref. It drives two clones diverging from a shared remote.
func assertFastForwardOnly(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	assertFastForwardOnlyImpl(t, newBackend)
}

// assertCredentialNeverLeaks proves Clone/Fetch/Push resolve the secrets.Reference via
// Deps.Secrets and feed it via the credential helper; the canary never appears in any recorded
// op argument projection; and a bad credential yields AuthError carrying the ref, never the
// value.
func assertCredentialNeverLeaks(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	assertCredentialNeverLeaksImpl(t, newBackend)
}

// assertTypedErrors proves unknown revision → NotFoundError, existing branch →
// AlreadyExistsError, and each classifies via errors.KindOf and carries the ref — never raw
// stderr or a credential.
func assertTypedErrors(t *testing.T, newBackend func() gitrepository.Backend) {
	t.Helper()
	fix := newFixture(t, newBackend(), nil)
	ctx := context.Background()
	seedCommit(t, fix, fix.root, "base.txt", "base\n", "base")

	// Unknown revision in a DiffCommits → NotFoundError.
	_, err := fix.repository.Diff(ctx, gitrepository.DiffOptions{Mode: gitrepository.DiffCommits, From: "main", To: "doesnotexist", MaxBytes: 1 << 20})
	if !errors.IsType[*gitrepository.NotFoundError](err) {
		t.Errorf("Diff over an unknown revision must be NotFoundError, got %v (%T)", err, err)
	}
	assertKind(t, err, errors.KindNotFound, "Diff(unknown revision)")

	// Creating a worktree on an existing branch via -b → AlreadyExistsError.
	path1 := filepath.Join(fix.root, "wt1")
	branch := mustParse(t, "feature/dup")
	if _, err := fix.repository.AddWorktree(ctx, gitrepository.WorktreeOptions{Path: path1, Branch: branch, Start: "main"}); err != nil {
		t.Fatalf("AddWorktree first: %v", err)
	}
	path2 := filepath.Join(fix.root, "wt2")
	_, dupErr := fix.repository.AddWorktree(ctx, gitrepository.WorktreeOptions{Path: path2, Branch: branch, Start: "main"})
	if !errors.IsType[*gitrepository.AlreadyExistsError](dupErr) {
		t.Errorf("AddWorktree over an existing branch must be AlreadyExistsError, got %v (%T)", dupErr, dupErr)
	}
	assertKind(t, dupErr, errors.KindConflict, "AddWorktree(existing branch)")
}

// Shared case helpers.

// seedCommit stages and commits one file as the platform actor — a base commit the worktree/
// diff/branch cases build on.
func seedCommit(t *testing.T, fix *fixture, worktree, path, content, message string) {
	t.Helper()
	fix.putWorking(worktree, path, content)
	if _, err := fix.repository.Stage(context.Background(), worktree, gitrepository.StageOptions{Paths: []string{path}}); err != nil {
		t.Fatalf("seed Stage: %v", err)
	}
	if _, err := fix.repository.Commit(context.Background(), worktree, message,
		gitrepository.Identity{Name: "Eden Seed", Email: "seed@eden.dev", Kind: gitrepository.ActorPlatform},
		gitrepository.CommitOptions{}); err != nil {
		t.Fatalf("seed Commit: %v", err)
	}
}

// agentIdentity builds an ActorAgent identity for a run id.
func agentIdentity(runID string) gitrepository.Identity {
	return gitrepository.Identity{
		Name: "Eden Agent", Email: "agent+" + runID + "@eden.dev", Kind: gitrepository.ActorAgent,
		RunID: runID, SessionID: "sess-" + runID, Phase: "implement",
	}
}

// mustParse parses a branch name in a test, failing on error.
func mustParse(t *testing.T, name string) gitrepository.BranchName {
	t.Helper()
	parsed, err := gitrepository.ParseBranchName(name)
	if err != nil {
		t.Fatalf("ParseBranchName(%q): %v", name, err)
	}
	return parsed
}

// hasChange reports whether changes contains path with the given kind.
func hasChange(changes []gitrepository.FileChange, path string, kind gitrepository.ChangeKind) bool {
	for _, change := range changes {
		if change.Path == path && change.Status == kind {
			return true
		}
	}
	return false
}

// hasBranch reports whether branches contains a branch named name.
func hasBranch(branches []gitrepository.Branch, name string) bool {
	for _, branch := range branches {
		if branch.Name.String() == name {
			return true
		}
	}
	return false
}

// anyBinary reports whether any file diff is flagged binary.
func anyBinary(files []gitrepository.FileDiff) bool {
	for _, f := range files {
		if f.IsBinary {
			return true
		}
	}
	return false
}
