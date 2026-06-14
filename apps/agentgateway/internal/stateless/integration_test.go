//go:build integration

// Package stateless_test's integration arm proves the STATELESS gateway end-to-end over a REAL
// NATS/JetStream — NEVER a mock. It boots an embedded real nats-server with JetStream, wires the
// REAL stateless.Gateway (the edenhttp dev-JWT spine + the natssse JetStream→SSE bridge + the
// natscontrol publisher) over httptest, and asserts:
//
//   - a publisher writes agentruntime.EventEnvelopes to agent.<id>.events → GET /sessions/{id}/events
//     streams them as SSE in Seq order (id == Seq) for a caller with a valid JWT carrying sessions:read;
//
//   - a RECONNECT with Last-Event-ID=N resumes gap-free at N+1;
//
//   - POST /sessions/{id}/control publishes a real agentruntime.ControlMessage to agent.<id>.control
//     (a subscriber receives it) for a caller with sessions:control;
//
//   - an UNAUTHENTICATED request (no/forged JWT) is 401 and never reaches the bridge/publisher;
//
//   - an UNDER-GRANTED caller (sessions:read only) is 403 on the control route.
//
//     go test -tags integration ./... -race
package stateless_test

import (
	"bufio"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
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

	"github.com/gophersys/eden/apps/agentgateway/internal/natscontrol"
	"github.com/gophersys/eden/apps/agentgateway/internal/stateless"
)

const agentID agentruntime.AgentID = "agent-gw-itest-1"

const streamName = "EDEN_AGENT_EVENTS"

//nolint:gosec // a fixed TEST HMAC secret, not a real credential.
const jwtSecret = "agentgateway-itest-signing-key"

// systemClock is the real clock the gateway uses in the integration arm.
type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// TestIntegration_EventsBridge_StreamsBySeqWithJWT proves the authed SSE bridge: a valid JWT carrying
// sessions:read streams the published EventEnvelopes as SSE in Seq order (id == Seq).
func TestIntegration_EventsBridge_StreamsBySeqWithJWT(t *testing.T) {
	t.Parallel()
	harness := newHarness(t)
	harness.publishStream(t, 4) // seqs 1..4, the 4th terminal.

	token := harness.mint(t, "sessions:read")
	events := harness.streamEvents(t, edenhttp.CursorAll, token)
	assertSeqOrder(t, events, 1, 4)
}

// TestIntegration_EventsBridge_ReconnectResumesGapFree proves a reconnect with Last-Event-ID=2
// resumes exactly seqs 3..4 (gap-free, no dup of 2) over the real gateway.
func TestIntegration_EventsBridge_ReconnectResumesGapFree(t *testing.T) {
	t.Parallel()
	harness := newHarness(t)
	harness.publishStream(t, 4)

	token := harness.mint(t, "sessions:read")
	events := harness.streamEventsLastEventID(t, "2", token)
	assertSeqOrder(t, events, 3, 4)
	for _, event := range events {
		if event.seq == 2 {
			t.Fatalf("reconnect re-delivered seq 2 (a duplicate)")
		}
	}
}

// TestIntegration_Events_Unauthenticated401 proves an unauthenticated request is 401 and never opens
// the SSE stream (no text/event-stream Content-Type).
func TestIntegration_Events_Unauthenticated401(t *testing.T) {
	t.Parallel()
	harness := newHarness(t)
	response := harness.do(t, http.MethodGet, "/sessions/"+string(agentID)+"/events", "", "")
	defer closeBody(t, response)
	if response.StatusCode != http.StatusUnauthorized {
		t.Fatalf("unauthenticated events: status = %d, want 401", response.StatusCode)
	}
	if strings.HasPrefix(response.Header.Get("Content-Type"), "text/event-stream") {
		t.Fatal("the SSE stream opened for an unauthenticated request")
	}
}

// TestIntegration_Control_PublishesMessage proves POST /control with a valid sessions:control JWT
// publishes a REAL agentruntime.ControlMessage to agent.<id>.control (a subscriber receives it).
func TestIntegration_Control_PublishesMessage(t *testing.T) {
	t.Parallel()
	harness := newHarness(t)

	// Subscribe to the control subject BEFORE the POST so the published verb is not missed.
	subscription, err := harness.conn.SubscribeSync(agentruntime.ControlSubject(agentID))
	if err != nil {
		t.Fatalf("subscribe control: %v", err)
	}
	t.Cleanup(func() { _ = subscription.Unsubscribe() }) //nolint:errcheck // best-effort reap.
	_ = harness.conn.Flush()                             //nolint:errcheck // ensure the interest propagates before the POST.

	token := harness.mint(t, "sessions:control")
	response := harness.do(t, http.MethodPost, "/sessions/"+string(agentID)+"/control", `{"verb":"prompt","text":"go"}`, token)
	defer closeBody(t, response)
	if response.StatusCode != http.StatusOK {
		body, readErr := io.ReadAll(response.Body)
		if readErr != nil {
			t.Logf("read body: %v", readErr)
		}
		t.Fatalf("control: status = %d, want 200; body=%s", response.StatusCode, body)
	}

	message, err := subscription.NextMsg(5 * time.Second)
	if err != nil {
		t.Fatalf("no control message arrived on %s: %v", agentruntime.ControlSubject(agentID), err)
	}
	var control agentruntime.ControlMessage
	if decodeErr := json.Unmarshal(message.Data, &control); decodeErr != nil {
		t.Fatalf("decode control message: %v", decodeErr)
	}
	if control.AgentID != agentID || control.Verb != agentruntime.VerbPrompt || control.Text != "go" {
		t.Errorf("control message = %+v, want {agent=%s verb=prompt text=go}", control, agentID)
	}
	if control.By == "" {
		t.Error("control message has no audit By (the authenticated subject)")
	}
}

// TestIntegration_Control_UnderGranted403 proves a caller with ONLY sessions:read is 403 on the
// control route (the authorize stage denies it; nothing is published).
func TestIntegration_Control_UnderGranted403(t *testing.T) {
	t.Parallel()
	harness := newHarness(t)
	token := harness.mint(t, "sessions:read") // NOT sessions:control.
	response := harness.do(t, http.MethodPost, "/sessions/"+string(agentID)+"/control", `{"verb":"abort"}`, token)
	defer closeBody(t, response)
	if response.StatusCode != http.StatusForbidden {
		t.Fatalf("under-granted control: status = %d, want 403", response.StatusCode)
	}
}

// TestIntegration_VerbRoute_Stop proves the convenience verb route POST /sessions/{id}/stop publishes
// a stop ControlMessage (an empty body is tolerated — abort/stop/kill carry no text).
func TestIntegration_VerbRoute_Stop(t *testing.T) {
	t.Parallel()
	harness := newHarness(t)
	subscription, err := harness.conn.SubscribeSync(agentruntime.ControlSubject(agentID))
	if err != nil {
		t.Fatalf("subscribe control: %v", err)
	}
	t.Cleanup(func() { _ = subscription.Unsubscribe() }) //nolint:errcheck // best-effort reap.
	_ = harness.conn.Flush()                             //nolint:errcheck // propagate interest.

	token := harness.mint(t, "sessions:control")
	response := harness.do(t, http.MethodPost, "/sessions/"+string(agentID)+"/stop", "", token)
	defer closeBody(t, response)
	if response.StatusCode != http.StatusOK {
		t.Fatalf("stop: status = %d, want 200", response.StatusCode)
	}
	message, err := subscription.NextMsg(5 * time.Second)
	if err != nil {
		t.Fatalf("no stop control message: %v", err)
	}
	var control agentruntime.ControlMessage
	if decodeErr := json.Unmarshal(message.Data, &control); decodeErr != nil {
		t.Fatalf("decode: %v", decodeErr)
	}
	if control.Verb != agentruntime.VerbStop {
		t.Errorf("verb = %s, want stop", control.Verb)
	}
}

// ── the harness ───────────────────────────────────────────────────────────────.

type harness struct {
	server    *httptest.Server
	conn      *nats.Conn
	jetStream nats.JetStreamContext
	verifier  *edenhttp.HMACVerifier
}

// newHarness boots an embedded real nats-server + JetStream, wires the REAL stateless.Gateway over
// httptest, and returns the harness. Everything is reaped on t.Cleanup.
func newHarness(t *testing.T) *harness {
	t.Helper()
	url := startEmbeddedJetStreamServer(t)
	conn, jetStream := dialJetStream(t, url)
	t.Cleanup(conn.Close)
	ensureStream(t, jetStream)

	verifier, err := edenhttp.NewHMACVerifier(jwtSecret)
	if err != nil {
		t.Fatalf("build verifier: %v", err)
	}
	spine, err := edenhttp.New(edenhttp.Config{}, edenhttp.Deps{Verifier: verifier, Clock: systemClock{}})
	if err != nil {
		t.Fatalf("build spine: %v", err)
	}
	bridge, err := natssse.New(
		natssse.Config{Stream: streamName, HeartbeatInterval: time.Hour},
		natssse.Deps{JetStream: jetStream, Clock: systemClock{}},
	)
	if err != nil {
		t.Fatalf("build bridge: %v", err)
	}
	control, err := natscontrol.New(conn)
	if err != nil {
		t.Fatalf("build control: %v", err)
	}
	gateway, err := stateless.New(
		stateless.Config{EventsStream: streamName},
		stateless.Deps{Spine: spine, Bridge: bridge, Control: control},
	)
	if err != nil {
		t.Fatalf("build gateway: %v", err)
	}
	server := httptest.NewServer(gateway.Handler())
	t.Cleanup(server.Close)
	return &harness{server: server, conn: conn, jetStream: jetStream, verifier: verifier}
}

// mint signs a dev-JWT carrying the given grants, valid for an hour.
func (h *harness) mint(t *testing.T, grantStrings ...string) string {
	t.Helper()
	grants := make([]edenhttp.Grant, 0, len(grantStrings))
	for _, raw := range grantStrings {
		grant, err := edenhttp.ParseGrant(raw)
		if err != nil {
			t.Fatalf("parse grant %q: %v", raw, err)
		}
		grants = append(grants, grant)
	}
	token, err := h.verifier.Sign("user-itest", grants, time.Now().Add(time.Hour))
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}
	return token
}

// do performs an HTTP request against the gateway with an optional Bearer token + JSON body.
func (h *harness) do(t *testing.T, method, path, body, token string) *http.Response {
	t.Helper()
	var reader io.Reader = http.NoBody
	if body != "" {
		reader = strings.NewReader(body)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	t.Cleanup(cancel)
	request, err := http.NewRequestWithContext(ctx, method, h.server.URL+path, reader)
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	if token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	if body != "" {
		request.Header.Set("Content-Type", "application/json")
	}
	response, err := h.server.Client().Do(request)
	if err != nil {
		t.Fatalf("request %s %s: %v", method, path, err)
	}
	return response
}

// publishStream publishes count EventEnvelopes to agent.<id>.events with MsgId==Seq, the last terminal.
func (h *harness) publishStream(t *testing.T, count uint64) {
	t.Helper()
	subject := agentruntime.EventsSubject(agentID)
	for seq := uint64(1); seq <= count; seq++ {
		kind := agentsession.EventTextDelta
		if seq == count {
			kind = agentsession.EventResult
		}
		envelope := agentruntime.EventEnvelope{
			AgentID: agentID,
			Seq:     seq,
			Event:   agentsession.Event{SessionID: string(agentID), Seq: seq, Kind: kind},
		}
		payload, err := json.Marshal(envelope)
		if err != nil {
			t.Fatalf("marshal envelope %d: %v", seq, err)
		}
		if _, err := h.jetStream.Publish(subject, payload, nats.MsgId(strconv.FormatUint(seq, 10))); err != nil {
			t.Fatalf("publish envelope %d: %v", seq, err)
		}
	}
}

// streamEvents opens GET /events with the cursor as ?from-seq= and the token, reading the SSE events.
func (h *harness) streamEvents(t *testing.T, fromSeq uint64, token string) []sseEvent {
	t.Helper()
	path := "/sessions/" + string(agentID) + "/events"
	if fromSeq != edenhttp.CursorAll {
		path += "?from-seq=" + strconv.FormatUint(fromSeq, 10)
	}
	return h.readEventStream(t, path, token, "")
}

// streamEventsLastEventID opens GET /events with a Last-Event-ID header (the reconnect path).
func (h *harness) streamEventsLastEventID(t *testing.T, lastEventID, token string) []sseEvent {
	t.Helper()
	return h.readEventStream(t, "/sessions/"+string(agentID)+"/events", token, lastEventID)
}

// readEventStream opens the SSE route and reads the frames until the stream closes (the terminal
// event ends it). The Last-Event-ID header is set when non-empty (the reconnect path).
func (h *harness) readEventStream(t *testing.T, path, token, lastEventID string) []sseEvent {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	t.Cleanup(cancel)
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, h.server.URL+path, http.NoBody)
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	request.Header.Set("Authorization", "Bearer "+token)
	if lastEventID != "" {
		request.Header.Set("Last-Event-ID", lastEventID)
	}
	response, err := h.server.Client().Do(request)
	if err != nil {
		t.Fatalf("events request: %v", err)
	}
	defer closeBody(t, response)
	if got := response.Header.Get("Content-Type"); !strings.HasPrefix(got, "text/event-stream") {
		t.Fatalf("Content-Type = %q, want text/event-stream (status %d)", got, response.StatusCode)
	}
	return parseSSE(t, response.Body)
}

// ── SSE parsing + assertions ──────────────────────────────────────────────────.

type sseEvent struct {
	seq   uint64
	event string
}

func parseSSE(t *testing.T, body io.Reader) []sseEvent {
	t.Helper()
	scanner := bufio.NewScanner(body)
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
		case line == "":
			if current.seq != 0 || current.event != "" {
				events = append(events, current)
				current = sseEvent{}
			}
		}
	}
	return events
}

func assertSeqOrder(t *testing.T, events []sseEvent, from, to uint64) {
	t.Helper()
	want := to - from + 1
	if uint64(len(events)) != want {
		t.Fatalf("got %d SSE events, want %d (seqs %d..%d): %+v", len(events), want, from, to, events)
	}
	expected := from
	for _, event := range events {
		if event.seq != expected {
			t.Fatalf("SSE stream not gap-free/ordered: got seq %d want %d", event.seq, expected)
		}
		expected++
	}
}

func closeBody(t *testing.T, response *http.Response) {
	t.Helper()
	if err := response.Body.Close(); err != nil {
		t.Errorf("close response body: %v", err)
	}
}

// ── real-substrate fixtures ───────────────────────────────────────────────────.

func ensureStream(t *testing.T, jetStream nats.JetStreamContext) {
	t.Helper()
	if _, err := jetStream.AddStream(&nats.StreamConfig{
		Name:     streamName,
		Subjects: []string{"agent.*.events"},
		Storage:  nats.FileStorage,
	}); err != nil {
		t.Fatalf("add stream: %v", err)
	}
}

func startEmbeddedJetStreamServer(t *testing.T) string {
	t.Helper()
	options := &natsserver.Options{Host: "127.0.0.1", Port: -1, JetStream: true, StoreDir: t.TempDir(), NoLog: true, NoSigs: true}
	server := natsservertest.RunServer(options)
	t.Cleanup(server.Shutdown)
	if !server.ReadyForConnections(10 * time.Second) {
		t.Fatal("embedded nats-server not ready within 10s")
	}
	return server.ClientURL()
}

//nolint:ireturn // nats.JetStreamContext is the vendor SDK's own interface type.
func dialJetStream(t *testing.T, url string) (*nats.Conn, nats.JetStreamContext) {
	t.Helper()
	conn, err := nats.Connect(url, nats.Timeout(5*time.Second))
	if err != nil {
		t.Fatalf("dial nats: %v", err)
	}
	jetStream, err := conn.JetStream()
	if err != nil {
		conn.Close()
		t.Fatalf("jetstream context: %v", err)
	}
	return conn, jetStream
}
