package ghadapter

import (
	"context"
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/internal/mint"
)

// schemeGitHubCLI is the Reference scheme resolved by shelling `gh auth token` (the keyring path).
const schemeGitHubCLI = "gh"

// schemeEnvironment is the Reference scheme resolved by reading a named environment variable (the
// fallback path).
const schemeEnvironment = "env"

// schemeSeparator is the canonical "scheme://path" delimiter, matching secrets.Reference's form.
const schemeSeparator = "://"

// authTokenArguments is the EXACT, library-shaped argv handed to the gh binary — a fixed constant,
// never assembled from consumer input, so no Reference path can influence what process runs.
// `gh auth token` prints the active account's token to stdout and nothing else.
var authTokenArguments = []string{"auth", "token"}

// CommandRunner is the narrow process seam the adapter depends on (1 method, well within the ≤5
// ceiling, 10 §9). The real implementation shells `gh` under a confined environment; a unit test
// fakes it to exercise the resolve/redact/mint logic WITHOUT a gh binary or a keyring. It is
// consumer-defined here (the shape of THIS adapter's need), not a mirror of os/exec. The
// REAL-gh proof is the integration lane (//go:build integration), never the fake (ADR-0016 §2).
type CommandRunner interface {
	// Run executes `gh <arguments...>` and returns its stdout bytes. The argument slice is the
	// library-fixed authTokenArguments; implementations MUST NOT log the returned stdout (it is the
	// token) and MUST NOT fold it into an error. A non-zero exit returns a wrapped error whose
	// message carries only the bounded, credential-free stderr.
	Run(ctx context.Context, arguments []string) ([]byte, error)
}

// Config is the immutable, fully-resolved construction input (the configuration pattern). New
// reads it and dials NOTHING — all I/O (the gh spawn, the env read) is lazy, on Resolve.
type Config struct {
	// Binary is the gh executable name/path. Empty defaults to "gh" (resolved on PATH). It is the
	// composition root's hook for a pinned/absolute gh location; it is never consumer input.
	Binary string
}

// Deps is the injected hexagon: the seams a test substitutes. Accepting interfaces / function
// values here is the accept-interfaces rule; New returns the concrete *Adapter.
type Deps struct {
	// Runner is the gh process seam. It defaults to the real confined `gh` runner (built from
	// Config.Binary) when nil; a test injects a fake to exercise the mapping logic without a gh
	// binary. The real-gh proof is the integration lane, never a mock (ADR-0016 §2).
	Runner CommandRunner

	// LookupEnvironment reads a named environment variable (the env:// scheme). It defaults to
	// os.LookupEnv when nil; a test injects a deterministic map-backed lookup so the env path is
	// exercised without mutating the real process environment. The bool reports "was it set",
	// distinguishing an unset variable (NotFound) from a set-but-empty one (also NotFound — an
	// empty token is no token).
	LookupEnvironment func(key string) (value string, ok bool)
}

// Adapter is the concrete secrets.Provider returned by New. It holds the injected seams and is
// stateless beyond them, so it is trivially safe for concurrent use by multiple goroutines. Zero
// value is not usable; construct via New.
type Adapter struct {
	runner            CommandRunner
	lookupEnvironment func(key string) (value string, ok bool)
}

// New is the constructor spine (10 §9). PURE: no I/O, no env reads, no clock, no process spawn. It
// defaults the optional seams to their real implementations and returns the concrete *Adapter. The
// gh spawn / env read happen lazily on Resolve.
func New(configuration Config, dependencies Deps) (*Adapter, error) {
	runner := dependencies.Runner
	if runner == nil {
		binary := strings.TrimSpace(configuration.Binary)
		if binary == "" {
			binary = "gh"
		}
		runner = newRealCommandRunner(binary)
	}

	lookupEnvironment := dependencies.LookupEnvironment
	if lookupEnvironment == nil {
		lookupEnvironment = osLookupEnv
	}

	return &Adapter{
		runner:            runner,
		lookupEnvironment: lookupEnvironment,
	}, nil
}

// Resolve implements secrets.Provider: it routes ref by scheme to the gh-keyring path or the
// environment path, reads the token, and mints an independent, un-printable *secrets.Secret. It
// returns the secrets taxonomy errors (InvalidReferenceError / NotFoundError / UnavailableError)
// — the message carries the Reference, never the value — and never a non-nil Secret with a
// non-nil error.
func (a *Adapter) Resolve(ctx context.Context, ref secrets.Reference) (*secrets.Secret, error) {
	if ref.IsZero() {
		return nil, secrets.InvalidReferenceError{Ref: ref}
	}

	scheme, path, ok := splitScheme(ref)
	if !ok {
		return nil, secrets.InvalidReferenceError{Ref: ref}
	}

	switch scheme {
	case schemeGitHubCLI:
		return a.resolveFromGitHubCLI(ctx, ref, path)
	case schemeEnvironment:
		return a.resolveFromEnvironment(ref, path)
	default:
		// This adapter owns only the two schemes above; a Reference routed here under any other
		// scheme is a composition-root wiring mistake, surfaced as an invalid reference.
		return nil, secrets.InvalidReferenceError{Ref: ref}
	}
}

// resolveFromGitHubCLI shells `gh auth token` and mints its stdout as the Secret. The only path
// component the keyring scheme accepts is "token" (the bare token request, gh://token); any other
// path is a malformed reference, because `gh auth token` resolves a single value and this adapter
// does not invent gh sub-selectors. The stdout (the token) is trimmed of its trailing newline,
// minted, and NEVER logged or placed in an error.
func (a *Adapter) resolveFromGitHubCLI(ctx context.Context, ref secrets.Reference, path string) (*secrets.Secret, error) {
	if path != "token" {
		return nil, secrets.InvalidReferenceError{Ref: ref}
	}

	stdout, err := a.runner.Run(ctx, authTokenArguments)
	if err != nil {
		// The runner already returns a wrapped, credential-free error; re-wrap to the secrets
		// taxonomy so the caller branches on AsType[UnavailableError] across rewordings. The
		// Reference is carried; the token (stdout) is not — err never contains it.
		return nil, mapRunnerError(ref, err)
	}

	token := strings.TrimRight(string(stdout), "\r\n")
	if token == "" {
		// gh exited 0 but printed no token: the account is not logged in / has no token. That is a
		// missing secret, not an availability fault.
		return nil, secrets.NotFoundError{Ref: ref}
	}
	return mintSecret([]byte(token)), nil
}

// resolveFromEnvironment reads the environment variable named by the reference path and mints it.
// An unset OR set-but-empty variable is NotFound (an empty token is no token). It performs no
// process spawn — the env read is the whole resolution.
func (a *Adapter) resolveFromEnvironment(ref secrets.Reference, name string) (*secrets.Secret, error) {
	if name == "" {
		return nil, secrets.InvalidReferenceError{Ref: ref}
	}
	value, ok := a.lookupEnvironment(name)
	if !ok || value == "" {
		return nil, secrets.NotFoundError{Ref: ref}
	}
	return mintSecret([]byte(value)), nil
}

// splitScheme parses a Reference into (scheme, path) at the canonical "scheme://path" delimiter.
// It reports ok=false for a Reference with no explicit scheme (a bare name) — this adapter is
// scheme-routed, so a schemeless reference cannot reach a resolution path here. The Reference's
// own Scheme() gives the leading scheme; this also returns the path remainder the schemes consume.
func splitScheme(ref secrets.Reference) (scheme, path string, ok bool) {
	raw := ref.String()
	index := strings.Index(raw, schemeSeparator)
	if index < 0 {
		return "", "", false
	}
	scheme = raw[:index]
	path = raw[index+len(schemeSeparator):]
	if scheme == "" {
		return "", "", false
	}
	return scheme, path, true
}

// mapRunnerError maps a CommandRunner error onto the secrets taxonomy. The runner classifies a
// spawn/exit failure as KindUnavailable (the backing CLI was unreachable or failed), which is the
// one retryable signal; this preserves that as a secrets.UnavailableError carrying the Reference.
// A KindNotFound (e.g. the binary is absent on PATH, were the runner to classify it so) maps to a
// NotFoundError. The token is never in err, so re-wrapping cannot leak it.
func mapRunnerError(ref secrets.Reference, err error) error {
	switch errors.KindOf(err) {
	case errors.KindNotFound:
		return secrets.NotFoundError{Ref: ref}
	default:
		return secrets.UnavailableError{Ref: ref}
	}
}

// mintSecret builds a genuine, un-printable *secrets.Secret from value through the module-internal
// minting seam (secrets.md §3 — the adapter is a sanctioned producer). The comma-ok guard turns an
// impossible registration mismatch into a clear panic, not a silent miscast.
func mintSecret(value []byte) *secrets.Secret {
	sec, ok := mint.Hook()(value).(*secrets.Secret)
	if !ok {
		panic("ghadapter: minting hook returned a non-*secrets.Secret value")
	}
	return sec
}

// compile-time: *Adapter is a secrets.Provider.
var _ secrets.Provider = (*Adapter)(nil)
