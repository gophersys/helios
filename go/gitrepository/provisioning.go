package gitrepository

import (
	"context"
	"path/filepath"
	"strings"
)

// Clone materializes the remote into dir. The library validates the destination and clone
// knobs, resolves the opaque Credential Reference to a short-lived Secret server-side (confined to
// the credential-helper seam), hands the Backend a normalized ProvisionOp + the Secret, and
// returns a *Repository rooted at the clone destination.
//
//nolint:gocritic // contract §2: Clone's CloneOptions is the frozen Provisioner signature (a plain copyable options struct).
func (r *Repository) Clone(ctx context.Context, remote, dir string, options CloneOptions) (*Repository, error) {
	if err := contextErr(ctx); err != nil {
		return nil, err
	}
	remoteName, err := r.validateClone(remote, dir, &options)
	if err != nil {
		return nil, err
	}

	credential, err := r.resolveCredential(ctx, options.Credential, remoteName)
	if err != nil {
		return nil, err
	}
	defer zeroize(credential)

	op := ProvisionOp{
		Kind:       ProvisionClone,
		Root:       r.root,
		RemoteURL:  remote,
		RemoteName: remoteName,
		Dir:        filepath.Clean(dir),
		Branch:     options.Branch.String(),
		Depth:      options.Depth,
		Filter:     options.Filter,
		Sparse:     options.Sparse,
	}
	if _, err := r.backend.Provision(ctx, op, credential); err != nil {
		return nil, wrapBackend(err)
	}

	// The cloned checkout is a new worked repository rooted at dir; it inherits this
	// Repository's remotes (the logical name → URL map) and authoring defaults.
	cloned := &Repository{
		root:          filepath.Clean(dir),
		remotes:       cloneRemotes(r.remotes),
		defaultAuthor: r.defaultAuthor,
		backend:       r.backend,
		secrets:       r.secrets,
		clock:         r.clock,
		locks:         newLockTable(),
	}
	// Record the clone's origin remote under its logical name so a later Fetch/Push resolves.
	cloned.remotes[remoteName] = remote
	return cloned, nil
}

// validateClone validates the clone arguments and capability requirements, returning the
// resolved local remote name (default "origin"). It is the argv/path/capability guard split
// out of Clone so the verb stays under the complexity ceiling.
func (r *Repository) validateClone(remote, dir string, options *CloneOptions) (string, error) {
	switch {
	case strings.TrimSpace(remote) == "":
		return "", wrapKind(&InvalidRefError{Ref: "clone remote URL must not be empty"})
	case strings.ContainsAny(remote, " \t\n") || strings.HasPrefix(remote, "-"):
		return "", wrapKind(&InvalidRefError{Ref: "clone remote URL is malformed: " + remote})
	case strings.TrimSpace(dir) == "" || !filepath.IsAbs(dir):
		return "", wrapKind(&InvalidRefError{Ref: "clone destination must be an absolute path: " + dir})
	case options.Depth < 0:
		return "", wrapKind(&InvalidRefError{Ref: "clone depth must not be negative"})
	case options.Depth > 0 && !r.backend.Capabilities().ShallowClone:
		return "", wrapKind(&InvalidRefError{Ref: "backend does not support shallow clone (--depth)"})
	case options.Filter != "" && !r.backend.Capabilities().PartialClone:
		return "", wrapKind(&InvalidRefError{Ref: "backend does not support partial clone (--filter)"})
	}
	remoteName := options.RemoteName
	if remoteName == "" {
		remoteName = "origin"
	}
	if !validRemoteName(remoteName) {
		return "", wrapKind(&InvalidRefError{Ref: "invalid clone remote name: " + remoteName})
	}
	return remoteName, nil
}

// AddWorktree materializes a NEW linked worktree at options.Path. It validates the path
// lives under Root, serializes against concurrent mutation of THAT path, and returns a
// *Repository rooted at the new worktree.
func (r *Repository) AddWorktree(ctx context.Context, options WorktreeOptions) (*Repository, error) {
	if err := contextErr(ctx); err != nil {
		return nil, err
	}
	if !r.backend.Capabilities().LinkedWorktree {
		return nil, wrapKind(&InvalidRefError{Ref: "backend does not support linked worktrees"})
	}
	if options.Branch.IsZero() {
		return nil, wrapKind(&InvalidRefError{Ref: "worktree branch is required"})
	}
	path, err := r.validateWorktree(options.Path)
	if err != nil {
		return nil, err
	}
	if path == r.root {
		return nil, wrapKind(&InvalidRefError{Ref: "worktree path must differ from Root"})
	}
	if options.Start != "" && !validRevision(options.Start) {
		return nil, wrapKind(&InvalidRefError{Ref: "invalid worktree start revision: " + options.Start})
	}

	lock := r.worktreeLock(path)
	lock.Lock()
	defer lock.Unlock()

	op := ProvisionOp{
		Kind:         ProvisionAddWorktree,
		Root:         r.root,
		Dir:          path,
		Branch:       options.Branch.String(),
		Start:        options.Start,
		CreateBranch: options.Start != "",
	}
	result, err := r.backend.Provision(ctx, op, nil)
	if err != nil {
		return nil, wrapBackend(err)
	}

	worktree := &Repository{
		root:          path,
		remotes:       cloneRemotes(r.remotes),
		defaultAuthor: r.defaultAuthor,
		backend:       r.backend,
		secrets:       r.secrets,
		clock:         r.clock,
		locks:         newLockTable(),
	}
	_ = result
	return worktree, nil
}

// RemoveWorktree prunes the linked worktree at path. It validates the path is under Root and
// is not the main tree, serializes against concurrent mutation of that path, and is
// idempotent (an already-removed worktree is a no-op, not an error).
func (r *Repository) RemoveWorktree(ctx context.Context, path string, options RemoveOptions) error {
	if err := contextErr(ctx); err != nil {
		return err
	}
	clean, err := r.validateWorktree(path)
	if err != nil {
		return err
	}
	if clean == r.root {
		return wrapKind(&InvalidRefError{Ref: "RemoveWorktree must not target the main working tree"})
	}

	lock := r.worktreeLock(clean)
	lock.Lock()
	defer lock.Unlock()

	op := ProvisionOp{
		Kind:         ProvisionRemoveWorktree,
		Root:         r.root,
		Dir:          clean,
		DeleteBranch: options.DeleteBranch,
		Force:        options.Force,
	}
	if _, err := r.backend.Provision(ctx, op, nil); err != nil {
		return wrapBackend(err)
	}
	return nil
}

// cloneRemotes copies the logical remote map so a derived Repository never aliases its
// parent's map (a later mutation on one must not bleed into the other).
func cloneRemotes(in map[string]string) map[string]string {
	out := make(map[string]string, len(in))
	for name, url := range in {
		out[name] = url
	}
	return out
}
