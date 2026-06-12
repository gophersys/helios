package agent

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os/exec"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// RPCError represents an OMP RPC command failure.
type RPCError struct {
	Command string
	Message string
}

func (e *RPCError) Error() string {
	return fmt.Sprintf("rpc error [%s]: %s", e.Command, e.Message)
}

// RPCClient manages a stdio JSONL connection to an OMP agent process.
type RPCClient struct {
	cmd      *exec.Cmd
	stdin    io.WriteCloser
	scanner  *bufio.Scanner
	mu       sync.Mutex
	startMu  sync.Mutex

	agentID string
	seq     atomic.Int64

	// All frames are broadcast to all subscribers.
	subs     map[string]chan RpcFrame
	subsMu   sync.RWMutex

	// Host tool handler
	hostToolHandler func(ctx context.Context, req RpcHostToolRequest) (interface{}, error)
	// hostToolSem limits concurrent host tool handler goroutines.
	hostToolSem chan struct{}

	ctx    context.Context
	cancel context.CancelFunc
	done   chan struct{}
	ready  chan struct{}
	readyErr error
}

// NewRPCClient spawns an OMP process in RPC mode and returns a connected client.
func NewRPCClient(ctx context.Context, agentID, ompPath string, extraArgs ...string) (*RPCClient, error) {
	ctx, cancel := context.WithCancel(ctx)

	args := []string{"--mode", "rpc"}
	args = append(args, extraArgs...)

	cmd := exec.CommandContext(ctx, ompPath, args...)

	stdin, err := cmd.StdinPipe()
	if err != nil {
		cancel()
		return nil, fmt.Errorf("stdin pipe: %w", err)
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		stdin.Close()
		cancel()
		return nil, fmt.Errorf("stdout pipe: %w", err)
	}

	cmd.Stderr = cmd.Stdout

	if err := cmd.Start(); err != nil {
		stdin.Close()
		cancel()
		return nil, fmt.Errorf("start omp: %w", err)
	}

	c := &RPCClient{
		cmd:         cmd,
		stdin:       stdin,
		scanner:     bufio.NewScanner(stdout),
		subs:        map[string]chan RpcFrame{},
		agentID:     agentID,
		ctx:         ctx,
		cancel:      cancel,
		done:        make(chan struct{}),
		ready:       make(chan struct{}),
		hostToolSem: make(chan struct{}, 10),
	}
	c.scanner.Buffer(make([]byte, 0, 256*1024), 1024*1024)

	// Start reading frames immediately — the first frame will be "ready"
	go c.readLoop()

	// Wait for "ready" frame
	select {
	case <-c.ready:
		if c.readyErr != nil {
			stdin.Close()
			cmd.Process.Kill()
			cancel()
			return nil, c.readyErr
		}
	case <-time.After(10 * time.Second):
		stdin.Close()
		cmd.Process.Kill()
		cancel()
		return nil, fmt.Errorf("timeout waiting for ready frame")
	case <-ctx.Done():
		stdin.Close()
		cmd.Process.Kill()
		cancel()
		return nil, ctx.Err()
	}

	return c, nil
}

func (c *RPCClient) nextSeq() string {
	n := c.seq.Add(1)
	return fmt.Sprintf("req_%d", n)
}

// readLoop processes frames from the OMP process stdout, forwarding all frames to subscribers.
// It also handles "ready" signal and host tool calls inline.
func (c *RPCClient) readLoop() {
	defer close(c.done)

	gotReady := false
	for c.scanner.Scan() {
		line := strings.TrimSpace(c.scanner.Text())
		if line == "" {
			continue
		}

		var frame RpcFrame
		if err := json.Unmarshal([]byte(line), &frame); err != nil {
			continue
		}

		// First frame must be "ready"
		if !gotReady {
			if frame.Type == "ready" {
				gotReady = true
				close(c.ready)
				continue
			}
			c.readyErr = fmt.Errorf("first frame must be 'ready', got: %s", frame.Type)
			close(c.ready)
			return
		}

		// Broadcast to all subscribers
		c.subsMu.RLock()
		for _, ch := range c.subs {
			select {
			case ch <- frame:
			default:
				// Drop frame if subscriber is slow
			}
		}
		c.subsMu.RUnlock()

		// Handle host tool calls
		if frame.Type == "host_tool_call" {
			c.handleHostToolCall(frame)
		}
	}

	// Scanner ended (stdin closed / process died)
	if !gotReady {
		c.readyErr = fmt.Errorf("EOF before ready")
		close(c.ready)
	}
}

// Send sends a command to the OMP process and waits for the matching response.
func (c *RPCClient) Send(ctx context.Context, cmd RpcCommand) (RpcFrame, error) {
	if cmd.ID == "" {
		cmd.ID = c.nextSeq()
	}

	data, err := json.Marshal(cmd)
	if err != nil {
		return RpcFrame{}, fmt.Errorf("marshal command: %w", err)
	}

	// Subscribe for ALL frames (we'll filter by ID ourselves)
	respCh := make(chan RpcFrame, 100)
	subID := "send_" + cmd.ID
	c.subsMu.Lock()
	c.subs[subID] = respCh
	c.subsMu.Unlock()

	defer func() {
		c.subsMu.Lock()
		delete(c.subs, subID)
		c.subsMu.Unlock()
	}()

	// Write to stdin
	c.mu.Lock()
	_, err = fmt.Fprintf(c.stdin, "%s\n", string(data))
	c.mu.Unlock()
	if err != nil {
		return RpcFrame{}, fmt.Errorf("write stdin: %w", err)
	}

	// Wait for the matching response frame
	timeout := 30 * time.Second
	if deadline, ok := ctx.Deadline(); ok {
		timeout = time.Until(deadline)
		if timeout <= 0 {
			timeout = 5 * time.Second
		}
	}

	timer := time.NewTimer(timeout)
	defer timer.Stop()

	for {
		select {
		case frame := <-respCh:
			// Match by ID and type "response"
			if frame.ID == cmd.ID && frame.Type == "response" {
				return frame, nil
			}
			// For commands that don't get a "response" frame (like "prompt" which
			// is ack'd immediately as a response frame), match any response
			if frame.Type == "response" && frame.Command == cmd.Type {
				return frame, nil
			}
			// Skip non-matching frames (UI events, other responses, etc.)
			continue

		case <-timer.C:
			return RpcFrame{}, &RPCError{Command: cmd.Type, Message: "response timeout"}

		case <-c.ctx.Done():
			return RpcFrame{}, c.ctx.Err()

		case <-ctx.Done():
			return RpcFrame{}, ctx.Err()
		}
	}
}

// Subscribe returns a channel that receives all subsequent RPC frames.
func (c *RPCClient) Subscribe(types ...AgentEventType) chan RpcFrame {
	// Cap subscriber channels to bound memory; slow consumers drop frames.
	ch := make(chan RpcFrame, 512)
	if len(types) == 0 {
		subID := fmt.Sprintf("sub_all_%d", len(c.subs))
		c.subsMu.Lock()
		c.subs[subID] = ch
		c.subsMu.Unlock()
		return ch
	}

	// Filtered subscription
	typeSet := make(map[string]bool, len(types))
	for _, t := range types {
		typeSet[string(t)] = true
	}
	filteredCh := make(chan RpcFrame, 512)
	go func() {
		for frame := range ch {
			if typeSet[frame.Type] {
				filteredCh <- frame
			}
		}
	}()

	subID := fmt.Sprintf("sub_filt_%d", len(c.subs))
	c.subsMu.Lock()
	c.subs[subID] = ch
	c.subsMu.Unlock()

	return filteredCh
}

// Unsubscribe removes a subscriber channel.
func (c *RPCClient) Unsubscribe(ch chan RpcFrame) {
	c.subsMu.Lock()
	defer c.subsMu.Unlock()
	for id, sub := range c.subs {
		if sub == ch {
			delete(c.subs, id)
			return
		}
	}
}

// SetHostToolHandler registers the callback for host tool execution requests.
func (c *RPCClient) SetHostToolHandler(handler func(ctx context.Context, req RpcHostToolRequest) (interface{}, error)) {
	c.hostToolHandler = handler
}

// SendHostToolResult sends a host tool result back to the OMP process.
func (c *RPCClient) SendHostToolResult(reqID string, result interface{}) error {
	return c.sendRaw(map[string]interface{}{
		"type":   "host_tool_result",
		"id":     reqID,
		"result": result,
	})
}

// SendHostToolUpdate sends a partial host tool update.
func (c *RPCClient) SendHostToolUpdate(reqID string, partial interface{}) error {
	return c.sendRaw(map[string]interface{}{
		"type":          "host_tool_update",
		"id":            reqID,
		"partialResult": partial,
	})
}

func (c *RPCClient) sendRaw(payload interface{}) error {
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	c.mu.Lock()
	_, err = fmt.Fprintf(c.stdin, "%s\n", string(data))
	c.mu.Unlock()
	return err
}

// Prompt sends a prompt command and returns the response.
func (c *RPCClient) Prompt(ctx context.Context, message string) (RpcFrame, error) {
	return c.Send(ctx, RpcCommand{
		Type:    "prompt",
		Message: message,
	})
}

// Abort sends an abort command.
func (c *RPCClient) Abort(ctx context.Context) (RpcFrame, error) {
	return c.Send(ctx, RpcCommand{Type: "abort"})
}

// GetState returns the full agent state as a parsed map.
func (c *RPCClient) GetState(ctx context.Context) (map[string]interface{}, error) {
	frame, err := c.Send(ctx, RpcCommand{Type: "get_state"})
	if err != nil {
		return nil, err
	}
	// Frame should have Success=true
	if frame.Success == nil || !*frame.Success {
		errMsg := "unknown error"
		if frame.Error != "" {
			errMsg = frame.Error
		}
		return nil, &RPCError{Command: "get_state", Message: errMsg}
	}
	var data map[string]interface{}
	if frame.Data != nil {
		if err := json.Unmarshal(frame.Data, &data); err != nil {
			return nil, fmt.Errorf("parse state data: %w", err)
		}
	}
	return data, nil
}

// SetModel sets the active model.
func (c *RPCClient) SetModel(ctx context.Context, provider, modelID string) (RpcFrame, error) {
	return c.Send(ctx, RpcCommand{
		Type:     "set_model",
		Provider: provider,
		ModelID:  modelID,
	})
}

// SetThinkingLevel sets the thinking level.
func (c *RPCClient) SetThinkingLevel(ctx context.Context, level string) (RpcFrame, error) {
	return c.Send(ctx, RpcCommand{
		Type:  "set_thinking_level",
		Level: level,
	})
}

// SetAutoCompaction enables or disables auto-compaction.
func (c *RPCClient) SetAutoCompaction(ctx context.Context, enabled bool) (RpcFrame, error) {
	e := enabled
	return c.Send(ctx, RpcCommand{
		Type:    "set_auto_compaction",
		Enabled: &e,
	})
}

// Close terminates the OMP process.
func (c *RPCClient) Close() error {
	c.cancel()
	c.mu.Lock()
	if c.stdin != nil {
		c.stdin.Close()
		c.stdin = nil
	}
	c.mu.Unlock()

	done := make(chan struct{})
	go func() {
		c.cmd.Wait()
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		c.cmd.Process.Kill()
	}
	return nil
}

// PID returns the process ID.
func (c *RPCClient) PID() int {
	if c.cmd != nil && c.cmd.Process != nil {
		return c.cmd.Process.Pid
	}
	return 0
}

// Done returns a channel that closes when the OMP process exits.
func (c *RPCClient) Done() <-chan struct{} {
	return c.done
}

func (c *RPCClient) handleHostToolCall(frame RpcFrame) {
	if c.hostToolHandler == nil {
		return
	}
	req := RpcHostToolRequest{
		Type:       frame.Type,
		ID:         frame.ID,
		ToolCallID: frame.ToolCallID,
		ToolName:   frame.ToolName,
		Arguments:  frame.Arguments,
		TargetID:   frame.TargetID,
	}
	// Acquire semaphore slot; drop if overloaded
	select {
	case c.hostToolSem <- struct{}{}:
	default:
		// Too many concurrent tool handlers, send error back
		c.SendHostToolResult(req.ID, map[string]interface{}{
			"isError": true,
			"content": []map[string]interface{}{
				{"type": "text", "text": "host tool handler overloaded, try again"},
			},
		})
		return
	}
	go func() {
		defer func() { <-c.hostToolSem }()
		result, err := c.hostToolHandler(c.ctx, req)
		if err != nil {
			c.SendHostToolResult(req.ID, map[string]interface{}{
				"isError": true,
				"content": []map[string]interface{}{
					{"type": "text", "text": err.Error()},
				},
			})
			return
		}
		c.SendHostToolResult(req.ID, result)
	}()
}