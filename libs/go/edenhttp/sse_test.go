package edenhttp_test

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// TestSSEStream_FramesEvent proves Send writes a well-formed SSE frame: event:/id:/data: lines and
// the blank-line terminator, in order — the exact wire shape an EventSource parses.
func TestSSEStream_FramesEvent(t *testing.T) {
	t.Parallel()
	recorder := httptest.NewRecorder()
	stream, err := edenhttp.NewSSEStream(recorder)
	if err != nil {
		t.Fatalf("NewSSEStream: %v", err)
	}
	if got := recorder.Header().Get("Content-Type"); !strings.HasPrefix(got, "text/event-stream") {
		t.Errorf("Content-Type = %q, want text/event-stream", got)
	}

	if err := stream.Send(edenhttp.SSEFrame{ID: 7, Event: "text-delta", Data: []byte(`{"delta":"hi"}`)}); err != nil {
		t.Fatalf("Send: %v", err)
	}
	body := recorder.Body.String()
	wantFrame := "event: text-delta\nid: 7\ndata: {\"delta\":\"hi\"}\n\n"
	if !strings.Contains(body, wantFrame) {
		t.Errorf("frame not found.\n got: %q\nwant substring: %q", body, wantFrame)
	}
}

// TestSSEStream_Heartbeat proves Heartbeat writes a comment line (no data, no id), so a standard
// EventSource ignores it as a keepalive no-op.
func TestSSEStream_Heartbeat(t *testing.T) {
	t.Parallel()
	recorder := httptest.NewRecorder()
	stream, err := edenhttp.NewSSEStream(recorder)
	if err != nil {
		t.Fatalf("NewSSEStream: %v", err)
	}
	if err := stream.Heartbeat(); err != nil {
		t.Fatalf("Heartbeat: %v", err)
	}
	if !strings.Contains(recorder.Body.String(), ": keepalive\n\n") {
		t.Errorf("heartbeat comment not found in %q", recorder.Body.String())
	}
}

// TestSSEStream_Comment proves a trailing fault comment carries the stable Kind token only.
func TestSSEStream_Comment(t *testing.T) {
	t.Parallel()
	recorder := httptest.NewRecorder()
	stream, err := edenhttp.NewSSEStream(recorder)
	if err != nil {
		t.Fatalf("NewSSEStream: %v", err)
	}
	stream.Comment(errors.KindUnavailable)
	if !strings.Contains(recorder.Body.String(), ": error kind=unavailable\n\n") {
		t.Errorf("error comment not found in %q", recorder.Body.String())
	}
}

// nonFlushWriter is an http.ResponseWriter that is NOT an http.Flusher, to prove NewSSEStream
// rejects a writer it cannot stream through.
type nonFlushWriter struct{ header http.Header }

func (w *nonFlushWriter) Header() http.Header         { return w.header }
func (w *nonFlushWriter) Write(p []byte) (int, error) { return len(p), nil }
func (w *nonFlushWriter) WriteHeader(int)             {}

// TestNewSSEStream_RequiresFlusher proves a non-flushable writer is a typed internal error (SSE is
// impossible without flushing).
func TestNewSSEStream_RequiresFlusher(t *testing.T) {
	t.Parallel()
	if _, err := edenhttp.NewSSEStream(&nonFlushWriter{header: http.Header{}}); errors.KindOf(err) != errors.KindInternal {
		t.Fatalf("non-flusher kind = %s, want internal", errors.KindOf(err))
	}
}
