//go:build lifecycle

package edenhttp_test

import (
	"bufio"
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/edenhttptest"
)

// TestLifecycle_AuthedRequestServerReaped drives a FULL authenticated request through a real
// httptest.Server (a real net/http listener + its connection goroutines) behind the spine
// Middleware, then closes the server and asserts no goroutine is leaked — the construct→use→teardown
// lifecycle (ADR-0020 dimension (c)) for the spine on a real HTTP transport.
//
//nolint:paralleltest // goleak.VerifyNone snapshots the goroutine set; a parallel test would race the snapshot.
func TestLifecycle_AuthedRequestServerReaped(t *testing.T) {
	defer goleak.VerifyNone(t, goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"))

	spine, err := edenhttp.New(
		edenhttp.Config{},
		edenhttp.Deps{Verifier: edenhttptest.NewVerifier(), Clock: edenhttptest.FixedClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	handler := spine.MiddlewareFunc(func(writer http.ResponseWriter, _ *http.Request) {
		edenhttp.WriteData(writer, http.StatusOK, map[string]string{"ok": "yes"})
	})

	server := httptest.NewServer(handler)
	defer server.Close()

	request, err := http.NewRequestWithContext(context.Background(), http.MethodGet, server.URL+"/probe", http.NoBody)
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	request.Header.Set("Authorization", "Bearer "+edenhttptest.MintToken("sessions:read"))
	response, err := server.Client().Do(request)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	if response.StatusCode != http.StatusOK {
		t.Errorf("status = %d, want 200", response.StatusCode)
	}
	if err := response.Body.Close(); err != nil {
		t.Errorf("close body: %v", err)
	}
}

// TestLifecycle_SSEStreamFramesAndReaps drives an SSE handler over a real httptest.Server: it sends
// frames + a heartbeat, the client reads them, then the client disconnects (closes the body) and the
// server is closed — asserting the streaming goroutine is reaped (no leak). This is the SSEStream's
// construct→stream→client-disconnect→teardown lifecycle on a real transport.
//
//nolint:paralleltest // goleak.VerifyNone snapshots the goroutine set; a parallel test would race the snapshot.
func TestLifecycle_SSEStreamFramesAndReaps(t *testing.T) {
	defer goleak.VerifyNone(t, goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"))

	spine, err := edenhttp.New(
		edenhttp.Config{},
		edenhttp.Deps{Verifier: edenhttptest.NewVerifier(), Clock: edenhttptest.FixedClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	server := httptest.NewServer(spine.MiddlewareFunc(streamThreeFrames(t)))
	defer server.Close()

	request, err := http.NewRequestWithContext(context.Background(), http.MethodGet, server.URL+"/sessions/x/events", http.NoBody)
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	request.Header.Set("Authorization", "Bearer "+edenhttptest.MintToken("sessions:read"))
	response, err := server.Client().Do(request)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	if got := response.Header.Get("Content-Type"); !strings.HasPrefix(got, "text/event-stream") {
		t.Errorf("Content-Type = %q, want text/event-stream", got)
	}

	// Read the three frames, then disconnect (close the body) — the server's handler observes the
	// canceled request context and returns, reaping its goroutine.
	if seen := readIDLines(response.Body, 3); seen != 3 {
		t.Errorf("read %d id: lines, want 3", seen)
	}
	if err := response.Body.Close(); err != nil {
		t.Errorf("close body: %v", err)
	}
}

// streamThreeFrames returns an SSE handler that sends three frames + a heartbeat, then blocks on the
// request context so a client disconnect ends it (the goroutine the lifecycle test asserts is reaped).
func streamThreeFrames(t *testing.T) http.HandlerFunc {
	t.Helper()
	return func(writer http.ResponseWriter, request *http.Request) {
		stream, streamErr := edenhttp.NewSSEStream(writer)
		if streamErr != nil {
			t.Errorf("server NewSSEStream: %v", streamErr)
			return
		}
		for seq := uint64(1); seq <= 3; seq++ {
			if request.Context().Err() != nil {
				return
			}
			if sendErr := stream.Send(edenhttp.SSEFrame{ID: seq, Event: "text-delta", Data: []byte(`{"d":"x"}`)}); sendErr != nil {
				return
			}
		}
		_ = stream.Heartbeat() //nolint:errcheck // best-effort keepalive; a client disconnect ends the handler regardless.
		<-request.Context().Done()
	}
}

// readIDLines reads SSE lines until it has seen want "id:" lines (or the stream ends), returning the
// count seen. It is the client-side reader the lifecycle test uses to consume frames before disconnect.
func readIDLines(body io.Reader, want int) int {
	scanner := bufio.NewScanner(body)
	seen := 0
	for scanner.Scan() {
		if strings.HasPrefix(scanner.Text(), "id: ") {
			seen++
			if seen == want {
				return seen
			}
		}
	}
	return seen
}
