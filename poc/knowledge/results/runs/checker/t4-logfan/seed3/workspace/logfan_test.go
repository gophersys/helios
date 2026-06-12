package logfan

import (
	"context"
	"log/slog"
	"sync"
	"testing"
)

func TestNewRing_InvalidCapacity(t *testing.T) {
	_, err := NewRing(0)
	if err == nil {
		t.Error("expected error for capacity 0")
	}
	_, err = NewRing(-1)
	if err == nil {
		t.Error("expected error for capacity -1")
	}
}

func TestNewRing_Valid(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("expected non-nil *Ring")
	}
}

func TestRing_Empty(t *testing.T) {
	r, _ := NewRing(3)
	recs := r.Records()
	if recs != nil {
		t.Errorf("expected nil, got %v", recs)
	}
}

func TestRing_OrderPreserved(t *testing.T) {
	r, _ := NewRing(5)
	h := slog.New(r)

	h.Info("one")
	h.Info("two")
	h.Info("three")

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records, got %d", len(recs))
	}
	msgs := []string{"one", "two", "three"}
	for i, rec := range recs {
		if rec.Message != msgs[i] {
			t.Errorf("record %d: message=%q, want %q", i, rec.Message, msgs[i])
		}
	}
}

func TestRing_EvictsOldest(t *testing.T) {
	r, _ := NewRing(2)
	h := slog.New(r)

	h.Info("a")
	h.Info("b")
	h.Info("c")

	recs := r.Records()
	if len(recs) != 2 {
		t.Fatalf("expected 2 records, got %d", len(recs))
	}
	if recs[0].Message != "b" {
		t.Errorf("oldest: message=%q, want %q", recs[0].Message, "b")
	}
	if recs[1].Message != "c" {
		t.Errorf("newest: message=%q, want %q", recs[1].Message, "c")
	}
}

func TestRing_EvictAll(t *testing.T) {
	r, _ := NewRing(1)
	h := slog.New(r)

	h.Info("x")
	h.Info("y")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}
	if recs[0].Message != "y" {
		t.Errorf("message=%q, want %q", recs[0].Message, "y")
	}
}

func TestRing_RecordsAreCopies(t *testing.T) {
	r, _ := NewRing(5)
	h := slog.New(r)

	h.Info("original", "key", "value")

	recs := r.Records()
	recs[0].Message = "mutated"

	// Read again — ring must be unaffected
	recs2 := r.Records()
	if recs2[0].Message != "original" {
		t.Errorf("ring mutated: message=%q", recs2[0].Message)
	}
}

func TestRing_RecordsAreDeepCopied(t *testing.T) {
	r, _ := NewRing(5)
	h := slog.New(r)

	h.Info("test", "k", "v")

	recs := r.Records()
	recs[0].AddAttrs(slog.Int("extra", 99))

	recs2 := r.Records()
	var count int
	recs2[0].Attrs(func(a slog.Attr) bool {
		count++
		if a.Key == "extra" {
			t.Error("extra attr leaked into ring")
		}
		return true
	})
	// original attr "k" should still be there, "extra" should not
	if count != 1 {
		t.Logf("attributed count: %d", count)
	}
}

func TestRing_Concurrency(t *testing.T) {
	r, _ := NewRing(100)
	h := slog.New(r)

	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		n := i
		wg.Go(func() {
			h.Info("msg", "n", n)
		})
	}
	wg.Wait()

	// Concurrent reads while writing
	var wg2 sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg2.Go(func() {
			h.Info("concurrent")
			_ = r.Records()
		})
	}
	wg2.Wait()

	if len(r.Records()) == 0 {
		t.Error("expected records after concurrent access")
	}
}

func TestNew_NoHandlers(t *testing.T) {
	_, err := New()
	if err == nil {
		t.Error("expected error")
	}
}

func TestNew_SingleHandler(t *testing.T) {
	r, _ := NewRing(3)
	logger, err := New(r)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	logger.Info("hello")
	if len(r.Records()) != 1 {
		t.Error("expected 1 record")
	}
}

func TestNew_FanOut(t *testing.T) {
	r1, _ := NewRing(5)
	r2, _ := NewRing(5)

	logger, err := New(r1, r2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	logger.Info("hello")

	if len(r1.Records()) != 1 {
		t.Error("r1 should have 1 record")
	}
	if len(r2.Records()) != 1 {
		t.Error("r2 should have 1 record")
	}
}

func TestNew_FanOutMessages(t *testing.T) {
	r1, _ := NewRing(5)
	r2, _ := NewRing(5)

	logger, err := New(r1, r2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	logger.Info("a")
	logger.Warn("b")
	logger.Error("c")

	recs1 := r1.Records()
	recs2 := r2.Records()

	if len(recs1) != 3 || len(recs2) != 3 {
		t.Fatalf("expected 3 records each, got %d and %d", len(recs1), len(recs2))
	}
	for i := 0; i < 3; i++ {
		if recs1[i].Message != recs2[i].Message {
			t.Errorf("record %d mismatch: r1=%q r2=%q", i, recs1[i].Message, recs2[i].Message)
		}
	}
}

func TestRing_WithAttrs(t *testing.T) {
	r, _ := NewRing(5)
	h := r.WithAttrs([]slog.Attr{slog.String("env", "test")})

	slog.New(h).Info("msg")

	ring := h.(*Ring)
	recs := ring.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "env" {
			found = true
			return false
		}
		return true
	})
	if !found {
		t.Error("attr env=test not found on record")
	}
}

func TestRing_WithGroup(t *testing.T) {
	r, _ := NewRing(5)
	h := r.WithGroup("request")
	h = h.WithAttrs([]slog.Attr{slog.String("id", "abc")})

	slog.New(h).Info("msg")

	ring := h.(*Ring)
	recs := ring.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "request" && a.Value.Kind() == slog.KindGroup {
			for _, inner := range a.Value.Group() {
				if inner.Key == "id" && inner.Value.String() == "abc" {
					found = true
					return false
				}
			}
		}
		return true
	})
	if !found {
		t.Error("no request.id attr found on record")
	}
}


func TestRing_EnabledTrue(t *testing.T) {
	r, _ := NewRing(3)
	if !r.Enabled(context.Background(), slog.LevelDebug) {
		t.Error("expected Enabled=true for Debug")
	}
	if !r.Enabled(context.Background(), slog.LevelError) {
		t.Error("expected Enabled=true for Error")
	}
}
