package gitrepository

import (
	"context"
	"os"
	"path/filepath"
	"strconv"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// clone shells `git clone` with the depth/branch/filter/sparse knobs and the credential
// helper seam. The credential value reaches git ONLY through the helper's Use frame, never
// argv or the URL (07 §2).
func (g *systemGit) clone(ctx context.Context, op *ProvisionOp, cred *secrets.Secret) (ProvisionResult, error) {
	args := []string{"clone", "--origin", op.RemoteName}
	if op.Depth > 0 {
		args = append(args, "--depth", strconv.Itoa(op.Depth), "--no-single-branch")
	}
	if op.Branch != "" {
		args = append(args, "--branch", op.Branch, "--single-branch")
	}
	if op.Filter != "" {
		args = append(args, "--filter="+op.Filter)
	}
	if len(op.Sparse) > 0 {
		args = append(args, "--sparse")
	}

	helperArgs, cleanup, err := credentialHelper(cred)
	if err != nil {
		return ProvisionResult{}, err
	}
	defer cleanup()
	args = append(args, helperArgs...)

	// `git clone <url> <dir>` — the URL and dir are the trailing positionals; the credential
	// is in the helper config above, never embedded in the URL.
	args = append(args, "--", op.RemoteURL, op.Dir)

	// Clone runs from the parent of the destination (the dest may not exist yet).
	parent := filepath.Dir(op.Dir)
	if _, runErr := g.run(ctx, parent, nil, nil, args...); runErr != nil {
		return ProvisionResult{}, runErr
	}

	if len(op.Sparse) > 0 {
		sparseArgs := append([]string{"sparse-checkout", "set"}, op.Sparse...)
		if _, serr := g.run(ctx, op.Dir, nil, nil, sparseArgs...); serr != nil {
			return ProvisionResult{}, serr
		}
	}

	return ProvisionResult{
		Head:   g.resolveHead(ctx, op.Dir),
		Branch: g.currentBranch(ctx, op.Dir),
	}, nil
}

// addWorktree shells `git worktree add`. When CreateBranch, it creates op.Branch from
// op.Start (`-b`); otherwise it checks out an existing branch.
func (g *systemGit) addWorktree(ctx context.Context, op *ProvisionOp) (ProvisionResult, error) {
	args := []string{"worktree", "add"}
	if op.CreateBranch {
		args = append(args, "-b", op.Branch, op.Dir, op.Start)
	} else {
		args = append(args, op.Dir, op.Branch)
	}
	if _, err := g.run(ctx, op.Root, nil, nil, args...); err != nil {
		return ProvisionResult{}, err
	}
	return ProvisionResult{
		Head:   g.resolveHead(ctx, op.Dir),
		Branch: g.currentBranch(ctx, op.Dir),
	}, nil
}

// removeWorktree shells `git worktree remove`, pruning the .git/worktrees metadata (NOT a
// bare rm), then optionally deletes the branch. It is IDEMPOTENT: an already-gone worktree
// (the directory does not exist and git has no record) is a no-op, not an error.
func (g *systemGit) removeWorktree(ctx context.Context, op *ProvisionOp) error {
	// Idempotency: if the path is already gone AND git does not list it, treat as a no-op.
	if _, statErr := os.Stat(op.Dir); statErr != nil && os.IsNotExist(statErr) {
		if !g.worktreeRegistered(ctx, op.Root, op.Dir) {
			// Prune any stale metadata for a directory removed out from under git, then return.
			_, _ = g.run(ctx, op.Root, nil, nil, "worktree", "prune") //nolint:errcheck // best-effort metadata prune on an already-removed worktree; the op is a no-op by contract.
			return nil
		}
	}

	args := []string{"worktree", "remove"}
	if op.Force {
		args = append(args, "--force")
	}
	args = append(args, op.Dir)
	if _, err := g.run(ctx, op.Root, nil, nil, args...); err != nil {
		return err
	}

	if op.DeleteBranch {
		branch := g.worktreeBranch(ctx, op.Root, op.Dir)
		if branch != "" {
			// -D (force-delete) the work-package branch; an unmerged branch is the norm here
			// (the gate, not this library, integrates it). A failure to delete a missing branch
			// is swallowed: the worktree is gone, which is the contract's success condition.
			_, _ = g.run(ctx, op.Root, nil, nil, "branch", "-D", branch) //nolint:errcheck // branch cleanup is best-effort; worktree removal is the contract's success condition.
		}
	}
	return nil
}

// worktreeRegistered reports whether git still lists a worktree at dir.
func (g *systemGit) worktreeRegistered(ctx context.Context, root, dir string) bool {
	out, err := g.run(ctx, root, nil, nil, "worktree", "list", "--porcelain")
	if err != nil {
		return false
	}
	target := filepath.Clean(dir)
	for _, line := range scanLines(out) {
		if path, ok := cutPrefix(line, "worktree "); ok {
			if filepath.Clean(path) == target {
				return true
			}
		}
	}
	return false
}

// worktreeBranch reads the branch a registered worktree has checked out (the branch to
// delete on a DeleteBranch removal). It must be read BEFORE the worktree is removed.
func (g *systemGit) worktreeBranch(ctx context.Context, root, dir string) string {
	out, err := g.run(ctx, root, nil, nil, "worktree", "list", "--porcelain")
	if err != nil {
		return ""
	}
	target := filepath.Clean(dir)
	var current string
	var match bool
	for _, line := range scanLines(out) {
		switch {
		case hasPrefix(line, "worktree "):
			path, _ := cutPrefix(line, "worktree ")
			match = filepath.Clean(path) == target
			current = ""
		case match && hasPrefix(line, "branch "):
			ref, _ := cutPrefix(line, "branch ")
			current = shortBranch(ref)
			return current
		}
	}
	return current
}

// credentialHelper installs the short-lived-token credential helper for a network op and
// returns the `-c credential.helper=…` args that point git at it, plus a cleanup that reaps
// the per-op temp dir. The resolved Secret is materialized into git's credential protocol ON
// STDOUT by a tiny helper script the library generates per-op; the value lives ONLY inside
// the helper script's token file (mode 0600, in a per-op temp dir) and the Secret.Use frame,
// never argv, the URL, or the on-disk remote config (07 §2). A nil cred (public/local op)
// returns no args and a no-op cleanup.
//
// The helper-script approach is the system-git seam's honest realization of the contract's
// credential-helper flow: the token is materialized via Secret.Use into a file readable only
// by the child git's uid, scoped to one op and wiped on cleanup. It never touches a process
// argument or any environment value.
func credentialHelper(cred *secrets.Secret) (args []string, cleanup func(), err error) {
	cleanup = func() {}
	if cred == nil {
		return nil, cleanup, nil
	}

	dir, mkErr := os.MkdirTemp("", "gitrepository-cred-")
	if mkErr != nil {
		return nil, cleanup, errors.Wrap(errors.KindInternal, "gitrepository: stage credential helper", mkErr)
	}
	cleanup = func() { _ = os.RemoveAll(dir) } //nolint:errcheck // best-effort reap of a per-op temp credential dir; nothing actionable on failure.

	// Materialize the token into a 0600 file inside the per-op dir, via the Secret.Use frame —
	// the ONLY legitimate read path. The helper script below cats it into git's credential
	// protocol on stdout.
	tokenPath := filepath.Join(dir, "token")
	if useErr := cred.Use(func(plaintext []byte) error {
		return os.WriteFile(tokenPath, plaintext, 0o600)
	}); useErr != nil {
		cleanup()
		return nil, func() {}, errors.Wrap(errors.KindUnauthenticated, "gitrepository: materialize credential", useErr)
	}

	helperPath := filepath.Join(dir, "helper.sh")
	script := "#!/bin/sh\n" +
		"if [ \"$1\" = get ]; then\n" +
		"  printf 'username=eden\\n'\n" +
		"  printf 'password=%s\\n' \"$(cat " + shellQuote(tokenPath) + ")\"\n" +
		"fi\n"
	// An executable credential helper MUST be mode 0700 (git invokes it); it lives in a per-op
	// temp dir reaped on cleanup, never world-readable.
	wErr := os.WriteFile(helperPath, []byte(script), 0o700) // #nosec G306 -- executable credential helper requires 0700; per-op temp dir, reaped on cleanup.
	if wErr != nil {
		cleanup()
		return nil, func() {}, errors.Wrap(errors.KindInternal, "gitrepository: write credential helper", wErr)
	}

	// Point git at the helper by absolute path, and clear any inherited helper first so ONLY
	// this op's helper can answer the credential challenge.
	return []string{"-c", "credential.helper=", "-c", "credential.helper=" + shellQuote(helperPath)}, cleanup, nil
}
