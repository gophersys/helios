package fetchall

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"testing"
	"time"
)

var errSentinel = errors.New("sentinel failure")

// --- Edge cases ---

func TestProcess_EmptyInputs(t *testing.T) {
	results, err := Process(context.Background(), nil, 1, nil)
	if results != nil || err != nil {
		t.Fatalf("nil inputs: got (%v, %v), want (nil, nil)", results, err)
	}

	results, err = Process(context.Background(), []string{}, 1, nil)
	if results != nil || err != nil {
		t.Fatalf("empty inputs: got (%v, %v), want (nil, nil)", results, err)
	}
}

func TestProcess_ConcurrencyUnderOne(t *testing.T) {
	_, err := Process(context.Background(), []string{"a"}, 0, nil)
	if err == nil {
		t.Fatal("concurrency=0: expected error, got nil")
	}

	_, err = Process(context.Background(), []string{"a"}, -5, nil)
	if err == nil {
		t.Fatal("concurrency=-5: expected error, got nil")
	}
}

// --- Success paths ---

func TestProcess_AllSucceed(t *testing.T) {
	inputs := []string{"a", "b", "c", "d"}
	op := func(_ context.Context, s string) (string, error) {
		return s + s, nil
	}
	results, err := Process(context.Background(), inputs, 2, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != len(inputs) {
		t.Fatalf("got %d results, want %d", len(results), len(inputs))
	}
	for i, r := range results {
		if r.Index != i {
			t.Errorf("result[%d].Index = %d, want %d", i, r.Index, i)
		}
		if r.Output != inputs[i]+inputs[i] {
			t.Errorf("result[%d].Output = %q, want %q", i, r.Output, inputs[i]+inputs[i])
		}
	}
}

func TestProcess_ResultsOrderedByIndex(t *testing.T) {
	// Ensure the first input blocks while later inputs complete.
	// Results must still be ordered by Index (0, 1, 2) not completion order.
	barrier := make(chan struct{})
	done := make(chan struct{}, 2)

	inputs := []string{"slow", "fast1", "fast2"}
	op := func(_ context.Context, s string) (string, error) {
		if s == "slow" {
			<-barrier
		} else {
			done <- struct{}{}
		}
		return s, nil
	}

	type procResult struct {
		results []Result
		err     error
	}
	prCh := make(chan procResult, 1)
	go func() {
		results, err := Process(context.Background(), inputs, 3, op)
		prCh <- procResult{results, err}
	}()

	// Wait until both fast items have started (they run without blocking).
	<-done
	<-done
	// Now release the slow one so all results are collected.
	close(barrier)

	pr := <-prCh
	if pr.err != nil {
		t.Fatalf("unexpected error: %v", pr.err)
	}
	if len(pr.results) != 3 {
		t.Fatalf("got %d results, want 3", len(pr.results))
	}
	for i, r := range pr.results {
		if r.Index != i {
			t.Errorf("results[%d].Index = %d, want %d", i, r.Index, i)
		}
	}
}

// --- Failure paths ---

func TestProcess_SomeFail(t *testing.T) {
	inputs := []string{"ok", "fail1", "ok2", "fail2"}
	op := func(_ context.Context, s string) (string, error) {
		if s == "fail1" || s == "fail2" {
			return "", errSentinel
		}
		return s, nil
	}
	results, err := Process(context.Background(), inputs, 2, op)
	if err == nil {
		t.Fatal("expected aggregated error, got nil")
	}
	if len(results) != 2 {
		t.Fatalf("got %d results, want 2", len(results))
	}
	if results[0].Index != 0 || results[0].Output != "ok" {
		t.Errorf("results[0] = %+v, want {Index:0 Output:ok}", results[0])
	}
	if results[1].Index != 2 || results[1].Output != "ok2" {
		t.Errorf("results[1] = %+v, want {Index:2 Output:ok2}", results[1])
	}
	// The sentinel failure must be reachable via errors.Is.
	if !errors.Is(err, errSentinel) {
		t.Error("aggregated error does not wrap errSentinel")
	}
}

// Test that concrete typed errors are reachable via errors.AsType / errors.As
// across the aggregated error tree.
type typedError struct{ msg string }

func (e *typedError) Error() string { return e.msg }

type typedErrorAlt struct{ msg string }

func (e *typedErrorAlt) Error() string { return e.msg }

func TestProcess_FailuresReachableViaAsType(t *testing.T) {
	inputs := []string{"a", "b"}
	op := func(_ context.Context, s string) (string, error) {
		if s == "a" {
			return "", &typedError{msg: "first"}
		}
		return "", &typedErrorAlt{msg: "second"}
	}
	_, err := Process(context.Background(), inputs, 1, op)
	if err == nil {
		t.Fatal("expected error")
	}
	// Both distinct typed errors must be reachable via errors.AsType.
	_, ok := errors.AsType[*typedError](err)
	if !ok {
		t.Error("typedError not reachable")
	}
	_, ok = errors.AsType[*typedErrorAlt](err)
	if !ok {
		t.Error("typedErrorAlt not reachable")
	}
}

func TestProcess_AllFail(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	op := func(_ context.Context, s string) (string, error) {
		return "", fmt.Errorf("fail %s", s)
	}
	results, err := Process(context.Background(), inputs, 2, op)
	if err == nil {
		t.Fatal("expected aggregated error")
	}
	if results != nil {
		t.Fatalf("expected nil results, got %v", results)
	}
}

// --- Concurrency enforcement ---

func TestProcess_ConcurrencyLimitRespected(t *testing.T) {
	const concurrency = 3
	var mu sync.Mutex
	var inflight int
	var peak int

	inputs := make([]string, 10)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("%d", i)
	}

	op := func(ctx context.Context, s string) (string, error) {
		mu.Lock()
		inflight++
		if inflight > peak {
			peak = inflight
		}
		mu.Unlock()

		// Block briefly so concurrency accumulates.
		select {
		case <-ctx.Done():
			return "", ctx.Err()
		case <-time.After(5 * time.Millisecond):
		}

		mu.Lock()
		inflight--
		mu.Unlock()

		return s, nil
	}

	_, err := Process(context.Background(), inputs, concurrency, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if peak > concurrency {
		t.Fatalf("peak concurrency = %d, want ≤ %d", peak, concurrency)
	}
}

// --- Context propagation ---

func TestProcess_ContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	started := make(chan struct{})

	op := func(ctx context.Context, s string) (string, error) {
		close(started)
		<-ctx.Done()
		return "", ctx.Err()
	}

	type procResult struct {
		results []Result
		err     error
	}
	prCh := make(chan procResult, 1)
	go func() {
		r, err := Process(ctx, []string{"a"}, 1, op)
		prCh <- procResult{r, err}
	}()

	// Wait until the operation is definitely running, then cancel.
	<-started
	cancel()

	pr := <-prCh
	if pr.err == nil {
		t.Fatal("expected error from cancellation, got nil")
	}
	if !errors.Is(pr.err, context.Canceled) {
		t.Errorf("error does not wrap context.Canceled: %v", pr.err)
	}
}

func TestProcess_ParentContextPassed(t *testing.T) {
	type ctxKey struct{}
	ctx := context.WithValue(context.Background(), ctxKey{}, "value")
	inputs := []string{"a"}
	var seenCtx context.Context
	op := func(ctx context.Context, s string) (string, error) {
		seenCtx = ctx
		return s, nil
	}
	_, err := Process(ctx, inputs, 1, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if v := seenCtx.Value(ctxKey{}); v != "value" {
		t.Fatalf("parent context value not propagated: got %v, want %q", v, "value")
	}
}
