//go:build integration

// Package agentsessiontest_test's integration arm drives the fake harness end-to-end
// under the RACE DETECTOR with many concurrent tailers, stressing the fan-out, the
// FromSeq replay-then-tail seam, and the slow-subscriber demotion->catch-up path that the
// resumability story rests on. It is gated behind the `integration` build tag so the
// default `go test` (and the pre-commit hook) stays fast; run it with
//
//	go test -tags integration ./... -race
//
// Everything is in-process (no real subprocess, no pod, no network); each session is
// reaped on t.Cleanup. The real-subprocess lifecycle is exercised in the claudeadapter
// integration arm against a trivial stub binary.
package agentsessiontest_test

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
)

// TestIntegration_ManyConcurrentTailers_FanoutReplayRaceClean opens MANY concurrent
// tailers over one session — some fresh (FromSeq 0), some resuming mid-stream, some
// reading slowly to force demotion->catch-up — and asserts every tailer observes the
// identical, gap-free, dup-free Seq stream. This is the multi-client + lossless
// start/stop/resume requirement, race-checked at scale.
func TestIntegration_ManyConcurrentTailers_FanoutReplayRaceClean(t *testing.T) {
	t.Parallel()
	adapter := agentsessiontest.New(agentsessiontest.CanonicalScript()...)
	session := agentsessiontest.OpenForIntegration(t, adapter, nil)

	const tailers = 24
	results := make([][]uint64, tailers)
	var wg sync.WaitGroup
	for i := range tailers {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			// Mix the resume cursors and read pace to exercise every path concurrently.
			cursor := agentsession.FromSeq(uint64(idx % 4))
			slow := idx%3 == 0
			stream := session.Events(context.Background(), cursor)
			results[idx] = drainSeqsPaced(context.Background(), stream, slow)
		}(i)
	}
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	wg.Wait()

	// Each tailer's stream is gap-free from its own cursor, and tailers sharing a cursor
	// agree exactly.
	byCursor := map[uint64][]uint64{}
	for idx := range results {
		cursor := uint64(idx % 4)
		assertContiguousFrom(t, results[idx], cursor+1)
		if prior, ok := byCursor[cursor]; ok {
			if !equalUint64(prior, results[idx]) {
				t.Errorf("tailers at cursor %d diverged:\n %v\n %v", cursor, prior, results[idx])
			}
		} else {
			byCursor[cursor] = results[idx]
		}
	}
}

// TestIntegration_PermissionRaceFirstDecisionWins fires many concurrent Resolve calls at
// one pending request and asserts EXACTLY one wins (the rest get UnknownPermissionError) —
// the first-decision-wins property under a real multi-client race, race-checked.
func TestIntegration_PermissionRaceFirstDecisionWins(t *testing.T) {
	t.Parallel()
	adapter := agentsessiontest.New(
		agentsessiontest.MessageStart("assistant"),
		agentsessiontest.TextDelta("need bash"),
		agentsessiontest.PermissionRequest("req-1", "Bash", "run go test"),
	).OnPermissionAnswer(
		"req-1",
		agentsessiontest.PermissionResolved("req-1", agentsession.GrantAllowed, "winner"),
		agentsessiontest.Usage(agentsession.UsageMeter{Model: "fake", Harness: "fake", InputTokens: 1, OutputTokens: 1, CacheReadTokens: 1, CacheCreationTokens: 1, CostMicros: 0, Cumulative: true}),
		agentsessiontest.Result(agentsession.TokenLedger{UsageMeter: agentsession.UsageMeter{Harness: "fake", Cumulative: true}, Turns: 1}, "done", "end_turn"),
	)
	session := agentsessiontest.OpenForIntegration(t, adapter, nil)
	if _, err := session.Control(context.Background(), agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}

	// A background drainer keeps the stream moving toward the request.
	go func() { _, _ = drainTo(context.Background(), session, agentsession.EventPermissionRequest) }()
	waitUntilRequest(t, session, "req-1")

	const racers = 16
	var wins, losses int64
	var mu sync.Mutex
	var wg sync.WaitGroup
	for i := range racers {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			_, err := session.Resolve(context.Background(), "req-1", agentsession.Decision{Allow: true, By: "racer"})
			mu.Lock()
			if err == nil {
				wins++
			} else {
				losses++
			}
			mu.Unlock()
		}(i)
	}
	wg.Wait()
	if wins != 1 {
		t.Errorf("first-decision-wins violated: %d winners (want 1), %d losers", wins, losses)
	}
	if losses != racers-1 {
		t.Errorf("expected %d losers, got %d", racers-1, losses)
	}
}

// drainSeqsPaced drains a stream to its terminal, returning the Seq sequence; when slow is
// set it yields between reads to force a live-subscriber overflow -> demotion.
func drainSeqsPaced(ctx context.Context, stream agentsession.Stream, slow bool) []uint64 {
	var out []uint64
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return out
		}
		out = append(out, event.Seq)
		if event.IsTerminal() {
			return out
		}
		if slow {
			time.Sleep(time.Millisecond)
		}
	}
}

// drainTo drains a stream until an event of the given kind (or terminal).
func drainTo(ctx context.Context, session agentsession.Session, kind agentsession.EventKind) (agentsession.Event, bool) {
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return agentsession.Event{}, false
		}
		if event.Kind == kind {
			return event, true
		}
		if event.IsTerminal() {
			return event, false
		}
	}
}

// waitUntilRequest blocks until the named permission request is observable on the stream.
func waitUntilRequest(t *testing.T, session agentsession.Session, requestID string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("session ended before request %q was observable", requestID)
		}
		if event.Kind == agentsession.EventPermissionRequest && event.Permission != nil && event.Permission.RequestID == requestID {
			return
		}
	}
}

// assertContiguousFrom asserts a Seq slice starts at start and is strictly contiguous.
func assertContiguousFrom(t *testing.T, seqsSlice []uint64, start uint64) {
	t.Helper()
	if len(seqsSlice) == 0 {
		t.Errorf("empty Seq slice (expected events from %d)", start)
		return
	}
	if seqsSlice[0] != start {
		t.Errorf("first Seq = %d, want %d", seqsSlice[0], start)
	}
	for i := 1; i < len(seqsSlice); i++ {
		if seqsSlice[i] != seqsSlice[i-1]+1 {
			t.Errorf("gap/dup at index %d: %d follows %d", i, seqsSlice[i], seqsSlice[i-1])
		}
	}
}

// equalUint64 reports whether two slices are identical.
func equalUint64(a, b []uint64) bool {
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
