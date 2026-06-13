package devserve_test

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/eden/apps/agentgateway/internal/devserve"
)

// This is the dev-gateway SMOKE TEST: it stands up the in-memory dev composition root over a
// real ephemeral loopback listener (httptest over the dev handler) and asserts the end-to-end
// happy path the SvelteKit frontend depends on — GET /healthz, POST /sessions, the SSE event
// stream (ordered, monotonic frames spanning the realistic demo taxonomy), and GET /sessions.
//
// It uses ONLY fakes (no real claude setup-token, no harness process, no container, no
// substrate), so it runs in the DEFAULT test lane (no build tag). Every server/session is
// reaped on t.Cleanup, and the stream wait is deadline-bounded, so it is race-clean and
// leak-free.

// smokeDeadline bounds the streaming wait so a wedged stream fails fast instead of hanging
// the lane.
const smokeDeadline = 10 * time.Second

// devServer bundles the served dev gateway and the helpers the smoke test drives it through.
type devServer struct {
	baseURL string
}

// newDevServer builds the dev gateway over in-memory fakes and serves it on a real ephemeral
// loopback listener via httptest. The server and the gateway's live sessions are reaped on
// t.Cleanup (no leak).
func newDevServer(t *testing.T) *devServer {
	t.Helper()
	gateway, err := devserve.BuildDevGateway(devserve.Config{})
	if err != nil {
		t.Fatalf("BuildDevGateway: %v", err)
	}
	server := httptest.NewServer(gateway.Handler())
	t.Cleanup(func() {
		server.Close()
		_ = gateway.Close(context.Background()) //nolint:errcheck // test cleanup reap; a close fault is not a test signal (the reaper is best-effort).
	})
	return &devServer{baseURL: server.URL}
}

// TestSmokeDevGatewayHappyPath proves the dev composition serves a working REST+SSE backend:
// healthz is live, a session creates, its SSE stream delivers ordered demo-taxonomy frames
// with a monotonic id cursor, and the session is then listed.
func TestSmokeDevGatewayHappyPath(t *testing.T) {
	t.Parallel()
	server := newDevServer(t)

	// GET /healthz -> 200.
	status, healthBody := server.getJSON(t, "/healthz")
	if status != http.StatusOK {
		t.Fatalf("healthz: status %d, body %v", status, healthBody)
	}
	if healthBody["status"] != "ok" {
		t.Fatalf("healthz: unexpected body %v", healthBody)
	}

	// POST /sessions -> 201 with an id.
	id := server.createSession(t, "build me a hello-world")

	// GET /sessions/{id}/events (SSE) -> ordered demo frames with a monotonic id cursor,
	// ending on the clean terminal Result, within the deadline.
	ctx, cancel := context.WithTimeout(context.Background(), smokeDeadline)
	defer cancel()
	frames := server.drainSSE(ctx, t, id)

	assertOrderedDemoFrames(t, frames)

	// GET /sessions -> the created session is listed.
	listStatus, listBody := server.getJSON(t, "/sessions?organizationId=org-eden&projectId=proj-chat")
	if listStatus != http.StatusOK {
		t.Fatalf("list: status %d, body %v", listStatus, listBody)
	}
	if !sessionListed(listBody, id) {
		t.Fatalf("created session %q not in list: %v", id, listBody["sessions"])
	}
}

// assertOrderedDemoFrames proves the SSE stream delivered the realistic demo taxonomy: a
// monotonic id (seq) cursor, the message/thinking/tool/usage kinds, and a clean terminal
// result. The exact kinds come from devserve.DemoScript (the agentsessiontest canonical run).
func assertOrderedDemoFrames(t *testing.T, frames []sseFrame) {
	t.Helper()
	if len(frames) < 4 {
		t.Fatalf("expected several demo frames, got %d: %v", len(frames), frameKinds(frames))
	}

	// Monotonic id: seq strictly increases across the ordered frames (REQ-0023 cursor).
	var previous uint64
	for i, frame := range frames {
		if frame.ID == "" {
			t.Fatalf("frame %d (%s) carries no id cursor", i, frame.Event)
		}
		seq := parseSeq(t, frame.ID)
		if i > 0 && seq <= previous {
			t.Fatalf("non-monotonic id at frame %d: %d after %d (kinds=%v)", i, seq, previous, frameKinds(frames))
		}
		previous = seq
	}

	// The demo taxonomy: a streamed message, a thinking block, a tool activity, a usage tick,
	// and a clean terminal result are all present and ordered.
	kinds := frameKinds(frames)
	for _, want := range []string{"text-delta", "thinking-delta", "tool-start", "tool-end", "usage"} {
		if !containsKind(kinds, want) {
			t.Fatalf("demo stream missing %q frame; got %v", want, kinds)
		}
	}
	if last := frames[len(frames)-1].Event; last != "result" {
		t.Fatalf("demo stream did not end on a clean result terminal; ended on %q (kinds=%v)", last, kinds)
	}

	// thinking precedes the terminal, and the tool start precedes its end (ordering sanity).
	if indexOfKind(kinds, "thinking-delta") > indexOfKind(kinds, "result") {
		t.Fatalf("thinking block did not precede the terminal: %v", kinds)
	}
	if indexOfKind(kinds, "tool-start") > indexOfKind(kinds, "tool-end") {
		t.Fatalf("tool-start did not precede tool-end: %v", kinds)
	}
}

// ── HTTP / SSE helpers ─────────────────────────────────────────────────────────.

// sseFrame is one parsed SSE frame: the event kind, the id (seq), and the raw data line.
type sseFrame struct {
	Event string
	ID    string
	Data  string
}

// getJSON sends a GET and returns the status and decoded object body.
func (s *devServer) getJSON(t *testing.T, path string) (status int, decoded map[string]any) {
	t.Helper()
	request, err := http.NewRequestWithContext(context.Background(), http.MethodGet, s.baseURL+path, http.NoBody)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
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
			t.Fatalf("decode body (%d): %v: %s", response.StatusCode, err, string(raw))
		}
	}
	return response.StatusCode, out
}

// createSession posts a create request naming the seeded default template and returns the
// assigned AgentID, failing on a non-201 or an empty id.
func (s *devServer) createSession(t *testing.T, prompt string) string {
	t.Helper()
	templateName, templateVersion := devserve.DefaultCreateTemplate()
	body := map[string]any{
		"organizationId":  "org-eden",
		"projectId":       "proj-chat",
		"templateName":    templateName,
		"templateVersion": templateVersion,
		"by":              "smoke-test",
		"prompt":          prompt,
	}
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(body); err != nil {
		t.Fatalf("encode create body: %v", err)
	}
	request, err := http.NewRequestWithContext(context.Background(), http.MethodPost, s.baseURL+"/sessions", &buf)
	if err != nil {
		t.Fatalf("new create request: %v", err)
	}
	request.Header.Set("Content-Type", "application/json")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("do create request: %v", err)
	}
	defer func() { _ = response.Body.Close() }() //nolint:errcheck // test cleanup; a body-close fault is not a test signal.
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatalf("read create body: %v", err)
	}
	if response.StatusCode != http.StatusCreated {
		t.Fatalf("create session: status %d, body %s", response.StatusCode, string(raw))
	}
	var decoded struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(raw, &decoded); err != nil {
		t.Fatalf("decode create body: %v: %s", err, string(raw))
	}
	if decoded.ID == "" {
		t.Fatalf("create session: empty id in %s", string(raw))
	}
	return decoded.ID
}

// drainSSE opens the SSE stream for id and reads frames until the terminal event or ctx
// cancellation, returning the frames in order.
func (s *devServer) drainSSE(ctx context.Context, t *testing.T, id string) []sseFrame {
	t.Helper()
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, s.baseURL+"/sessions/"+id+"/events", http.NoBody)
	if err != nil {
		t.Fatalf("new sse request: %v", err)
	}
	request.Header.Set("Accept", "text/event-stream")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("open sse: %v", err)
	}
	if response.StatusCode != http.StatusOK {
		_ = response.Body.Close() //nolint:errcheck // closing on the error path; the status is the signal.
		t.Fatalf("sse: status %d", response.StatusCode)
	}
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
			// SSE comment (": heartbeat") / unknown field — ignored by a standard EventSource.
		}
	}
	if err := scanner.Err(); err != nil {
		t.Fatalf("scan sse stream: %v", err)
	}
	return frames
}

// isTerminalKind reports whether an SSE event kind token is a terminal event.
func isTerminalKind(kind string) bool {
	return kind == "result" || kind == "failed" || kind == "aborted"
}

// frameKinds projects the ordered event-kind tokens of a frame slice.
func frameKinds(frames []sseFrame) []string {
	out := make([]string, len(frames))
	for i, frame := range frames {
		out[i] = frame.Event
	}
	return out
}

// containsKind reports whether kinds contains want.
func containsKind(kinds []string, want string) bool {
	return indexOfKind(kinds, want) >= 0
}

// indexOfKind returns the first index of want in kinds, or -1.
func indexOfKind(kinds []string, want string) int {
	for i, kind := range kinds {
		if kind == want {
			return i
		}
	}
	return -1
}

// parseSeq parses an SSE id token to a numeric seq for the monotonicity check.
func parseSeq(t *testing.T, token string) uint64 {
	t.Helper()
	seq, err := strconv.ParseUint(token, 10, 64)
	if err != nil {
		t.Fatalf("id token %q not numeric: %v", token, err)
	}
	return seq
}

// sessionListed reports whether the list-response body carries a session with the given id.
func sessionListed(body map[string]any, id string) bool {
	sessions, ok := body["sessions"].([]any)
	if !ok {
		return false
	}
	for _, entry := range sessions {
		record, ok := entry.(map[string]any)
		if !ok {
			continue
		}
		if record["id"] == id {
			return true
		}
	}
	return false
}
