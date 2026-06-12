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

// custom error for testing errors.AsType reachability.
type testErr struct{ msg string }

func (e *testErr) Error() string { return "testErr: " + e.msg }

func TestProcessSuccess(t *testing.T) {
	ctx := context.Background()
	inputs := []string{"a", "b", "c"}
	op := func(_ context.Context, input string) (string, error) {
		return input + "-ok", nil
	}
	results, err := Process(ctx, inputs, 2, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 3 {
		t.Fatalf("want 3 results, got %d", len(results))
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result %d: want Index %d, got %d", i, i, r.Index)
		}
		want := inputs[i] + "-ok"
		if r.Output != want {
			t.Errorf("result %d: want Output %q, got %q", i, want, r.Output)
		}
	}
}

func TestProcessConcurrencyLessThanOne(t *testing.T) {
	ctx := context.Background()
	_, err := Process(ctx, []string{"a"}, 0, nil)
	if err == nil {
		t.Fatal("expected error for concurrency < 1")
	}
}

func TestProcessEmptyInputs(t *testing.T) {
	ctx := context.Background()
	results, err := Process(ctx, nil, 2, nil)
	if results != nil || err != nil {
		t.Errorf("want (nil, nil), got (%v, %v)", results, err)
	}
	results, err = Process(ctx, []string{}, 2, nil)
	if results != nil || err != nil {
		t.Errorf("want (nil, nil), got (%v, %v)", results, err)
	}
}

func TestProcessAllFail(t *testing.T) {
	ctx := context.Background()
	inputs := []string{"x", "y"}
	op := func(_ context.Context, input string) (string, error) {
		return "", &testErr{msg: input}
	}
	results, err := Process(ctx, inputs, 1, op)
	if err == nil {
		t.Fatal("expected error")
	}
	if results != nil {
		t.Errorf("want nil results on all-fail, got %v", results)
	}
	if _, ok := errors.AsType[*testErr](err); !ok {
		t.Error("testErr should be reachable via errors.AsType")
	}
}

func TestProcessMixedFailures(t *testing.T) {
	ctx := context.Background()
	inputs := []string{"ok1", "bad", "ok2", "bad2"}
	op := func(_ context.Context, input string) (string, error) {
		if input == "bad" || input == "bad2" {
			return "", errors.New("fail: " + input)
		}
		return input + "-ok", nil
	}
	results, err := Process(ctx, inputs, 2, op)
	if err == nil {
		t.Fatal("expected error")
	}
	if len(results) != 2 {
		t.Fatalf("want 2 successful results, got %d", len(results))
	}
	if results[0].Index != 0 || results[0].Output != "ok1-ok" {
		t.Errorf("first result mismatch: %+v", results[0])
	}
	if results[1].Index != 2 || results[1].Output != "ok2-ok" {
		t.Errorf("second result mismatch: %+v", results[1])
	}
}

func TestProcessResultOrderingPreserved(t *testing.T) {
	ctx := context.Background()
	inputs := []string{"a", "b", "c"}
	results, err := Process(ctx, inputs, 3, func(_ context.Context, input string) (string, error) {
		time.Sleep(10 * time.Millisecond)
		return input + "-ok", nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 3 {
		t.Fatalf("want 3 results, got %d", len(results))
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result %d: Index %d out of order", i, r.Index)
		}
	}
}

type concurrencyCounter struct {
	mu       sync.Mutex
	maxInFly int
	curInFly int
}

func (c *concurrencyCounter) track(ctx context.Context, delay time.Duration) func() {
	c.mu.Lock()
	c.curInFly++
	if c.curInFly > c.maxInFly {
		c.maxInFly = c.curInFly
	}
	c.mu.Unlock()

	timer := time.NewTimer(delay)
	done := make(chan struct{})
	go func() {
		select {
		case <-timer.C:
		case <-ctx.Done():
			if !timer.Stop() {
				<-timer.C
			}
		}
		close(done)
	}()

	return func() {
		<-done
		c.mu.Lock()
		c.curInFly--
		c.mu.Unlock()
	}
}

func (c *concurrencyCounter) max() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.maxInFly
}

func TestProcessConcurrencyBounded(t *testing.T) {
	ctx := context.Background()
	inputs := make([]string, 10)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("input-%d", i)
	}

	counter := &concurrencyCounter{}
	op := func(ctx context.Context, input string) (string, error) {
		done := counter.track(ctx, 100*time.Millisecond)
		defer done()
		return input + "-ok", nil
	}

	results, err := Process(ctx, inputs, 3, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 10 {
		t.Fatalf("want 10 results, got %d", len(results))
	}
	if m := counter.max(); m > 3 {
		t.Errorf("max concurrency exceeded: got %d, want ≤3", m)
	}
}

func TestProcessConcurrencyOne(t *testing.T) {
	ctx := context.Background()
	inputs := []string{"a", "b", "c"}
	op := func(_ context.Context, input string) (string, error) {
		time.Sleep(10 * time.Millisecond)
		return input + "-ok", nil
	}
	results, err := Process(ctx, inputs, 1, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 3 {
		t.Fatalf("want 3 results, got %d", len(results))
	}
}

func TestProcessContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	inputs := []string{"a", "b", "c"}
	var started atomic.Int32

	op := func(ctx context.Context, input string) (string, error) {
		started.Add(1)
		<-ctx.Done()
		return "", ctx.Err()
	}

	go func() {
		time.Sleep(5 * time.Millisecond)
		cancel()
	}()

	_, _ = Process(ctx, inputs, 2, op)
	// Must not hang. Some operations may have succeeded or not started;
	// the function returns whatever it gets.
}

func TestProcessAllErrorsReachable(t *testing.T) {
	ctx := context.Background()
	inputs := []string{"e1", "e2", "e3"}
	sentinelErr := errors.New("boom")
	op := func(_ context.Context, input string) (string, error) {
		return "", sentinelErr
	}
	_, err := Process(ctx, inputs, 2, op)
	if err == nil {
		t.Fatal("expected error")
	}
	if !errors.Is(err, sentinelErr) {
		t.Error("sentinelErr should be reachable via errors.Is")
	}
}

func TestProcessAllErrorsAsTypeReachable(t *testing.T) {
	ctx := context.Background()
	inputs := []string{"a", "b"}
	op := func(_ context.Context, input string) (string, error) {
		return "", &testErr{msg: "fail"}
	}
	_, err := Process(ctx, inputs, 2, op)
	if err == nil {
		t.Fatal("expected error")
	}
	if _, ok := errors.AsType[*testErr](err); !ok {
		t.Error("testErr should be reachable via errors.AsType")
	}
}