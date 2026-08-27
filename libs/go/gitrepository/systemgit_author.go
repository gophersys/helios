package gitrepository

import (
	"context"
	"strings"
)

// stage runs `git add` over the explicit path set (or `git add -A` for All), then returns
// the post-stage Status (a flat call site for the caller).
func (g *systemGit) stage(ctx context.Context, op *AuthorOp) (AuthorResult, error) {
	args := []string{"add"}
	if op.All && len(op.Paths) == 0 {
		args = append(args, "--all")
	} else {
		args = append(args, "--")
		args = append(args, op.Paths...)
	}
	if _, err := g.run(ctx, op.Worktree, nil, nil, args...); err != nil {
		return AuthorResult{}, err
	}

	statusResult, err := g.status(ctx, &InspectOp{Kind: InspectStatus, Root: op.Root, Worktree: op.Worktree})
	if err != nil {
		return AuthorResult{}, err
	}
	return AuthorResult{Status: statusResult.Status}, nil
}

// commit runs `git commit` with author AND committer pinned to the stamped Identity and the
// Eden-* trailers appended. The message is fed on STDIN (`-F -`) so a message with shell
// metacharacters or newlines can never reach an argv. The author date and committer date are
// pinned via env so a deterministic Clock produces reproducible timestamps. It NEVER reads a
// credential (commit identity is attribution, not authentication).
func (g *systemGit) commit(ctx context.Context, op *AuthorOp) (AuthorResult, error) {
	// Pre-check the empty-index case to return the typed NothingToCommitError rather than
	// relying on git's stderr phrasing (which varies). `git diff --cached --quiet` exits 1 when
	// the index has staged changes, 0 when it is empty vs HEAD.
	if !op.AllowEmpty {
		empty, err := g.indexEmpty(ctx, op.Worktree)
		if err != nil {
			return AuthorResult{}, err
		}
		if empty {
			return AuthorResult{}, wrapKind(&NothingToCommitError{})
		}
	}

	message := buildCommitMessage(op.Message, op.Trailers)

	args := []string{
		"-c", "user.name=" + op.AuthorName,
		"-c", "user.email=" + op.AuthorEmail,
		"commit",
		"--author=" + op.AuthorName + " <" + op.AuthorEmail + ">",
		"-F", "-",
	}
	if op.AllowEmpty {
		args = append(args, "--allow-empty")
	}

	env := []string{
		"GIT_AUTHOR_NAME=" + op.AuthorName,
		"GIT_AUTHOR_EMAIL=" + op.AuthorEmail,
		"GIT_AUTHOR_DATE=" + op.When,
		"GIT_COMMITTER_NAME=" + op.AuthorName,
		"GIT_COMMITTER_EMAIL=" + op.AuthorEmail,
		"GIT_COMMITTER_DATE=" + op.When,
	}

	if _, err := g.run(ctx, op.Worktree, env, []byte(message), args...); err != nil {
		return AuthorResult{}, err
	}
	return AuthorResult{Commit: g.resolveHead(ctx, op.Worktree)}, nil
}

// indexEmpty reports whether the index has nothing staged vs HEAD (the NothingToCommit
// precondition). `git diff --cached --quiet` exits 0 (no error) when empty, non-zero
// (classified, but here we map exit-1 to "not empty") when there are staged changes.
func (g *systemGit) indexEmpty(ctx context.Context, worktree string) (bool, error) {
	// Use --exit-code semantics directly: run returns an error for a non-zero exit, but exit 1
	// here is the EXPECTED "there are changes" signal, not a failure. We therefore inspect the
	// exit by running a porcelain status instead, which is unambiguous and never errors on a
	// dirty index.
	statusResult, err := g.status(ctx, &InspectOp{Kind: InspectStatus, Worktree: worktree})
	if err != nil {
		return false, err
	}
	for _, change := range statusResult.Status.Changes {
		if change.Staged {
			return false, nil
		}
	}
	return true, nil
}

// buildCommitMessage appends the Eden-* trailers to the message body, separated by a blank
// line per git-interpret-trailers conventions, so the trailers are queryable by
// `git log --format=%(trailers)`.
func buildCommitMessage(body string, trailers []AuthorTrailer) string {
	if len(trailers) == 0 {
		return body
	}
	var builder strings.Builder
	builder.WriteString(strings.TrimRight(body, "\n"))
	builder.WriteString("\n\n")
	for _, trailer := range trailers {
		builder.WriteString(trailer.Key)
		builder.WriteString(": ")
		builder.WriteString(trailer.Value)
		builder.WriteString("\n")
	}
	return builder.String()
}
