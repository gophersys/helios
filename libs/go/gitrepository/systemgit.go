package gitrepository

import (
	"bufio"
	"bytes"
	"context"
	"os"
	"os/exec"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// systemGit is the default Backend (§6, §7 Q1): it SHELLS the system git binary for the
// whole surface — worktrees, shallow/partial/sparse clone, and the credential-helper
// short-lived-token seam — so the behavior is bit-for-bit identical to the eventual
// self-hosted git server and to byo-authority hosts (ADR-0013). It is THIN beyond the raw
// invocation: argument shaping, the ff-only guard, Author stamping, and result mapping all
// live in the library; this backend runs the op and parses git's machine-readable output.
type systemGit struct {
	// binary is the git executable name/path; "git" by default (found on PATH).
	binary string
}

// compile-time assertion: *systemGit implements Backend.
var _ Backend = (*systemGit)(nil)

// SystemGit returns the default Backend that shells the system git binary. It probes
// nothing at construction (New stays pure); the first git process spawns on the first verb.
//
//nolint:ireturn // contract §2/§5: SystemGit returns the Backend port for Deps wiring; the surface is frozen.
func SystemGit() Backend {
	return &systemGit{binary: "git"}
}

// Capabilities declares the system git binary's full surface: shallow, linked worktrees, and
// partial clone are all mature in the binary (the whole point of shelling it, §6).
func (g *systemGit) Capabilities() Capabilities {
	return Capabilities{ShallowClone: true, LinkedWorktree: true, PartialClone: true}
}

// run executes git with args in dir, returning stdout. A non-zero exit is classified from
// stderr into a typed gitrepository error (wrapped with its Kind). env is appended to a
// minimal, isolated environment — NEVER Eden's full env — so a credential helper variable is
// confined to the child process (07 §2). stdin, when non-nil, is fed to the process (the
// commit-message path).
func (g *systemGit) run(ctx context.Context, dir string, env []string, stdin []byte, args ...string) ([]byte, error) {
	command := exec.CommandContext(ctx, g.binary, args...) // #nosec G204 -- inherent exec adapter: binary is the configured git; args are library-shaped and ref-validated (refname.go), never raw user input on argv, never a shell.
	command.Dir = dir
	command.Env = append(baseEnv(), env...)
	if stdin != nil {
		command.Stdin = bytes.NewReader(stdin)
	}
	var stdout, stderr bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = &stderr

	err := command.Run()
	if err == nil {
		return stdout.Bytes(), nil
	}
	if ctxErr := errors.FromContext(ctx); ctxErr != nil {
		return nil, ctxErr
	}
	return nil, classifyStderr(stderr.String(), args)
}

// baseEnv is the minimal, isolated environment every git child runs under. It pins
// non-interactive, deterministic behavior and — crucially — DISABLES every ambient
// credential path (the system credential helper, the terminal prompt, askpass) so the ONLY
// credential git can obtain is the one the library injects via its own helper (07 §2). PATH
// is forwarded so git can find itself and its sub-tools; HOME points at a throwaway so no
// user ~/.gitconfig leaks in.
func baseEnv() []string {
	env := []string{
		"GIT_TERMINAL_PROMPT=0",             // never block on an interactive credential prompt
		"GIT_CONFIG_NOSYSTEM=1",             // ignore /etc/gitconfig
		"GIT_ASKPASS=/bin/false",            // no GUI/askpass credential path
		"GIT_CONFIG_GLOBAL=/dev/null",       // ignore the user's ~/.gitconfig
		"GIT_ALLOW_PROTOCOL=file:https:ssh", // constrain transports
		"LC_ALL=C",                          // stable, parseable porcelain
	}
	if path := os.Getenv("PATH"); path != "" {
		env = append(env, "PATH="+path)
	}
	if home := os.Getenv("HOME"); home != "" {
		// HOME is forwarded only so git can locate per-user data dirs; GIT_CONFIG_GLOBAL above
		// already neutralizes ~/.gitconfig, so no user identity/credential leaks in.
		env = append(env, "HOME="+home)
	}
	return env
}

// stderrRule maps a set of stable git stderr phrasing fragments to the typed error they
// signify. The table is ORDERED: the first rule whose any-fragment matches wins, so more
// specific signals (non-fast-forward, auth) precede broader ones (not-found). Each fragment is
// lowercase; classifyStderr lowercases the stderr once before matching.
type stderrRule struct {
	fragments []string
	build     func(stderr string, args []string) error
}

// stderrRules is the ordered classification table — the single place git's stderr is mapped to
// a typed error (the library owns classification; the seam owns only the raw op, §6).
var stderrRules = []stderrRule{
	{
		[]string{"non-fast-forward", "fetch first", "tip of your current branch is behind"},
		func(s string, _ []string) error { return wrapKindMsg(&NonFastForwardError{}, s) },
	},
	{
		[]string{"authentication failed", "could not read username", "invalid credentials", "terminal prompts disabled"},
		func(s string, a []string) error { return wrapKindMsg(&AuthError{Remote: remoteArg(a)}, s) },
	},
	{
		[]string{"protected branch", "denied", "permission denied", "pre-receive hook declined", "not allowed to push"},
		func(s string, a []string) error { return wrapKindMsg(&DeniedError{Ref: Ref{Remote: remoteArg(a)}}, s) },
	},
	{
		[]string{"could not resolve host", "connection refused", "connection timed out", "unable to access", "operation timed out"},
		func(s string, a []string) error { return wrapKindMsg(&UnavailableError{Remote: remoteArg(a)}, s) },
	},
	{
		[]string{"already exists", "is already checked out", "already used by worktree"},
		func(s string, _ []string) error { return wrapKindMsg(&AlreadyExistsError{What: s}, s) },
	},
	{
		[]string{"nothing to commit", "no changes added to commit", "nothing added to commit"},
		func(s string, _ []string) error { return wrapKindMsg(&NothingToCommitError{}, s) },
	},
	{
		[]string{"contains modified or untracked files", "use --force to delete it", "is dirty"},
		func(s string, _ []string) error { return wrapKindMsg(&DirtyWorktreeError{}, s) },
	},
	{
		[]string{"unmerged", "conflict"},
		func(s string, _ []string) error { return wrapKindMsg(&ConflictError{}, s) },
	},
	{
		[]string{"not a git repository", "unknown revision", "does not exist", "no such", "not found", "did not match"},
		func(s string, _ []string) error { return wrapKindMsg(&NotFoundError{What: s}, s) },
	},
}

// classifyStderr maps git's stderr into a typed gitrepository error via the ordered
// stderrRules table; an unmatched failure is an unanticipated internal invariant surfaced with
// KindInternal and the (operator-safe, secret-free) stderr for diagnosis.
func classifyStderr(stderr string, args []string) error {
	lower := strings.ToLower(stderr)
	trimmed := strings.TrimSpace(stderr)
	for _, rule := range stderrRules {
		for _, fragment := range rule.fragments {
			if strings.Contains(lower, fragment) {
				return rule.build(trimmed, args)
			}
		}
	}
	return errors.New(errors.KindInternal, "gitrepository: git failed: "+truncate(trimmed, stderrCap))
}

// stderrCap bounds the stderr we fold into an error message so a runaway git failure cannot
// produce an unbounded error string.
const stderrCap = 512

// remoteArg recovers the remote name from a transfer argv for the typed error (best effort —
// "" if not present). git transfer commands place the remote right after the subcommand.
func remoteArg(args []string) string {
	for i, a := range args {
		if (a == "push" || a == "fetch") && i+1 < len(args) {
			// Skip flags to find the remote positional.
			for j := i + 1; j < len(args); j++ {
				if !strings.HasPrefix(args[j], "-") {
					return args[j]
				}
			}
		}
	}
	return ""
}

// wrapKindMsg wraps a typed gitrepository error with its Kind, folding the (secret-free)
// stderr fragment into the chain for diagnosis without losing the type.
func wrapKindMsg(typed error, stderr string) error {
	return errors.Wrap(kindOf(typed), typed.Error()+": "+truncate(stderr, stderrCap), typed)
}

// truncate bounds a string to n bytes with an ellipsis marker.
func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}

// Backend verbs.

//nolint:gocritic // contract §2: the Backend interface takes the op descriptor by value (the frozen seam).
func (g *systemGit) Provision(ctx context.Context, op ProvisionOp, cred *secrets.Secret) (ProvisionResult, error) {
	switch op.Kind {
	case ProvisionClone:
		return g.clone(ctx, &op, cred)
	case ProvisionAddWorktree:
		return g.addWorktree(ctx, &op)
	case ProvisionRemoveWorktree:
		return ProvisionResult{}, g.removeWorktree(ctx, &op)
	case ProvisionFlattenHistory:
		return g.flattenHistory(ctx, &op)
	default:
		return ProvisionResult{}, errors.New(errors.KindInternal, "gitrepository: unknown provision kind")
	}
}

//nolint:gocritic // contract §2: the Backend interface takes the op descriptor by value (the frozen seam).
func (g *systemGit) Inspect(ctx context.Context, op InspectOp) (InspectResult, error) {
	switch op.Kind {
	case InspectStatus:
		return g.status(ctx, &op)
	case InspectDiff:
		return g.diff(ctx, &op)
	case InspectBranches:
		return g.branches(ctx, &op)
	case InspectWorktrees:
		return g.worktrees(ctx, &op)
	default:
		return InspectResult{}, errors.New(errors.KindInternal, "gitrepository: unknown inspect kind")
	}
}

//nolint:gocritic // contract §2: the Backend interface takes the op descriptor by value (the frozen seam).
func (g *systemGit) Author(ctx context.Context, op AuthorOp) (AuthorResult, error) {
	switch op.Kind {
	case AuthorStage:
		return g.stage(ctx, &op)
	case AuthorCommit:
		return g.commit(ctx, &op)
	default:
		return AuthorResult{}, errors.New(errors.KindInternal, "gitrepository: unknown author kind")
	}
}

//nolint:gocritic // contract §2: the Backend interface takes the op descriptor by value (the frozen seam).
func (g *systemGit) Transfer(ctx context.Context, op TransferOp, cred *secrets.Secret) (TransferResult, error) {
	switch op.Kind {
	case TransferFetch:
		return g.fetch(ctx, &op, cred)
	case TransferPush:
		return g.push(ctx, &op, cred)
	default:
		return TransferResult{}, errors.New(errors.KindInternal, "gitrepository: unknown transfer kind")
	}
}

// resolveHead reads HEAD in dir, returning the zero CommitID for an unborn branch (a fresh
// repo with no commits — `git rev-parse HEAD` fails, which is not an error here).
func (g *systemGit) resolveHead(ctx context.Context, dir string) CommitID {
	out, err := g.run(ctx, dir, nil, nil, "rev-parse", "--verify", "--quiet", "HEAD")
	if err != nil {
		return CommitID{}
	}
	return commitIDFromHex(string(out))
}

// currentBranch reads the checked-out branch in dir, the zero BranchName for a detached HEAD.
func (g *systemGit) currentBranch(ctx context.Context, dir string) BranchName {
	out, err := g.run(ctx, dir, nil, nil, "symbolic-ref", "--quiet", "--short", "HEAD")
	if err != nil {
		return BranchName{}
	}
	name := strings.TrimSpace(string(out))
	parsed, perr := ParseBranchName(name)
	if perr != nil {
		return BranchName{}
	}
	return parsed
}

// scanLines splits git output on newlines, dropping the trailing empty line. It bounds
// nothing (callers bound the output via git itself); a bufio.Scanner with a generous buffer
// handles long porcelain lines.
func scanLines(data []byte) []string {
	if len(data) == 0 {
		return nil
	}
	scanner := bufio.NewScanner(bytes.NewReader(data))
	scanner.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
	var lines []string
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}
	return lines
}

// nul-splits a -z porcelain stream into records, dropping the trailing empty record.
func splitNUL(data []byte) []string {
	if len(data) == 0 {
		return nil
	}
	parts := strings.Split(string(data), "\x00")
	if len(parts) > 0 && parts[len(parts)-1] == "" {
		parts = parts[:len(parts)-1]
	}
	return parts
}

// atoiSafe parses an int, returning 0 on malformed input (a defensive parse of git's own
// numeric output, which is well-formed in practice).
func atoiSafe(s string) int {
	n, err := strconv.Atoi(strings.TrimSpace(s))
	if err != nil {
		return 0
	}
	return n
}
