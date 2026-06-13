//go:build integration

package gateway_test

import (
	"bufio"
	"net/http"
	"strings"
	"testing"
)

// sseReader reads SSE frames incrementally from a live response so a test can consume a
// prefix, disconnect (cancel the request ctx / close the body), and reconnect — the
// REQ-0023 mid-stream kill + resume proof.
type sseReader struct {
	response *http.Response
	scanner  *bufio.Scanner
}

// newSSEReader wraps a live SSE response for incremental frame reads.
func newSSEReader(response *http.Response) *sseReader {
	scanner := bufio.NewScanner(response.Body)
	scanner.Buffer(make([]byte, 0, 64*1024), 1<<20)
	return &sseReader{response: response, scanner: scanner}
}

// next reads the next complete SSE frame. ok=false at end-of-stream (terminal reached,
// connection closed, or ctx canceled). Comment lines (heartbeats / trailing errors) are
// skipped.
func (r *sseReader) next(t *testing.T) (sseFrame, bool) {
	t.Helper()
	var current sseFrame
	for r.scanner.Scan() {
		line := r.scanner.Text()
		switch {
		case line == "":
			if current.Event != "" || current.Data != "" {
				return current, true
			}
		case strings.HasPrefix(line, "event: "):
			current.Event = strings.TrimPrefix(line, "event: ")
		case strings.HasPrefix(line, "id: "):
			current.ID = strings.TrimPrefix(line, "id: ")
		case strings.HasPrefix(line, "data: "):
			current.Data = strings.TrimPrefix(line, "data: ")
		default:
			// SSE comment (": ...") / unknown field; ignored.
		}
	}
	return sseFrame{}, false
}

// close closes the underlying response body (a client disconnect).
func (r *sseReader) close() {
	_ = r.response.Body.Close() //nolint:errcheck // simulated client disconnect; a close fault is the intended teardown, not a signal.
}

// drainToTerminal reads frames until a terminal event or end-of-stream, returning all
// frames in order.
func (r *sseReader) drainToTerminal(t *testing.T) []sseFrame {
	t.Helper()
	var frames []sseFrame
	for {
		frame, ok := r.next(t)
		if !ok {
			return frames
		}
		frames = append(frames, frame)
		if isTerminalKind(frame.Event) {
			return frames
		}
	}
}
