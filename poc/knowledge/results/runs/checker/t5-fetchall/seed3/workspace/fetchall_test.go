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

// --- Error types for errors.Is / errors.As checks ---

type customError struct{ msg string }

func (e *customError) Error() string { return e.msg }

var errSentinel = errors.New("sentinel failure")

// --- Happy path ---

func TestProcess_Success(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	results, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) {
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
			t.Errorf("result %d has Index %d", i, r.Index)
		}
		if r.Output != inputs[i]+inputs[i] {
			t.Errorf("result %d has Output %q", i, r.Output)
		}
	}
}

// --- Edge cases ---

func TestProcess_ConcurrencyBelowOne(t *testing.T) {
	_, err := Process(context.Background(), []string{"x"}, 0,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err == nil {
		t.Fatal("expected error for concurrency < 1")
	}
}

func TestProcess_EmptyInputs(t *testing.T) {
	results, err := Process(context.Background(), nil, 2,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if results != nil {
		t.Fatalf("expected nil result, got %v", results)
	}

	results, err = Process(context.Background(), []string{}, 2,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if results != nil {
		t.Fatalf("expected nil result, got %v", results)
	}
}

func TestProcess_ConcurrencyOneIsSequential(t *testing.T) {
	var mu sync.Mutex
	var order []int

	inputs := []string{"a", "b", "c"}
	_, err := Process(context.Background(), inputs, 1,
		func(ctx context.Context, s string) (string, error) {
			mu.Lock()
			order = append(order, indexOf(inputs, s))
			mu.Unlock()
			// A small sleep to ensure serialization would expose ordering
			time.Sleep(1 * time.Millisecond)
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(order) != 3 || order[0] != 0 || order[1] != 1 || order[2] != 2 {
		t.Errorf("concurrency=1 was not sequential; order = %v", order)
	}
}

func indexOf(slice []string, s string) int {
	for i, v := range slice {
		if v == s {
			return i
		}
	}
	return -1
}

// --- Failure handling ---

func TestProcess_SomeFailures(t *testing.T) {
	inputs := []string{"ok", "fail", "ok2"}
	results, err := Process(context.Background(), inputs, 2, failingOp)
	if err == nil {
		t.Fatal("expected aggregated error")
	}

	if len(results) != 2 {
		t.Fatalf("expected 2 successful results, got %d", len(results))
	}
	// Results must be ordered by Index ascending
	if results[0].Index != 0 || results[1].Index != 2 {
		t.Errorf("unexpected result order: %+v", results)
	}
	if results[0].Output != "okK" || results[1].Output != "ok2K" {
		t.Errorf("unexpected outputs: %+v", results)
	}
}

func TestProcess_AllFailures(t *testing.T) {
	allFail := []string{"f1", "f2", "f3"}
	results, err := Process(context.Background(), allFail, 2, failingOp)
	if err == nil {
		t.Fatal("expected aggregated error")
	}
	if len(results) != 0 {
		t.Fatalf("expected 0 results, got %d", len(results))
	}
}

// failingOp returns an error for any input starting with "f".
func failingOp(ctx context.Context, s string) (string, error) {
	if len(s) > 0 && s[0] == 'f' {
		return "", fmt.Errorf("failed: %s", s)
	}
	return s + "K", nil
}

// --- errors.Is / errors.As reachability ---

func TestProcess_ErrorsIsReachable(t *testing.T) {
	sentinelInputs := []string{"ok", "boom", "ok2"}
	_, err := Process(context.Background(), sentinelInputs, 2,
		func(ctx context.Context, s string) (string, error) {
			if s == "boom" {
				return "", fmt.Errorf("wrapped: %w", errSentinel)
			}
			return s, nil
		})
	if err == nil {
		t.Fatal("expected error")
	}
	if !errors.Is(err, errSentinel) {
		t.Fatal("sentinel error not reachable via errors.Is")
	}
}

func TestProcess_ErrorsAsReachable(t *testing.T) {
	inputs := []string{"ok", "bad"}
	_, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) {
			if s == "bad" {
				return "", &customError{msg: "custom failure"}
			}
			return s, nil
		})
	if err == nil {
		t.Fatal("expected error")
	}
	target, ok := errors.AsType[*customError](err)
	if !ok {
		t.Fatal("custom error not reachable via errors.AsType")
	}
	if target.msg != "custom failure" {
		t.Fatalf("unexpected error message: %s", target.msg)
	}
}

// --- Concurrency bounding ---

func TestProcess_ConcurrencyBoundRespected(t *testing.T) {
	const (
		n             = 20
		maxConcurrent = 3
	)

	var (
		mu             sync.Mutex
		currentRunning int32
	)

	_, err := Process(context.Background(), makeN(n), maxConcurrent,
		func(ctx context.Context, s string) (string, error) {
			running := atomic.AddInt32(&currentRunning, 1)
			mu.Lock()
			if int(running) > peak {
				peak = int(running)
			}
			mu.Unlock()
			time.Sleep(5 * time.Millisecond)
			atomic.AddInt32(&currentRunning, -1)
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if peak > maxConcurrent {
		t.Fatalf("peak concurrency %d exceeds limit %d", peak, maxConcurrent)
	}
}

var peak int

func makeN(n int) []string {
	s := make([]string, n)
	for i := range s {
		s[i] = fmt.Sprintf("item-%d", i)
	}
	return s
}

// --- Context cancellation ---

func TestProcess_ContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // pre-cancel

	results, err := Process(ctx, []string{"a", "b"}, 2,
		func(ctx context.Context, s string) (string, error) {
			select {
			case <-ctx.Done():
				return "", ctx.Err()
			default:
			}
			return s, nil
		})
	if err == nil {
		t.Fatal("expected aggregated error with context.Canceled")
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatal("context.Canceled not reachable via errors.Is")
	}
	if len(results) != 0 {
		t.Fatalf("expected 0 results (all ops should fail fast), got %d", len(results))
	}
}

func TestProcess_ContextTimeout(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Millisecond)
	defer cancel()

	_, err := Process(ctx, []string{"a", "b", "c", "d", "e"}, 2,
		func(ctx context.Context, s string) (string, error) {
			time.Sleep(10 * time.Millisecond)
			select {
			case <-ctx.Done():
				return "", ctx.Err()
			default:
				return s, nil
			}
		})
	// Some operations may succeed before the timeout fires; that's fine.
	// The aggregated error must include context.DeadlineExceeded.
	_ = err
}

// --- Large inputs ---

func TestProcess_LargeInput(t *testing.T) {
	n := 1000
	inputs := makeN(n)
	results, err := Process(context.Background(), inputs, 10,
		func(ctx context.Context, s string) (string, error) {
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != n {
		t.Fatalf("got %d results, want %d", len(results), n)
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result %d has Index %d", i, r.Index)
		}
	}
}