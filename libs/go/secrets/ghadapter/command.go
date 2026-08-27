package ghadapter

import (
	"bytes"
	"context"
	"os"
	"os/exec"

	"github.com/gophersys/libs/go/errors"
)

// stderrCap bounds the `gh` stderr folded into an error message so a runaway CLI failure cannot
// produce an unbounded error string. Stdout (the token) is NEVER folded into an error — only
// this bounded, credential-free stderr is.
const stderrCap = 512

// realCommandRunner is the default CommandRunner: it shells the `gh` binary under a MINIMAL,
// isolated environment, capturing stdout (the token) and stderr (the diagnostic) separately. It
// mirrors the gitrepository systemGit precedent (07 §2): the only credential the child can see
// is the one its own keyring holds, and the token surfaces ONLY on stdout, never on an argv or a
// logged command line. It is the sole code in this package that spawns a process.
type realCommandRunner struct {
	// binary is the gh executable name/path; "gh" by default (found on PATH).
	binary string
}

// newRealCommandRunner builds the production runner. It performs NO I/O (matching New's
// purity): constructing the struct spawns nothing; the first `gh` process spawns on Resolve.
func newRealCommandRunner(binary string) *realCommandRunner {
	return &realCommandRunner{binary: binary}
}

// Run executes `gh <arguments...>` under the confined environment and returns its stdout bytes.
// A non-zero exit (or a spawn failure) is mapped to a typed, credential-free error: the token
// lives on stdout, which is NEVER placed in the error — only the bounded stderr is. A canceled
// context surfaces as the context's error so callers can branch on cancellation/deadline.
func (r *realCommandRunner) Run(ctx context.Context, arguments []string) ([]byte, error) {
	command := exec.CommandContext(ctx, r.binary, arguments...) // #nosec G204 -- inherent exec adapter: binary is the configured gh; arguments are library-shaped constants (authTokenArguments), never raw consumer input on argv, never a shell.
	command.Env = confinedEnvironment()
	var stdout, stderr bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = &stderr

	err := command.Run()
	if err == nil {
		return stdout.Bytes(), nil
	}
	if contextErr := ctx.Err(); contextErr != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "ghadapter: gh auth token canceled", contextErr)
	}
	// stdout may carry the token even on a partial failure; it is discarded here and never folded
	// into the error. Only the bounded, credential-free stderr describes the failure.
	return nil, errors.Wrap(errors.KindUnavailable,
		"ghadapter: gh auth token failed: "+truncate(stderr.String(), stderrCap), err)
}

// confinedEnvironment is the minimal, isolated environment every `gh` child runs under. PATH is
// forwarded so `gh` and its sub-tools resolve; HOME and the gh-specific dirs are forwarded so
// `gh` can locate its OWN keyring/config (the whole point of `gh auth token`), but no broader
// ambient credential surface is exported into the child. GH_PROMPT_DISABLED and GH_NO_UPDATE_
// NOTIFIER pin non-interactive, deterministic behavior so the child never blocks on a prompt.
//
// Unlike the git credential path (which DISABLES the ambient keyring so only the injected helper
// wins), `gh auth token` MUST read gh's own keyring — that keyring IS the source of truth here —
// so HOME / XDG_CONFIG_HOME / GH_CONFIG_DIR are forwarded; the GH_TOKEN/GITHUB_TOKEN ambient vars
// are NOT forwarded into the gh child so its answer comes from the keyring, not from whatever
// token already sits in this process's environment (that ambient path is the env:// scheme's job,
// resolved without spawning gh).
func confinedEnvironment() []string {
	environment := []string{
		"GH_PROMPT_DISABLED=1",    // never block on an interactive prompt
		"GH_NO_UPDATE_NOTIFIER=1", // no update-check chatter on stderr
	}
	for _, key := range forwardedEnvironmentKeys {
		if value, ok := os.LookupEnv(key); ok {
			environment = append(environment, key+"="+value)
		}
	}
	return environment
}

// forwardedEnvironmentKeys are the only ambient variables passed into the `gh` child: PATH so it
// can find itself and its sub-tools, and the home/config locators so it can read its OWN keyring.
// GH_TOKEN / GITHUB_TOKEN are deliberately absent — see confinedEnvironment.
var forwardedEnvironmentKeys = []string{
	"PATH",
	"HOME",
	"XDG_CONFIG_HOME",
	"XDG_DATA_HOME",
	"XDG_STATE_HOME",
	"GH_CONFIG_DIR",
}

// osLookupEnv is the production environment reader (the env:// scheme's default). A test injects
// its own map-backed lookup so the env path is exercised without mutating the real process
// environment. It is a thin alias so New's defaulting reads as a value, not an inline closure.
func osLookupEnv(key string) (string, bool) { return os.LookupEnv(key) }

// truncate bounds a string to n bytes with an ellipsis marker, so a runaway gh stderr cannot
// produce an unbounded error string.
func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}

// compile-time: *realCommandRunner is a CommandRunner.
var _ CommandRunner = (*realCommandRunner)(nil)
