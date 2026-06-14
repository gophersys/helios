package ompadapter

import (
	"bufio"
	"context"
	"os"
	"os/exec"
	"sync"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// maxLineBytes bounds one omp json line the scanner accepts. A tool result can carry a whole
// file, so the buffer is generous (4 MiB); beyond it the line is treated as an Extension
// rather than a fatal scan error.
const maxLineBytes = 4 << 20

// Spawn prepares an omp HarnessConn for spec.Workspace with the resolved Route and the
// OpenRouter key injected onto the CHILD env ONLY. The key crosses the boundary EXACTLY at
// Secret.Use(fn) here — it never enters the Spec, an Event, a log, or a retained string
// outside the assembled child-env slice (the legitimate vehicle, mirrored on every per-turn
// omp invocation). Higher-precedence / route-diverting credential keys are scrubbed first.
//
// omp's headless json mode (`omp -p --mode json <prompt>`) is a ONE-SHOT per turn: the
// prompt is a positional argv (the spike proved omp does NOT read the turn from stdin in
// either `-p` or interactive json mode — both emit only the `session` frame and exit). So
// Spawn does NOT launch omp yet; it returns a conn that signals Ready immediately (omp is
// ready to accept a turn the moment the binary + key are resolved) and launches one omp
// process per Prompt/Steer, streaming that turn's frames to terminal.
//
//nolint:gocritic,ireturn // contract §2: Spec is the frozen copyable input and Spawn returns the HarnessConn port — the frozen lower seam.
func (a *Adapter) Spawn(ctx context.Context, spec agentsession.Spec, route agentsession.Route, cred agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	if err := errors.FromContext(ctx); err != nil {
		return nil, err
	}
	env, err := injectEnvironment(os.Environ(), cred)
	if err != nil {
		return nil, err
	}
	baseArgs := buildArguments(spec, route)
	conn := newProcessConn(a.binary, baseArgs, spec.Workspace, env)
	conn.start()
	return conn, nil
}

// injectEnvironment resolves the OpenRouter key from the protected Secret at the injection
// site (Secret.Use) and returns the scrubbed child environment with exactly the injected var
// set. The plaintext is confined to the Use closure; only the assembled []string escapes,
// and the only entry carrying the key is the one env var omp reads. A nil Secret is an
// AuthError (the value was never resolved).
func injectEnvironment(base []string, cred agentsession.InjectedCredential) ([]string, error) {
	envName := cred.EnvName
	// The adapter OWNS final env placement: it ignores the library default (OMP_AUTH_TOKEN)
	// and lands the key on OPENROUTER_API_KEY, which is where omp's OpenRouter route reads it.
	if envName == "" || envName == "OMP_AUTH_TOKEN" {
		envName = openRouterEnvName
	}
	if cred.Secret == nil {
		return nil, errors.Wrap(errors.KindUnauthenticated, "ompadapter: inject credential",
			agentsession.AuthError{})
	}
	var env []string
	useErr := cred.Secret.Use(func(plaintext []byte) error {
		// childEnvironment copies the key bytes into exactly one env entry; the plaintext slice
		// is not retained past this closure.
		env = childEnvironment(base, envName, string(plaintext))
		return nil
	})
	if useErr != nil {
		return nil, errors.Wrap(errors.KindUnauthenticated, "ompadapter: read credential", useErr)
	}
	return env, nil
}

// processConn is the os/exec-backed HarnessConn for omp's one-shot-per-turn headless json
// mode. It owns the events channel and the lifecycle: Ready is signaled on start; each
// Prompt/Steer launches one `omp -p --mode json <text>` process whose stdout is scanned into
// normalized Events on a turn goroutine; Abort kills the in-flight turn; Close ends the
// stream.
//
// Concurrency: a single turn goroutine owns the events channel at a time (turnMu serializes
// Send so two turns never race the stream); Close is idempotent via sync.Once.
type processConn struct {
	binary    string
	baseArgs  []string
	workspace string
	env       []string

	events chan agentsession.Event

	// turnMu serializes every send on events (the Ready handshake and each turn) AND the
	// channel close, so a turn never races Close into a send-on-closed-channel. closed is set
	// under turnMu before the channel is closed.
	turnMu sync.Mutex
	closed bool

	// procMu guards the in-flight turn process pointer so Abort/Close can kill it WITHOUT
	// waiting on the turn-long turnMu held by runTurn.
	procMu  sync.Mutex
	current *exec.Cmd // the in-flight turn process; nil between turns

	startOnce sync.Once
	closeOnce sync.Once
	done      chan struct{} // closed on Close to unblock a turn's send-loop select
}

// newProcessConn builds a conn from the resolved binary, the session-wide base args, the
// workspace dir, and the assembled child env (carrying the injected key).
func newProcessConn(binary string, baseArgs []string, workspace string, env []string) *processConn {
	return &processConn{
		binary:    binary,
		baseArgs:  baseArgs,
		workspace: workspace,
		env:       env,
		events:    make(chan agentsession.Event),
		done:      make(chan struct{}),
	}
}

// start signals Ready on its own goroutine: omp is ready to accept a turn the moment the
// binary + key are resolved (the spike's session frame is per-turn startup metadata, not a
// pre-turn readiness signal, so the adapter cannot wait for it before the first Prompt — the
// claudeadapter Ready-on-spawn lesson, applied to omp's one-shot model).
func (c *processConn) start() {
	c.startOnce.Do(func() { go c.signalReady() })
}

// signalReady emits the Initializing->Ready handshake the library Open() blocks on. The send
// is guarded by turnMu so it never races Close's channel close.
func (c *processConn) signalReady() {
	c.turnMu.Lock()
	defer c.turnMu.Unlock()
	if c.closed {
		return
	}
	select {
	case c.events <- agentsession.Event{
		Kind:  agentsession.EventSessionState,
		State: &agentsession.StatePayload{From: agentsession.StateInitializing, To: agentsession.StateReady},
	}:
	case <-c.done:
	}
}

// Events returns the normalized, pre-Seq event channel the library pumps.
func (c *processConn) Events() <-chan agentsession.Event { return c.events }

// Send runs one turn. Prompt and Steer launch `omp -p --mode json <text>` and stream that
// turn's frames to terminal (synchronously, so the next Send waits for the current turn —
// matching the one-shot model). Abort kills the in-flight turn process. Sends are serialized
// under turnMu.
func (c *processConn) Send(ctx context.Context, command agentsession.Command) error {
	if err := errors.FromContext(ctx); err != nil {
		return err
	}
	switch command.Kind {
	case agentsession.CommandAbort:
		return c.abort()
	case agentsession.CommandPrompt, agentsession.CommandSteer:
		return c.runTurn(ctx, command.Text)
	default:
		return errors.New(errors.KindInvalid, "ompadapter: unknown control kind")
	}
}

// runTurn launches one omp process with the turn text as the positional argv, scans its
// stdout into normalized Events, and reaps it. It holds turnMu for the whole turn so the
// stream carries one turn's frames at a time.
func (c *processConn) runTurn(ctx context.Context, text string) error {
	c.turnMu.Lock()
	defer c.turnMu.Unlock()
	if c.closed {
		return errors.New(errors.KindUnavailable, "ompadapter: connection closed")
	}

	args := make([]string, 0, len(c.baseArgs)+1)
	args = append(args, c.baseArgs...)
	args = append(args, text)
	command := exec.CommandContext(ctx, c.binary, args...) // #nosec G204 -- binary is Eden-configured; args are Eden-resolved (mode/model/tools/route) plus the turn text — never a shell.
	command.Dir = c.workspace
	command.Env = c.env
	command.Stderr = nil // stderr is diagnostic; the event stream rides stdout only

	stdout, err := command.StdoutPipe()
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "ompadapter: stdout pipe",
			agentsession.SpawnError{Harness: harnessName})
	}
	if err := command.Start(); err != nil {
		return errors.Wrap(errors.KindUnavailable, "ompadapter: start process",
			agentsession.SpawnError{Harness: harnessName})
	}
	c.setCurrent(command)
	defer func() {
		c.setCurrent(nil)
		_ = command.Wait() //nolint:errcheck // the process exit status is not the contract; the terminal Event (or its absence) is.
	}()

	normalizer := newNormalizer()
	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 0, 64*1024), maxLineBytes)
	for scanner.Scan() {
		events := normalizer.normalize(scanner.Bytes())
		for i := range events {
			select {
			case c.events <- events[i]:
			case <-c.done:
				return nil
			}
		}
	}
	return nil
}

// setCurrent stores (or clears) the in-flight turn process pointer under procMu.
func (c *processConn) setCurrent(command *exec.Cmd) {
	c.procMu.Lock()
	c.current = command
	c.procMu.Unlock()
}

// abort kills the in-flight turn process (the omp cancel). It is best-effort: a turn that has
// already exited leaves current nil.
func (c *processConn) abort() error {
	c.procMu.Lock()
	current := c.current
	c.procMu.Unlock()
	if current != nil && current.Process != nil {
		_ = current.Process.Kill() //nolint:errcheck // best-effort turn cancel; an already-exited process is the desired state.
	}
	return nil
}

// Close stops accepting turns, kills any in-flight turn, and closes the event stream. It is
// idempotent. The ladder: close done (unblocks a turn's send-loop select) -> kill the
// in-flight process -> acquire turnMu (the running turn releases it once done unblocks its
// send) -> mark closed and close the events channel under turnMu so no sender races it.
func (c *processConn) Close(_ context.Context) error {
	c.closeOnce.Do(func() {
		close(c.done)
		_ = c.abort() //nolint:errcheck // best-effort in-flight turn cancel on Close.
		c.turnMu.Lock()
		c.closed = true
		close(c.events)
		c.turnMu.Unlock()
	})
	return nil
}

// compile-time assertion: *processConn is an agentsession.HarnessConn.
var _ agentsession.HarnessConn = (*processConn)(nil)
