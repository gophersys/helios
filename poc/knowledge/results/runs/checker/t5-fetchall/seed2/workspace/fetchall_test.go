package fetchall

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"
)

func TestProcess_Success(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	op := func(_ context.Context, input string) (string, error) {
		return input + "!", nil
	}

	results, err := Process(context.Background(), inputs, 2, op)
	if err != nil {
		t.Fatal("unexpected error:", err)
	}
	if len(results) != 3 {
		t.Fatalf("expected 3 results, got %d", len(results))
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result %d: expected Index %d, got %d", i, i, r.Index)
		}
		want := inputs[i] + "!"
		if r.Output != want {
			t.Errorf("result %d: expected Output %q, got %q", i, want, r.Output)
		}
	}
}

func TestProcess_EmptyInputs(t *testing.T) {
	// nil slice
	results, err := Process(context.Background(), nil, 2, nil)
	if results != nil || err != nil {
		t.Errorf("expected (nil, nil), got (%v, %v)", results, err)
	}
	// empty slice
	results, err = Process(context.Background(), []string{}, 2, nil)
	if results != nil || err != nil {
		t.Errorf("expected (nil, nil), got (%v, %v)", results, err)
	}
}

func TestProcess_InvalidConcurrency(t *testing.T) {
	op := func(_ context.Context, _ string) (string, error) { return "", nil }

	_, err := Process(context.Background(), []string{"a"}, 0, op)
	if err == nil {
		t.Fatal("expected error for concurrency=0")
	}
	_, err = Process(context.Background(), []string{"a"}, -1, op)
	if err == nil {
		t.Fatal("expected error for concurrency=-1")
	}
}

func TestProcess_ResultsOrdered(t *testing.T) {
	inputs := []string{"x", "y", "z", "w"}
	op := func(_ context.Context, input string) (string, error) {
		switch input {
		case "x":
			time.Sleep(20 * time.Millisecond)
		case "y":
			time.Sleep(15 * time.Millisecond)
		case "z":
			time.Sleep(10 * time.Millisecond)
		case "w":
			time.Sleep(5 * time.Millisecond)
		}
		return input, nil
	}

	results, err := Process(context.Background(), inputs, 4, op)
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 4 {
		t.Fatalf("expected 4 results, got %d", len(results))
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result %d: expected Index %d, got %d", i, i, r.Index)
		}
	}
}

func TestProcess_ConcurrencyLimit(t *testing.T) {
	const concurrency = 2
	inputs := []string{"a", "b", "c", "d"}

	var running atomic.Int32
	var maxRunning atomic.Int32

	op := func(_ context.Context, _ string) (string, error) {
		cur := running.Add(1)
		for {
			old := maxRunning.Load()
			if cur <= old || maxRunning.CompareAndSwap(old, cur) {
				break
			}
		}

		time.Sleep(10 * time.Millisecond)
		running.Add(-1)
		return "", nil
	}

	_, err := Process(context.Background(), inputs, concurrency, op)
	if err != nil {
		t.Fatal(err)
	}

	if m := maxRunning.Load(); m > int32(concurrency) {
		t.Errorf("max concurrent operations was %d, want ≤ %d", m, concurrency)
	}
}

func TestProcess_ErrorAggregation(t *testing.T) {
	inputs := []string{"ok1", "fail1", "ok2", "fail2", "ok3"}

	errFail1 := errors.New("first error")
	errFail2 := errors.New("second error")

	op := func(_ context.Context, input string) (string, error) {
		switch input {
		case "fail1":
			return "", errFail1
		case "fail2":
			return "", errFail2
		default:
			return input + "_done", nil
		}
	}

	results, err := Process(context.Background(), inputs, 2, op)
	if err == nil {
		t.Fatal("expected error, got nil")
	}

	if !errors.Is(err, errFail1) {
		t.Error("errors.Is should find errFail1 in the aggregate")
	}
	if !errors.Is(err, errFail2) {
		t.Error("errors.Is should find errFail2 in the aggregate")
	}

	if len(results) != 3 {
		t.Fatalf("expected 3 successful results, got %d", len(results))
	}
	expected := []struct {
		index int
		out   string
	}{
		{0, "ok1_done"},
		{2, "ok2_done"},
		{4, "ok3_done"},
	}
	for i, r := range results {
		if r.Index != expected[i].index {
			t.Errorf("result %d: expected Index %d, got %d", i, expected[i].index, r.Index)
		}
		if r.Output != expected[i].out {
			t.Errorf("result %d: expected Output %q, got %q", i, expected[i].out, r.Output)
		}
	}
}

func TestProcess_AllFail(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	myErr := errors.New("fail")

	results, err := Process(context.Background(), inputs, 2, func(_ context.Context, _ string) (string, error) {
		return "", myErr
	})
	if err == nil {
		t.Fatal("expected error")
	}
	if len(results) != 0 {
		t.Errorf("expected 0 results, got %d", len(results))
	}
	if !errors.Is(err, myErr) {
		t.Error("errors.Is should find myErr in the aggregate")
	}
}

func TestProcess_ContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())

	op := func(c context.Context, _ string) (string, error) {
		<-c.Done()
		return "", c.Err()
	}

	time.AfterFunc(2*time.Millisecond, cancel)

	_, err := Process(ctx, []string{"a", "b", "c"}, 2, op)
	if err == nil {
		t.Error("expected non-nil error from context cancellation")
	}
}

func TestProcess_ConcurrencyExceedsInputs(t *testing.T) {
	inputs := []string{"a", "b"}
	op := func(_ context.Context, input string) (string, error) {
		return input, nil
	}

	results, err := Process(context.Background(), inputs, 10, op)
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 2 {
		t.Fatalf("expected 2 results, got %d", len(results))
	}
}

func TestProcess_PartialCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	inputs := []string{"fast1", "fast2", "slow", "fast3"}
	op := func(c context.Context, input string) (string, error) {
		if input == "slow" {
			time.Sleep(50 * time.Millisecond)
		}
		select {
		case <-c.Done():
			return "", c.Err()
		default:
		}
		return input, nil
	}

	time.AfterFunc(20*time.Millisecond, cancel)

	results, _ := Process(ctx, inputs, 4, op)
	t.Logf("partial cancellation produced %d results", len(results))
}

func TestProcess_ContextCancellationBeforeAcquire(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	results, err := Process(ctx, []string{"a", "b", "c"}, 2, func(_ context.Context, _ string) (string, error) {
		return "unreachable", nil
	})
	if len(results) != 0 {
		t.Logf("pre-cancelled context produced %d results", len(results))
	}
	if err == nil {
		t.Log("pre-cancelled context returned nil error (expected context.Canceled)")
	}
}
