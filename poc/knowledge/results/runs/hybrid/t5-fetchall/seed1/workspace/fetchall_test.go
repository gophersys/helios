package fetchall

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

var errSentinel = errors.New("sentinel")

func TestProcess_EmptyInputs(t *testing.T) {
	t.Parallel()
	results, err := Process(context.Background(), nil, 5, nil)
	if results != nil || err != nil {
		t.Fatalf("nil inputs: expected (nil, nil), got (%v, %v)", results, err)
	}
	results, err = Process(context.Background(), []string{}, 5, nil)
	if results != nil || err != nil {
		t.Fatalf("empty inputs: expected (nil, nil), got (%v, %v)", results, err)
	}
}

func TestProcess_InvalidConcurrency(t *testing.T) {
	t.Parallel()
	_, err := Process(context.Background(), []string{"a"}, 0, nil)
	if err == nil {
		t.Fatal("expected error for concurrency=0")
	}
	_, err = Process(context.Background(), []string{"a"}, -1, nil)
	if err == nil {
		t.Fatal("expected error for concurrency=-1")
	}
}

func TestProcess_Success(t *testing.T) {
	t.Parallel()
	inputs := []string{"a", "b", "c", "d", "e"}
	results, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) {
			return s + "!", nil
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
		if r.Output != inputs[i]+"!" {
			t.Errorf("result %d has Output=%q, want %q", i, r.Output, inputs[i]+"!")
		}
	}
}

func TestProcess_ResultsOrderedByIndex(t *testing.T) {
	t.Parallel()
	// Operations take variable time so they finish out of order.
	inputs := []string{"slow", "fast", "medium"}
	var mu sync.Mutex
	delays := map[string]time.Duration{
		"slow":   50 * time.Millisecond,
		"fast":   5 * time.Millisecond,
		"medium": 20 * time.Millisecond,
	}
	results, err := Process(context.Background(), inputs, 3,
		func(ctx context.Context, s string) (string, error) {
			mu.Lock()
			d := delays[s]
			mu.Unlock()
			time.Sleep(d)
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 3 {
		t.Fatalf("got %d results, want 3", len(results))
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result %d has Index=%d, want %d", i, r.Index, i)
		}
		if r.Output != inputs[i] {
			t.Errorf("result %d has Output=%q, want %q", i, r.Output, inputs[i])
		}
	}
}

func TestProcess_PartialFailures(t *testing.T) {
	t.Parallel()
	var errFail1 = errors.New("fail1")
	var errFail2 = errors.New("fail2")

	inputs := []string{"ok1", "fail1", "ok2", "fail2", "ok3"}
	results, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) {
			switch s {
			case "fail1":
				return "", errFail1
			case "fail2":
				return "", errFail2
			default:
				return s, nil
			}
		})
	if err == nil {
		t.Fatal("expected aggregated error")
	}
	if len(results) != 3 {
		t.Fatalf("got %d results, want 3", len(results))
	}
	expected := []struct {
		idx    int
		output string
	}{
		{0, "ok1"},
		{2, "ok2"},
		{4, "ok3"},
	}
	for i, r := range results {
		if r.Index != expected[i].idx {
			t.Errorf("result %d: Index=%d, want %d", i, r.Index, expected[i].idx)
		}
		if r.Output != expected[i].output {
			t.Errorf("result %d: Output=%q, want %q", i, r.Output, expected[i].output)
		}
	}
	// Each individual sentinel must be reachable via errors.Is.
	if !errors.Is(err, errFail1) {
		t.Errorf("errors.Is(err, errFail1) failed on aggregated error: %v", err)
	}
	if !errors.Is(err, errFail2) {
		t.Errorf("errors.Is(err, errFail2) failed on aggregated error: %v", err)
	}
}

func TestProcess_AllFailures(t *testing.T) {
	t.Parallel()
	inputs := []string{"x", "y", "z"}
	results, err := Process(context.Background(), inputs, 2,
		func(ctx context.Context, s string) (string, error) {
			return "", errSentinel
		})
	if err == nil {
		t.Fatal("expected aggregated error")
	}
	if len(results) != 0 {
		t.Fatalf("expected 0 results, got %d", len(results))
	}
	// errors.Is must work on the aggregated error for errSentinel.
	if !errors.Is(err, errSentinel) {
		t.Fatalf("errors.Is(err, errSentinel) failed on aggregated error: %v", err)
	}
}

func TestProcess_ContextCancellation(t *testing.T) {
	t.Parallel()
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // immediately cancelled

	// Even though context is already cancelled, Process should run all
	// operations; each operation will see the cancelled context.
	inputs := []string{"a", "b", "c"}
	results, err := Process(ctx, inputs, 2,
		func(ctx context.Context, s string) (string, error) {
			return "", ctx.Err()
		})
	if err == nil {
		t.Fatal("expected aggregated error from cancelled context")
	}
	if len(results) != 0 {
		t.Fatalf("expected 0 results, got %d", len(results))
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

func TestProcess_ConcurrencyLimit(t *testing.T) {
	t.Parallel()
	const concurrency = 3
	const totalInputs = 12

	var inFlight atomic.Int64
	var maxInFlight atomic.Int64

	results, err := Process(context.Background(), make([]string, totalInputs), concurrency,
		func(ctx context.Context, s string) (string, error) {
			n := inFlight.Add(1)
			defer inFlight.Add(-1)
			for prev := maxInFlight.Load(); n > prev; {
				if maxInFlight.CompareAndSwap(prev, n) {
					break
				}
				prev = maxInFlight.Load()
			}
			time.Sleep(10 * time.Millisecond) // ensure overlap
			return "ok", nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != totalInputs {
		t.Fatalf("got %d results, want %d", len(results), totalInputs)
	}
	if got := maxInFlight.Load(); got > int64(concurrency) {
		t.Fatalf("max concurrency was %d, want <= %d", got, concurrency)
	}
}
