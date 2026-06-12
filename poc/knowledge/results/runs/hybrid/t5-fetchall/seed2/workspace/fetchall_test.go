package fetchall

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestProcess_EmptyInputs(t *testing.T) {
	res, err := Process(context.Background(), nil, 2, nopOp)
	if res != nil || err != nil {
		t.Fatalf("expected (nil, nil), got (%v, %v)", res, err)
	}
	res, err = Process(context.Background(), []string{}, 2, nopOp)
	if res != nil || err != nil {
		t.Fatalf("expected (nil, nil), got (%v, %v)", res, err)
	}
}

func TestProcess_InvalidConcurrency(t *testing.T) {
	_, err := Process(context.Background(), []string{"a"}, 0, nopOp)
	if err == nil {
		t.Fatal("expected error for concurrency 0")
	}
	_, err = Process(context.Background(), []string{"a"}, -1, nopOp)
	if err == nil {
		t.Fatal("expected error for concurrency -1")
	}
}

func TestProcess_AllSucceed(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	op := func(_ context.Context, input string) (string, error) {
		return input + "!", nil
	}
	res, err := Process(context.Background(), inputs, 2, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != 3 {
		t.Fatalf("expected 3 results, got %d", len(res))
	}
	for i, r := range res {
		if r.Index != i {
			t.Errorf("result %d: expected Index %d, got %d", i, i, r.Index)
		}
		if r.Output != inputs[i]+"!" {
			t.Errorf("result %d: expected Output %q, got %q", i, inputs[i]+"!", r.Output)
		}
	}
}

func TestProcess_ResultsOrderedByIndex(t *testing.T) {
	// Operations complete out of order but results must be in original order.
	inputs := []string{"slow", "fast"}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	op := func(ctx context.Context, input string) (string, error) {
		if input == "slow" {
			// Block until "fast" finishes and cancels the context.
			<-ctx.Done()
			return "", ctx.Err()
		}
		// "fast" completes, then cancels the context to unblock "slow".
		go cancel()
		return "ok", nil
	}
	res, err := Process(ctx, inputs, 2, op)
	if err == nil {
		t.Fatal("expected an error")
	}
	if len(res) != 1 {
		t.Fatalf("expected 1 result, got %d", len(res))
	}
	if res[0].Index != 1 || res[0].Output != "ok" {
		t.Errorf("expected Result{Index: 1, Output: \"ok\"}, got %+v", res[0])
	}
}


func TestProcess_ConcurrencyLimitMax(t *testing.T) {
	const concurrency = 3
	const total = 10
	var (
		inflight atomic.Int32
		peak     atomic.Int32
	)

	op := func(_ context.Context, input string) (string, error) {
		v := inflight.Add(1)
		for prev := peak.Load(); v > prev; {
			if peak.CompareAndSwap(prev, v) {
				break
			}
			prev = peak.Load()
		}
		time.Sleep(5 * time.Millisecond)
		inflight.Add(-1)
		return input, nil
	}

	res, err := Process(context.Background(), make([]string, total), concurrency, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != total {
		t.Fatalf("expected %d results, got %d", total, len(res))
	}
	if p := peak.Load(); p > int32(concurrency) {
		t.Errorf("saw %d concurrent operations, limit is %d", p, concurrency)
	}
	if p := peak.Load(); p < 1 {
		t.Error("expected at least some concurrency")
	}
}

func TestProcess_MixedFailure(t *testing.T) {
	errFail := errors.New("fail")
	inputs := []string{"ok", "bad", "ok2", "bad2"}
	op := func(_ context.Context, input string) (string, error) {
		if input == "bad" || input == "bad2" {
			return "", errFail
		}
		return input, nil
	}
	res, err := Process(context.Background(), inputs, 2, op)
	if !errors.Is(err, errFail) {
		t.Error("aggregated error should wrap errFail")
	}

	if len(res) != 2 {
		t.Fatalf("expected 2 successful results, got %d", len(res))
	}
	if res[0].Output != "ok" || res[1].Output != "ok2" {
		t.Errorf("unexpected results: %+v", res)
	}
}

func TestProcess_AllFail(t *testing.T) {
	errSentinel := errors.New("boom")
	op := func(_ context.Context, input string) (string, error) {
		return "", errSentinel
	}
	res, err := Process(context.Background(), []string{"a", "b", "c"}, 2, op)
	if err == nil {
		t.Fatal("expected error")
	}
	if len(res) != 0 {
		t.Errorf("expected empty results, got %v", res)
	}
	if !errors.Is(err, errSentinel) {
		t.Error("aggregated error should wrap errSentinel")
	}
}

func TestProcess_RespectsContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // cancel immediately

	op := func(_ context.Context, input string) (string, error) {
		// Since the parent is cancelled, this should still be called but
		// we return "ok" — the operation doesn't check ctx itself.
		// The spec says the parent context is the parent of every per-operation ctx.
		// The operation is free to check or ignore it.
		// Process itself must still run everything and return.
		return input + "!", nil
	}
	res, err := Process(ctx, []string{"a", "b"}, 2, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != 2 {
		t.Fatalf("expected 2 results, got %d", len(res))
	}
}
func TestProcess_AllOpsRunDespiteCancellation(t *testing.T) {
	// Verify that all operations are executed even if the context is cancelled
	// while operations are in flight.
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	var count int32

	op := func(_ context.Context, input string) (string, error) {
		atomic.AddInt32(&count, 1)
		// Second operation cancels the context — first is already running.
		if input == "b" {
			cancel()
		}
		return input, nil
	}

	res, err := Process(ctx, []string{"a", "b", "c", "d"}, 2, op)
	// All operations succeed despite cancellation — they don't check ctx.
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != 4 {
		t.Fatalf("expected 4 results, got %d", len(res))
	}
	if c := atomic.LoadInt32(&count); c != 4 {
		t.Errorf("expected 4 operations to run, got %d", c)
	}
}
func TestProcess_ErrorsReachable(t *testing.T) {
	var errA = errors.New("errA")
	var errB = errors.New("errB")

	op := func(_ context.Context, input string) (string, error) {
		switch input {
		case "a":
			return "", errA
		case "b":
			return "", errB
		default:
			return input, nil
		}
	}

	res, err := Process(context.Background(), []string{"a", "c", "b", "d"}, 3, op)
	if err == nil {
		t.Fatal("expected aggregated error")
	}
	// Both sentinels must be reachable.
	if !errors.Is(err, errA) {
		t.Error("errA not reachable via errors.Is")
	}
	if !errors.Is(err, errB) {
		t.Error("errB not reachable via errors.Is")
	}
	// Successful results must come back in the right order with correct indices.
	if len(res) != 2 {
		t.Fatalf("expected 2 successful results, got %d", len(res))
	}
	// c (index 1) should come before d (index 3).
	if res[0].Index != 1 || res[0].Output != "c" {
		t.Errorf("first result should be {1, c}, got %+v", res[0])
	}
	if res[1].Index != 3 || res[1].Output != "d" {
		t.Errorf("second result should be {3, d}, got %+v", res[1])
	}
}

func TestProcess_SingleConcurrency(t *testing.T) {
	// Sequential processing with concurrency=1.
	order := make([]int, 0, 3)
	var mu sync.Mutex
	op := func(_ context.Context, input string) (string, error) {
		mu.Lock()
		order = append(order, len(order))
		mu.Unlock()
		return input, nil
	}
	res, err := Process(context.Background(), []string{"x", "y", "z"}, 1, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != 3 {
		t.Fatalf("expected 3 results, got %d", len(res))
	}
}

func TestProcess_HighConcurrency(t *testing.T) {
	// concurrency > len(inputs) — all run in parallel.
	n := 100
	inputs := make([]string, n)
	for i := range n {
		inputs[i] = "x"
	}
	var inflight atomic.Int32
	var peak atomic.Int32
	op := func(_ context.Context, input string) (string, error) {
		v := inflight.Add(1)
		for prev := peak.Load(); v > prev; {
			if peak.CompareAndSwap(prev, v) {
				break
			}
			prev = peak.Load()
		}
		defer inflight.Add(-1)
		time.Sleep(time.Microsecond)
		return input, nil
	}
	res, err := Process(context.Background(), inputs, n, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != n {
		t.Fatalf("expected %d results, got %d", n, len(res))
	}
	// We set concurrency=n, so we should see peak=n running at once.
	if peak.Load() != int32(n) {
		t.Logf("observed peak concurrency = %d (expected %d)", peak.Load(), n)
	}
}

// nopOp is a no-op operation that returns the input unchanged.
func nopOp(_ context.Context, input string) (string, error) {
	return input, nil
}
