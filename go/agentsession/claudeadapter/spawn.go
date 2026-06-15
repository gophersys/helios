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
	command := exec.CommandContext(ctx, a.binary, arguments...) // #nosec G204 -- binary is Eden-configured; args are Eden-resolved (allowlist/route), never raw user input
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

	conn := newProcessConn(command, stdin, stdout, spec.HostTools)
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

	hostTools   *hostToolRouter // services mcp_message host-tool drives over the control channel
	hostServers []string        // the SDK-MCP servers advertised at the initialize handshake

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

// newProcessConn builds a conn over a started command and its pipes, with the host-tool
// router and SDK-MCP server set derived from the spec's HostTools.
func newProcessConn(command *exec.Cmd, stdin writeCloser, stdout readCloser, hostTools []agentsession.HostTool) *processConn {
	return &processConn{
		command:     command,
		stdin:       stdin,
		stdout:      stdout,
		normalizer:  newNormalizer(),
		events:      make(chan agentsession.Event),
		hostTools:   newHostToolRouter(hostTools),
		hostServers: hostToolNames(hostTools),
		done:        make(chan struct{}),
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
	case agentsession.CommandSteer:
		// A Steer frame may be a permission ANSWER (the library's forwardDecision sends the
		// resolved decision as a CommandSteer carrying the internal eden:permission frame). If
		// so, TRANSLATE it to the can_use_tool control_response on the wire — the whole fix:
		// the decision rides the out-of-band control channel, NOT a {"type":"user"} stdin turn
		// the model would read as conversation. A genuine Steer interjection falls through.
		if answer, ok := parsePermissionAnswer(command.Text); ok {
			return c.writePermissionDecision(answer)
		}
		return c.writeUserTurn(command.Text)
	case agentsession.CommandPrompt:
		return c.writeUserTurn(command.Text)
	default:
		return errors.New(errors.KindInvalid, "claudeadapter: unknown control kind")
	}
}

// writeUserTurn renders text as a stream-json user message and writes it on stdin. Caller
// holds writeMu.
func (c *processConn) writeUserTurn(text string) error {
	line, err := userTurn(text)
	if err != nil {
		return err
	}
	if _, werr := c.stdin.Write(line); werr != nil {
		return errors.Wrap(errors.KindUnavailable, "claudeadapter: write stdin", werr)
	}
	return nil
}

// writePermissionDecision writes the can_use_tool control_response for a resolved decision,
// correlated by request id. An allow echoes the original input (stashed by the normalizer when
// the ask arrived) as updatedInput; a deny carries the operator-safe message. Caller holds
// writeMu. The original input is consumed exactly once here.
func (c *processConn) writePermissionDecision(answer parsedPermissionAnswer) error {
	originalInput, _ := c.normalizer.takeInput(answer.requestID)
	result := permissionResult(answer.allow, denyMessage(answer.by), originalInput)
	line, err := controlResponseFrame(answer.requestID, result)
	if err != nil {
		return err
	}
	if _, werr := c.stdin.Write(line); werr != nil {
		return errors.Wrap(errors.KindUnavailable, "claudeadapter: write permission decision", werr)
	}
	return nil
}

// writeControl writes a pre-rendered control frame (the initialize handshake, or an
// mcp_message control_response) on stdin under writeMu. It is the conn-internal control writer,
// serialized against Send's user/decision writes.
func (c *processConn) writeControl(frame []byte) error {
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	if _, err := c.stdin.Write(frame); err != nil {
		return errors.Wrap(errors.KindUnavailable, "claudeadapter: write control frame", err)
	}
	return nil
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
	// Signal Ready as soon as the process is up. Real `claude` in stream-json INPUT mode does
	// NOT emit `system/init` until it receives the first stdin user turn — but Open() blocks on
	// the Ready handshake BEFORE any prompt is sent, so waiting for init deadlocks (the
	// real-claude hang the fakes hid). The harness is ready to accept a turn the moment it is
	// spawned with stdin open; claude's later `system/init` is session metadata (normalize.go
	// maps it to Extension), not the readiness signal.
	select {
	case c.events <- agentsession.Event{
		Kind:  agentsession.EventSessionState,
		State: &agentsession.StatePayload{From: agentsession.StateInitializing, To: agentsession.StateReady},
	}:
	case <-c.done:
		return
	}
	// Send the host's initialize control_request: it advertises the SDK-MCP servers (when host
	// tools are registered) so claude drives them over mcp_message, and primes the control
	// channel. A write failure here is best-effort — the conn still scans; the conversation
	// path does not depend on the ack.
	if frame, err := initializeFrame("eden-init-1", c.hostServers); err == nil {
		_ = c.writeControl(frame) //nolint:errcheck // best-effort handshake; the conversation stream does not depend on the ack.
	}
	scanner := bufio.NewScanner(c.stdout)
	scanner.Buffer(make([]byte, 0, 64*1024), maxLineBytes)
	for scanner.Scan() {
		line := scanner.Bytes()
		// Service host-tool mcp_message control_requests inline (they are not conversation):
		// the router answers tools/list+tools/call into the HostTool.Handler and the conn
		// writes the control_response. serviced==true means the line was a host-tool drive; any
		// EventToolUpdate it produced is fanned out, and the line is not normalized.
		if events, serviced := c.serviceControl(line); serviced {
			for i := range events {
				select {
				case c.events <- events[i]:
				case <-c.done:
					return
				}
			}
			continue
		}
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

// serviceControl intercepts an mcp_message control_request line — the host-tool half of the
// control channel — services it via the host-tool router, and writes the control_response.
// serviced=false means the line is NOT a host-tool drive (a conversation line, a permission
// can_use_tool ask, or a control ack); the caller normalizes it. The returned events are the
// host-tool EventToolUpdates to fan out.
func (c *processConn) serviceControl(line []byte) (events []agentsession.Event, serviced bool) {
	var envelope streamLine
	if err := json.Unmarshal(line, &envelope); err != nil {
		return nil, false
	}
	if envelope.Type != "control_request" || envelope.Request == nil || envelope.Request.Subtype != "mcp_message" {
		return nil, false
	}
	response, toolEvents, ok := c.hostTools.route(context.Background(), envelope.Request.JSONRPC)
	if ok {
		if frame, err := controlResponseFrame(envelope.RequestID, map[string]any{"mcp_response": response}); err == nil {
			_ = c.writeControl(frame) //nolint:errcheck // best-effort host-tool answer; a transport drop ends the stream and synthesizes a Failed terminal.
		}
	}
	return toolEvents, true
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
