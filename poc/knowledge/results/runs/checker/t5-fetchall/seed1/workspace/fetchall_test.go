package fetchall

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"
)

type customErr struct{ msg string }

func (e customErr) Error() string { return e.msg }

func TestProcess_EmptyInputs(t *testing.T) {
	res, err := Process(context.Background(), nil, 1, nop)
	if res != nil || err != nil {
		t.Fatalf("expected (nil, nil), got (%v, %v)", res, err)
	}
	res, err = Process(context.Background(), []string{}, 5, nop)
	if res != nil || err != nil {
		t.Fatalf("expected (nil, nil), got (%v, %v)", res, err)
	}
}

func TestProcess_ConcurrencyTooSmall(t *testing.T) {
	res, err := Process(context.Background(), []string{"a"}, 0, nop)
	if res != nil || err == nil {
		t.Fatalf("expected error, got (%v, %v)", res, err)
	}
	res, err = Process(context.Background(), []string{"a"}, -1, nop)
	if res != nil || err == nil {
		t.Fatalf("expected error, got (%v, %v)", res, err)
	}
}

func TestProcess_AllSucceed(t *testing.T) {
	inputs := []string{"a", "b", "c"}
	res, err := Process(context.Background(), inputs, 2, func(_ context.Context, s string) (string, error) {
		return s + s, nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []Result{{Index: 0, Output: "aa"}, {Index: 1, Output: "bb"}, {Index: 2, Output: "cc"}}
	if !eq(res, want) {
		t.Fatalf("got %v, want %v", res, want)
	}
}

func TestProcess_ResultsOrderedByIndex(t *testing.T) {
	inputs := []string{"slow", "fast", "fastest"}
	res, err := Process(context.Background(), inputs, 3, func(_ context.Context, s string) (string, error) {
		switch s {
		case "slow":
			time.Sleep(50 * time.Millisecond)
		case "fast":
			time.Sleep(10 * time.Millisecond)
		}
		return s, nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for i, r := range res {
		if r.Index != i {
			t.Fatalf("result at position %d has Index %d", i, r.Index)
		}
	}
}

func TestProcess_SomeFailures(t *testing.T) {
	err1 := errors.New("err1")
	err2 := errors.New("err2")
	inputs := []string{"ok", "fail1", "ok2", "fail2"}
	res, err := Process(context.Background(), inputs, 2, func(_ context.Context, s string) (string, error) {
		if s == "fail1" {
			return "", err1
		}
		if s == "fail2" {
			return "", err2
		}
		return s, nil
	})
	if err == nil {
		t.Fatal("expected an error")
	}
	if !errors.Is(err, err1) {
		t.Error("err1 not reachable via errors.Is")
	}
	if !errors.Is(err, err2) {
		t.Error("err2 not reachable via errors.Is")
	}
	if len(res) != 2 || res[0].Output != "ok" || res[1].Output != "ok2" {
		t.Fatalf("unexpected results: %v", res)
	}
}

func TestProcess_AllFailures(t *testing.T) {
	inputs := []string{"x", "y", "z"}
	e := errors.New("boom")
	_, err := Process(context.Background(), inputs, 1, func(_ context.Context, s string) (string, error) {
		return "", e
	})
	if err == nil {
		t.Fatal("expected an error")
	}
	if !errors.Is(err, e) {
		t.Error("individual error not reachable via errors.Is")
	}
}

func TestProcess_MaxConcurrency(t *testing.T) {
	var concurrent int32
	var maxConcurrent int32

	inputs := []string{"a", "b", "c", "d", "e"}
	res, err := Process(context.Background(), inputs, 3, func(_ context.Context, s string) (string, error) {
		v := atomic.AddInt32(&concurrent, 1)
		if v > maxConcurrent {
			maxConcurrent = v
		}
		time.Sleep(20 * time.Millisecond)
		atomic.AddInt32(&concurrent, -1)
		return s, nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if maxConcurrent > 3 {
		t.Fatalf("observed concurrency %d, want ≤ 3", maxConcurrent)
	}
	if len(res) != len(inputs) {
		t.Fatalf("got %d results, want %d", len(res), len(inputs))
	}
}

func TestProcess_RunsAllOnFailure(t *testing.T) {
	var ran int32
	inputs := []string{"a", "b", "c", "d"}
	_, err := Process(context.Background(), inputs, 2, func(_ context.Context, s string) (string, error) {
		atomic.AddInt32(&ran, 1)
		return "", errors.New("fail")
	})
	if err == nil {
		t.Fatal("expected error")
	}
	if n := atomic.LoadInt32(&ran); n != 4 {
		t.Fatalf("expected all 4 inputs to run, got %d", n)
	}
}

func TestProcess_CustomErrorTypeAggregation(t *testing.T) {
	inputs := []string{"a", "b"}
	_, err := Process(context.Background(), inputs, 1, func(_ context.Context, s string) (string, error) {
		return "", customErr{msg: s + "err"}
	})
	if err == nil {
		t.Fatal("expected error")
	}
	var ce customErr
	if !errors.As(err, &ce) {
		t.Error("customErr not reachable via errors.As")
	}
}

func nop(_ context.Context, s string) (string, error) {
	return s, nil
}

func eq(a, b []Result) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
