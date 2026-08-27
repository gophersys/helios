package edenhttp

import (
	"bufio"
	"net/http"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/errors"
)

// CursorAll is the cursor value meaning "replay from the very start of the stream" (the JetStream
// DeliverAll intent). A reconnecting client that has seen no events, or asked for the whole stream,
// resolves to this. Concretely it is 0: "deliver everything after sequence 0".
const CursorAll uint64 = 0

// ResolveCursor reads the SSE resume cursor from the Last-Event-ID header (the EventSource reconnect
// standard) OR the ?from-seq= query — the SAME replay mechanism, so a fresh client and a
// reconnecting browser share one code path. The header wins when both are present (a reconnecting
// EventSource always sends Last-Event-ID). Absent both, the cursor is CursorAll (full replay from
// the start). A malformed value is a typed *errors.Error (KindInvalid → 400).
//
// The returned value is the LAST SEEN sequence: the bridge replays from seq+1, so a client that
// last saw N resumes gap-free at N+1 with no duplicate of N.
func ResolveCursor(request *http.Request) (uint64, error) {
	if header := strings.TrimSpace(request.Header.Get("Last-Event-ID")); header != "" {
		return parseSeq(header, "Last-Event-ID")
	}
	if query := strings.TrimSpace(request.URL.Query().Get("from-seq")); query != "" {
		return parseSeq(query, "from-seq")
	}
	return CursorAll, nil
}

// parseSeq parses a non-negative integer sequence from a header/query value, naming the source in a
// typed RequestError on a malformed value.
func parseSeq(value, source string) (uint64, error) {
	seq, err := strconv.ParseUint(value, 10, 64)
	if err != nil {
		return 0, errors.Wrap(errors.KindInvalid, "edenhttp: resolve cursor",
			RequestError{Reason: source + " must be a non-negative integer sequence"})
	}
	return seq, nil
}

// SSEFrame is one Server-Sent Event the SSEStream writes: the per-type Event token (the EventSource
// `event:` field, so a UI dispatches per kind without parsing the body), the monotonic ID (the
// `id:` field — the cursor the browser echoes as Last-Event-ID on reconnect), and the JSON Data
// payload (the `data:` field). Data is pre-marshaled bytes the consumer supplies (its redaction-safe
// projection); the stream frames it verbatim.
type SSEFrame struct {
	// ID is the SSE event id (the resume cursor); for the gateway bridge this is the event Seq.
	ID uint64
	// Event is the SSE event type token (e.g. the agentsession EventKind), enabling per-type dispatch.
	Event string
	// Data is the pre-marshaled JSON payload written on the `data:` line(s).
	Data []byte
}

// SSEStream is the writer half of the NATS→SSE bridge: it owns the buffered write side of an
// http.ResponseWriter, frames each SSEFrame, flushes promptly, and emits keepalive heartbeat
// comments so a proxy never idles the long-lived stream. It is NOT safe for concurrent Send (one
// stream, one writing goroutine — the bridge's pump loop); that is the SSE contract (a single
// ordered byte stream per connection). Construct via NewSSEStream; it requires a flushable writer.
type SSEStream struct {
	writer  *bufio.Writer
	flusher http.Flusher
}

// NewSSEStream sets the text/event-stream response headers, commits the 200 + headers (so the
// client's EventSource opens immediately), and returns a stream bound to writer. It fails with a
// KindInternal error if writer is not an http.Flusher (SSE is impossible without flushing). The
// caller writes frames with Send and keepalives with Heartbeat, then lets the request context bound
// the stream's life; there is no Close (the http.Server owns the connection teardown).
func NewSSEStream(writer http.ResponseWriter) (*SSEStream, error) {
	flusher, ok := writer.(http.Flusher)
	if !ok {
		return nil, errors.New(errors.KindInternal, "edenhttp: response writer does not support streaming (no http.Flusher)")
	}
	writeSSEHeaders(writer)
	writer.WriteHeader(http.StatusOK)
	flusher.Flush() // commit the 200 + headers so EventSource transitions to open before the first frame
	return &SSEStream{writer: bufio.NewWriter(writer), flusher: flusher}, nil
}

// Send writes one frame as a single SSE event (`event:`, `id:`, `data:`, blank-line terminator) and
// flushes it to the client. A write fault (the client connection dropped mid-write) is returned as a
// wrapped KindUnavailable error so the bridge stops pumping and reaps; the request context reports the
// disconnect on the next read regardless. The id is the resume cursor the browser echoes on reconnect.
func (s *SSEStream) Send(frame SSEFrame) error {
	if err := s.writeLine("event: ", frame.Event); err != nil {
		return err
	}
	if err := s.writeLine("id: ", strconv.FormatUint(frame.ID, 10)); err != nil {
		return err
	}
	if _, err := s.writer.WriteString("data: "); err != nil {
		return errors.Wrap(errors.KindUnavailable, "edenhttp: write sse data prefix", err)
	}
	if _, err := s.writer.Write(frame.Data); err != nil {
		return errors.Wrap(errors.KindUnavailable, "edenhttp: write sse data", err)
	}
	if _, err := s.writer.WriteString("\n\n"); err != nil {
		return errors.Wrap(errors.KindUnavailable, "edenhttp: write sse frame end", err)
	}
	return s.flush()
}

// Heartbeat writes one SSE comment line (": keepalive") and flushes it. A standard EventSource
// ignores a comment as a no-op, so it neither delivers data nor advances the cursor — it only keeps
// the connection (and any intermediary proxy) from idling out a quiet stream. A write fault is a
// wrapped KindUnavailable (the client is gone).
func (s *SSEStream) Heartbeat() error {
	if _, err := s.writer.WriteString(": keepalive\n\n"); err != nil {
		return errors.Wrap(errors.KindUnavailable, "edenhttp: write sse heartbeat", err)
	}
	return s.flush()
}

// Comment writes one operator-visible SSE comment carrying a stable kind token, used to report a
// stream fault AFTER the 200 is committed (the status can no longer change). It is a comment line so
// a standard EventSource ignores it; the UI recovers via Last-Event-ID. It carries the Kind token
// ONLY, never a cause chain or a credential. Best-effort: the connection may already be gone.
func (s *SSEStream) Comment(kind errors.Kind) {
	//nolint:errcheck // best-effort trailing comment on a possibly-gone connection; nothing to act on.
	_, _ = s.writer.WriteString(": error kind=" + kind.String() + "\n\n")
	//nolint:errcheck // best-effort flush of a trailing comment.
	_ = s.writer.Flush()
	s.flusher.Flush()
}

// writeLine writes a "<prefix><value>\n" SSE line, wrapping a write fault as KindUnavailable.
func (s *SSEStream) writeLine(prefix, value string) error {
	if _, err := s.writer.WriteString(prefix + value + "\n"); err != nil {
		return errors.Wrap(errors.KindUnavailable, "edenhttp: write sse line", err)
	}
	return nil
}

// flush drains the buffered writer to the underlying ResponseWriter and flushes that to the client,
// so a frame reaches the browser promptly rather than sitting in a buffer.
func (s *SSEStream) flush() error {
	if err := s.writer.Flush(); err != nil {
		return errors.Wrap(errors.KindUnavailable, "edenhttp: flush sse buffer", err)
	}
	s.flusher.Flush()
	return nil
}

// writeSSEHeaders sets the text/event-stream headers. no-cache/no-transform + keep-alive stop a
// proxy from buffering or idling the long-lived stream; X-Accel-Buffering off disables nginx proxy
// buffering so frames reach the client promptly.
func writeSSEHeaders(writer http.ResponseWriter) {
	header := writer.Header()
	header.Set("Content-Type", "text/event-stream; charset=utf-8")
	header.Set("Cache-Control", "no-cache, no-transform")
	header.Set("Connection", "keep-alive")
	header.Set("X-Accel-Buffering", "no")
}
