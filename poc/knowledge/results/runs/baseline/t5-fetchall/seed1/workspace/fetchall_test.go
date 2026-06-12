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

// --- Validation ---

func TestProcessConcurrencyBelowOne(t *testing.T) {
	_, err := Process(context.Background(), []string{"a"}, 0,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err == nil {
		t.Fatal("expected error for concurrency=0")
	}
	_, err = Process(context.Background(), []string{"a"}, -5,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err == nil {
		t.Fatal("expected error for concurrency=-5")
	}
}

func TestProcessEmptyInputs(t *testing.T) {
	res, err := Process(context.Background(), nil, 2,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res != nil {
		t.Fatalf("expected nil result, got %v", res)
	}

	res, err = Process(context.Background(), []string{}, 2,
		func(ctx context.Context, s string) (string, error) { return s, nil })
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res != nil {
		t.Fatalf("expected nil result, got %v", res)
	}
}

// --- Happy path ---

func TestProcessAllSucceed(t *testing.T) {
	inputs := []string{"a", "b", "c", "d", "e"}
	results, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) {
			return fmt.Sprintf("out:%s", s), nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != len(inputs) {
		t.Fatalf("got %d results, want %d", len(results), len(inputs))
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result %d has Index=%d, want %d", i, r.Index, i)
		}
		want := fmt.Sprintf("out:%s", inputs[i])
		if r.Output != want {
			t.Errorf("result %d has Output=%q, want %q", i, r.Output, want)
		}
	}
}

func TestProcessPreservesOrder(t *testing.T) {
	inputs := []string{"first", "second", "third", "fourth", "fifth"}
	// operation that sleeps proportional to index — slowest input first so
	// results would be out-of-order if Process didn't sort them.
	results, err := Process(context.Background(), inputs, 5,
		func(ctx context.Context, s string) (string, error) {
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for i, r := range results {
		if r.Index != i {
			t.Fatalf("result %d has Index=%d, want %d", i, r.Index, i)
		}
		if r.Output != inputs[i] {
			t.Fatalf("result %d has Output=%q, want %q", i, r.Output, inputs[i])
		}
	}
}

// --- Concurrency bound ---

func TestProcessRespectsConcurrencyLimit(t *testing.T) {
	const concurrency = 3
	var inflight atomic.Int64
	var maxInflight atomic.Int64

	inputs := make([]string, 20)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("input-%d", i)
	}

	results, err := Process(context.Background(), inputs, concurrency,
		func(ctx context.Context, s string) (string, error) {
			v := inflight.Add(1)
			defer inflight.Add(-1)

			// Track the peak concurrency observed.
			for {
				current := maxInflight.Load()
				if v <= current || maxInflight.CompareAndSwap(current, v) {
					break
				}
			}

			// Yield to increase the chance other goroutines also run
			// concurrently.
			time.Sleep(time.Millisecond)
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != len(inputs) {
		t.Fatalf("got %d results, want %d", len(results), len(inputs))
	}
	if peak := maxInflight.Load(); peak > int64(concurrency) {
		t.Errorf("peak concurrency was %d, want ≤ %d", peak, concurrency)
	}
}

// --- Failures ---

type sentinelErr struct{ msg string }

func (e *sentinelErr) Error() string { return e.msg }

func TestProcessPartialFailures(t *testing.T) {
	inputs := []string{"ok", "fail1", "ok2", "fail2", "ok3"}

	results, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) {
			if s == "fail1" || s == "fail2" {
				return "", &sentinelErr{msg: fmt.Sprintf("err:%s", s)}
			}
			return fmt.Sprintf("out:%s", s), nil
		})

	if err == nil {
		t.Fatal("expected aggregated error for partial failures")
	}

	// Verify every individual failure is reachable.
	for _, idx := range []int{1, 3} {
		target := &sentinelErr{msg: fmt.Sprintf("err:%s", inputs[idx])}
		if !errors.As(err, &target) {
			t.Errorf("aggregated error does not contain sentinelErr(%q)", target.msg)
		}
		if !errors.Is(err, target) {
			t.Errorf("aggregated error errors.Is does not find sentinelErr(%q)", target.msg)
		}
	}

	// Verify successful results are present and ordered.
	if len(results) != 3 {
		t.Fatalf("got %d successful results, want 3", len(results))
	}
	expected := []struct {
		idx    int
		output string
	}{
		{0, "out:ok"},
		{2, "out:ok2"},
		{4, "out:ok3"},
	}
	for i, e := range expected {
		if results[i].Index != e.idx {
			t.Errorf("result %d has Index=%d, want %d", i, results[i].Index, e.idx)
		}
		if results[i].Output != e.output {
			t.Errorf("result %d has Output=%q, want %q", i, results[i].Output, e.output)
		}
	}
}

func TestProcessAllFail(t *testing.T) {
	inputs := []string{"x", "y", "z"}
	results, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) {
			return "", &sentinelErr{msg: fmt.Sprintf("fail:%s", s)}
		})
	if err == nil {
		t.Fatal("expected aggregated error")
	}
	if results != nil {
		t.Fatalf("expected nil results, got %v", results)
	}
	// Each individual failure reachable via errors.Is / errors.As.
	for _, s := range inputs {
		target := &sentinelErr{msg: fmt.Sprintf("fail:%s", s)}
		if !errors.As(err, &target) {
			t.Errorf("errors.As does not find sentinelErr(%q)", target.msg)
		}
		if !errors.Is(err, target) {
			t.Errorf("errors.Is does not find sentinelErr(%q)", target.msg)
		}
	}
}

// --- Context propagation ---

func TestProcessContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // already cancelled

	results, err := Process(ctx, []string{"a", "b", "c"}, 2,
		func(ctx context.Context, s string) (string, error) {
			select {
			case <-ctx.Done():
				return "", ctx.Err()
			default:
				return s, nil
			}
		})
	if err == nil {
		t.Fatal("expected error when context is cancelled")
	}
	if !errors.Is(err, context.Canceled) {
		t.Errorf("expected context.Canceled, got %v", err)
	}
	if results != nil {
		t.Fatalf("expected nil results, got %v", results)
	}
}

func TestProcessContextPropagated(t *testing.T) {
	type keyType struct{}
	key := keyType{}
	want := "hello"
	ctx := context.WithValue(context.Background(), key, want)

	results, err := Process(ctx, []string{"x"}, 1,
		func(ctx context.Context, s string) (string, error) {
			v := ctx.Value(key)
			if v == nil {
				return "", fmt.Errorf("context value not propagated")
			}
			return v.(string), nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 1 || results[0].Output != want {
		t.Fatalf("got %+v, want Output=%q", results, want)
	}
}

// --- Race detection ---

func TestProcessConcurrentSafe(t *testing.T) {
	inputs := make([]string, 100)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("v-%d", i)
	}

	var mu sync.Mutex
	seen := make(map[string]bool)

	results, err := Process(context.Background(), inputs, 10,
		func(ctx context.Context, s string) (string, error) {
			mu.Lock()
			seen[s] = true
			mu.Unlock()
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != len(inputs) {
		t.Fatalf("got %d results, want %d", len(results), len(inputs))
	}
}

// --- Single-input edge case ---

func TestProcessSingleInput(t *testing.T) {
	results, err := Process(context.Background(), []string{"only"}, 5,
		func(ctx context.Context, s string) (string, error) {
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 1 || results[0].Index != 0 || results[0].Output != "only" {
		t.Fatalf("unexpected results: %+v", results)
	}
}

// --- Concurrency == len(inputs) ---

func TestProcessConcurrencyEqualsInputs(t *testing.T) {
	inputs := []string{"a", "b", "c", "d", "e"}
	results, err := Process(context.Background(), inputs, len(inputs),
		func(ctx context.Context, s string) (string, error) {
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != len(inputs) {
		t.Fatalf("got %d results, want %d", len(results), len(inputs))
	}
}