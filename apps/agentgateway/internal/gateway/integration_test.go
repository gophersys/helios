//go:build integration

// Package gateway_test's integration arm drives the agentsession gateway end-to-end under
// the RACE DETECTOR against the REAL orchestrator record plane (orchestratortest.Manager)
// and the REAL agentsession live plane (its agentsessiontest scripted Adapter wired into a
// real agentsession.Pool + a real in-memory Transcript), all served via httptest. No real
// claude/omp process, no container, no network beyond the loopback httptest server: the
// proof here is the gateway's CONCURRENCY (multi-client SSE fan-out), RESUMABILITY
// (Last-Event-ID / from-seq replay with no loss/dup), PER-SESSION ISOLATION, mid-stream
// CONTROL, and the CREDENTIAL SEAM — not a real cluster. It is gated behind the
// `integration` build tag so the default `go test` (and the pre-commit hook) stays fast.
//
//	go test -tags integration ./... -race
//
// Every server/session/goroutine is reaped on t.Cleanup (no leak).
package gateway_test

import (
	"context"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
)

// integrationDeadline bounds every streaming wait so a wedged stream fails fast.
const integrationDeadline = 10 * time.Second

// TestIntegrationConcurrentFanOut proves REQ-0022 per-session fan-out under concurrency: N
// concurrent SSE clients on ONE session each receive the FULL ordered taxonomy from their
// own cursor, with identical seqs (one durable transcript, many independent viewers),
// race-clean. Subscribing to one stream does not stall another.
func TestIntegrationConcurrentFanOut(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	id := h.createSession(t, "go")

	const clients = 32
	ctx, cancel := context.WithTimeout(context.Background(), integrationDeadline)
	defer cancel()

	var wg sync.WaitGroup
	results := make([][]sseFrame, clients)
	for i := 0; i < clients; i++ {
		wg.Add(1)
		go func(index int) {
			defer wg.Done()
			reader := newSSEReader(h.openSSE(ctx, t, id, "", ""))
			defer reader.close()
			results[index] = reader.drainToTerminal(t)
		}(i)
	}
	wg.Wait()

	// Every client saw the SAME ordered seq sequence ending on the terminal Result.
	reference := ids(results[0])
	if len(reference) == 0 {
		t.Fatal("client 0 received no frames")
	}
	assertMonotonicIDs(t, reference)
	for i := 1; i < clients; i++ {
		if got := ids(results[i]); !equalStrings(got, reference) {
			t.Fatalf("client %d seq sequence diverged: %v vs %v", i, got, reference)
		}
	}
	if frames := results[0]; frames[len(frames)-1].Event != "result" {
		t.Fatalf("stream did not end on result")
	}
}

// TestIntegrationLastEventIDReplay proves REQ-0023 lossless, dup-free resume: a client
// consumes a PREFIX of the stream, disconnects mid-session, then reconnects with its
// last-seen seq as the Last-Event-ID header and receives EXACTLY the missing events in
// order — no loss, no duplication. The whole-session set reconstructed across the two
// connections equals an uninterrupted single-connection read.
func TestIntegrationLastEventIDReplay(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	id := h.createSession(t, "go")

	// A reference single-connection read of the full ordered stream.
	refCtx, refCancel := context.WithTimeout(context.Background(), integrationDeadline)
	defer refCancel()
	refSession := h.createSession(t, "go")
	reference := newSSEReader(h.openSSE(refCtx, t, refSession, "", "")).drainToTerminal(t)
	refSeqs := ids(reference)

	// First connection: consume a prefix, then disconnect mid-stream.
	ctx1, cancel1 := context.WithTimeout(context.Background(), integrationDeadline)
	defer cancel1()
	reader1 := newSSEReader(h.openSSE(ctx1, t, id, "", ""))
	const prefix = 4
	var firstSeqs []string
	var lastSeen string
	for i := 0; i < prefix; i++ {
		frame, ok := reader1.next(t)
		if !ok {
			t.Fatalf("first connection ended early at frame %d", i)
		}
		firstSeqs = append(firstSeqs, frame.ID)
		lastSeen = frame.ID
	}
	reader1.close() // kill the client mid-session

	// Reconnect with Last-Event-ID == lastSeen: receive EXACTLY the missing events.
	ctx2, cancel2 := context.WithTimeout(context.Background(), integrationDeadline)
	defer cancel2()
	reader2 := newSSEReader(h.openSSE(ctx2, t, id, lastSeen, ""))
	defer reader2.close()
	resumed := reader2.drainToTerminal(t)
	resumedSeqs := ids(resumed)

	// No duplication: the first resumed seq is strictly after lastSeen (numeric compare —
	// string compare would misorder "10" vs "4").
	if len(resumedSeqs) == 0 {
		t.Fatal("resume delivered no events")
	}
	if seqNum(t, resumedSeqs[0]) <= seqNum(t, lastSeen) {
		t.Fatalf("resume duplicated: first resumed seq %s <= last-seen %s", resumedSeqs[0], lastSeen)
	}

	// No loss: prefix ++ resumed == the full reference sequence, contiguous.
	combined := append(append([]string{}, firstSeqs...), resumedSeqs...)
	if !equalStrings(combined, refSeqs) {
		t.Fatalf("resume not lossless/contiguous:\n prefix+resumed = %v\n reference      = %v", combined, refSeqs)
	}
	assertMonotonicIDs(t, combined)
}

// TestIntegrationFromSeqQueryReplay proves the ?from-seq= query is the SAME replay
// mechanism as Last-Event-ID: a fresh client requesting from-seq=N receives exactly the
// events after N, in order.
func TestIntegrationFromSeqQueryReplay(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	id := h.createSession(t, "go")

	ctx, cancel := context.WithTimeout(context.Background(), integrationDeadline)
	defer cancel()
	full := newSSEReader(h.openSSE(ctx, t, id, "", "")).drainToTerminal(t)
	fullSeqs := ids(full)
	if len(fullSeqs) < 3 {
		t.Fatalf("expected at least 3 events, got %d", len(fullSeqs))
	}

	// Replay from the 3rd seq: expect exactly the tail after it.
	from := fullSeqs[2]
	ctx2, cancel2 := context.WithTimeout(context.Background(), integrationDeadline)
	defer cancel2()
	tail := newSSEReader(h.openSSE(ctx2, t, id, "", from)).drainToTerminal(t)
	tailSeqs := ids(tail)

	if !equalStrings(tailSeqs, fullSeqs[3:]) {
		t.Fatalf("from-seq replay mismatch:\n tail = %v\n want = %v", tailSeqs, fullSeqs[3:])
	}
}

// TestIntegrationPerSessionIsolation proves REQ-0022 per-session fan-out: a stream on
// session B carries ONLY B's events — none of session A's traffic — even when both run
// concurrently over the same gateway/pool. The proof is by SessionID attribution: every
// frame on a stream carries the SessionID of the session whose URL it was opened on.
func TestIntegrationPerSessionIsolation(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)

	idA := h.createSession(t, "session A work")
	idB := h.createSession(t, "session B work")

	ctx, cancel := context.WithTimeout(context.Background(), integrationDeadline)
	defer cancel()

	framesA := newSSEReader(h.openSSE(ctx, t, idA, "", "")).drainToTerminal(t)
	framesB := newSSEReader(h.openSSE(ctx, t, idB, "", "")).drainToTerminal(t)

	sessionA := frameSessionID(t, framesA)
	sessionB := frameSessionID(t, framesB)
	if sessionA == sessionB || sessionA == "" || sessionB == "" {
		t.Fatalf("sessions not distinct: A=%q B=%q", sessionA, sessionB)
	}

	// Stream A carries ONLY session A's id; stream B carries ONLY session B's id.
	assertAllSessionID(t, "stream A", framesA, sessionA)
	assertAllSessionID(t, "stream B", framesB, sessionB)

	// And A's stream never carries B's id (the no-cross-talk assertion, explicit).
	for _, frame := range framesA {
		if data := decodeData(t, frame.Data); data["sessionId"] == sessionB {
			t.Fatalf("session B event leaked into session A's stream: %v", data)
		}
	}
}

// TestIntegrationSteerTakesEffectMidStream proves REQ-0020 mid-session steer: a steer
// command posted to the control channel injects its scripted reaction into the running
// turn, observable on the live stream, then the run completes.
func TestIntegrationSteerTakesEffectMidStream(t *testing.T) {
	t.Parallel()
	// A long-running script (no terminal) so the session is StateRunning when the steer
	// arrives; the steer reaction carries the terminal Result.
	script := []agentsession.Event{
		agentsessiontest.MessageStart("assistant"),
		agentsessiontest.TextDelta("starting"),
	}
	h := newHarness(t, script...)
	// Pin the steer reaction: a distinctive text delta + the terminal Result.
	h.adapter.OnSteer(
		"focus on tests",
		agentsessiontest.TextDelta("steered: focusing on tests"),
		agentsessiontest.Result(agentsession.TokenLedger{
			UsageMeter: agentsession.UsageMeter{Model: "fake-fable-5", Harness: "fake", Cumulative: true},
			Turns:      1,
		}, "done", "end_turn"),
	)

	id := h.createSession(t, "go")

	// Open the stream BEFORE steering so the mid-stream effect is observed live.
	ctx, cancel := context.WithTimeout(context.Background(), integrationDeadline)
	defer cancel()
	reader := newSSEReader(h.openSSE(ctx, t, id, "", ""))
	defer reader.close()

	// Read the lead-in (state-ready, message-start, the first text-delta) so the session is
	// running, then steer.
	waitForKind(t, reader, "text-delta")

	status, body := h.postJSON(t, "/sessions/"+id+"/control", map[string]any{
		"command": "steer", "text": "focus on tests",
	})
	if status != 200 {
		t.Fatalf("steer control: status %d (%v)", status, body)
	}
	assertReceivedCommand(t, h.adapter, agentsession.CommandSteer)

	// The steered text delta appears on the live stream before the terminal.
	rest := reader.drainToTerminal(t)
	if !anyDataContains(t, rest, "steered: focusing on tests") {
		t.Fatalf("steer reaction not observed mid-stream; frames=%v", kinds(rest))
	}
}

// TestIntegrationCredentialNeverReachesClient proves REQ-0021: the seeded setup-token
// canary (resolved server-side at Open) appears in NO create/list/get/transcript response,
// NO SSE payload, and NO log line. The whole journey is scanned.
func TestIntegrationCredentialNeverReachesClient(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)

	// Create — the credential ref is threaded server-side; the response carries only the id.
	id := h.createSession(t, "go")

	// SSE — drain the whole taxonomy and scan every frame's raw data.
	ctx, cancel := context.WithTimeout(context.Background(), integrationDeadline)
	defer cancel()
	frames := newSSEReader(h.openSSE(ctx, t, id, "", "")).drainToTerminal(t)
	for _, frame := range frames {
		assertNoCanary(t, "sse data", frame.Data)
	}

	// Record reads — list, get, transcript.
	_, listBody := h.getJSON(t, "/sessions?organizationId=org-eden&projectId=proj-chat")
	assertNoCanary(t, "list response", marshal(t, listBody))
	_, getBody := h.getJSON(t, "/sessions/"+id)
	assertNoCanary(t, "get response", marshal(t, getBody))
	_, txBody := h.getJSON(t, "/sessions/"+id+"/transcript")
	assertNoCanary(t, "transcript response", marshal(t, txBody))

	// Logs — every emitted line.
	for _, line := range h.logger.snapshot() {
		assertNoCanary(t, "log line", line)
	}

	// And the orchestrator record plane's own no-leak guard (every record version + every
	// observability event) — belt and suspenders on the record plane.
	h.manager.AssertNoSecretInRecord(t, agentsessiontest.SeededCanary)

	// Sanity: the scripted adapter WAS asked to inject the credential REFERENCE (refs only,
	// never the value) — so the seam is exercised, not vacuously absent.
	if len(h.adapter.InjectedRefs()) == 0 {
		t.Fatal("adapter never asked to inject a credential ref — the seam is vacuous")
	}
}

// TestIntegrationTranscriptReconstructsAfterKill proves REQ-0023's reconstruct-from-
// persisted-events: after the session reaches terminal and is stopped (the live handle
// reaped), the transcript route still serves the full ordered Run — the state a reopened
// chat reconstructs.
func TestIntegrationTranscriptReconstructsAfterKill(t *testing.T) {
	t.Parallel()
	h := newHarness(t, chatScript()...)
	id := h.createSession(t, "go")

	ctx, cancel := context.WithTimeout(context.Background(), integrationDeadline)
	defer cancel()
	live := newSSEReader(h.openSSE(ctx, t, id, "", "")).drainToTerminal(t)
	liveSeqs := ids(live)

	// Stop reaps the live handle.
	if status, _ := h.postJSON(t, "/sessions/"+id+"/stop", nil); status != 200 {
		t.Fatalf("stop status %d", status)
	}

	// The transcript still reconstructs the full Run by persisted seq.
	_, body := h.getJSON(t, "/sessions/"+id+"/transcript")
	events, ok := body["events"].([]any)
	if !ok {
		t.Fatalf("transcript events not an array: %v", body["events"])
	}
	if len(events) != len(liveSeqs) {
		t.Fatalf("transcript reconstructs %d events, live streamed %d", len(events), len(liveSeqs))
	}
	if body["complete"] != true {
		t.Fatalf("reconstructed transcript not complete")
	}
}

// TestIntegrationNoGoroutineLeak proves the no-leak guarantee: after a full session
// lifecycle (create -> stream to terminal -> stop) and the gateway's Close reap, the
// goroutine count returns to its pre-session baseline. Every Open is matched by a Close;
// no harness pump or stream goroutine outlives the session.
//
//nolint:paralleltest // DELIBERATELY serial: the goroutine-count baseline must not race other tests' goroutines (a parallel sibling would inflate the count and mask/forge a leak).
func TestIntegrationNoGoroutineLeak(t *testing.T) {
	h := newHarness(t, chatScript()...)

	baseline := stableGoroutineCount()

	for i := 0; i < 8; i++ {
		id := h.createSession(t, "go")
		ctx, cancel := context.WithTimeout(context.Background(), integrationDeadline)
		_ = newSSEReader(h.openSSE(ctx, t, id, "", "")).drainToTerminal(t)
		cancel()
		if status, _ := h.postJSON(t, "/sessions/"+id+"/stop", nil); status != 200 {
			t.Fatalf("stop status %d", status)
		}
	}

	after := stableGoroutineCount()
	// Allow a small slack for httptest's transient connection goroutines settling; the
	// proof is that the count does NOT grow with the 8 sessions (a leak would be ~8+ per
	// session: a pump + a stream goroutine each).
	if after > baseline+4 {
		t.Fatalf("goroutine leak: baseline %d, after 8 session lifecycles %d", baseline, after)
	}
}

// ── integration helpers ──────────────────────────────────────────────────────.

// stableGoroutineCount returns the goroutine count after a short settle (GC + scheduler
// yields) so transient teardown goroutines are not miscounted as a leak.
func stableGoroutineCount() int {
	var last int
	for i := 0; i < 20; i++ {
		runtime.GC()
		time.Sleep(20 * time.Millisecond)
		current := runtime.NumGoroutine()
		if current == last {
			return current
		}
		last = current
	}
	return last
}

// frameSessionID returns the SessionID carried by the first frame.

// frameSessionID returns the SessionID carried by the first frame.
func frameSessionID(t *testing.T, frames []sseFrame) string {
	t.Helper()
	if len(frames) == 0 {
		return ""
	}
	data := decodeData(t, frames[0].Data)
	id, _ := data["sessionId"].(string) //nolint:errcheck // a missing/empty sessionId is asserted by the caller (distinctness check).
	return id
}

// assertAllSessionID proves every frame carries the expected SessionID (per-session
// attribution).
func assertAllSessionID(t *testing.T, where string, frames []sseFrame, want string) {
	t.Helper()
	for i, frame := range frames {
		data := decodeData(t, frame.Data)
		if data["sessionId"] != want {
			t.Fatalf("%s frame %d carries sessionId %v, want %s", where, i, data["sessionId"], want)
		}
	}
}

// waitForKind reads frames until one of the given kind is seen (or the stream ends).
func waitForKind(t *testing.T, reader *sseReader, kind string) {
	t.Helper()
	for {
		frame, ok := reader.next(t)
		if !ok {
			t.Fatalf("stream ended before kind %q", kind)
		}
		if frame.Event == kind {
			return
		}
	}
}

// anyDataContains reports whether any frame's data contains the substring.
func anyDataContains(t *testing.T, frames []sseFrame, substr string) bool {
	t.Helper()
	for _, frame := range frames {
		if strings.Contains(frame.Data, substr) {
			return true
		}
	}
	return false
}

// seqNum parses an SSE id token to a numeric seq for ordering comparisons.
func seqNum(t *testing.T, token string) uint64 {
	t.Helper()
	n, err := strconv.ParseUint(token, 10, 64)
	if err != nil {
		t.Fatalf("seq token %q not numeric: %v", token, err)
	}
	return n
}

// equalStrings reports whether two string slices are element-wise equal.
func equalStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// marshal renders a decoded body back to JSON text for the canary scan.
func marshal(t *testing.T, body map[string]any) string {
	t.Helper()
	return mapToString(body)
}

// mapToString renders a generic map to a flat string for substring scanning (the canary is
// a literal token; a flattened render is sufficient and avoids importing encoding/json here
// for a value that is already decoded).
func mapToString(v any) string {
	switch x := v.(type) {
	case string:
		return x
	case map[string]any:
		out := ""
		for k, val := range x {
			out += k + ":" + mapToString(val) + " "
		}
		return out
	case []any:
		out := ""
		for _, val := range x {
			out += mapToString(val) + " "
		}
		return out
	case float64:
		return strconv.FormatFloat(x, 'f', -1, 64)
	case bool:
		return strconv.FormatBool(x)
	default:
		return ""
	}
}
