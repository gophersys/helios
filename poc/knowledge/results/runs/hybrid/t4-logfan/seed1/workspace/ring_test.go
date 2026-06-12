package logfan

import (
	"log/slog"
	"sync"
	"testing"
)

func TestNewRing_ErrorZero(t *testing.T) {
	t.Parallel()
	r, err := NewRing(0)
	if err == nil {
		t.Error("NewRing(0) should return an error")
	}
	if r != nil {
		t.Error("NewRing(0) should return nil *Ring")
	}
}

func TestNewRing_ErrorNegative(t *testing.T) {
	t.Parallel()
	r, err := NewRing(-1)
	if err == nil {
		t.Error("NewRing(-1) should return an error")
	}
	if r != nil {
		t.Error("NewRing(-1) should return nil *Ring")
	}
}

func TestNewRing_OK(t *testing.T) {
	t.Parallel()
	r, err := NewRing(3)
	if err != nil {
		t.Fatalf("NewRing(3) unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("NewRing(3) returned nil")
	}
}

func TestRing_RecordsOrder(t *testing.T) {
	t.Parallel()
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	logger := slog.New(r)

	logger.Info("one")
	logger.Info("two")
	logger.Info("three")

	recs := r.Records()
	if want := 3; len(recs) != want {
		t.Fatalf("got %d records, want %d", len(recs), want)
	}
	if recs[0].Message != "one" {
		t.Errorf("records[0].Message = %q, want %q", recs[0].Message, "one")
	}
	if recs[1].Message != "two" {
		t.Errorf("records[1].Message = %q, want %q", recs[1].Message, "two")
	}
	if recs[2].Message != "three" {
		t.Errorf("records[2].Message = %q, want %q", recs[2].Message, "three")
	}
}

func TestRing_Eviction(t *testing.T) {
	t.Parallel()
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}
	logger := slog.New(r)

	logger.Info("a")
	logger.Info("b")
	logger.Info("c")

	recs := r.Records()
	if want := 2; len(recs) != want {
		t.Fatalf("got %d records, want %d", len(recs), want)
	}
	if recs[0].Message != "b" {
		t.Errorf("records[0].Message = %q, want %q", recs[0].Message, "b")
	}
	if recs[1].Message != "c" {
		t.Errorf("records[1].Message = %q, want %q", recs[1].Message, "c")
	}
}

func TestRing_RecordsReturnsCopy(t *testing.T) {
	t.Parallel()
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}
	logger := slog.New(r)
	logger.Info("persist")

	recs := r.Records()
	recs[0] = slog.NewRecord(recs[0].Time, recs[0].Level, "mutated", 0)

	recs2 := r.Records()
	if len(recs2) != 1 || recs2[0].Message != "persist" {
		t.Error("mutating the returned slice affected the ring buffer")
	}
}

func TestRing_EmptyRecords(t *testing.T) {
	t.Parallel()
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	recs := r.Records()
	if len(recs) != 0 {
		t.Errorf("expected empty records, got %d", len(recs))
	}
}

func TestRing_RecordAttrs(t *testing.T) {
	t.Parallel()
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	logger := slog.New(r)
	logger.Info("msg", "key", "val", "num", 42)

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatal("expected 1 record")
	}

	var gotKey, gotNum bool
	recs[0].Attrs(func(a slog.Attr) bool {
		switch a.Key {
		case "key":
			if a.Value.String() == "val" {
				gotKey = true
			}
		case "num":
			if a.Value.Int64() == 42 {
				gotNum = true
			}
		}
		return true
	})
	if !gotKey {
		t.Error("missing attr 'key'")
	}
	if !gotNum {
		t.Error("missing attr 'num'")
	}
}

func TestRing_WithAttrs(t *testing.T) {
	t.Parallel()
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	logger := slog.New(r).With("component", "test")
	logger.Info("hello")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatal("expected 1 record")
	}

	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "component" && a.Value.String() == "test" {
			found = true
			return false
		}
		return true
	})
	if !found {
		t.Error("handler attr 'component' not found in record")
	}
}

func TestRing_WithGroup(t *testing.T) {
	t.Parallel()
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	logger := slog.New(r).WithGroup("request")
	logger.Info("hello", "id", 42)

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatal("expected 1 record")
	}

	var groupFound bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "request" {
			groupFound = true
			return false
		}
		return true
	})
	if !groupFound {
		t.Error("group 'request' not found in record")
	}
}

func TestRing_HandlerIdentity(t *testing.T) {
	t.Parallel()
	// slog.Handler interface must be implemented by *Ring, not Ring.
	var h slog.Handler
	var err error
	h, err = NewRing(3)
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := h.(*Ring); !ok {
		t.Error("NewRing returned value does not satisfy slog.Handler via *Ring")
	}
}

func TestNew_ErrorNoHandlers(t *testing.T) {
	t.Parallel()
	l, err := New()
	if err == nil {
		t.Error("New() should return an error")
	}
	if l != nil {
		t.Error("New() should return nil")
	}
}

func TestNew_FanOutToMultiple(t *testing.T) {
	t.Parallel()
	r1, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	r2, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}

	logger, err := New(r1, r2)
	if err != nil {
		t.Fatalf("New() unexpected error: %v", err)
	}
	logger.Info("fanned out")

	if len(r1.Records()) != 1 {
		t.Error("handler 1 did not receive the record")
	}
	if len(r2.Records()) != 1 {
		t.Error("handler 2 did not receive the record")
	}
}

func TestNew_ReturnsLogger(t *testing.T) {
	t.Parallel()
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	logger, err := New(r)
	if err != nil {
		t.Fatalf("New() unexpected error: %v", err)
	}
	if logger == nil {
		t.Error("New() returned nil logger")
	}
}

func TestRing_ConcurrentAccess(t *testing.T) {
	t.Parallel()
	r, err := NewRing(100)
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	// Concurrent writers.
	for i := 0; i < 10; i++ {
		wg.Go(func() {
			logger := slog.New(r)
			for j := 0; j < 10; j++ {
				logger.Info("data")
			}
		})
	}
	// Concurrent readers.
	for i := 0; i < 5; i++ {
		wg.Go(func() {
			for j := 0; j < 5; j++ {
				_ = r.Records()
			}
		})
	}
	wg.Wait()

	recs := r.Records()
	if want := 100; len(recs) != want {
		t.Errorf("got %d records after concurrent writes, want %d", len(recs), want)
	}
}
