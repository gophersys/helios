package claudeadapter

import (
	"bufio"
	"context"
	"encoding/json"
	"io"
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

	conn := newProcessConn(command, stdin, stdout, spec)
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

// peerDeliveryBuffer bounds the hand-off channel a peer delivery's event rides from Send (the
// library's deliver goroutine) to the scanner (the sole sender on the events channel). A session
// takes deliveries one at a time, but the buffer is generous so a burst never blocks that
// goroutine on the scanner.
const peerDeliveryBuffer = 8

// processConn is the os/exec-backed HarnessConn: it scans the subprocess stdout into
// normalized Events and writes control frames (Prompt/Steer/Abort) to stdin as
// stream-json user turns. The graceful Close ladder closes stdin and joins the scanner, which
// reaps the child once its stdout has reached its end.
//
// Concurrency: one scanner goroutine owns the events channel; a reader goroutine owns stdout
// and hands it whole lines; Send writes to stdin under a mutex; Close is idempotent via
// sync.Once.
type processConn struct {
	command    *exec.Cmd
	stdin      writeCloser
	stdout     io.Reader
	normalizer *normalizer
	events     chan agentsession.Event

	name        string          // this session's peer address; "" == not addressable
	hostTools   *hostToolRouter // services mcp_message host-tool drives over the control channel
	hostServers []string        // the SDK-MCP servers advertised at the initialize handshake

	// peerEvents carries an inbound delivery's EventPeerMessage from Send to the scanner.
	peerEvents chan agentsession.Event

	writeMu   sync.Mutex
	closeOnce sync.Once
	doneOnce  sync.Once
	done      chan struct{} // closed when the scanner has ended: the Close join and the queue's escape
}

// writeCloser is the minimal stdin seam the conn needs (so a test can substitute an in-memory
// pipe without a real process — the unit-testable surface).
type writeCloser interface {
	Write(p []byte) (int, error)
	Close() error
}

// newProcessConn builds a conn over an already-open transport, with the peer address, the
// host-tool router and the SDK-MCP server set derived from the spec. command is nil on the
// in-memory transport seam, which owns no child to reap.
//
//nolint:gocritic // contract §2: Spec is the frozen copyable session input; the conn mirrors Spawn's by-value port.
func newProcessConn(command *exec.Cmd, stdin writeCloser, stdout io.Reader, spec agentsession.Spec) *processConn {
	return &processConn{
		command:     command,
		stdin:       stdin,
		stdout:      stdout,
		normalizer:  newNormalizer(),
		events:      make(chan agentsession.Event),
		name:        spec.Name,
		hostTools:   newHostToolRouter(spec.HostTools),
		hostServers: hostToolNames(spec.HostTools),
		peerEvents:  make(chan agentsession.Event, peerDeliveryBuffer),
		done:        make(chan struct{}),
	}
}

// newPipeConn builds the REAL conn over an INJECTED transport instead of a spawned process and
// starts it scanning — Spawn adds only the child process and its two pipes on top of it. It
// takes the Spec for the same reason Spawn does: a conn that does not know its own Name cannot
// tell a delivery meant for it from one that is not.
//
//nolint:gocritic // contract §2: Spec is the frozen copyable session input; the seam mirrors Spawn's by-value port.
func newPipeConn(spec agentsession.Spec, stdout io.Reader, stdin io.WriteCloser) *processConn {
	conn := newProcessConn(nil, stdin, stdout, spec)
	conn.start()
	return conn
}

// start launches the stdout scanner.
func (c *processConn) start() { go c.scan() }

// Events returns the normalized, pre-Seq event channel the library pumps.
func (c *processConn) Events() <-chan agentsession.Event { return c.events }

// Send writes a normalized control frame to the subprocess stdin as a stream-json user
// turn. Prompt and Steer send the text as a user message; Abort closes stdin to end the
// turn (the CLI's headless cancel). Each write is serialized under writeMu by the leaf writer
// itself (as writeControl already does), NOT across the whole call: a peer delivery hands its
// event to the scanner AFTER the write, and holding writeMu across that channel push is how a
// full peerEvents buffer plus a wedged scanner made Close (which needs writeMu) unkillable.
func (c *processConn) Send(ctx context.Context, command agentsession.Command) error {
	if err := errors.FromContext(ctx); err != nil {
		return err
	}
	switch command.Kind {
	case agentsession.CommandAbort:
		// End the turn: close stdin so the headless CLI stops reading input.
		c.writeMu.Lock()
		_ = c.stdin.Close() //nolint:errcheck // best-effort turn cancel; an already-closed stdin is the desired state.
		c.writeMu.Unlock()
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
		// The library's deliver goroutine steers an inbound peer message into a RUNNING turn,
		// so the delivery path is on both turn-taking verbs, not only Prompt.
		if delivery, ok := decodePeerDelivery(command.Text); ok {
			return c.deliverPeer(&delivery)
		}
		return c.writeUserTurn(command.Text)
	case agentsession.CommandPrompt:
		if delivery, ok := decodePeerDelivery(command.Text); ok {
			return c.deliverPeer(&delivery)
		}
		return c.writeUserTurn(command.Text)
	default:
		return errors.New(errors.KindInvalid, "claudeadapter: unknown control kind")
	}
}

// writeUserTurn renders text as a stream-json user message and writes it on stdin. The render is
// lock-free; only the stdin write is serialized, under writeMu taken HERE (as writeControl does),
// so deliverPeer can queue the scanner's event after it without holding the send lock.
func (c *processConn) writeUserTurn(text string) error {
	line, err := userTurn(text)
	if err != nil {
		return err
	}
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	if _, werr := c.stdin.Write(line); werr != nil {
		return errors.Wrap(errors.KindUnavailable, "claudeadapter: write stdin", werr)
	}
	return nil
}

// writePermissionDecision writes the can_use_tool control_response for a resolved decision,
// correlated by request id. An allow echoes the original input (stashed by the normalizer when
// the ask arrived) as updatedInput; a deny carries the operator-safe message. The original input
// is consumed exactly once here; only the stdin write is serialized under writeMu, taken HERE.
func (c *processConn) writePermissionDecision(answer parsedPermissionAnswer) error {
	originalInput, _ := c.normalizer.takeInput(answer.requestID)
	result := permissionResult(answer.allow, denyMessage(answer.by, answer.rationale), originalInput)
	line, err := controlResponseFrame(answer.requestID, result)
	if err != nil {
		return err
	}
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
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
//
// The scanner ends on the child's stdout EOF, which the child produces by exiting on that same
// stdin EOF — so the join is what makes the tail of the session reach the stream before it
// closes. A conn built over an INJECTED transport has no child, so nothing on this side will
// ever produce that EOF and the transport's lifetime belongs to whoever injected it: there is
// nothing to wait for, and waiting would be a deadlock rather than a drain.
func (c *processConn) Close(_ context.Context) error {
	c.closeOnce.Do(func() {
		c.writeMu.Lock()
		_ = c.stdin.Close() //nolint:errcheck // best-effort stdin close in the graceful ladder; the scanner drain is the join.
		c.writeMu.Unlock()
	})
	if c.command == nil {
		return nil
	}
	<-c.done
	return nil
}

// scan is the SOLE sender on the events channel. It interleaves the harness's own stdout lines,
// read off a reader goroutine, with the inbound peer DELIVERIES Send hands back — which cannot
// be published by Send itself, because the events channel is unbuffered and a second sender on
// it would race the scanner. On EOF it closes the channel (the library's pump treats a closed
// channel without a terminal as a transport failure, and without a Ready as the
// silent-bad-token trap).
func (c *processConn) scan() {
	defer c.finish()
	// Signal Ready as soon as the process is up. Real `claude` in stream-json INPUT mode does
	// NOT emit `system/init` until it receives the first stdin user turn — but Open() blocks on
	// the Ready handshake BEFORE any prompt is sent, so waiting for init deadlocks (the
	// real-claude hang the fakes hid). The harness is ready to accept a turn the moment it is
	// spawned with stdin open; claude's later `system/init` is session metadata (normalize.go
	// maps it to Extension), not the readiness signal.
	if !c.publish(agentsession.Event{
		Kind:  agentsession.EventSessionState,
		State: &agentsession.StatePayload{From: agentsession.StateInitializing, To: agentsession.StateReady},
	}) {
		return
	}
	// Send the host's initialize control_request: it advertises the SDK-MCP servers (when host
	// tools are registered) so claude drives them over mcp_message, and primes the control
	// channel. A write failure here is best-effort — the conn still scans; the conversation
	// path does not depend on the ack.
	if frame, err := initializeFrame("eden-init-1", c.hostServers); err == nil {
		_ = c.writeControl(frame) //nolint:errcheck // best-effort handshake; the conversation stream does not depend on the ack.
	}
	lines := make(chan []byte)
	go c.readLines(lines)
	for {
		// A delivery goes out FIRST, so the arrival precedes the lines the turn it caused
		// produces — the same ordering the origin-bearing result line owes.
		select {
		case delivered := <-c.peerEvents:
			if !c.publish(delivered) {
				return
			}
			continue
		default:
		}
		select {
		case delivered := <-c.peerEvents:
			if !c.publish(delivered) {
				return
			}
		case line, ok := <-lines:
			if !ok {
				c.waitProcess()
				return
			}
			if !c.publishLine(line) {
				return
			}
		case <-c.done:
			return
		}
	}
}

// readLines scans the harness stdout into whole lines and hands COPIES to the scanner (bufio
// reuses its buffer), closing the channel on EOF so the scanner ends the session.
func (c *processConn) readLines(lines chan<- []byte) {
	defer close(lines)
	scanner := bufio.NewScanner(c.stdout)
	scanner.Buffer(make([]byte, 0, 64*1024), maxLineBytes)
	for scanner.Scan() {
		line := make([]byte, len(scanner.Bytes()))
		copy(line, scanner.Bytes())
		select {
		case lines <- line:
		case <-c.done:
			return
		}
	}
}

// publishLine services or normalizes one stdout line and fans out what it produced. Host-tool
// mcp_message control_requests are serviced inline (they are not conversation): the router
// answers tools/list+tools/call into the HostTool.Handler and the conn writes the
// control_response; any EventToolUpdate it produced is fanned out and the line is not
// normalized. It reports false when Close ended the session first.
func (c *processConn) publishLine(line []byte) bool {
	if events, serviced := c.serviceControl(line); serviced {
		return c.publishAll(events)
	}
	return c.publishAll(c.normalizer.normalize(line))
}

// publish fans one event onto the channel, reporting false when Close ended the session first so
// the scanner returns instead of blocking on a stream nobody will read.
//
//nolint:gocritic // Event is the contract's copyable record; the scanner publishes it by value.
func (c *processConn) publish(event agentsession.Event) bool {
	select {
	case c.events <- event:
		return true
	case <-c.done:
		return false
	}
}

// publishAll fans a batch out in order, stopping at the first Close.
func (c *processConn) publishAll(events []agentsession.Event) bool {
	for i := range events {
		if !c.publish(events[i]) {
			return false
		}
	}
	return true
}

// waitProcess reaps the child once its stdout has reached its end. The in-memory transport seam
// owns no child and has nothing to reap.
func (c *processConn) waitProcess() {
	if c.command == nil {
		return
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
