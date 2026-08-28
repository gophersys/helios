package gitrepository

import (
	"context"
)

// defaultDiffCap bounds a Diff when DiffOptions.MaxBytes is 0 — a diff is NEVER unbounded
// (a runaway generated file cannot blow the read surface; the frontend pages "view full").
const defaultDiffCap int64 = 1 << 20 // 1 MiB

// Status reports a worktree's working-tree state against HEAD. Read-only; concurrency-safe;
// no lock, no network.
func (r *Repository) Status(ctx context.Context, worktree string) (Status, error) {
	if err := contextErr(ctx); err != nil {
		return Status{}, err
	}
	path, err := r.validateWorktree(worktree)
	if err != nil {
		return Status{}, err
	}
	result, err := r.backend.Inspect(ctx, InspectOp{
		Kind:     InspectStatus,
		Root:     r.root,
		Worktree: path,
	})
	if err != nil {
		return Status{}, wrapBackend(err)
	}
	return result.Status, nil
}

// Diff returns the bounded diff for the requested DiffOptions. Read-only.
//
//nolint:gocritic // contract §2: Diff's DiffOptions is the frozen Inspector signature (a plain copyable options struct).
func (r *Repository) Diff(ctx context.Context, options DiffOptions) (Diff, error) {
	if err := contextErr(ctx); err != nil {
		return Diff{}, err
	}

	op := InspectOp{
		Kind:     InspectDiff,
		Root:     r.root,
		DiffMode: options.Mode,
		Paths:    options.Paths,
		NameOnly: options.NameOnly,
		MaxBytes: options.MaxBytes,
	}
	if op.MaxBytes <= 0 {
		op.MaxBytes = defaultDiffCap
	}

	switch options.Mode {
	case DiffWorkingVsHead, DiffStagedVsHead:
		path, err := r.validateWorktree(options.Worktree)
		if err != nil {
			return Diff{}, err
		}
		op.Worktree = path
	case DiffCommits:
		if !validRevision(options.From) {
			return Diff{}, wrapKind(&InvalidRefError{Ref: "invalid diff base revision: " + options.From})
		}
		if !validRevision(options.To) {
			return Diff{}, wrapKind(&InvalidRefError{Ref: "invalid diff target revision: " + options.To})
		}
		op.Worktree = r.root
		op.From = options.From
		op.To = options.To
	default:
		return Diff{}, wrapKind(&InvalidRefError{Ref: "unknown diff mode"})
	}

	for _, p := range options.Paths {
		if p == "" || p == "--" {
			return Diff{}, wrapKind(&InvalidRefError{Ref: "invalid diff pathspec"})
		}
	}

	result, err := r.backend.Inspect(ctx, op)
	if err != nil {
		return Diff{}, wrapBackend(err)
	}
	return result.Diff, nil
}

// Branches lists local (and optionally remote-tracking) branches. Read-only.
func (r *Repository) Branches(ctx context.Context, options BranchOptions) ([]Branch, error) {
	if err := contextErr(ctx); err != nil {
		return nil, err
	}
	result, err := r.backend.Inspect(ctx, InspectOp{
		Kind:          InspectBranches,
		Root:          r.root,
		IncludeRemote: options.IncludeRemote,
	})
	if err != nil {
		return nil, wrapBackend(err)
	}
	return result.Branches, nil
}

// Worktrees lists the live worktrees of the repository. Read-only.
func (r *Repository) Worktrees(ctx context.Context) ([]WorktreeInfo, error) {
	if err := contextErr(ctx); err != nil {
		return nil, err
	}
	result, err := r.backend.Inspect(ctx, InspectOp{
		Kind: InspectWorktrees,
		Root: r.root,
	})
	if err != nil {
		return nil, wrapBackend(err)
	}
	return result.Worktrees, nil
}
