package gitrepository

import (
	"context"
	"strings"

	"github.com/gophersys/libs/go/secrets"
)

// fetch runs `git fetch` against the resolved remote URL, updating remote-tracking refs
// WITHOUT touching the working tree or local branches (the no-merge half of the old "pull").
// The credential rides the helper seam, never argv/URL. It returns the fetched tips.
func (g *systemGit) fetch(ctx context.Context, op *TransferOp, cred *secrets.Secret) (TransferResult, error) {
	helperArgs, cleanup, err := credentialHelper(cred)
	if err != nil {
		return TransferResult{}, err
	}
	defer cleanup()

	args := append([]string{}, helperArgs...)
	args = append(args, "fetch", "--no-write-fetch-head")
	if op.Prune {
		args = append(args, "--prune")
	}
	// Fetch by URL (the resolved remote), with explicit refspecs when Refs is set so only the
	// requested branches' tracking refs move. The URL never carries credentials.
	args = append(args, op.RemoteURL)
	for _, ref := range op.Refs {
		args = append(args, fetchRefspec(op.Remote, ref))
	}

	if _, runErr := g.run(ctx, op.Root, nil, nil, args...); runErr != nil {
		return TransferResult{}, runErr
	}

	tips := make(map[Ref]CommitID, len(op.Refs))
	for _, ref := range op.Refs {
		tips[ref] = g.trackingTip(ctx, op.Root, op.Remote, ref.Branch.String())
	}
	return TransferResult{Tips: tips}, nil
}

// fetchRefspec builds "refs/heads/<branch>:refs/remotes/<remote>/<branch>" so a fetch updates
// the tracking ref for the requested branch.
func fetchRefspec(remote string, ref Ref) string {
	branch := ref.Branch.String()
	return "refs/heads/" + branch + ":refs/remotes/" + remote + "/" + branch
}

// trackingTip reads the tip of a remote-tracking ref after a fetch (zero if absent).
func (g *systemGit) trackingTip(ctx context.Context, root, remote, branch string) CommitID {
	out, err := g.run(ctx, root, nil, nil, "rev-parse", "--verify", "--quiet", "refs/remotes/"+remote+"/"+branch)
	if err != nil {
		return CommitID{}
	}
	return commitIDFromHex(string(out))
}

// push publishes the local branch tip to the remote. It is FAST-FORWARD-ONLY by contract:
// git's default push refuses a non-fast-forward (there is no --force here, ever), and a
// non-ff rejection is classified into NonFastForwardError carrying BOTH tips. A clean no-op
// (already up to date) sets UpToDate.
func (g *systemGit) push(ctx context.Context, op *TransferOp, cred *secrets.Secret) (TransferResult, error) {
	helperArgs, cleanup, err := credentialHelper(cred)
	if err != nil {
		return TransferResult{}, err
	}
	defer cleanup()

	localTip := g.resolveRev(ctx, op.Root, "refs/heads/"+op.LocalRef)
	remoteBefore := g.lsRemoteTip(ctx, op, cred, op.DestRef)

	args := append([]string{}, helperArgs...)
	// Explicit refspec, no --force: a non-ff update is rejected by git and classified below.
	// The dest is fully-qualified so the remote side cannot be tricked into a different ref.
	args = append(args, "push", op.RemoteURL, "refs/heads/"+op.LocalRef+":refs/heads/"+op.DestRef)

	out, runErr := g.run(ctx, op.Root, nil, nil, args...)
	if runErr != nil {
		// Enrich a non-fast-forward rejection with both tips for the gate-escalation signal
		// (the contract's load-bearing NonFastForwardError).
		var nff NonFastForwardError
		if asNonFastForward(runErr, &nff) {
			nff.Ref = Ref{Remote: op.Remote, Branch: mustBranch(op.DestRef)}
			nff.Local = localTip
			nff.Remote = remoteBefore
			return TransferResult{}, wrapKind(&nff)
		}
		return TransferResult{}, runErr
	}

	upToDate := strings.Contains(string(out), "Everything up-to-date") ||
		(remoteBefore == localTip && !localTip.IsZero())

	ref := Ref{Remote: op.Remote, Branch: mustBranch(op.DestRef)}
	return TransferResult{
		Tips:     map[Ref]CommitID{ref: localTip},
		UpToDate: upToDate,
	}, nil
}

// resolveRev reads a revision's commit id in dir (zero if it does not resolve).
func (g *systemGit) resolveRev(ctx context.Context, dir, rev string) CommitID {
	out, err := g.run(ctx, dir, nil, nil, "rev-parse", "--verify", "--quiet", rev)
	if err != nil {
		return CommitID{}
	}
	return commitIDFromHex(string(out))
}

// lsRemoteTip reads the remote's current tip for the destination branch BEFORE the push, so a
// NonFastForwardError can carry the remote tip the local one diverged from. The credential
// rides the same helper seam. A missing remote ref (a brand-new branch) is the zero CommitID.
func (g *systemGit) lsRemoteTip(ctx context.Context, op *TransferOp, cred *secrets.Secret, branch string) CommitID {
	helperArgs, cleanup, err := credentialHelper(cred)
	if err != nil {
		return CommitID{}
	}
	defer cleanup()

	args := append([]string{}, helperArgs...)
	args = append(args, "ls-remote", op.RemoteURL, "refs/heads/"+branch)
	out, runErr := g.run(ctx, op.Root, nil, nil, args...)
	if runErr != nil {
		return CommitID{}
	}
	for _, line := range scanLines(out) {
		hex, _, ok := strings.Cut(line, "\t")
		if ok {
			return commitIDFromHex(hex)
		}
	}
	return CommitID{}
}

// asNonFastForward reports whether err's chain carries a NonFastForwardError, copying it into
// target. It is a thin wrapper so the push verb reads cleanly.
func asNonFastForward(err error, target *NonFastForwardError) bool {
	pointer, ok := asType[*NonFastForwardError](err)
	if ok && pointer != nil {
		*target = *pointer
	}
	return ok
}

// mustBranch parses a branch name the library itself produced (already validated upstream),
// returning the zero BranchName on the impossible malformed case rather than panicking.
func mustBranch(name string) BranchName {
	parsed, err := ParseBranchName(name)
	if err != nil {
		return BranchName{}
	}
	return parsed
}
