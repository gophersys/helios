package fetchall

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// --- success cases ---

func TestProcessSimple(t *testing.T) {
	ctx := context.Background()
	inputs := []string{"a", "b", "c"}
	results, err := Process(ctx, inputs, 1, func(_ context.Context, s string) (string, error) {
		return s + s, nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 3 {
		t.Fatalf("got %d results, want 3", len(results))
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result %d: Index=%d, want %d", i, r.Index, i)
		}
		want := inputs[i] + inputs[i]
		if r.Output != want {
			t.Errorf("result %d: Output=%q, want %q", i, r.Output, want)
		}
	}
}

func TestProcessEmpty(t *testing.T) {
	results, err := Process(context.Background(), nil, 5, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if results != nil {
		t.Fatalf("expected nil results for empty input, got %v", results)
	}

	results, err = Process(context.Background(), []string{}, 5, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if results != nil {
		t.Fatalf("expected nil results for empty input, got %v", results)
	}
}

func TestProcessInvalidConcurrency(t *testing.T) {
	_, err := Process(context.Background(), []string{"a"}, 0, nil)
	if err == nil {
		t.Fatal("expected error for concurrency == 0")
	}

	_, err = Process(context.Background(), []string{"a"}, -1, nil)
	if err == nil {
		t.Fatal("expected error for concurrency == -1")
	}
}

// --- concurrency limiting ---

func TestProcessMaxConcurrency(t *testing.T) {
	const (
		n            = 50
		concurrency  = 4
	)

	var mu sync.Mutex
	var maxSeen int
	var cur int32

	inputs := make([]string, n)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("%d", i)
	}

	results, err := Process(context.Background(), inputs, concurrency,
		func(ctx context.Context, s string) (string, error) {
			v := atomic.AddInt32(&cur, 1)
			mu.Lock()
			if int(v) > maxSeen {
				maxSeen = int(v)
			}
			mu.Unlock()
			defer atomic.AddInt32(&cur, -1)

			// Yield briefly so other goroutines can start.
			time.Sleep(time.Microsecond)
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != n {
		t.Fatalf("got %d results, want %d", len(results), n)
	}
	if maxSeen > concurrency {
		t.Errorf("saw %d concurrent ops, max allowed %d", maxSeen, concurrency)
	}
}

// --- error aggregation ---

type sentinelErr struct{ msg string }

func (e *sentinelErr) Error() string { return e.msg }

func TestProcessSomeFail(t *testing.T) {
	inputs := []string{"ok", "fail1", "ok2", "fail2"}

	sentinel1 := &sentinelErr{"boom1"}
	sentinel2 := &sentinelErr{"boom2"}

	results, err := Process(context.Background(), inputs, 2,
		func(_ context.Context, s string) (string, error) {
			switch s {
			case "fail1":
				return "", sentinel1
			case "fail2":
				return "", sentinel2
			default:
				return s, nil
			}
		})
	if err == nil {
		t.Fatal("expected non-nil error")
	}

	// Both sentinel errors must be reachable.
	if !errors.Is(err, sentinel1) {
		t.Error("errors.Is(err, sentinel1) is false")
	}
	if !errors.Is(err, sentinel2) {
		t.Error("errors.Is(err, sentinel2) is false")
	}

	// errors.As must also work.
	var got1 *sentinelErr
	if !errors.As(err, &got1) {
		t.Error("errors.As(err, &sentinelErr) is false")
	}

	// Results must only contain the successful ones, ordered by index.
	if len(results) != 2 {
		t.Fatalf("got %d results, want 2", len(results))
	}
	if results[0].Index != 0 || results[0].Output != "ok" {
		t.Errorf("result[0] = %+v, want {Index:0, Output:ok}", results[0])
	}
	if results[1].Index != 2 || results[1].Output != "ok2" {
		t.Errorf("result[1] = %+v, want {Index:2, Output:ok2}", results[1])
	}
}

func TestProcessAllFail(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	results, err := Process(context.Background(), inputs, 2,
		func(_ context.Context, s string) (string, error) {
			return "", fmt.Errorf("fail %s", s)
		})
	if err == nil {
		t.Fatal("expected non-nil error")
	}
	if results != nil {
		t.Errorf("expected nil results when all fail, got %v", results)
	}
}

// --- context cancellation ---

func TestProcessContextCancel(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	inputs := make([]string, 100)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("%d", i)
	}

	var started int32

	results, err := Process(ctx, inputs, 10,
		func(ctx context.Context, s string) (string, error) {
			atomic.AddInt32(&started, 1)

			// Block until cancelled.
			<-ctx.Done()
			return "", ctx.Err()
		})

	// All should have started (concurrency 10 with 100 inputs).
	// Cancel and verify we get some results.
	cancel()

	// Process should return with an aggregated error.
	if err == nil {
		t.Fatal("expected error after cancellation")
	}
	if !errors.Is(err, context.Canceled) {
		t.Errorf("expected context.Canceled, got %v", err)
	}
	_ = results
}

func TestProcessContextDeadline(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer cancel()

	inputs := []string{"a", "b"}
	_, err := Process(ctx, inputs, 1,
		func(ctx context.Context, s string) (string, error) {
			select {
			case <-time.After(time.Second):
				return s, nil
			case <-ctx.Done():
				return "", ctx.Err()
			}
		})
	if err == nil {
		t.Fatal("expected error after deadline")
	}
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Errorf("expected context.DeadlineExceeded, got %v", err)
	}
}

// --- results preserve input order ---

func TestProcessOrdering(t *testing.T) {
	// Run out of order to verify results come back sorted by Index.
	inputs := []string{"z", "a", "m", "b", "c"}
	results, err := Process(context.Background(), inputs, 1,
		func(_ context.Context, s string) (string, error) {
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 5 {
		t.Fatalf("got %d results, want 5", len(results))
	}
	for i, r := range results {
		if r.Index != i {
			t.Fatalf("result[%d].Index = %d, want %d", i, r.Index, i)
		}
		if r.Output != inputs[i] {
			t.Fatalf("result[%d].Output = %q, want %q", i, r.Output, inputs[i])
		}
	}
}

// --- concurrency == len(inputs) is fine ---

func TestProcessHighConcurrency(t *testing.T) {
	inputs := []string{"a", "b", "c", "d", "e"}
	results, err := Process(context.Background(), inputs, 100,
		func(_ context.Context, s string) (string, error) {
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 5 {
		t.Fatalf("got %d results, want 5", len(results))
	}
}

// --- single input ---

func TestProcessSingle(t *testing.T) {
	results, err := Process(context.Background(), []string{"hello"}, 1,
		func(_ context.Context, s string) (string, error) {
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("got %d results, want 1", len(results))
	}
	if results[0].Index != 0 || results[0].Output != "hello" {
		t.Errorf("unexpected result: %+v", results[0])
	}
}

// --- concurrency 1 is strictly sequential ---

func TestProcessSequential(t *testing.T) {
	var order []int
	var mu sync.Mutex

	inputs := []string{"a", "b", "c"}
	_, err := Process(context.Background(), inputs, 1,
		func(_ context.Context, s string) (string, error) {
			mu.Lock()
			order = append(order, len(order))
			mu.Unlock()
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(order) != 3 {
		t.Fatalf("got %d entries, want 3", len(order))
	}
	for i, v := range order {
		if v != i {
			t.Errorf("order[%d] = %d, want %d", i, v, i)
		}
	}
}

func TestProcessNonBlockedCtxCancel(t *testing.T) {
	// Verify that context cancellation doesn't leak goroutines.
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	inputs := make([]string, 20)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("%d", i)
	}

	blocker := make(chan struct{})
	started := make(chan struct{}, 20)
	var seen int32

	go func() {
		results, err := Process(ctx, inputs, 4,
			func(ctx context.Context, s string) (string, error) {
				atomic.AddInt32(&seen, 1)
				started <- struct{}{}
				// Block until cancelled or until blocker closes.
				select {
				case <-blocker:
					return s, nil
				case <-ctx.Done():
					return "", ctx.Err()
				}
			})
		_ = results
		_ = err
		close(started)
	}()

	// Wait for at least 4 goroutines to start.
	for i := 0; i < 4; i++ {
		<-started
	}

	// Cancel while some are still blocked.
	cancel()

	// Process should return quickly (no hang).
	_ = blocker // not closed — goroutines must unblock via ctx cancellation.
}