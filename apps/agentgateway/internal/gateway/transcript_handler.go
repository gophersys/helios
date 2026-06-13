package gateway

import (
	"context"
	"net/http"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
)

// handleTranscript serves GET /sessions/{id}/transcript — the persisted Run's full ordered
// event list, queryable AFTER the session ends (REQ-0020 persisted Run; REQ-0023 a killed
// client reopening reconstructs full state from persisted events). It reads from the
// durable Transcript port by the canonical agentsession SessionID (discovered at create
// and retained past Close), so it works whether or not the live session is still in the
// registry. ?from-seq= bounds the read [from+1 .. head] (the same cursor mechanism); absent
// it, the whole Run is returned. When no Transcript is injected, it falls back to a live
// session's replay tail (live-only read).
func (g *Gateway) handleTranscript(w http.ResponseWriter, r *http.Request) {
	id := orchestrator.AgentID(r.PathValue("id"))

	from, err := transcriptCursor(r)
	if err != nil {
		g.writeError(w, err)
		return
	}

	events, err := g.readTranscript(r.Context(), id, from)
	if err != nil {
		g.writeError(w, err)
		return
	}

	views := make([]eventView, 0, len(events))
	var head uint64
	complete := false
	for i := range events {
		views = append(views, toEventView(events[i]))
		head = events[i].Seq
		if events[i].IsTerminal() {
			complete = true
		}
	}
	g.writeJSON(w, http.StatusOK, transcriptResponse{
		ID:       string(id),
		Events:   views,
		HeadSeq:  head,
		Complete: complete,
	})
}

// readTranscript reads the persisted Run for an AgentID from the durable Transcript port
// (post-Close-safe), or from a live session's replay tail when no Transcript is injected. A
// 404 is returned when neither the SessionID nor a live session is known.
func (g *Gateway) readTranscript(ctx context.Context, id orchestrator.AgentID, from agentsession.Cursor) ([]agentsession.Event, error) {
	if g.dependencies.Transcript != nil {
		sessionID, ok := g.registry.sessionID(id)
		if !ok {
			return nil, errors.Wrap(errors.KindNotFound, "gateway: transcript",
				RequestError{Reason: "no known session for id " + string(id)})
		}
		stream, err := g.dependencies.Transcript.ReadFrom(ctx, sessionID, from)
		if err != nil {
			return nil, errors.Wrap(errors.KindUnavailable, "gateway: read transcript", err)
		}
		return drainStream(ctx, stream)
	}

	// No durable Transcript injected: serve a live session's replay tail (replays the
	// transcript prefix then attaches live — bounded here to the persisted prefix by reading
	// only the events available without blocking past the head is not possible on the live
	// tail, so this fallback is for live, non-terminal reads only).
	session, ok := g.registry.lookup(id)
	if !ok {
		return nil, errors.Wrap(errors.KindNotFound, "gateway: transcript",
			RequestError{Reason: "no live session for id " + string(id)})
	}
	return drainToTerminal(ctx, session.Events(ctx, from))
}

// drainStream reads a one-shot replay Stream to its end (the durable transcript snapshot is
// finite: it ends when the persisted prefix is exhausted). A stream fault is wrapped on the
// errors seam.
func drainStream(ctx context.Context, stream agentsession.Stream) ([]agentsession.Event, error) {
	var events []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			break
		}
		events = append(events, event)
	}
	if err := stream.Err(); err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "gateway: drain transcript", err)
	}
	return events, nil
}

// drainToTerminal reads a live replay-then-tail Stream until the terminal event (or ctx).
// It is the fallback live read: it bounds the read at the terminal so it does not block
// forever on a still-running session.
func drainToTerminal(ctx context.Context, stream agentsession.Stream) ([]agentsession.Event, error) {
	var events []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			break
		}
		events = append(events, event)
		if event.IsTerminal() {
			break
		}
	}
	if err := stream.Err(); err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "gateway: drain transcript", err)
	}
	return events, nil
}

// transcriptCursor reads the optional ?from-seq= bound for a transcript read (the same
// cursor mechanism as the SSE route). Absent, it is FromSeq(0): the whole Run.
func transcriptCursor(r *http.Request) (agentsession.Cursor, error) {
	query := strings.TrimSpace(r.URL.Query().Get("from-seq"))
	if query == "" {
		return agentsession.FromSeq(0), nil
	}
	seq, err := strconv.ParseUint(query, 10, 64)
	if err != nil {
		return 0, errors.Wrap(errors.KindInvalid, "gateway: transcript cursor",
			RequestError{Reason: "from-seq must be a non-negative integer"})
	}
	return agentsession.FromSeq(seq), nil
}
