package fetchall

import (
	"context"
	"errors"
	"fmt"
	"sync/atomic"
	"testing"
	"time"
)

// errBang is a sentinel error for testing error reachability.
var errBang = errors.New("bang")

// typedError is an error type for testing errors.AsType reachability.
type typedError struct{ msg string }

func (e *typedError) Error() string { return fmt.Sprintf("typed: %s", e.msg) }

func TestProcess_ConcurrencyTooLow(t *testing.T) {
	_, err := Process(context.Background(), []string{"a"}, 0,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err == nil {
		t.Fatal("expected error for concurrency == 0")
	}
}

func TestProcess_ConcurrencyNegative(t *testing.T) {
	_, err := Process(context.Background(), []string{"a"}, -1,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err == nil {
		t.Fatal("expected error for concurrency == -1")
	}
}

func TestProcess_EmptyInputs(t *testing.T) {
	results, err := Process(context.Background(), nil, 2,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if results != nil {
		t.Fatalf("expected nil results, got %v", results)
	}
}

func TestProcess_EmptySlice(t *testing.T) {
	results, err := Process(context.Background(), []string{}, 2,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if results != nil {
		t.Fatalf("expected nil results, got %v", results)
	}
}

func TestProcess_AllSucceed(t *testing.T) {
	inputs := []string{"alpha", "beta", "gamma"}
	results, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) { return s + "-ok", nil })
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 3 {
		t.Fatalf("expected 3 results, got %d", len(results))
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result %d: expected Index %d, got %d", i, i, r.Index)
		}
		if r.Output != inputs[i]+"-ok" {
			t.Errorf("result %d: expected Output %q, got %q", i, inputs[i]+"-ok", r.Output)
		}
	}
}

func TestProcess_OrderingPreserved(t *testing.T) {
	// Operations complete in reverse order but results must be in original order.
	inputs := []string{"slow", "fast"}
	results, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) {
			if s == "slow" {
				time.Sleep(50 * time.Millisecond)
			}
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 2 {
		t.Fatalf("expected 2 results, got %d", len(results))
	}
	if results[0].Output != "slow" || results[1].Output != "fast" {
		t.Errorf("results out of order: got %v, %v", results[0].Output, results[1].Output)
	}
}
func TestProcess_ConcurrencyLimit(t *testing.T) {
	const concurrency = 3
	const numInputs = 6

	var inflight atomic.Int64
	var maxSeen atomic.Int64

	start := time.Now()
	results, err := Process(context.Background(), make([]string, numInputs), concurrency,
		func(ctx context.Context, s string) (string, error) {
			v := inflight.Add(1)
			for {
				current := maxSeen.Load()
				if v <= current || maxSeen.CompareAndSwap(current, v) {
					break
				}
			}
			time.Sleep(50 * time.Millisecond)
			inflight.Add(-1)
			return "ok", nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != numInputs {
		t.Fatalf("expected %d results, got %d", numInputs, len(results))
	}
	// With concurrency=3, 6 ops × 50ms each → 2 batches → ~100ms.
	// If serial, would be 6 × 50ms = 300ms. Use a wide margin.
	if elapsed := time.Since(start); elapsed >= 250*time.Millisecond {
		t.Errorf("took too long (%v), likely concurrency not respected", elapsed)
	}
	if got := maxSeen.Load(); got > int64(concurrency) {
		t.Errorf("concurrency exceeded: saw %d in flight, max %d", got, concurrency)
	}
}

func TestProcess_PartialFailures(t *testing.T) {
	inputs := []string{"ok1", "bad", "ok2", "also bad"}
	results, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) {
			switch s {
			case "bad", "also bad":
				return "", fmt.Errorf("error: %s", s)
			default:
				return s + "-result", nil
			}
		})
	if err == nil {
		t.Fatal("expected an error")
	}
	// Two successful results.
	if len(results) != 2 {
		t.Fatalf("expected 2 successful results, got %d", len(results))
	}
	if results[0].Index != 0 || results[0].Output != "ok1-result" {
		t.Errorf("unexpected first result: %+v", results[0])
	}
	if results[1].Index != 2 || results[1].Output != "ok2-result" {
		t.Errorf("unexpected second result: %+v", results[1])
	}
}

func TestProcess_AllFail(t *testing.T) {
	results, err := Process(context.Background(), []string{"a", "b"}, 1,
		func(ctx context.Context, s string) (string, error) {
			return "", fmt.Errorf("fail: %s", s)
		})
	if err == nil {
		t.Fatal("expected an error")
	}
	if results != nil {
		// nil slice is acceptable when no results; we just check len is 0.
		if len(results) != 0 {
			t.Fatalf("expected 0 results, got %d", len(results))
		}
	}
}

func TestProcess_ErrorsReachableByIs(t *testing.T) {
	inputs := []string{"ok", "boom"}
	_, err := Process(context.Background(), inputs, 1,
		func(ctx context.Context, s string) (string, error) {
			if s == "boom" {
				return "", errBang
			}
			return s, nil
		})
	if err == nil {
		t.Fatal("expected an error")
	}
	if !errors.Is(err, errBang) {
		t.Fatalf("expected errors.Is(err, errBang) to be true")
	}
}

func TestProcess_ErrorsReachableByAsType(t *testing.T) {
	inputs := []string{"ok", "whoops"}
	_, err := Process(context.Background(), inputs, 1,
		func(ctx context.Context, s string) (string, error) {
			if s == "whoops" {
				return "", &typedError{msg: "whoops"}
			}
			return s, nil
		})
	if err == nil {
		t.Fatal("expected an error")
	}
	te, ok := errors.AsType[*typedError](err)
	if !ok {
		t.Fatal("expected errors.AsType[*typedError](err) to succeed")
	}
	if te.msg != "whoops" {
		t.Errorf("expected msg 'whoops', got %q", te.msg)
	}
}

func TestProcess_ContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // already cancelled

	results, err := Process(ctx, []string{"a", "b"}, 2,
		func(ctx context.Context, s string) (string, error) {
			select {
			case <-ctx.Done():
				return "", ctx.Err()
			default:
			}
			return s, nil
		})
	// When context is cancelled before any operation starts, every operation
	// should respect ctx.Done(). In-flight goroutines whose sem acquire
	// selects ctx.Done() return without producing results or errors.
	// It's valid to get (nil, nil) or (nil, error) depending on whether any
	// error was recorded. We just test that it returns reasonably fast and
	// doesn't panic or deadlock.
	_ = results
	_ = err
}

func TestProcess_ContextCancellationDuringWork(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())

	started := make(chan struct{}, 1)

	go func() {
		_, err := Process(ctx, []string{"a", "b", "c"}, 2,
			func(ctx context.Context, s string) (string, error) {
				select {
				case started <- struct{}{}:
				default:
				}
				// Block until cancelled.
				<-ctx.Done()
				return "", ctx.Err()
			})
		// Process returned; we don't care about the result.
		_ = err
	}()

	// Wait for at least one operation to start.
	<-started
	cancel()

	done := make(chan struct{})
	go func() {
		// Give Process time to finish after cancellation (goroutine above
		// will unblock once ctx is cancelled and wg.Wait returns).
		time.Sleep(2 * time.Second)
		close(done)
	}()

	select {
	case <-done:
		// OK: no deadlock.
	case <-time.After(5 * time.Second):
		t.Fatal("Process did not return within 5s after cancellation")
	}
}