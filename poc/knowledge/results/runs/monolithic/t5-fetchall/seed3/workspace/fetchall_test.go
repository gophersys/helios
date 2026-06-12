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

// errSentinel is a sentinel error used to verify errors.Is propagation.
var errSentinel = errors.New("boom")

type errTyped struct{ msg string }

func (e *errTyped) Error() string { return e.msg }

func TestProcess_InvalidConcurrency(t *testing.T) {
	_, err := Process(context.Background(), []string{"a"}, 0, nopOp)
	if err == nil {
		t.Fatal("expected error for concurrency=0")
	}
	_, err = Process(context.Background(), []string{"a"}, -1, nopOp)
	if err == nil {
		t.Fatal("expected error for concurrency=-1")
	}
}

func TestProcess_EmptyInputs(t *testing.T) {
	res, err := Process(context.Background(), nil, 1, nopOp)
	if res != nil || err != nil {
		t.Fatalf("expected (nil, nil), got (%v, %v)", res, err)
	}
	res, err = Process(context.Background(), []string{}, 1, nopOp)
	if res != nil || err != nil {
		t.Fatalf("expected (nil, nil), got (%v, %v)", res, err)
	}
}

func TestProcess_AllSucceed(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	res, err := Process(context.Background(), inputs, 2, echoOp)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != len(inputs) {
		t.Fatalf("got %d results, want %d", len(res), len(inputs))
	}
	for i, r := range res {
		if r.Index != i {
			t.Errorf("result %d: Index=%d, want %d", i, r.Index, i)
		}
		if r.Output != inputs[i] {
			t.Errorf("result %d: Output=%q, want %q", i, r.Output, inputs[i])
		}
	}
}

func TestProcess_ResultsOrdered(t *testing.T) {
	// Operations sleep inversely proportional to index so later inputs finish
	// first; the output must still be ordered by index.
	inputs := []string{"0", "1", "2", "3", "4"}
	op := func(ctx context.Context, input string) (string, error) {
		time.Sleep(time.Duration(5-int(input[0]-'0')) * time.Millisecond)
		return "x" + input, nil
	}
	res, err := Process(context.Background(), inputs, 5, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != len(inputs) {
		t.Fatalf("got %d results, want %d", len(res), len(inputs))
	}
	for i, r := range res {
		if r.Index != i {
			t.Errorf("result %d: Index=%d, want %d", i, r.Index, i)
		}
	}
}

func TestProcess_SomeFail(t *testing.T) {
	inputs := []string{"ok", "fail", "ok2", "fail2"}
	op := func(ctx context.Context, input string) (string, error) {
		if input == "fail" || input == "fail2" {
			return "", fmt.Errorf("op %q: %w", input, errSentinel)
		}
		return input, nil
	}
	res, err := Process(context.Background(), inputs, 2, op)
	if err == nil {
		t.Fatal("expected aggregated error")
	}
	if len(res) != 2 {
		t.Fatalf("got %d successful results, want 2", len(res))
	}
	// Verify ordering.
	if res[0].Index != 0 || res[0].Output != "ok" {
		t.Errorf("first result mismatch: %+v", res[0])
	}
	if res[1].Index != 2 || res[1].Output != "ok2" {
		t.Errorf("second result mismatch: %+v", res[1])
	}
	// Every individual failure must be reachable.
	if !errors.Is(err, errSentinel) {
		t.Error("aggregated error does not wrap errSentinel")
	}
}

func TestProcess_AllFail(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	op := func(ctx context.Context, input string) (string, error) {
		return "", &errTyped{msg: "fail: " + input}
	}
	res, err := Process(context.Background(), inputs, 2, op)
	if err == nil {
		t.Fatal("expected aggregated error")
	}
	if len(res) != 0 {
		t.Fatalf("expected 0 successful results, got %d", len(res))
	}
	// Verify typed error reachable via errors.As.
	var typed *errTyped
	if !errors.As(err, &typed) {
		t.Error("aggregated error should contain *errTyped")
	}
}

func TestProcess_ConcurrencyBoundRespected(t *testing.T) {
	const (
		n           = 20
		concurrency = 3
	)

	var (
		mu       sync.Mutex
		peak     int
		inflight atomic.Int32
	)

	op := func(ctx context.Context, input string) (string, error) {
		v := int(inflight.Add(1))
		mu.Lock()
		if v > peak {
			peak = v
		}
		mu.Unlock()
		// Sleep long enough that the semaphore forces serialized dispatch.
		time.Sleep(30 * time.Millisecond)
		inflight.Add(-1)
		return input, nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	res, err := Process(ctx, makeInputs(n), concurrency, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != n {
		t.Fatalf("got %d results, want %d", len(res), n)
	}
	if peak > concurrency {
		t.Fatalf("peak concurrency %d exceeds limit %d", peak, concurrency)
	}
}

func TestProcess_ContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // already cancelled

	res, err := Process(ctx, []string{"a", "b"}, 2, func(ctx context.Context, input string) (string, error) {
		select {
		case <-ctx.Done():
			return "", ctx.Err()
		default:
			return input, nil
		}
	})

	if err == nil {
		t.Fatal("expected error from cancelled context")
	}
	if !errors.Is(err, context.Canceled) {
		t.Errorf("expected context.Canceled, got %v", err)
	}
	if len(res) != 0 {
		t.Errorf("expected 0 results, got %d", len(res))
	}
}

func TestProcess_ConcurrencyOne(t *testing.T) {
	// Sequential execution: one at a time.
	var orderMu sync.Mutex
	var order []int

	op := func(ctx context.Context, input string) (string, error) {
		time.Sleep(5 * time.Millisecond)
		orderMu.Lock()
		order = append(order, int(input[0]-'0'))
		orderMu.Unlock()
		return input, nil
	}

	res, err := Process(context.Background(), []string{"0", "1", "2"}, 1, op)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != 3 {
		t.Fatalf("got %d results, want %d", len(res), 3)
	}
	// With concurrency=1 the order slice should be [0,1,2] because operations
	// run sequentially (no reordering even though sleep is uniform).
	if len(order) != 3 || order[0] != 0 || order[1] != 1 || order[2] != 2 {
		t.Errorf("unexpected execution order: %v", order)
	}
}

// --- helpers ---

func nopOp(_ context.Context, input string) (string, error) {
	return input, nil
}

func echoOp(_ context.Context, input string) (string, error) {
	return input, nil
}

func makeInputs(n int) []string {
	s := make([]string, n)
	for i := range s {
		s[i] = fmt.Sprintf("%d", i)
	}
	return s
}