package fetchall_test

import (
	"context"
	"errors"
	"fmt"
	"sync/atomic"
	"testing"
	"time"

	fetchall "example.helios/fetchall"
)

func TestVerifyAllSucceedInOrder(t *testing.T) {
	inputs := make([]string, 10)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("input-%d", i)
	}
	results, err := fetchall.Process(context.Background(), inputs, 3,
		func(ctx context.Context, input string) (string, error) {
			return "out:" + input, nil
		})
	if err != nil {
		t.Fatalf("Process: %v", err)
	}
	if len(results) != 10 {
		t.Fatalf("len(results) = %d; want 10", len(results))
	}
	for i, r := range results {
		if r.Index != i || r.Output != "out:"+inputs[i] {
			t.Fatalf("results[%d] = %+v; want ordered by Index with matching output", i, r)
		}
	}
}

func TestVerifyConcurrencyBound(t *testing.T) {
	var inflight, peak atomic.Int64
	inputs := make([]string, 20)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("i%d", i)
	}
	_, err := fetchall.Process(context.Background(), inputs, 3,
		func(ctx context.Context, input string) (string, error) {
			n := inflight.Add(1)
			for {
				p := peak.Load()
				if n <= p || peak.CompareAndSwap(p, n) {
					break
				}
			}
			time.Sleep(10 * time.Millisecond)
			inflight.Add(-1)
			return input, nil
		})
	if err != nil {
		t.Fatalf("Process: %v", err)
	}
	if got := peak.Load(); got > 3 {
		t.Fatalf("peak in-flight = %d; want <= 3", got)
	}
	if got := peak.Load(); got < 2 {
		t.Fatalf("peak in-flight = %d; bound respected but work never overlapped — not concurrent", got)
	}
}

func TestVerifyFailuresAggregatedAndInspectable(t *testing.T) {
	errA := errors.New("boom-a")
	errB := errors.New("boom-b")
	inputs := []string{"ok-0", "bad-a", "ok-2", "bad-b", "ok-4"}

	results, err := fetchall.Process(context.Background(), inputs, 2,
		func(ctx context.Context, input string) (string, error) {
			switch input {
			case "bad-a":
				return "", errA
			case "bad-b":
				return "", errB
			default:
				return input, nil
			}
		})
	if err == nil {
		t.Fatal("Process with failures: want error")
	}
	if !errors.Is(err, errA) || !errors.Is(err, errB) {
		t.Fatalf("aggregated error %q must match both failures via errors.Is", err)
	}
	if len(results) != 3 {
		t.Fatalf("len(results) = %d; want 3 successes", len(results))
	}
	wantIndexes := []int{0, 2, 4}
	for i, r := range results {
		if r.Index != wantIndexes[i] {
			t.Fatalf("results[%d].Index = %d; want %d", i, r.Index, wantIndexes[i])
		}
	}
}

func TestVerifyContextPropagates(t *testing.T) {
	type key struct{}
	ctx := context.WithValue(context.Background(), key{}, "v")
	_, err := fetchall.Process(ctx, []string{"a"}, 1,
		func(ctx context.Context, input string) (string, error) {
			if ctx.Value(key{}) != "v" {
				return "", errors.New("operation ctx is not derived from the Process ctx")
			}
			return input, nil
		})
	if err != nil {
		t.Fatalf("Process: %v", err)
	}
}

func TestVerifyValidationAndEmpty(t *testing.T) {
	if _, err := fetchall.Process(context.Background(), []string{"a"}, 0, func(ctx context.Context, s string) (string, error) { return s, nil }); err == nil {
		t.Fatal("concurrency 0: want error")
	}
	results, err := fetchall.Process(context.Background(), nil, 2, func(ctx context.Context, s string) (string, error) { return s, nil })
	if err != nil || len(results) != 0 {
		t.Fatalf("empty inputs = (%v, %v); want (empty, nil)", results, err)
	}
}
