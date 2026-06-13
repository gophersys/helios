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
func RunPortSuite(t *testing.T, newSet func() dependencies.Set) {
	t.Helper()
	if newSet == nil {
		t.Fatal("RunPortSuite: newSet must not be nil")
	}
	// A complete Set is the precondition for the whole suite.
	if err := dependencies.Validate(newSet()); err != nil {
		t.Fatalf("RunPortSuite: newSet() produced an incomplete Set: %v", err)
	}

	t.Run("ClockNowNonDecreasing", func(t *testing.T) {
		clock := newSet().Clock
		prev := clock.Now()
		for i := 0; i < 100; i++ {
			now := clock.Now()
			if now.Before(prev) {
				t.Fatalf("Now() went backward: %v then %v", prev, now)
			}
			prev = now
		}
	})

	t.Run("ClockAfterRespectsCancellation", func(t *testing.T) {
		clock := newSet().Clock
		ctx, cancel := context.WithCancel(context.Background())
		ch := clock.After(ctx, time.Hour) // far enough it cannot fire on its own
		cancel()
		select {
		case v, ok := <-ch:
			if ok {
				t.Fatalf("cancelled After delivered %v; the channel must be un-sent", v)
			}
		case <-time.After(200 * time.Millisecond):
			// Acceptable: never sent; a real shutdown select unwinds via ctx.Done().
		}
	})

	t.Run("RandomFullRead", func(t *testing.T) {
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
	})

	t.Run("SinkEmitBestEffort", func(t *testing.T) {
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
	})

	t.Run("Concurrency", func(t *testing.T) {
		set := newSet()
		var wg sync.WaitGroup
		for i := 0; i < 64; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				_ = set.Clock.Now()
				p := make([]byte, 16)
				_, _ = set.Random.Read(p)
				_ = set.Sink.Emit(context.Background(), "rec")
			}()
		}
		wg.Wait()
	})

	t.Run("ResolvePurityAndIdempotence", func(t *testing.T) {
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
	})

	t.Run("ValidateCompleteness", func(t *testing.T) {
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
	})

	// Determinism sanity: a fresh RandomSource read of a fixed size is well-formed.
	t.Run("RandomNonNilFill", func(t *testing.T) {
		p := make([]byte, 32)
		if _, err := newSet().Random.Read(p); err != nil {
			t.Fatalf("Read error: %v", err)
		}
		// The buffer must have been touched (filled), not left untouched.
		if bytes.Equal(p, make([]byte, 32)) {
			// All-zero is astronomically unlikely for both real and fake; treat as a fill failure.
			t.Fatal("Read left the buffer all-zero; entropy port did not fill")
		}
	})
}
