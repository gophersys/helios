//go:build integration

// Package natssse_test's integration arm proves the JetStream→SSE bridge end-to-end over a REAL
// NATS/JetStream — NEVER a mock of the NATS protocol. It runs against TWO real substrates:
//
//   - an EMBEDDED real nats-server/v2 with JetStream (started in-process, millisecond boot,
//     deterministic) — the primary arm, exercised on every integration run;
//   - a REAL `nats:2.14.2` container booted docker-out-of-docker — the cross-process wire arm,
//     SKIPPED if docker/the image is unavailable locally, REQUIRED in the devcontainer.
//
// Both arms drive the SAME assertions through the real natssse.Bridge: a publisher writes
// agentruntime.EventEnvelopes to agent.<id>.events with MsgId==Seq (the natsbus durability
// contract); the bridge replays them as SSE frames in Seq order (id == Seq); a RECONNECT from
// Last-Event-ID N resumes gap-free at N+1; the consumer + goroutine are reaped on disconnect.
//
//	go test -tags integration ./... -race
package natssse_test

import (
	"bufio"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os/exec"
	"strconv"
	"strings"
	"testing"
	"time"

	natsserver "github.com/nats-io/nats-server/v2/server"
	natsservertest "github.com/nats-io/nats-server/v2/test"
	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/natssse"
)

// agentID is the canonical agent the integration arms publish + bridge for.
const agentID agentruntime.AgentID = "agent-itest-1"

// itestClock is a fixed clock for the bridge's heartbeat scheduling (no heartbeat fires within these
// fast arms; the events arrive well under the cadence).
type itestClock struct{}

func (itestClock) Now() time.Time { return time.Date(2026, time.June, 14, 12, 0, 0, 0, time.UTC) }

// advancingClock returns a Now that jumps forward by a fixed step on every call, so a SHORT
// heartbeat interval elapses after the first quiet fetch — exercising the bridge's keepalive path on
// a quiet stream deterministically (no wall-clock sleep).
type advancingClock struct {
	now  atomicTime
	step time.Duration
}

func (c *advancingClock) Now() time.Time {
	previous := c.now.load()
	c.now.store(previous.Add(c.step))
	return previous
}

// atomicTime is a tiny mutex-free time holder safe for the single bridge goroutine's sequential
// Now() calls (the bridge calls Now serially within one Stream loop).
type atomicTime struct{ value time.Time }

func (a *atomicTime) load() time.Time   { return a.value }
func (a *atomicTime) store(t time.Time) { a.value = t }

// TestIntegration_EmbeddedNATS_ReplayBySeq is the primary real-substrate arm: a publisher writes a
// Seq-ordered EventEnvelope stream (the last one terminal) to a REAL embedded JetStream, and the
// bridge replays the WHOLE stream from the start (CursorAll) as SSE frames in Seq order, id == Seq.
func TestIntegration_EmbeddedNATS_ReplayBySeq(t *testing.T) {
	t.Parallel()
	url := startEmbeddedJetStreamServer(t)
	conn, jetStream := dialJetStream(t, url)
	t.Cleanup(conn.Close)
	ensureStream(t, jetStream)

	publishCanonicalStream(t, jetStream, 5) // seqs 1..5, the 5th terminal.

	frames := runBridgeToEnd(t, jetStream, edenhttp.CursorAll)
	assertSeqOrder(t, frames, 1, 5)
}

// TestIntegration_EmbeddedNATS_ReconnectResumesGapFree proves the reconnect contract: a client that
// last saw Seq 2 reconnects with Last-Event-ID=2, and the bridge replays EXACTLY seqs 3..5 (the
// missing events, in order, with no duplicate of 2) — the stateless-replica resume.
func TestIntegration_EmbeddedNATS_ReconnectResumesGapFree(t *testing.T) {
	t.Parallel()
	url := startEmbeddedJetStreamServer(t)
	conn, jetStream := dialJetStream(t, url)
	t.Cleanup(conn.Close)
	ensureStream(t, jetStream)

	publishCanonicalStream(t, jetStream, 5)

	// Reconnect from Last-Event-ID = 2: resume at 3, gap-free to the terminal 5.
	frames := runBridgeToEnd(t, jetStream, 2)
	assertSeqOrder(t, frames, 3, 5)
	for _, frame := range frames {
		if frame.seq == 2 {
			t.Fatalf("reconnect from Last-Event-ID=2 re-delivered seq 2 (a duplicate)")
		}
	}
}

// TestIntegration_EmbeddedNATS_HeartbeatOnQuietStream proves the bridge emits an SSE keepalive
// comment on a QUIET real stream: a non-terminal event is published, then the stream goes quiet, the
// fetch window times out, and the (advancing-clock) cadence elapses → a ": keepalive" comment is
// written before the terminal event finally arrives. The keepalive keeps a proxy from idling a slow
// agent's stream.
func TestIntegration_EmbeddedNATS_HeartbeatOnQuietStream(t *testing.T) {
	t.Parallel()
	url := startEmbeddedJetStreamServer(t)
	conn, jetStream := dialJetStream(t, url)
	t.Cleanup(conn.Close)
	ensureStream(t, jetStream)

	// Publish ONE non-terminal event up front; the terminal is published AFTER a quiet window below.
	publishOne(t, jetStream, 1, false)

	// An advancing clock with a tiny step makes the heartbeat cadence elapse after the first quiet
	// fetch (no wall-clock sleep), and a 1ms heartbeat interval guarantees a keepalive on the gap.
	clock := &advancingClock{now: atomicTime{value: time.Unix(0, 0)}, step: time.Second}
	bridge, err := natssse.New(
		natssse.Config{Stream: agentruntime.EventsStreamName, HeartbeatInterval: time.Millisecond},
		natssse.Deps{JetStream: jetStream, Clock: clock},
	)
	if err != nil {
		t.Fatalf("natssse.New: %v", err)
	}

	handler := http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		stream, streamErr := edenhttp.NewSSEStream(writer)
		if streamErr != nil {
			t.Errorf("server NewSSEStream: %v", streamErr)
			return
		}
		if bridgeErr := bridge.Stream(request.Context(), agentID, edenhttp.CursorAll, stream); bridgeErr != nil {
			t.Errorf("bridge.Stream: %v", bridgeErr)
		}
	})
	server := httptest.NewServer(handler)
	defer server.Close()

	// Publish the terminal event after a brief quiet window so the bridge passes through the
	// timeout/heartbeat path at least once before ending.
	go func() {
		time.Sleep(1500 * time.Millisecond)
		publishOne(t, jetStream, 2, true)
	}()

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, server.URL+"/sessions/"+string(agentID)+"/events", http.NoBody)
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	response, err := server.Client().Do(request)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	defer func() {
		if closeErr := response.Body.Close(); closeErr != nil {
			t.Errorf("close response body: %v", closeErr)
		}
	}()
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	if !strings.Contains(string(raw), ": keepalive") {
		t.Fatalf("no keepalive comment on the quiet stream:\n%s", raw)
	}
	if !strings.Contains(string(raw), "id: 2") {
		t.Fatalf("the terminal event (seq 2) did not arrive:\n%s", raw)
	}
}

// TestIntegration_EmbeddedNATS_ClientDisconnectReaps proves a client disconnect (closing the body
// mid-stream, before the terminal) ends the bridge cleanly and reaps the consumer — the goleak
// TestMain asserts no goroutine/subscription is leaked after the server closes.
func TestIntegration_EmbeddedNATS_ClientDisconnectReaps(t *testing.T) {
	t.Parallel()
	url := startEmbeddedJetStreamServer(t)
	conn, jetStream := dialJetStream(t, url)
	t.Cleanup(conn.Close)
	ensureStream(t, jetStream)

	// Publish two NON-terminal events: the stream never reaches a terminal, so only a client
	// disconnect ends the bridge.
	publishOne(t, jetStream, 1, false)
	publishOne(t, jetStream, 2, false)

	bridge, err := natssse.New(
		natssse.Config{Stream: agentruntime.EventsStreamName, HeartbeatInterval: time.Hour},
		natssse.Deps{JetStream: jetStream, Clock: itestClock{}},
	)
	if err != nil {
		t.Fatalf("natssse.New: %v", err)
	}
	handler := http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		stream, streamErr := edenhttp.NewSSEStream(writer)
		if streamErr != nil {
			t.Errorf("server NewSSEStream: %v", streamErr)
			return
		}
		// A non-terminal stream ends only when the client disconnects (ctx canceled); the bridge
		// returns nil and the deferred Unsubscribe reaps the consumer.
		_ = bridge.Stream(request.Context(), agentID, edenhttp.CursorAll, stream) //nolint:errcheck // a clean disconnect returns nil; the assertion is the reap (goleak).
	})
	server := httptest.NewServer(handler)
	defer server.Close()

	ctx, cancel := context.WithCancel(context.Background())
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, server.URL+"/sessions/"+string(agentID)+"/events", http.NoBody)
	if err != nil {
		cancel()
		t.Fatalf("build request: %v", err)
	}
	response, err := server.Client().Do(request)
	if err != nil {
		cancel()
		t.Fatalf("request: %v", err)
	}
	// Read the two events, then DISCONNECT (cancel the request + close the body) mid-stream.
	if seen := readIDLinesUntil(response.Body, 2); seen != 2 {
		t.Errorf("read %d id: lines before disconnect, want 2", seen)
	}
	cancel()
	if closeErr := response.Body.Close(); closeErr != nil {
		t.Errorf("close response body: %v", closeErr)
	}
	// Give the server handler a moment to observe the canceled context and reap before the server
	// Close (the goleak TestMain is the leak assertion).
	time.Sleep(200 * time.Millisecond)
}

// readIDLinesUntil reads SSE lines until it has seen want "id:" lines (or the stream ends), returning
// the count; used by the disconnect arm to consume events before disconnecting.
func readIDLinesUntil(body io.Reader, want int) int {
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

// publishOne publishes a single EventEnvelope at seq (terminal when terminal is true), MsgId==seq.
func publishOne(t *testing.T, jetStream nats.JetStreamContext, seq uint64, terminal bool) {
	t.Helper()
	kind := agentsession.EventTextDelta
	if terminal {
		kind = agentsession.EventResult
	}
	envelope := agentruntime.EventEnvelope{
		AgentID:  agentID,
		Seq:      seq,
		Event:    agentsession.Event{SessionID: string(agentID), Seq: seq, Kind: kind},
		OTel:     agentruntime.OTelContext{"traceparent": "00-itest-trace-01"},
		EmitTime: time.Now(),
	}
	payload, err := json.Marshal(envelope)
	if err != nil {
		t.Fatalf("marshal envelope %d: %v", seq, err)
	}
	if _, err := jetStream.Publish(agentruntime.EventsSubject(agentID), payload, nats.MsgId(strconv.FormatUint(seq, 10))); err != nil {
		t.Fatalf("publish envelope %d: %v", seq, err)
	}
}

// TestIntegration_RealNATSContainer_ReplayBySeq is the cross-process arm: a REAL nats:2.14.2
// container booted docker-out-of-docker. SKIPPED if docker/the image is unavailable locally.
func TestIntegration_RealNATSContainer_ReplayBySeq(t *testing.T) {
	t.Parallel()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker CLI not on PATH: the real-container arm is skipped (the embedded arm still proves real NATS)")
	}
	url := startNATSContainer(t)
	conn, jetStream := dialJetStream(t, url)
	t.Cleanup(conn.Close)
	ensureStream(t, jetStream)

	publishCanonicalStream(t, jetStream, 4)
	frames := runBridgeToEnd(t, jetStream, edenhttp.CursorAll)
	assertSeqOrder(t, frames, 1, 4)
}

// ── bridge driver ─────────────────────────────────────────────────────────────.

// sseEvent is one parsed SSE event the client reader extracts (the id and event token).
type sseEvent struct {
	seq   uint64
	event string
}

// runBridgeToEnd serves ONE SSE request through a real httptest.Server whose handler runs the real
// natssse.Bridge against jetStream, then reads the SSE frames the client receives until the stream
// closes (the bridge ends on the terminal event). It asserts no goroutine is leaked after the server
// closes (the consumer + bridge goroutine are reaped on the terminal).
func runBridgeToEnd(t *testing.T, jetStream nats.JetStreamContext, lastSeq uint64) []sseEvent {
	t.Helper()
	bridge, err := natssse.New(
		natssse.Config{Stream: agentruntime.EventsStreamName, HeartbeatInterval: time.Hour},
		natssse.Deps{JetStream: jetStream, Clock: itestClock{}},
	)
	if err != nil {
		t.Fatalf("natssse.New: %v", err)
	}

	handler := http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		stream, streamErr := edenhttp.NewSSEStream(writer)
		if streamErr != nil {
			t.Errorf("server NewSSEStream: %v", streamErr)
			return
		}
		if bridgeErr := bridge.Stream(request.Context(), agentID, lastSeq, stream); bridgeErr != nil {
			t.Errorf("bridge.Stream: %v", bridgeErr)
		}
	})

	server := httptest.NewServer(handler)
	defer server.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, server.URL+"/sessions/"+string(agentID)+"/events", http.NoBody)
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	response, err := server.Client().Do(request)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	defer func() {
		if closeErr := response.Body.Close(); closeErr != nil {
			t.Errorf("close response body: %v", closeErr)
		}
	}()
	if got := response.Header.Get("Content-Type"); !strings.HasPrefix(got, "text/event-stream") {
		t.Fatalf("Content-Type = %q, want text/event-stream", got)
	}
	return readSSE(t, response.Body)
}

// readSSE parses the SSE byte stream into events, reading id:/event: lines until the stream closes
// (the bridge closes it on the terminal event, so the read returns cleanly).
func readSSE(t *testing.T, body interface{ Read([]byte) (int, error) }) []sseEvent {
	t.Helper()
	scanner := bufio.NewScanner(bufio.NewReader(body))
	var events []sseEvent
	var current sseEvent
	for scanner.Scan() {
		line := scanner.Text()
		switch {
		case strings.HasPrefix(line, "event: "):
			current.event = strings.TrimPrefix(line, "event: ")
		case strings.HasPrefix(line, "id: "):
			seq, err := strconv.ParseUint(strings.TrimPrefix(line, "id: "), 10, 64)
			if err != nil {
				t.Fatalf("bad id line %q: %v", line, err)
			}
			current.seq = seq
		case line == "": // frame terminator.
			if current.seq != 0 || current.event != "" {
				events = append(events, current)
				current = sseEvent{}
			}
		}
	}
	return events
}

// assertSeqOrder asserts the SSE events carry exactly the contiguous seqs [from..to] in order.
func assertSeqOrder(t *testing.T, events []sseEvent, from, to uint64) {
	t.Helper()
	want := to - from + 1
	if uint64(len(events)) != want {
		t.Fatalf("got %d SSE events, want %d (seqs %d..%d): %+v", len(events), want, from, to, events)
	}
	expected := from
	for _, event := range events {
		if event.seq != expected {
			t.Fatalf("SSE stream not gap-free/ordered: got seq %d want %d (events=%+v)", event.seq, expected, events)
		}
		expected++
	}
}

// ── the publisher (the agentruntime sidecar's role) ───────────────────────────.

// publishCanonicalStream publishes count EventEnvelopes to agent.<id>.events with MsgId==Seq (the
// natsbus durability contract), the last one a terminal Result so the bridge ends cleanly.
func publishCanonicalStream(t *testing.T, jetStream nats.JetStreamContext, count uint64) {
	t.Helper()
	subject := agentruntime.EventsSubject(agentID)
	for seq := uint64(1); seq <= count; seq++ {
		kind := agentsession.EventTextDelta
		if seq == count {
			kind = agentsession.EventResult // the single terminal event.
		}
		envelope := agentruntime.EventEnvelope{
			AgentID:  agentID,
			Seq:      seq,
			Event:    agentsession.Event{SessionID: string(agentID), Seq: seq, Kind: kind},
			OTel:     agentruntime.OTelContext{"traceparent": "00-itest-trace-01"},
			EmitTime: time.Now(),
		}
		payload, err := json.Marshal(envelope)
		if err != nil {
			t.Fatalf("marshal envelope %d: %v", seq, err)
		}
		if _, err := jetStream.Publish(subject, payload, nats.MsgId(strconv.FormatUint(seq, 10))); err != nil {
			t.Fatalf("publish envelope %d: %v", seq, err)
		}
	}
}

// ── real-substrate fixtures (mirrors the natsbus integration harness) ──────────.

func ensureStream(t *testing.T, jetStream nats.JetStreamContext) {
	t.Helper()
	_, err := jetStream.AddStream(&nats.StreamConfig{
		Name:     agentruntime.EventsStreamName,
		Subjects: []string{"agent.*.events"},
		Storage:  nats.FileStorage,
	})
	if err != nil {
		t.Fatalf("add stream: %v", err)
	}
}

func startEmbeddedJetStreamServer(t *testing.T) string {
	t.Helper()
	options := &natsserver.Options{
		Host:      "127.0.0.1",
		Port:      -1,
		JetStream: true,
		StoreDir:  t.TempDir(),
		NoLog:     true,
		NoSigs:    true,
	}
	server := natsservertest.RunServer(options)
	t.Cleanup(server.Shutdown)
	if !server.ReadyForConnections(10 * time.Second) {
		t.Fatal("embedded nats-server not ready within 10s")
	}
	return server.ClientURL()
}

//nolint:ireturn // nats.JetStreamContext is the vendor SDK's own interface type; the helper returns it as the SDK vends it.
func dialJetStream(t *testing.T, url string) (*nats.Conn, nats.JetStreamContext) {
	t.Helper()
	conn, err := nats.Connect(url, nats.Timeout(5*time.Second))
	if err != nil {
		t.Fatalf("dial nats at %s: %v", url, err)
	}
	jetStream, err := conn.JetStream()
	if err != nil {
		conn.Close()
		t.Fatalf("jetstream context: %v", err)
	}
	return conn, jetStream
}

func startNATSContainer(t *testing.T) string {
	t.Helper()
	name := "eden-edenhttp-nats-" + strconv.FormatInt(time.Now().UnixNano(), 36)
	// #nosec G204 -- fixed `docker run` of the official nats image; name is time-derived, not user input.
	run := exec.Command("docker", "run", "-d", "--rm", "--name", name, "nats:2.14.2", "-js")
	if out, err := run.CombinedOutput(); err != nil {
		t.Skipf("could not start nats container (image unavailable?): %v\n%s", err, out)
	}
	t.Cleanup(func() {
		// #nosec G204 -- fixed `docker rm -f` of the just-created container by its time-derived name.
		_ = exec.Command("docker", "rm", "-f", name).Run() //nolint:errcheck // best-effort reap.
	})
	ip := dockerBridgeIP(t, name)
	url := "nats://" + ip + ":4222"
	waitForServer(t, url)
	return url
}

func dockerBridgeIP(t *testing.T, name string) string {
	t.Helper()
	// #nosec G204 -- fixed `docker inspect` of the just-created container by its time-derived name.
	out, err := exec.Command("docker", "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name).CombinedOutput()
	if err != nil {
		t.Fatalf("docker inspect: %v\n%s", err, out)
	}
	ip := strings.TrimSpace(string(out))
	if ip == "" {
		t.Fatalf("docker inspect returned an empty bridge IP for %s", name)
	}
	return ip
}

func waitForServer(t *testing.T, url string) {
	t.Helper()
	deadline := time.After(20 * time.Second)
	for {
		conn, err := nats.Connect(url, nats.Timeout(1*time.Second))
		if err == nil {
			conn.Close()
			return
		}
		select {
		case <-deadline:
			t.Fatalf("nats container at %s never became ready: %v", url, err)
		case <-time.After(200 * time.Millisecond):
		}
	}
}
