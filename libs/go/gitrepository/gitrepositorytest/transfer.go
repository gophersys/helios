package gitrepositorytest

import (
	"context"

	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/secrets"
)

// Transfer runs fetch / push against the shared bare-remote registry. cred is the resolved
// short-lived Secret; the fake records the resolution (CredentialRefs) and consumes it via
// Secret.Use, but the value never reaches an argument projection. push is FAST-FORWARD-ONLY:
// a non-ff update returns NonFastForwardError carrying both tips and does NOT advance the
// remote ref.
//
//nolint:gocritic // contract §2/§3: the Backend interface takes the op descriptor by value (the frozen seam); the fake mirrors it.
func (b *Backend) Transfer(ctx context.Context, op gitrepository.TransferOp, cred *secrets.Secret) (gitrepository.TransferResult, error) {
	if err := contextDone(ctx); err != nil {
		return gitrepository.TransferResult{}, err
	}
	b.mu.Lock()
	defer b.mu.Unlock()

	consumeCredential(cred)
	b.recordArgs(op.RemoteURL, op.Remote, op.LocalRef, op.DestRef)

	switch op.Kind {
	case gitrepository.TransferFetch:
		result, err := b.fetch(&op)
		return result, gitrepository.WrapError(err) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	case gitrepository.TransferPush:
		result, err := b.push(&op)
		return result, gitrepository.WrapError(err) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	default:
		return gitrepository.TransferResult{}, gitrepository.WrapError(&gitrepository.NotFoundError{What: "unknown transfer kind"}) //nolint:wrapcheck // gitrepository.WrapError IS the Backend's wrap+classify boundary (the errors.Wrap analog the gate ignores); it returns an already-wrapped, Kind-classified error.
	}
}

// fetch reads the remote's current tips for the requested refs (or all) into the result. The
// in-memory model has no separate tracking-ref store; the fetched tips are the remote's heads.
func (b *Backend) fetch(op *gitrepository.TransferOp) (gitrepository.TransferResult, error) {
	remote := b.remotes[op.RemoteURL]
	tips := map[gitrepository.Ref]gitrepository.CommitID{}
	if remote == nil {
		return gitrepository.TransferResult{Tips: tips}, nil
	}
	for _, ref := range op.Refs {
		branch := ref.Branch.String()
		if tip, ok := remote.branches[branch]; ok && tip != "" {
			tips[ref] = gitrepository.CommitIDFromHex(tip)
		}
	}
	return gitrepository.TransferResult{Tips: tips}, nil
}

// push fast-forwards the remote's destination branch to the local tip. A non-fast-forward
// (the remote advanced under the local branch) returns NonFastForwardError carrying both tips
// and leaves the remote ref UNCHANGED — the gate-escalation signal (E3). An identical tip is a
// clean no-op (UpToDate).
func (b *Backend) push(op *gitrepository.TransferOp) (gitrepository.TransferResult, error) {
	if b.failNextPush != nil {
		err := b.failNextPush
		b.failNextPush = nil
		return gitrepository.TransferResult{}, err
	}

	b.Pushed = append(b.Pushed, gitrepository.PushOptions{
		Remote:   op.Remote,
		LocalRef: mustBranch(op.LocalRef),
		DestRef:  mustBranch(op.DestRef),
	})
	if op.HasCredential {
		// The reference is recorded by the library's resolve path; here we only confirm a
		// credential rode the op (the value never reaches us).
		b.CredentialRefs = append(b.CredentialRefs, secrets.Reference{})
	}

	local := b.model
	if local == nil {
		return gitrepository.TransferResult{}, &gitrepository.NotFoundError{What: "local repository"}
	}
	localTip := local.branches[op.LocalRef]

	remote := b.remotes[op.RemoteURL]
	if remote == nil {
		remote = newBareRemote()
		b.remotes[op.RemoteURL] = remote
	}
	// Ensure the remote has the commits the local tip reaches (a real push transfers objects).
	copyAncestry(local, remote, localTip)

	remoteTip := remote.branches[op.DestRef]
	ref := gitrepository.Ref{Remote: op.Remote, Branch: mustBranch(op.DestRef)}

	switch {
	case remoteTip == localTip:
		return gitrepository.TransferResult{
			Tips:     map[gitrepository.Ref]gitrepository.CommitID{ref: gitrepository.CommitIDFromHex(localTip)},
			UpToDate: true,
		}, nil
	case op.FastForwardOnly && !remote.isAncestor(remoteTip, localTip):
		// The remote tip is NOT an ancestor of the local tip → non-fast-forward. Leave the
		// remote unchanged and signal escalation with both tips.
		return gitrepository.TransferResult{}, &gitrepository.NonFastForwardError{
			Ref:    ref,
			Local:  gitrepository.CommitIDFromHex(localTip),
			Remote: gitrepository.CommitIDFromHex(remoteTip),
		}
	default:
		remote.branches[op.DestRef] = localTip
		return gitrepository.TransferResult{
			Tips: map[gitrepository.Ref]gitrepository.CommitID{ref: gitrepository.CommitIDFromHex(localTip)},
		}, nil
	}
}

// AdvanceRemote models a CONCURRENT writer moving the remote's branch one commit ahead of
// whatever the local repository last pushed — the divergence the fast-forward-only conformance
// case needs. It appends a fresh commit to the remote registered under remoteURL (creating the
// remote if absent) on the given branch, so the local repository's next push to that branch is
// non-fast-forward. It is a test seam: a real concurrent writer does the same to a real bare
// remote; the in-memory fake exposes it so the suite can drive the same property without a
// second process.
func (b *Backend) AdvanceRemote(remoteURL, branch, content string) {
	b.mu.Lock()
	defer b.mu.Unlock()
	remote := b.remotes[remoteURL]
	if remote == nil {
		remote = newBareRemote()
		b.remotes[remoteURL] = remote
	}
	parent := remote.branches[branch]
	id := remote.mintID()
	remote.commits[id] = &commit{
		id:      id,
		parent:  parent,
		tree:    map[string][]byte{"remote-advance.txt": []byte(content)},
		message: "concurrent advance",
		author:  "Other <other@eden.dev>",
	}
	remote.branches[branch] = id
}

// newBareRemote builds an empty remote model (no main worktree, no default branch — a bare
// repository's branch namespace starts empty).
func newBareRemote() *model {
	return &model{
		commits:   map[string]*commit{},
		branches:  map[string]string{},
		worktrees: map[string]*worktree{},
	}
}

// copyAncestry copies the commit chain reaching tip from src into dst (the object transfer a
// push performs), so the remote can answer ancestry queries for the ff-only test.
func copyAncestry(src, dst *model, tip string) {
	for cursor := tip; cursor != ""; {
		node := src.commits[cursor]
		if node == nil {
			return
		}
		if _, present := dst.commits[cursor]; present {
			return
		}
		dst.commits[cursor] = node
		cursor = node.parent
	}
}
