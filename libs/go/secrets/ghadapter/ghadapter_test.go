package ghadapter_test

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/ghadapter"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// fakeRunner is an in-memory ghadapter.CommandRunner for the UNIT lane: it exercises the adapter's
// route → run → trim → mint mapping WITHOUT a gh binary or a keyring. The REAL-gh proof is the
// integration lane (//go:build integration), never this fake (ADR-0016 §2). It records the argv it
// was handed so a test can assert the adapter passed the fixed `auth token` arguments and nothing
// influenced by the Reference.
type fakeRunner struct {
	mu sync.Mutex

	// stdout is the bytes Run returns on success (the simulated `gh auth token` output, including a
	// trailing newline to prove trimming). err, when non-nil, forces a failure instead.
	stdout []byte
	err    error

	calls    int
	gotArgsv []string
}

func (f *fakeRunner) Run(_ context.Context, arguments []string) ([]byte, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls++
	f.gotArgsv = append([]string(nil), arguments...)
	if f.err != nil {
		return nil, f.err
	}
	return f.stdout, nil
}

// newGitHubCLIAdapter builds an adapter over a fake runner (the keyring path). The env lookup is
// stubbed to "nothing set" so a keyring-path test cannot accidentally read the real environment.
func newGitHubCLIAdapter(t *testing.T, runner ghadapter.CommandRunner) *ghadapter.Adapter {
	t.Helper()
	adapter, err := ghadapter.New(
		ghadapter.Config{},
		ghadapter.Deps{
			Runner:            runner,
			LookupEnvironment: func(string) (string, bool) { return "", false },
		},
	)
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	return adapter
}

// Construction: New is pure and defaults its seams.

func TestNew_DefaultsSeamsAndIsPure(t *testing.T) {
	t.Parallel()
	// No Runner, no LookupEnvironment, no Binary: New must succeed (defaulting both seams) and must
	// NOT spawn gh or read the environment — construction returns immediately.
	adapter, err := ghadapter.New(ghadapter.Config{}, ghadapter.Deps{})
	if err != nil {
		t.Fatalf("New(zero) error = %v, want nil (seams default)", err)
	}
	if adapter == nil {
		t.Fatal("New(zero) returned a nil Adapter")
	}
}

// Happy path: the keyring scheme shells gh and mints the trimmed stdout.

func TestResolve_GitHubCLIReadsTokenAndMintsSecret(t *testing.T) {
	t.Parallel()
	// stdout carries a trailing newline (gh prints one); the adapter must trim it from the minted value.
	runner := &fakeRunner{stdout: []byte(secretstest.SeededPlaintext + "\n")}
	adapter := newGitHubCLIAdapter(t, runner)

	sec, err := adapter.Resolve(context.Background(), secrets.Ref("gh://token"))
	if err != nil {
		t.Fatalf("Resolve error = %v", err)
	}
	defer sec.Zeroize()

	got, err := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
	if err != nil {
		t.Fatalf("Use1 error = %v", err)
	}
	if got != secretstest.SeededPlaintext {
		t.Errorf("resolved value = %q, want %q (trailing newline trimmed)", got, secretstest.SeededPlaintext)
	}
	if runner.calls != 1 {
		t.Errorf("gh invoked %d times, want exactly 1", runner.calls)
	}
	if strings.Join(runner.gotArgsv, " ") != "auth token" {
		t.Errorf("gh argv = %v, want fixed [auth token]", runner.gotArgsv)
	}
}

// Happy path: the env scheme reads the named variable and mints it.

func TestResolve_EnvironmentReadsNamedVariableAndMints(t *testing.T) {
	t.Parallel()
	environment := map[string]string{"GITHUB_TOKEN": secretstest.SeededPlaintext}
	adapter, err := ghadapter.New(
		ghadapter.Config{},
		ghadapter.Deps{
			// The env path must not spawn gh; a runner that fails the test if called proves it.
			Runner:            &fakeRunner{err: errors.New(errors.KindInternal, "runner must not be called on the env path")},
			LookupEnvironment: func(key string) (string, bool) { v, ok := environment[key]; return v, ok },
		},
	)
	if err != nil {
		t.Fatalf("New error = %v", err)
	}

	sec, err := adapter.Resolve(context.Background(), secrets.Ref("env://GITHUB_TOKEN"))
	if err != nil {
		t.Fatalf("Resolve(env) error = %v", err)
	}
	defer sec.Zeroize()
	got, uerr := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
	if uerr != nil {
		t.Fatalf("Use1 error = %v", uerr)
	}
	if got != secretstest.SeededPlaintext {
		t.Errorf("env-resolved value = %q, want %q", got, secretstest.SeededPlaintext)
	}
}

// Reference validation → InvalidReferenceError.

func TestResolve_MalformedOrUnownedReferenceIsInvalid(t *testing.T) {
	t.Parallel()
	adapter := newGitHubCLIAdapter(t, &fakeRunner{stdout: []byte("x")})
	for _, raw := range []string{
		"token",            // bare name, no scheme (this adapter is scheme-routed)
		"gh://",            // gh scheme but empty path (not "token")
		"gh://account",     // gh scheme but an unsupported sub-selector
		"env://",           // env scheme but no variable name
		"vault://eden/p#k", // a scheme this adapter does not own
	} {
		_, err := adapter.Resolve(context.Background(), secrets.Ref(raw))
		if !errors.IsType[secrets.InvalidReferenceError](err) {
			t.Errorf("Resolve(%q) error = %v, want InvalidReferenceError", raw, err)
		}
	}
}

func TestResolve_ZeroReferenceIsInvalid(t *testing.T) {
	t.Parallel()
	adapter := newGitHubCLIAdapter(t, &fakeRunner{})
	_, err := adapter.Resolve(context.Background(), secrets.Reference{})
	if !errors.IsType[secrets.InvalidReferenceError](err) {
		t.Errorf("Resolve(zero ref) error = %v, want InvalidReferenceError", err)
	}
}

// Empty / missing token → NotFoundError (an empty token is no token).

func TestResolve_GitHubCLIEmptyStdoutIsNotFound(t *testing.T) {
	t.Parallel()
	// gh exits 0 but prints only whitespace/newline: not logged in / no token.
	adapter := newGitHubCLIAdapter(t, &fakeRunner{stdout: []byte("\n")})
	_, err := adapter.Resolve(context.Background(), secrets.Ref("gh://token"))
	if !errors.IsType[secrets.NotFoundError](err) {
		t.Errorf("Resolve(empty gh stdout) error = %v, want NotFoundError", err)
	}
}

func TestResolve_EnvironmentUnsetOrEmptyIsNotFound(t *testing.T) {
	t.Parallel()
	for name, environment := range map[string]map[string]string{
		"unset":         {},
		"set-but-empty": {"GITHUB_TOKEN": ""},
	} {
		adapter, err := ghadapter.New(
			ghadapter.Config{},
			ghadapter.Deps{LookupEnvironment: func(key string) (string, bool) { v, ok := environment[key]; return v, ok }},
		)
		if err != nil {
			t.Fatalf("%s: New error = %v", name, err)
		}
		_, rerr := adapter.Resolve(context.Background(), secrets.Ref("env://GITHUB_TOKEN"))
		if !errors.IsType[secrets.NotFoundError](rerr) {
			t.Errorf("%s: Resolve error = %v, want NotFoundError", name, rerr)
		}
	}
}

// Runner failure → the secrets taxonomy (Unavailable / NotFound), token never in the error.

func TestResolve_GitHubCLIFailureIsUnavailable(t *testing.T) {
	t.Parallel()
	adapter := newGitHubCLIAdapter(t, &fakeRunner{
		err: errors.Wrap(errors.KindUnavailable, "ghadapter: gh auth token failed: not logged in", errors.New(errors.KindUnavailable, "exit 1")),
	})
	_, err := adapter.Resolve(context.Background(), secrets.Ref("gh://token"))
	if !errors.IsType[secrets.UnavailableError](err) {
		t.Errorf("Resolve(gh failure) error = %v, want UnavailableError", err)
	}
}

func TestResolve_GitHubCLIBinaryAbsentIsNotFound(t *testing.T) {
	t.Parallel()
	// A runner that classifies "gh not on PATH" as KindNotFound must surface as a secrets NotFound.
	adapter := newGitHubCLIAdapter(t, &fakeRunner{
		err: errors.New(errors.KindNotFound, "ghadapter: gh binary not found on PATH"),
	})
	_, err := adapter.Resolve(context.Background(), secrets.Ref("gh://token"))
	if !errors.IsType[secrets.NotFoundError](err) {
		t.Errorf("Resolve(gh absent) error = %v, want NotFoundError", err)
	}
}

// No-leak: the resolved token never appears in the Secret's printed/marshaled forms, and a
// runner-failure error never carries stdout (the token).

func TestResolve_SecretRedactsAndErrorNeverCarriesToken(t *testing.T) {
	t.Parallel()
	const needle = "ghp_SEEDED_CANARY_do_not_leak_0123456789"

	// (1) A successfully resolved Secret must redact in every print/marshal surface.
	runner := &fakeRunner{stdout: []byte(needle + "\n")}
	adapter := newGitHubCLIAdapter(t, runner)
	sec, err := adapter.Resolve(context.Background(), secrets.Ref("gh://token"))
	if err != nil {
		t.Fatalf("Resolve error = %v", err)
	}
	defer sec.Zeroize()
	textBytes, terr := sec.MarshalText()
	if terr != nil {
		t.Fatalf("MarshalText error = %v", terr)
	}
	jsonBytes, jerr := sec.MarshalJSON()
	if jerr != nil {
		t.Fatalf("MarshalJSON error = %v", jerr)
	}
	for _, rendered := range []string{
		fmt.Sprintf("%+v", sec), // Format
		fmt.Sprintf("%#v", sec), // GoString
		fmt.Sprintf("%q", sec),  // Format
		sec.String(),
		string(textBytes),
		string(jsonBytes),
	} {
		secretstest.AssertNotLeaked(t, rendered, needle)
	}

	// (2) A runner failure must not fold stdout (the token) into the surfaced error. The runner's
	// contract is that its error carries only stderr; assert the secrets error is token-free.
	failing := newGitHubCLIAdapter(t, &fakeRunner{
		err: errors.Wrap(errors.KindUnavailable, "ghadapter: gh auth token failed: HTTP 401 Unauthorized", errors.New(errors.KindUnavailable, "exit 1")),
	})
	_, ferr := failing.Resolve(context.Background(), secrets.Ref("gh://token"))
	if ferr == nil {
		t.Fatal("expected an error from the failing runner")
	}
	secretstest.AssertNotLeaked(t, ferr.Error(), needle)
}
