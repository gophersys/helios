package claudeadapter

import (
	"bufio"
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"sync"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// maxLineBytes bounds one stream-json line the scanner accepts. A tool result can carry
// a whole file, so the buffer is generous (4 MiB) — beyond it the line is treated as an
// Extension rather than a fatal scan error.
const maxLineBytes = 4 << 20

// Spawn launches the headless `claude` subprocess in spec.Workspace with the resolved
// Route and the credential injected onto the CHILD env ONLY. The setup-token crosses the
// boundary EXACTLY at Secret.Use(fn) here — it never enters the Spec, an Event, a log, or
// a retained string outside the closure. Higher-precedence credential keys are scrubbed
// first (the precedence trap). It returns a HarnessConn streaming normalized Events.
//
// NOTE: this is the WIRED-but-gated live path. The arg/env construction and the
// stream-json normalizer are unit-tested with fixtures; a live authenticated run is
// exercised only behind //go:build integration with an explicit, externally-supplied
// token (never minted here, never read from ~/.claude).
//
//nolint:gocritic,ireturn // contract §2: Spec is the frozen copyable input and Spawn returns the HarnessConn port — the frozen lower seam.
func (a *Adapter) Spawn(ctx context.Context, spec agentsession.Spec, route agentsession.Route, cred agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	arguments := buildArguments(spec, route)
	command := exec.CommandContext(ctx, a.binary, arguments...) //nolint:gosec // binary is Eden-configured; args are Eden-resolved (allowlist/route), never raw user input
	command.Dir = spec.Workspace

	env, err := injectEnvironment(os.Environ(), cred)
	if err != nil {
		return nil, err
	}
	command.Env = env

	stdin, err := command.StdinPipe()
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "claudeadapter: stdin pipe",
			agentsession.SpawnError{Harness: harnessName})
	}
	stdout, err := command.StdoutPipe()
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "claudeadapter: stdout pipe",
			agentsession.SpawnError{Harness: harnessName})
	}
	command.Stderr = nil // stderr is diagnostic; the event stream rides stdout only

	if err := command.Start(); err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "claudeadapter: start process",
			agentsession.SpawnError{Harness: harnessName})
	}

	conn := newProcessConn(command, stdin, stdout)
	conn.start()
	return conn, nil
}

// injectEnvironment resolves the token from the protected Secret at the injection site
// (Secret.Use) and returns the scrubbed child environment with exactly the injected var
// set. The plaintext is confined to the Use closure; only the assembled []string escapes,
// and the only entry carrying the token is the one env var the CLI reads. A nil Secret is
// an AuthError (the value was never resolved).
func injectEnvironment(base []string, cred agentsession.InjectedCredential) ([]string, error) {
	envName := cred.EnvName
	if envName == "" {
		envName = credentialEnvName
	}
	if cred.Secret == nil {
		return nil, errors.Wrap(errors.KindUnauthenticated, "claudeadapter: inject credential",
			agentsession.AuthError{})
	}
	var env []string
	useErr := cred.Secret.Use(func(plaintext []byte) error {
		// childEnvironment copies the token bytes into exactly one env entry; the
		// plaintext slice is not retained past this closure.
		env = childEnvironment(base, envName, string(plaintext))
		return nil
	})
	if useErr != nil {
		return nil, errors.Wrap(errors.KindUnauthenticated, "claudeadapter: read credential", useErr)
	}
	return env, nil
}

// processConn is the os/exec-backed HarnessConn: it scans the subprocess stdout into
// normalized Events and writes control frames (Prompt/Steer/Abort) to stdin as
// stream-json user turns. The graceful Close ladder closes stdin, waits, then kills.
//
// Concurrency: one scanner goroutine owns stdout and the events channel; Send writes to
// stdin under a mutex; Close is idempotent via sync.Once.
type processConn struct {
	command    *exec.Cmd
	stdin      writeCloser
	stdout     readCloser
	normalizer *normalizer
	events     chan agentsession.Event

	writeMu   sync.Mutex
	closeOnce sync.Once
	doneOnce  sync.Once
	done      chan struct{}
}

// writeCloser and readCloser are the minimal pipe seams the conn needs (so a test can
// substitute in-memory pipes without a real process — the unit-testable surface).
type (
	writeCloser interface {
		Write(p []byte) (int, error)
		Close() error
	}
	readCloser interface {
		Read(p []byte) (int, error)
		Close() error
	}
)

// newProcessConn builds a conn over a started command and its pipes.
func newProcessConn(command *exec.Cmd, stdin writeCloser, stdout readCloser) *processConn {
	return &processConn{
		command:    command,
		stdin:      stdin,
		stdout:     stdout,
		normalizer: newNormalizer(),
		events:     make(chan agentsession.Event),
		done:       make(chan struct{}),
	}
}

// start launches the stdout scanner.
func (c *processConn) start() { go c.scan() }

// Events returns the normalized, pre-Seq event channel the library pumps.
func (c *processConn) Events() <-chan agentsession.Event { return c.events }

// Send writes a normalized control frame to the subprocess stdin as a stream-json user
// turn. Prompt and Steer send the text as a user message; Abort closes stdin to end the
// turn (the CLI's headless cancel). Writes are serialized under writeMu.
func (c *processConn) Send(ctx context.Context, command agentsession.Command) error {
	if err := errors.FromContext(ctx); err != nil {
		return err
	}
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	switch command.Kind {
	case agentsession.CommandAbort:
		// End the turn: close stdin so the headless CLI stops reading input.
		_ = c.stdin.Close() //nolint:errcheck // best-effort turn cancel; an already-closed stdin is the desired state.
		return nil
	case agentsession.CommandPrompt, agentsession.CommandSteer:
		line, err := userTurn(command.Text)
		if err != nil {
			return err
		}
		if _, werr := c.stdin.Write(line); werr != nil {
			return errors.Wrap(errors.KindUnavailable, "claudeadapter: write stdin", werr)
		}
		return nil
	default:
		return errors.New(errors.KindInvalid, "claudeadapter: unknown control kind")
	}
}

// Close runs the graceful ladder: close stdin (signal end of input), then wait for the
// scanner to drain. The exec.CommandContext cancel reaps the process if it does not exit;
// Close is idempotent.
func (c *processConn) Close(_ context.Context) error {
	c.closeOnce.Do(func() {
		c.writeMu.Lock()
		_ = c.stdin.Close() //nolint:errcheck // best-effort stdin close in the graceful ladder; the scanner drain is the join.
		c.writeMu.Unlock()
	})
	<-c.done
	return nil
}

// scan reads stdout line by line, normalizes each into Events, and fans them onto the
// events channel. On EOF / scan end it closes the channel (the library's pump treats a
// closed channel without a terminal as a transport failure, and without a Ready as the
// silent-bad-token trap).
func (c *processConn) scan() {
	defer c.finish()
	scanner := bufio.NewScanner(c.stdout)
	scanner.Buffer(make([]byte, 0, 64*1024), maxLineBytes)
	for scanner.Scan() {
		line := scanner.Bytes()
		events := c.normalizer.normalize(line)
		for i := range events {
			select {
			case c.events <- events[i]:
			case <-c.done:
				return
			}
		}
	}
	_ = c.command.Wait() //nolint:errcheck // the process exit status is not the contract; the terminal Event (or its absence) is.
}

// finish closes the events channel and signals done exactly once.
func (c *processConn) finish() {
	c.doneOnce.Do(func() {
		close(c.events)
		close(c.done)
	})
}

// userTurn renders a control turn as a stream-json user message line the headless CLI
// reads on stdin.
func userTurn(text string) ([]byte, error) {
	payload := map[string]any{
		"type": "user",
		"message": map[string]any{
			"role":    "user",
			"content": text,
		},
	}
	line, err := json.Marshal(payload)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "claudeadapter: marshal user turn", err)
	}
	return append(line, '\n'), nil
}

// compile-time assertion: *processConn is an agentsession.HarnessConn.
var _ agentsession.HarnessConn = (*processConn)(nil)
