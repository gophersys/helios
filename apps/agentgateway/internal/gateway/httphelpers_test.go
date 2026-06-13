package gateway_test

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"
)

// sseFrame is one parsed SSE frame: the event kind, the id (seq), and the raw data line.
type sseFrame struct {
	Event string
	ID    string
	Data  string
}

// postJSON sends a JSON body to path and returns the status and decoded response.
func (h *harness) postJSON(t *testing.T, path string, body any) (status int, decoded map[string]any) {
	t.Helper()
	var buf bytes.Buffer
	if body != nil {
		if err := json.NewEncoder(&buf).Encode(body); err != nil {
			t.Fatalf("encode body: %v", err)
		}
	}
	request, err := http.NewRequestWithContext(context.Background(), http.MethodPost, h.baseURL+path, &buf)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	request.Header.Set("Content-Type", "application/json")
	return doDecode(t, request)
}

// getJSON sends a GET to path and returns the status and decoded response.
func (h *harness) getJSON(t *testing.T, path string) (status int, decoded map[string]any) {
	t.Helper()
	request, err := http.NewRequestWithContext(context.Background(), http.MethodGet, h.baseURL+path, http.NoBody)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	return doDecode(t, request)
}

// doDecode runs a request and decodes the JSON body into a generic map.
func doDecode(t *testing.T, request *http.Request) (status int, decoded map[string]any) {
	t.Helper()
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("do request: %v", err)
	}
	defer func() { _ = response.Body.Close() }() //nolint:errcheck // test cleanup; a body-close fault is not a test signal.
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	out := map[string]any{}
	if len(bytes.TrimSpace(raw)) > 0 {
		if err := json.Unmarshal(raw, &out); err != nil {
			// A list/transcript body may be an object with arrays — still an object, so a
			// decode failure here is a real test signal.
			t.Fatalf("decode body (%d): %v: %s", response.StatusCode, err, string(raw))
		}
	}
	return response.StatusCode, out
}

// createSession posts a create request and returns the assigned AgentID, failing on a
// non-201.
func (h *harness) createSession(t *testing.T, prompt string) string {
	t.Helper()
	status, body := h.postJSON(t, "/sessions", createBody(prompt))
	if status != http.StatusCreated {
		t.Fatalf("create session: status %d, body %v", status, body)
	}
	id, ok := body["id"].(string)
	if !ok || id == "" {
		t.Fatalf("create session: empty id in %v", body)
	}
	return id
}

// openSSE opens the SSE stream for an agent at the given cursor and returns the response so
// the caller can read frames incrementally. lastEventID, when non-empty, is sent as the
// Last-Event-ID header (the reconnect path); fromSeqQuery, when non-empty, as the ?from-seq=
// query. ctx bounds the stream (cancel to disconnect).
func (h *harness) openSSE(ctx context.Context, t *testing.T, id, lastEventID, fromSeqQuery string) *http.Response {
	t.Helper()
	url := h.baseURL + "/sessions/" + id + "/events"
	if fromSeqQuery != "" {
		url += "?from-seq=" + fromSeqQuery
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, url, http.NoBody)
	if err != nil {
		t.Fatalf("new sse request: %v", err)
	}
	request.Header.Set("Accept", "text/event-stream")
	if lastEventID != "" {
		request.Header.Set("Last-Event-ID", lastEventID)
	}
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("open sse: %v", err)
	}
	return response
}

// readFramesUntilTerminal reads SSE frames from response until a terminal event (result /
// failed / aborted) or EOF, returning the frames in order. It is bounded by the response
// body close / ctx the caller controls.
func readFramesUntilTerminal(t *testing.T, response *http.Response) []sseFrame {
	t.Helper()
	defer func() { _ = response.Body.Close() }() //nolint:errcheck // test cleanup; a body-close fault is not a test signal.
	scanner := bufio.NewScanner(response.Body)
	scanner.Buffer(make([]byte, 0, 64*1024), 1<<20)

	var frames []sseFrame
	var current sseFrame
	for scanner.Scan() {
		line := scanner.Text()
		switch {
		case line == "":
			if current.Event != "" || current.Data != "" {
				frames = append(frames, current)
				if isTerminalKind(current.Event) {
					return frames
				}
				current = sseFrame{}
			}
		case strings.HasPrefix(line, "event: "):
			current.Event = strings.TrimPrefix(line, "event: ")
		case strings.HasPrefix(line, "id: "):
			current.ID = strings.TrimPrefix(line, "id: ")
		case strings.HasPrefix(line, "data: "):
			current.Data = strings.TrimPrefix(line, "data: ")
		default:
			// SSE comment (": ...") / unknown field; ignored by a standard EventSource.
		}
	}
	return frames
}

// isTerminalKind reports whether an SSE event kind token is a terminal event.
func isTerminalKind(kind string) bool {
	return kind == "result" || kind == "failed" || kind == "aborted"
}

// kinds projects the ordered event-kind tokens of a frame slice.
func kinds(frames []sseFrame) []string {
	out := make([]string, len(frames))
	for i, f := range frames {
		out[i] = f.Event
	}
	return out
}

// ids projects the ordered id (seq) tokens of a frame slice.
func ids(frames []sseFrame) []string {
	out := make([]string, len(frames))
	for i, f := range frames {
		out[i] = f.ID
	}
	return out
}
