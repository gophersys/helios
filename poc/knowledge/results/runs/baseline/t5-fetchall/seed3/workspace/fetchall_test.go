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

// ---------------------------------------------------------------------------
// Success cases
// ---------------------------------------------------------------------------

func TestProcess_Success(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	op := func(_ context.Context, s string) (string, error) {
		return s + s, nil
	}
	results, err := Process(context.Background(), inputs, 2, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 3 {
		t.Fatalf("got %d results, want 3", len(results))
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result %d has Index %d, want %d", i, r.Index, i)
		}
		want := inputs[i] + inputs[i]
		if r.Output != want {
			t.Errorf("result %d has Output %q, want %q", i, r.Output, want)
		}
	}
}

func TestProcess_ResultsOrderedByIndex(t *testing.T) {
	// Operation that returns out-of-order results by sleeping proportional to
	// input length. The returned slice must still be ordered by Index.
	inputs := []string{"ccc", "bb", "a"}
	op := func(_ context.Context, s string) (string, error) {
		time.Sleep(time.Duration(len(s)) * 10 * time.Millisecond)
		return s, nil
	}
	results, err := Process(context.Background(), inputs, 3, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for i, r := range results {
		if r.Index != i {
			t.Fatalf("result %d has Index %d, want %d", i, r.Index, i)
		}
	}
}

func TestProcess_SingleInput(t *testing.T) {
	results, err := Process(context.Background(), []string{"x"}, 1,
		func(_ context.Context, s string) (string, error) {
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 1 || results[0].Output != "x" {
		t.Fatalf("got %+v, want [{0 x}]", results)
	}
}

func TestProcess_ConcurrencyGreaterThanInputs(t *testing.T) {
	inputs := []string{"a", "b"}
	results, err := Process(context.Background(), inputs, 10,
		func(_ context.Context, s string) (string, error) {
			return s, nil
		})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 2 {
		t.Fatalf("got %d results, want 2", len(results))
	}
}

// ---------------------------------------------------------------------------
// Error cases
// ---------------------------------------------------------------------------

func TestProcess_ConcurrencyLessThanOne(t *testing.T) {
	_, err := Process(context.Background(), []string{"a"}, 0,
		func(_ context.Context, s string) (string, error) {
			return s, nil
		})
	if err == nil {
		t.Fatal("expected error for concurrency < 1")
	}
}

func TestProcess_ConcurrencyNegative(t *testing.T) {
	_, err := Process(context.Background(), []string{"a"}, -5,
		func(_ context.Context, s string) (string, error) {
			return s, nil
		})
	if err == nil {
		t.Fatal("expected error for concurrency < 1")
	}
}

func TestProcess_EmptyInputs(t *testing.T) {
	results, err := Process(context.Background(), nil, 2,
		func(_ context.Context, s string) (string, error) {
			return s, nil
		})
	if results != nil || err != nil {
		t.Fatalf("expected (nil, nil), got (%v, %v)", results, err)
	}
}

func TestProcess_EmptySliceInputs(t *testing.T) {
	results, err := Process(context.Background(), []string{}, 2,
		func(_ context.Context, s string) (string, error) {
			return s, nil
		})
	if results != nil || err != nil {
		t.Fatalf("expected (nil, nil), got (%v, %v)", results, err)
	}
}

func TestProcess_SomeFailures(t *testing.T) {
	inputs := []string{"ok", "fail", "ok2"}
	op := func(_ context.Context, s string) (string, error) {
		if s == "fail" {
			return "", errors.New("boom")
		}
		return s, nil
	}
	results, err := Process(context.Background(), inputs, 2, op)
	if err == nil {
		t.Fatal("expected aggregated error")
	}
	if len(results) != 2 {
		t.Fatalf("got %d results, want 2", len(results))
	}
	if results[0].Output != "ok" || results[1].Output != "ok2" {
		t.Fatalf("unexpected results: %+v", results)
	}
}

func TestProcess_AllFailures(t *testing.T) {
	inputs := []string{"a", "b"}
	op := func(_ context.Context, s string) (string, error) {
		return "", fmt.Errorf("err %s", s)
	}
	results, err := Process(context.Background(), inputs, 2, op)
	if err == nil {
		t.Fatal("expected aggregated error")
	}
	if results != nil {
		t.Fatalf("expected nil results, got %+v", results)
	}
}

func TestProcess_ErrorReachableViaErrorsIs(t *testing.T) {
	sentinel := errors.New("sentinel")
	inputs := []string{"ok", "bad", "ok2"}
	op := func(_ context.Context, s string) (string, error) {
		if s == "bad" {
			return "", sentinel
		}
		return s, nil
	}
	_, err := Process(context.Background(), inputs, 2, op)
	if err == nil {
		t.Fatal("expected error")
	}
	if !errors.Is(err, sentinel) {
		t.Fatalf("aggregated error should contain sentinel via errors.Is")
	}
}

type customError struct{ msg string }

func (e *customError) Error() string { return e.msg }

func TestProcess_ErrorReachableViaErrorsAs(t *testing.T) {
	inputs := []string{"ok", "bad"}
	op := func(_ context.Context, s string) (string, error) {
		if s == "bad" {
			return "", &customError{msg: "custom"}
		}
		return s, nil
	}
	_, err := Process(context.Background(), inputs, 2, op)
	if err == nil {
		t.Fatal("expected error")
	}
	var target *customError
	if !errors.As(err, &target) {
		t.Fatalf("aggregated error should contain *customError via errors.As")
	}
	if target.msg != "custom" {
		t.Fatalf("got msg %q, want %q", target.msg, "custom")
	}
}

// ---------------------------------------------------------------------------
// Concurrency bounding
// ---------------------------------------------------------------------------

func TestProcess_AtMostConcurrencyInFlight(t *testing.T) {
	const concurrency = 3
	var active int32
	var maxActive int32
	var mu sync.Mutex

	inputs := make([]string, 20)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("x%d", i)
	}

	op := func(ctx context.Context, s string) (string, error) {
		v := atomic.AddInt32(&active, 1)
		mu.Lock()
		if v > maxActive {
			maxActive = v
		}
		mu.Unlock()
		defer atomic.AddInt32(&active, -1)

		time.Sleep(5 * time.Millisecond)
		return s, nil
	}

	_, err := Process(context.Background(), inputs, concurrency, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if maxActive > int32(concurrency) {
		t.Fatalf("saw %d concurrent operations, max allowed %d", maxActive, concurrency)
	}
}

func TestProcess_ConcurrencyOneIsSequential(t *testing.T) {
	var mu sync.Mutex
	var last time.Time
	ok := true

	inputs := []string{"a", "b", "c"}
	op := func(_ context.Context, s string) (string, error) {
		mu.Lock()
		now := time.Now()
		if !last.IsZero() && now.Sub(last) < 5*time.Millisecond {
			ok = false
		}
		last = now
		mu.Unlock()
		time.Sleep(10 * time.Millisecond)
		return s, nil
	}

	_, err := Process(context.Background(), inputs, 1, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ok {
		t.Fatal("operations ran concurrently despite concurrency=1")
	}
}

// ---------------------------------------------------------------------------
// Context propagation
// ---------------------------------------------------------------------------

func TestProcess_ContextCancelled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // already cancelled

	inputs := []string{"a", "b"}
	op := func(ctx context.Context, s string) (string, error) {
		// operation should see the cancelled context
		if ctx.Err() != nil {
			return "", ctx.Err()
		}
		return s, nil
	}

	results, err := Process(ctx, inputs, 2, op)
	if err == nil {
		t.Fatal("expected error when context is cancelled")
	}
	if len(results) != 0 {
		t.Fatalf("expected 0 results, got %d", len(results))
	}
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}

func TestProcess_ContextPassedToOperation(t *testing.T) {
	ctx := context.WithValue(context.Background(), contextKey("k"), "v")
	inputs := []string{"a"}
	op := func(ctx context.Context, s string) (string, error) {
		v := ctx.Value(contextKey("k"))
		if v == nil {
			return "", errors.New("context value not propagated")
		}
		return v.(string), nil
	}
	results, err := Process(ctx, inputs, 1, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if results[0].Output != "v" {
		t.Fatalf("got %q, want %q", results[0].Output, "v")
	}
}

type contextKey string

// ---------------------------------------------------------------------------
// Mixed success/failure ordering
// ---------------------------------------------------------------------------

func TestProcess_MixedOrdering(t *testing.T) {
	// Failures at various positions; successful results must still be ordered.
	inputs := []string{"ok0", "fail1", "ok2", "fail3", "ok4"}
	op := func(_ context.Context, s string) (string, error) {
		if s[:3] == "fail" {
			return "", errors.New(s)
		}
		return s, nil
	}
	results, err := Process(context.Background(), inputs, 3, op)
	if err == nil {
		t.Fatal("expected error")
	}
	if len(results) != 3 {
		t.Fatalf("got %d results, want 3", len(results))
	}
	for i, r := range results {
		if r.Index != i*2 { // indices 0, 2, 4
			t.Fatalf("result %d has Index %d, want %d", i, r.Index, i*2)
		}
	}
}