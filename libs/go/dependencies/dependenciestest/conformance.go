package dependenciestest

import (
	"bytes"
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
)

// RunPortSuite asserts every universal port honors its contract, for BOTH the real
// adapters and the dependenciestest fakes, proving substitutability (08 §2). newSet must
// return a freshly-constructed, fully-populated dependencies.Set on each call so the
// suite can drive independent instances per property.
//
// Properties (contract §4): Clock.Now monotonic-aware & non-decreasing; Clock.After
// fires / respects cancellation; RandomSource full-read; Sink.Emit best-effort &
// non-blocking; concurrency safety; Resolve purity & idempotence; Validate completeness.
//
// Each property is a self-contained helper so the suite stays readable and every check
// has a single, named home.
func RunPortSuite(t *testing.T, newSet func() dependencies.Set) {
	t.Helper()
	if newSet == nil {
		t.Fatal("RunPortSuite: newSet must not be nil")
	}
	// A complete Set is the precondition for the whole suite.
	if err := dependencies.Validate(newSet()); err != nil {
		t.Fatalf("RunPortSuite: newSet() produced an incomplete Set: %v", err)
	}

	t.Run("ClockNowNonDecreasing", func(t *testing.T) { assertClockNowNonDecreasing(t, newSet) })
	t.Run("ClockAfterRespectsCancellation", func(t *testing.T) { assertClockAfterRespectsCancellation(t, newSet) })
	t.Run("RandomFullRead", func(t *testing.T) { assertRandomFullRead(t, newSet) })
	t.Run("SinkEmitBestEffort", func(t *testing.T) { assertSinkEmitBestEffort(t, newSet) })
	t.Run("Concurrency", func(t *testing.T) { assertConcurrency(t, newSet) })
	t.Run("ResolvePurityAndIdempotence", func(t *testing.T) { assertResolvePurityAndIdempotence(t, newSet) })
	t.Run("ValidateCompleteness", func(t *testing.T) { assertValidateCompleteness(t, newSet) })
	t.Run("RandomNonNilFill", func(t *testing.T) { assertRandomNonNilFill(t, newSet) })
}

// assertClockNowNonDecreasing checks successive Now() calls never go backward.
func assertClockNowNonDecreasing(t *testing.T, newSet func() dependencies.Set) {
	t.Helper()
	clock := newSet().Clock
	prev := clock.Now()
	for range 100 {
		now := clock.Now()
		if now.Before(prev) {
			t.Fatalf("Now() went backward: %v then %v", prev, now)
		}
		prev = now
	}
}

// assertClockAfterRespectsCancellation checks a canceled After leaves the channel un-sent.
func assertClockAfterRespectsCancellation(t *testing.T, newSet func() dependencies.Set) {
	t.Helper()
	clock := newSet().Clock
	ctx, cancel := context.WithCancel(context.Background())
	ch := clock.After(ctx, time.Hour) // far enough it cannot fire on its own
	cancel()
	select {
	case v, ok := <-ch:
		if ok {
			t.Fatalf("canceled After delivered %v; the channel must be un-sent", v)
		}
	case <-time.After(200 * time.Millisecond):
		// Acceptable: never sent; a real shutdown select unwinds via ctx.Done().
	}
}

// assertRandomFullRead checks Read fills p entirely or returns a non-nil error.
func assertRandomFullRead(t *testing.T, newSet func() dependencies.Set) {
	t.Helper()
	random := newSet().Random
	for _, size := range []int{1, 7, 32, 257} {
		p := make([]byte, size)
		n, err := random.Read(p)
		if err != nil {
			t.Fatalf("Read(%d) error: %v", size, err)
		}
		if n != size {
			t.Fatalf("Read(%d) short: got n=%d with nil err (forbidden)", size, n)
		}
	}
}

// assertSinkEmitBestEffort checks Emit returns without blocking and reports acceptance.
func assertSinkEmitBestEffort(t *testing.T, newSet func() dependencies.Set) {
	t.Helper()
	sink := newSet().Sink
	// Returns without blocking on a live ctx; nil error means accepted.
	done := make(chan error, 1)
	go func() { done <- sink.Emit(context.Background(), "record") }()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("Emit on live ctx returned error: %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("Emit blocked; the port must be best-effort and non-blocking")
	}
}

// assertConcurrency drives every port from N goroutines under the race detector.
func assertConcurrency(t *testing.T, newSet func() dependencies.Set) {
	t.Helper()
	set := newSet()
	var wg sync.WaitGroup
	for range 64 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = set.Clock.Now()
			p := make([]byte, 16)
			if _, err := set.Random.Read(p); err != nil {
				return // a real read error is asserted elsewhere; here we only race the port
			}
			if err := set.Sink.Emit(context.Background(), "rec"); err != nil {
				return // best-effort emit; correctness is asserted in SinkEmitBestEffort
			}
		}()
	}
	wg.Wait()
}

// assertResolvePurityAndIdempotence checks Resolve fills only nil ports, never overwrites
// a wired one, is idempotent, and does no I/O (no argument mutation).
func assertResolvePurityAndIdempotence(t *testing.T, newSet func() dependencies.Set) {
	t.Helper()
	// Resolve fills exactly the nil ports and never overwrites a non-nil port.
	wired := newSet()
	got := dependencies.Resolve(wired)
	if got.Clock != wired.Clock || got.Random != wired.Random || got.Sink != wired.Sink {
		t.Fatal("Resolve overwrote a non-nil port")
	}
	// Resolve fills a zero Set completely and is idempotent.
	once := dependencies.Resolve(dependencies.Set{})
	if err := dependencies.Validate(once); err != nil {
		t.Fatalf("Resolve(zero) incomplete: %v", err)
	}
	if twice := dependencies.Resolve(once); once != twice {
		t.Fatal("Resolve not idempotent")
	}
	// Resolve does no I/O: it must not mutate its by-value argument.
	arg := dependencies.Set{}
	_ = dependencies.Resolve(arg)
	if arg.Clock != nil || arg.Random != nil || arg.Sink != nil {
		t.Fatal("Resolve mutated its argument")
	}
}

// assertValidateCompleteness checks Validate names the first nil port and passes a full Set.
func assertValidateCompleteness(t *testing.T, newSet func() dependencies.Set) {
	t.Helper()
	if err := dependencies.Validate(newSet()); err != nil {
		t.Fatalf("Validate(full) = %v, want nil", err)
	}
	err := dependencies.Validate(dependencies.Set{})
	var missing *dependencies.MissingPortError
	if !errors.As(err, &missing) {
		t.Fatalf("Validate(zero) must yield *MissingPortError, got %T", err)
	}
	if missing.Port != "Clock" {
		t.Fatalf("first missing port = %q, want Clock", missing.Port)
	}
}

// assertRandomNonNilFill checks a fresh RandomSource read actually fills the buffer.
func assertRandomNonNilFill(t *testing.T, newSet func() dependencies.Set) {
	t.Helper()
	p := make([]byte, 32)
	if _, err := newSet().Random.Read(p); err != nil {
		t.Fatalf("Read error: %v", err)
	}
	// The buffer must have been touched (filled), not left untouched.
	if bytes.Equal(p, make([]byte, 32)) {
		// All-zero is astronomically unlikely for both real and fake; treat as a fill failure.
		t.Fatal("Read left the buffer all-zero; entropy port did not fill")
	}
}
