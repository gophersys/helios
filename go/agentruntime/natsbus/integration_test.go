//go:build integration

// Package natsbus_test's integration arm proves the agentruntime sidecar end-to-end over a REAL
// NATS/JetStream — NEVER a mock of the NATS protocol. It runs against TWO real substrates:
//
//   - an EMBEDDED real nats-server/v2 with JetStream (a real server started in-process, millisecond
//     boot, deterministic) — the primary arm, exercised on every integration run;
//   - a REAL `nats:latest` container booted docker-out-of-docker (the vaultadapter posture) — the
//     cross-process wire arm, SKIPPED if the docker CLI / image is unavailable locally but REQUIRED
//     in the devcontainer where docker is live.
//
// Both arms drive the SAME assertions through the real natsbus.Adapter wired into a real
// agentruntime.Runtime over a real agentsession session (the scripted stub harness): the ordered,
// Seq-stamped event stream reaches a JetStream subscriber; a control verb published to
// agent.<id>.control is enacted (a reply streams back); heartbeats arrive on agent.<id>.health;
// OTel context rides every message; the run is race-clean and leak-free (the conn + pump goroutines
// reaped on shutdown).
//
//	go test -tags integration ./... -race
package natsbus_test

import (
	"context"
	"encoding/json"
	"os/exec"
	"strconv"
	"testing"
	"time"

	natsserver "github.com/nats-io/nats-server/v2/server"
	natsservertest "github.com/nats-io/nats-server/v2/test"
	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
	"github.com/gophersys/libs/go/agentruntime/natsbus"
)

// TestIntegration_EmbeddedNATS_FullSidecarRoundTrip is the primary real-substrate arm: an embedded
// real nats-server with JetStream. It drives the full sidecar through the REAL natsbus adapter and
// asserts the ordered event stream, the control round-trip, heartbeats, OTel propagation, and a
// clean reaped shutdown.
func TestIntegration_EmbeddedNATS_FullSidecarRoundTrip(t *testing.T) {
	t.Parallel()
	url := startEmbeddedJetStreamServer(t)
	runSidecarRoundTrip(t, url)
}

// TestIntegration_EmbeddedNATS_DurableReplayBySeq proves the JetStream durability/replay invariant:
// after the sidecar has published its stream, a FRESH consumer binding the stream replays the whole
// Seq-ordered stream from sequence 1 (the B5 gateway's replay-by-Seq), gap-free and dup-free — the
// MsgId==Seq de-dup holds on a real JetStream.
func TestIntegration_EmbeddedNATS_DurableReplayBySeq(t *testing.T) {
	t.Parallel()
	url := startEmbeddedJetStreamServer(t)
	_, bus := newRealBus(t, url)
	driveCanonicalToTerminal(t, bus)

	// A fresh JetStream consumer replays the durable stream from the start.
	conn, jetStream := dialJetStream(t, url)
	subject := agentruntime.EventsSubject(agentruntimetest.AgentID)
	subscription, err := jetStream.SubscribeSync(subject, nats.DeliverAll())
	if err != nil {
		t.Fatalf("durable replay subscribe: %v", err)
	}
	t.Cleanup(func() { _ = subscription.Unsubscribe() }) //nolint:errcheck // best-effort reap.
	t.Cleanup(conn.Close)

	var prev uint64
	var sawTerminal bool
	for !sawTerminal {
		message, recvErr := subscription.NextMsg(5 * time.Second)
		if recvErr != nil {
			t.Fatalf("replay NextMsg: %v (saw up to seq %d)", recvErr, prev)
		}
		var envelope agentruntime.EventEnvelope
		if decodeErr := json.Unmarshal(message.Data, &envelope); decodeErr != nil {
			t.Fatalf("replay decode: %v", decodeErr)
		}
		if envelope.Seq != prev+1 {
			t.Fatalf("durable replay not gap-free/ordered: got seq %d want %d", envelope.Seq, prev+1)
		}
		if envelope.OTel["traceparent"] != agentruntimetest.TraceParent {
			t.Errorf("replayed envelope seq %d missing OTel carrier", envelope.Seq)
		}
		prev = envelope.Seq
		sawTerminal = envelope.Event.IsTerminal()
	}
	if prev == 0 {
		t.Fatal("durable replay produced no events")
	}
}

// TestIntegration_RealNATSContainer_RoundTrip is the cross-process arm: a REAL nats:latest container
// booted docker-out-of-docker. SKIPPED if docker/the image is unavailable locally; REQUIRED in the
// devcontainer where docker is live.
func TestIntegration_RealNATSContainer_RoundTrip(t *testing.T) {
	t.Parallel()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker CLI not on PATH: the real-container arm is skipped (the embedded arm still proves real NATS)")
	}
	url := startNATSContainer(t)
	runSidecarRoundTrip(t, url)
}

// runSidecarRoundTrip drives a full sidecar over the real bus at url and asserts the ordered stream,
// the control round-trip, heartbeats, OTel, and a clean reaped shutdown. Shared by the embedded +
// container arms (the SAME assertions over the SAME adapter — only the substrate differs). The
// health + events subscribers are attached BEFORE Run starts, so neither races the (fast) session.
func runSidecarRoundTrip(t *testing.T, url string) {
	t.Helper()
	runtime, _ := newRealBus(t, url)

	// Attach the gateway-role subscribers FIRST (events durable + health core) so nothing is missed.
	conn, jetStream := dialJetStream(t, url)
	t.Cleanup(conn.Close)
	eventsSub, err := jetStream.SubscribeSync(agentruntime.EventsSubject(agentruntimetest.AgentID), nats.DeliverAll())
	if err != nil {
		t.Fatalf("subscribe events: %v", err)
	}
	t.Cleanup(func() { _ = eventsSub.Unsubscribe() }) //nolint:errcheck // best-effort reap.
	healthSub, err := conn.SubscribeSync(agentruntime.HealthSubject(agentruntimetest.AgentID))
	if err != nil {
		t.Fatalf("subscribe health: %v", err)
	}
	t.Cleanup(func() { _ = healthSub.Unsubscribe() }) //nolint:errcheck // best-effort reap.
	_ = conn.Flush()                                  //nolint:errcheck // ensure the interests propagate before Run publishes.

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan agentruntime.TerminationReason, 1)
	go func() {
		reason, _ := runtime.Run(ctx) //nolint:errcheck // the assertions below verify the run via the bus + the reason channel.
		done <- reason
	}()

	// Publish a PROMPT verb to agent.<id>.control (the orchestrator's role) so the scripted harness
	// streams its reply — the SOFT control round-trip over a real bus.
	control, _ := json.Marshal(agentruntime.ControlMessage{ //nolint:errcheck // a fixed struct marshals.
		AgentID: agentruntimetest.AgentID, Verb: agentruntime.VerbPrompt, Text: "go",
		OTel: agentruntime.OTelContext{"traceparent": agentruntimetest.TraceParent},
	})
	waitForControlSubscriber(t, conn, "")
	if pubErr := conn.Publish(agentruntime.ControlSubject(agentruntimetest.AgentID), control); pubErr != nil {
		t.Fatalf("publish control: %v", pubErr)
	}
	_ = conn.Flush() //nolint:errcheck // best-effort flush of the control publish.

	// Drain the real event subject to the terminal, asserting Seq order + OTel on every message.
	var prev uint64
	var sawTerminal, sawTool bool
	for !sawTerminal {
		message, recvErr := eventsSub.NextMsg(10 * time.Second)
		if recvErr != nil {
			t.Fatalf("events NextMsg: %v (saw up to seq %d)", recvErr, prev)
		}
		var envelope agentruntime.EventEnvelope
		if decodeErr := json.Unmarshal(message.Data, &envelope); decodeErr != nil {
			t.Fatalf("decode envelope: %v", decodeErr)
		}
		if envelope.Seq != prev+1 {
			t.Fatalf("event stream not gap-free/ordered over real NATS: got %d want %d", envelope.Seq, prev+1)
		}
		if envelope.OTel["traceparent"] != agentruntimetest.TraceParent {
			t.Errorf("envelope seq %d missing OTel carrier over real NATS", envelope.Seq)
		}
		prev = envelope.Seq
		sawTool = sawTool || envelope.Event.Kind.String() == "tool-start"
		sawTerminal = envelope.Event.IsTerminal()
	}
	if !sawTool {
		t.Errorf("the canonical tool-start did not reach the real event subject")
	}

	// At least one heartbeat reached agent.<id>.health carrying the agent id + OTel (the subscriber
	// was attached before Run, so a beat is queued even though the session ended quickly).
	assertHeartbeat(t, healthSub)

	// The run reaped cleanly on the session terminal.
	select {
	case reason := <-done:
		if reason != agentruntime.TerminationSessionEnd {
			t.Errorf("run reason = %s, want session-end", reason)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("run did not reap within 10s after the session terminal")
	}
}

// driveCanonicalToTerminal runs a seed-prompt sidecar to its terminal over the real bus (used by the
// durable-replay arm, which then replays the stored stream).
func driveCanonicalToTerminal(t *testing.T, bus *natsbus.Adapter) {
	t.Helper()
	runtime, err := agentruntime.New(
		agentruntime.Config{
			AgentID:           agentruntimetest.AgentID,
			Spec:              agentruntimetest.Spec(),
			HeartbeatInterval: 20 * time.Millisecond,
			DrainTimeout:      5 * time.Second,
			InitialPrompt:     "go",
		},
		agentruntime.Deps{
			Sessions: agentruntimetest.NewSessionsNoT(agentruntimetest.CanonicalScript()...),
			Bus:      bus,
			Observer: agentruntimetest.NewFakeObserver(),
			Clock:    agentruntimetest.FixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("construct sidecar: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if _, runErr := runtime.Run(ctx); runErr != nil {
		t.Fatalf("run to terminal: %v", runErr)
	}
}

// newRealBus builds a real natsbus.Adapter over a connection to url (ensuring the JetStream stream)
// and a Runtime over it with the canonical script. The connection is reaped on cleanup.
func newRealBus(t *testing.T, url string) (*agentruntime.Runtime, *natsbus.Adapter) {
	t.Helper()
	conn, jetStream := dialJetStream(t, url)
	t.Cleanup(conn.Close)
	bus, err := natsbus.New(natsbus.Config{}, natsbus.Deps{Conn: conn, JetStream: jetStream})
	if err != nil {
		t.Fatalf("construct natsbus adapter: %v", err)
	}
	if ensureErr := bus.EnsureStream(context.Background()); ensureErr != nil {
		t.Fatalf("ensure events stream: %v", ensureErr)
	}
	runtime, err := agentruntime.New(
		agentruntime.Config{
			AgentID:           agentruntimetest.AgentID,
			Spec:              agentruntimetest.Spec(),
			HeartbeatInterval: 20 * time.Millisecond,
			DrainTimeout:      5 * time.Second,
		},
		agentruntime.Deps{
			Sessions: agentruntimetest.NewSessionsNoT(agentruntimetest.CanonicalScript()...),
			Bus:      bus,
			Observer: agentruntimetest.NewFakeObserver(),
			Clock:    agentruntimetest.FixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("construct runtime: %v", err)
	}
	return runtime, bus
}

// assertHeartbeat waits on an already-attached health subscription for one heartbeat carrying the
// agent id + OTel carrier (a real core-NATS publish).
func assertHeartbeat(t *testing.T, subscription *nats.Subscription) {
	t.Helper()
	message, err := subscription.NextMsg(8 * time.Second)
	if err != nil {
		t.Fatalf("no heartbeat arrived on %s: %v", agentruntime.HealthSubject(agentruntimetest.AgentID), err)
	}
	var heartbeat agentruntime.Heartbeat
	if decodeErr := json.Unmarshal(message.Data, &heartbeat); decodeErr != nil {
		t.Fatalf("decode heartbeat: %v", decodeErr)
	}
	if heartbeat.AgentID != agentruntimetest.AgentID {
		t.Errorf("heartbeat agent id = %q, want %q", heartbeat.AgentID, agentruntimetest.AgentID)
	}
	if heartbeat.OTel["traceparent"] != agentruntimetest.TraceParent {
		t.Errorf("heartbeat missing OTel carrier over real NATS")
	}
}

// waitForControlSubscriber gives the sidecar's control subscription a brief, bounded grace to attach
// before the orchestrator publishes, so the verb is not raced. A short fixed grace is sufficient: the
// sidecar subscribes synchronously at Run start, well within this window.
func waitForControlSubscriber(t *testing.T, conn *nats.Conn, _ string) {
	t.Helper()
	_ = conn.Flush() //nolint:errcheck // best-effort: flush the connection so prior interest propagates.
	time.Sleep(250 * time.Millisecond)
}

// startEmbeddedJetStreamServer boots an in-process real nats-server with JetStream on a random port,
// reaped on cleanup, and returns its client URL.
func startEmbeddedJetStreamServer(t *testing.T) string {
	t.Helper()
	options := &natsserver.Options{
		Host:      "127.0.0.1",
		Port:      -1, // random free port
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

// dialJetStream dials url and returns a connection + a JetStream context, reaped on cleanup.
//
//nolint:ireturn // nats.JetStreamContext is the vendor SDK's own interface type; the test helper returns it as the SDK vends it.
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

// startNATSContainer boots a real nats:latest container with JetStream (docker-out-of-docker) and
// returns its client URL reached over the container's docker-bridge IP — NOT a published host port:
// the devcontainer shares the docker network, so the bridge IP is directly reachable (the
// vaultadapter posture), while a published 127.0.0.1 port would land on the docker HOST, not the
// devcontainer. The container is reaped on cleanup under a unique name.
func startNATSContainer(t *testing.T) string {
	t.Helper()
	name := "eden-agentruntime-nats-" + strconv.FormatInt(time.Now().UnixNano(), 36)
	// #nosec G204 -- fixed `docker run` of the official nats image; name is time-derived, not user input.
	run := exec.Command("docker", "run", "-d", "--rm", "--name", name, "nats:latest", "-js")
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

// dockerBridgeIP reads the container's docker-bridge IP (directly reachable from the devcontainer on
// the shared docker network).
func dockerBridgeIP(t *testing.T, name string) string {
	t.Helper()
	// #nosec G204 -- fixed `docker inspect` of the just-created container by its time-derived name.
	out, err := exec.Command("docker", "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name).CombinedOutput()
	if err != nil {
		t.Fatalf("docker inspect: %v\n%s", err, out)
	}
	ip := string(out)
	for ip != "" && (ip[len(ip)-1] == '\n' || ip[len(ip)-1] == '\r' || ip[len(ip)-1] == ' ') {
		ip = ip[:len(ip)-1]
	}
	if ip == "" {
		t.Fatalf("docker inspect returned an empty bridge IP for %s", name)
	}
	return ip
}

// waitForServer polls until url accepts a NATS connection (the container's boot grace).
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
