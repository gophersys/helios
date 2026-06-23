package gateway

import (
	"bufio"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
)

// handleEvents is the SSE stream (REQ-0023/0024). It serves GET /sessions/{id}/events as
// text/event-stream over a SINGLE live agentsession.Session resolved from the registry —
// PER-SESSION fan-out: subscribing to one session's stream delivers ONLY that session's
// events, never another's, because each request opens its own agentsession.Stream off the
// one session keyed by {id} (REQ-0022 per-session fan-out).
//
// Replay: the cursor is read from the Last-Event-ID header (the SSE reconnect standard) OR
// the ?from-seq= query — the SAME mechanism. agentsession.FromSeq(n) replays the durable
// transcript [n+1 .. head] then attaches to the live tail with no gap and no dup
// (REQ-0023 exactly the missing events, in order). FromSeq(0) replays the whole session —
// a client killed mid-session and reopened reconstructs full state from persisted events.
//
// Each Event becomes one SSE frame: `event: <kind>` (the taxonomy token, so the UI
// dispatches per type — REQ-0024), `id: <seq>` (the monotonic cursor the browser echoes on
// reconnect — REQ-0023), `data: <json>` (the redaction-safe projection). The terminal
// event ends the stream cleanly. The response flushes after every frame so deltas reach the
// client within ~1s (REQ-0020).
func (g *Gateway) handleEvents(w http.ResponseWriter, r *http.Request) {
	id := orchestrator.AgentID(r.PathValue("id"))

	flusher, ok := w.(http.Flusher)
	if !ok {
		g.writeError(w, errors.New(errors.KindInternal, "gateway: streaming unsupported by response writer"))
		return
	}

	cursor, err := resolveCursor(r)
	if err != nil {
		g.writeError(w, err)
		return
	}

	session, ok := g.resolveSession(id)
	if !ok {
		g.writeError(w, errors.Wrap(errors.KindNotFound, "gateway: events",
			RequestError{Reason: "no live session for id " + string(id)}))
		return
	}

	g.writeSSEHeaders(w)
	flusher.Flush() // commit the 200 + headers so the client's EventSource opens immediately

	// One Stream per request == per-cursor, per-client fan-out off this one session. The
	// request context bounds it: a client disconnect cancels ctx, which drops THIS
	// subscriber only (it neither stalls other viewers nor the agent).
	stream := session.Events(r.Context(), cursor)
	writer := bufio.NewWriter(w)

	g.pumpSSE(r, writer, flusher, stream, string(id))
}

// pumpSSE drains the stream to terminal/disconnect, writing one SSE frame per event and
// flushing promptly. It ends cleanly on the terminal event, on client disconnect (ctx
// canceled), or on a stream fault (surfaced as a final SSE error comment, since the 200 is
// already committed and we cannot change the status code).
func (g *Gateway) pumpSSE(
	r *http.Request,
	writer *bufio.Writer,
	flusher http.Flusher,
	stream agentsession.Stream,
	agentID string,
) {
	ctx := r.Context()
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			break
		}
		if err := writeSSEEvent(writer, event); err != nil {
			// The client connection dropped mid-write; ctx will report it on the next Next.
			g.logInfo("gateway: sse write dropped", "agent", agentID, "seq", event.Seq)
			return
		}
		if err := writer.Flush(); err != nil {
			return
		}
		flusher.Flush()
		if event.IsTerminal() {
			return // clean end-of-stream on the single terminal event (REQ-0023)
		}
	}
	// The stream ended without a terminal event: either the client disconnected (ctx) or
	// the stream faulted. A fault is reported as a trailing SSE error comment.
	if streamErr := stream.Err(); streamErr != nil && ctx.Err() == nil {
		writeSSEError(writer, streamErr)
		_ = writer.Flush() //nolint:errcheck // best-effort trailing error; the connection may already be gone.
		flusher.Flush()
		g.logError("gateway: sse stream faulted", "agent", agentID, "kind", errors.KindOf(streamErr).String())
	}
}

// resolveCursor reads the resume cursor from the Last-Event-ID header (the SSE reconnect
// standard) OR the ?from-seq= query — the same replay mechanism. The header wins when both
// are present (a reconnecting EventSource always sends Last-Event-ID). Absent both, the
// cursor is FromSeq(0): full replay-from-start then live tail (a fresh client gets the
// whole session, reconstructing state from persisted events — REQ-0023). A malformed value
// is a typed RequestError (KindInvalid → 400).
func resolveCursor(r *http.Request) (agentsession.Cursor, error) {
	if header := strings.TrimSpace(r.Header.Get("Last-Event-ID")); header != "" {
		seq, err := strconv.ParseUint(header, 10, 64)
		if err != nil {
			return 0, errors.Wrap(errors.KindInvalid, "gateway: resolve cursor",
				RequestError{Reason: "Last-Event-ID must be a non-negative integer seq"})
		}
		return agentsession.FromSeq(seq), nil
	}
	if query := strings.TrimSpace(r.URL.Query().Get("from-seq")); query != "" {
		seq, err := strconv.ParseUint(query, 10, 64)
		if err != nil {
			return 0, errors.Wrap(errors.KindInvalid, "gateway: resolve cursor",
				RequestError{Reason: "from-seq must be a non-negative integer"})
		}
		return agentsession.FromSeq(seq), nil
	}
	return agentsession.FromSeq(0), nil
}

// writeSSEHeaders sets the text/event-stream headers. No-cache + keep-alive keep proxies
// from buffering or idling the long-lived stream; X-Accel-Buffering off disables nginx
// proxy buffering so frames reach the client promptly (REQ-0020 ~1s).
func (g *Gateway) writeSSEHeaders(w http.ResponseWriter) {
	header := w.Header()
	header.Set("Content-Type", "text/event-stream; charset=utf-8")
	header.Set("Cache-Control", "no-cache, no-transform")
	header.Set("Connection", "keep-alive")
	header.Set("X-Accel-Buffering", "no")
	w.WriteHeader(http.StatusOK)
}

// writeSSEEvent renders one agentsession.Event as a single SSE frame. The frame carries the
// kind token on `event:` (per-type dispatch — REQ-0024), the monotonic Seq on `id:` (the
// reconnect cursor — REQ-0023), and the redaction-safe JSON projection on `data:`. The
// trailing blank line terminates the frame.
//
//nolint:gocritic // Event is the contract's copyable value record; the writer reads it by value.
func writeSSEEvent(writer *bufio.Writer, event agentsession.Event) error {
	payload, err := json.Marshal(toEventView(event))
	if err != nil {
		return errors.Wrap(errors.KindInternal, "gateway: encode sse event", err)
	}
	if _, err := writer.WriteString("event: " + event.Kind.String() + "\n"); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: write sse event line", err)
	}
	if _, err := writer.WriteString("id: " + strconv.FormatUint(event.Seq, 10) + "\n"); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: write sse id line", err)
	}
	if _, err := writer.WriteString("data: "); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: write sse data prefix", err)
	}
	if _, err := writer.Write(payload); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: write sse data", err)
	}
	if _, err := writer.WriteString("\n\n"); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: write sse frame end", err)
	}
	return nil
}

// writeSSEError emits a trailing SSE comment carrying the stable Kind token when a stream
// faults after the 200 is committed (we cannot change the status code mid-stream). It is a
// comment line (`: ...`) so a standard EventSource ignores it as a no-op rather than
// misparsing it as data — the UI's reconnect logic recovers via Last-Event-ID. It carries
// the Kind token only, never the cause chain or a credential.
func writeSSEError(writer *bufio.Writer, err error) {
	_, _ = writer.WriteString(": error kind=" + errors.KindOf(err).String() + "\n\n") //nolint:errcheck // best-effort trailing comment on a possibly-gone connection.
}
