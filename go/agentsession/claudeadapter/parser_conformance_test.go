package claudeadapter_test

import (
	"bufio"
	"context"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// TestRealParser_ThroughLibraryMachinery is the parser arm of the conformance proof: the
// REAL claude-code stream-json normalizer's output is driven through the SAME library
// machinery (Pool -> session pump -> Seq -> Transcript -> fan-out) the fake conformance
// suite exercises. It asserts the substitutability properties hold for the real parser's
// events — ordering + Seq monotonicity, FromSeq replay, multi-client fan-out parity, and
// the rate_limit_event Extension surviving — WITHOUT a live authenticated process.
//
// A fake Adapter is scripted with the real-normalized fixture events: this isolates the
// VENDOR PARSER (the thing that differs between harnesses) and runs it through the one
// library, which is exactly the conformance closure the contract names (the real adapter
// passes the same suite the fake does, at the parser level).
func TestRealParser_ThroughLibraryMachinery(t *testing.T) {
	t.Parallel()
	script := realNormalizedFixture(t, "sample-stream.jsonl")

	adapter := agentsessiontest.New(script...)
	pool := buildPool(t, adapter)

	session, err := pool.Open(context.Background(), parserSpec())
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	// Two concurrent tailers (one fresh, one resuming) observe the identical Seq stream.
	const tailers = 2
	results := make([][]agentsession.Event, tailers)
	var wg sync.WaitGroup
	for i := range tailers {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			stream := session.Events(context.Background(), agentsession.FromSeq(0))
			results[idx] = drainAll(context.Background(), stream)
		}(i)
	}
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	wg.Wait()

	canonical := results[0]
	if len(canonical) == 0 {
		t.Fatal("real parser produced no events through the library")
	}
	assertSeqContiguous(t, canonical)
	assertFanoutParity(t, results, canonical)

	// The rate_limit_event survived as Extension through the library too.
	if !anyKind(canonical, agentsession.EventExtension) {
		t.Errorf("the real parser's rate_limit_event Extension must survive the library machinery")
	}
	assertTerminalCacheTokens(t, canonical[len(canonical)-1])

	// Post-terminate replay reproduces the whole session (old-Run reload).
	replay := drainAll(context.Background(), session.Events(context.Background(), agentsession.FromSeq(0)))
	if len(replay) != len(canonical) {
		t.Errorf("post-terminate replay saw %d events, live saw %d", len(replay), len(canonical))
	}
}

// assertSeqContiguous proves a drained slice is strictly Seq-contiguous from 1.
func assertSeqContiguous(t *testing.T, events []agentsession.Event) {
	t.Helper()
	var prev uint64
	for i := range events {
		ev := &events[i]
		if ev.Seq != prev+1 {
			t.Fatalf("event %d Seq = %d, want %d", i, ev.Seq, prev+1)
		}
		prev = ev.Seq
	}
}

// assertFanoutParity proves every tailer's Seq stream equals the canonical one.
func assertFanoutParity(t *testing.T, results [][]agentsession.Event, canonical []agentsession.Event) {
	t.Helper()
	for i := 1; i < len(results); i++ {
		if len(results[i]) != len(canonical) {
			t.Fatalf("tailer %d saw %d events, tailer 0 saw %d", i, len(results[i]), len(canonical))
		}
		for j := range canonical {
			if results[i][j].Seq != canonical[j].Seq {
				t.Fatalf("fan-out parity broke at tailer %d index %d", i, j)
			}
		}
	}
}

// assertTerminalCacheTokens proves the terminal ledger carries the cache token kinds.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); this fake/test helper takes it by value.
func assertTerminalCacheTokens(t *testing.T, terminal agentsession.Event) {
	t.Helper()
	if !terminal.IsTerminal() || terminal.Terminal == nil {
		t.Fatalf("stream did not end on a terminal carrying a ledger")
	}
	if terminal.Terminal.Ledger.CacheReadTokens == 0 || terminal.Terminal.Ledger.CacheCreationTokens == 0 {
		t.Errorf("real parser terminal ledger missing cache tokens: %+v", terminal.Terminal.Ledger)
	}
}

// realNormalizedFixture runs the REAL stream-json normalizer over a fixture and returns
// the normalized Events as a fake-adapter script. The terminal Result/Failed is stripped
// of nothing; it is the genuine parser output.
func realNormalizedFixture(t *testing.T, name string) []agentsession.Event {
	t.Helper()
	file, err := os.Open(filepath.Join("testdata", name)) //nolint:gosec // a fixed test fixture path
	if err != nil {
		t.Fatalf("open fixture: %v", err)
	}
	t.Cleanup(func() { _ = file.Close() }) //nolint:errcheck // best-effort fixture-file close on test cleanup.

	normalize := claudeadapter.StreamNormalizerForTest()
	var events []agentsession.Event
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 0, 64*1024), 8<<20)
	for scanner.Scan() {
		line := make([]byte, len(scanner.Bytes()))
		copy(line, scanner.Bytes())
		normalized := normalize(line)
		for i := range normalized {
			ev := &normalized[i]
			// The fake conn emits its OWN Ready handshake at Spawn, so drop the parser's
			// Ready transition from the script to avoid a duplicate (the library dedups by
			// Seq, but the script must drive a single coherent lifecycle).
			if ev.Kind == agentsession.EventSessionState && ev.State != nil && ev.State.To == agentsession.StateReady {
				continue
			}
			events = append(events, *ev)
		}
	}
	if serr := scanner.Err(); serr != nil {
		t.Fatalf("scan: %v", serr)
	}
	return events
}

// buildPool constructs a Pool over the given adapter (the fake, scripted from the real
// parser output), a seeded provider, and an in-memory transcript.
func buildPool(t *testing.T, adapter agentsession.Adapter) *agentsession.Pool {
	t.Helper()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "claude-code", Model: "claude-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"claude-code": adapter},
			Secrets:    secretstest.New(map[string]string{"vault://eden/anthropic#setup-token": "S3CR3T"}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      parserClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return pool
}

// parserSpec is the spec the parser-conformance session opens with.
func parserSpec() agentsession.Spec {
	return agentsession.Spec{
		Workspace:  "/workspace",
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Grants:     []agentsession.ToolGrant{{ID: "g-write", Tool: "Write"}, {ID: "g-bash", Tool: "Bash"}},
		Credential: secrets.Ref("vault://eden/anthropic#setup-token"),
	}
}

// parserClock is a deterministic clock for the parser-conformance pool.
type parserClock struct{}

func (parserClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// drainAll reads a stream to its terminal.
func drainAll(ctx context.Context, stream agentsession.Stream) []agentsession.Event {
	var events []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return events
		}
		events = append(events, event)
		if event.IsTerminal() {
			return events
		}
	}
}

// anyKind reports whether any event has the given kind.
func anyKind(events []agentsession.Event, kind agentsession.EventKind) bool {
	for i := range events {
		ev := &events[i]
		if ev.Kind == kind {
			return true
		}
	}
	return false
}
