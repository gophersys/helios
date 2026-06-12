package logfan

import (
	"context"
	"log/slog"
	"sync"
	"testing"
	"time"
)

func TestNewRing_InvalidCapacity(t *testing.T) {
	_, err := NewRing(0)
	if err == nil {
		t.Fatal("expected error for capacity 0")
	}
	_, err = NewRing(-1)
	if err == nil {
		t.Fatal("expected error for capacity -1")
	}
}

func TestNewRing_ValidCapacity(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("expected non-nil Ring")
	}
}

func TestRing_RecordsEmpty(t *testing.T) {
	r, _ := NewRing(5)
	recs := r.Records()
	if len(recs) != 0 {
		t.Fatalf("expected 0 records, got %d", len(recs))
	}
}

func TestRing_HandleAndRetrieve(t *testing.T) {
	r, _ := NewRing(3)
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	mustHandle(t, r, slog.NewRecord(now, slog.LevelInfo, "msg1", 0))
	mustHandle(t, r, slog.NewRecord(now, slog.LevelWarn, "msg2", 0))

	recs := r.Records()
	if len(recs) != 2 {
		t.Fatalf("expected 2 records, got %d", len(recs))
	}
	if recs[0].Message != "msg1" {
		t.Errorf("expected msg1 first, got %s", recs[0].Message)
	}
	if recs[1].Message != "msg2" {
		t.Errorf("expected msg2 second, got %s", recs[1].Message)
	}
}

func TestRing_Eviction(t *testing.T) {
	r, _ := NewRing(3)
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	msgs := []string{"msg1", "msg2", "msg3", "msg4", "msg5"}
	for _, m := range msgs {
		mustHandle(t, r, slog.NewRecord(now, slog.LevelInfo, m, 0))
	}

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records (capacity), got %d", len(recs))
	}
	expected := []string{"msg3", "msg4", "msg5"}
	for i, e := range expected {
		if recs[i].Message != e {
			t.Errorf("recs[%d] = %s, want %s", i, recs[i].Message, e)
		}
	}
}

func TestRing_RecordsCopyIndependence(t *testing.T) {
	r, _ := NewRing(3)
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	mustHandle(t, r, slog.NewRecord(now, slog.LevelInfo, "msg", 0))

	recs := r.Records()
	recs[0].Message = "tampered"

	r2 := r.Records()
	if r2[0].Message != "msg" {
		t.Errorf("ring was mutated via returned slice: got %s", r2[0].Message)
	}
}

func TestRing_WithAttrs(t *testing.T) {
	r, _ := NewRing(5)
	h := r.WithAttrs([]slog.Attr{slog.String("key", "val")})
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	mustHandle(t, h.(*Ring), slog.NewRecord(now, slog.LevelInfo, "msg", 0))

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}
	var got string
	recs[0].Attrs(func(a slog.Attr) bool {
		got = a.Value.String()
		return false
	})
	if got != "val" {
		t.Errorf("expected attr val, got %s", got)
	}
}

func TestRing_WithGroup(t *testing.T) {
	r, _ := NewRing(5)
	h := r.WithGroup("g1").WithAttrs([]slog.Attr{slog.String("k", "v")})
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	mustHandle(t, h.(*Ring), slog.NewRecord(now, slog.LevelInfo, "msg", 0))

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}
	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "g1" {
			found = true
			for _, ga := range a.Value.Group() {
				if ga.Key == "k" && ga.Value.String() == "v" {
					break
				}
			}
			return false
		}
		return true
	})
	if !found {
		t.Error("expected group g1 with attr k=v")
	}
}

func TestRing_Enabled(t *testing.T) {
	r, _ := NewRing(5)
	if !r.Enabled(context.Background(), slog.LevelDebug) {
		t.Error("expected debug to be enabled")
	}
	if r.Enabled(context.Background(), slog.LevelDebug-1) {
		t.Error("expected level below debug to be disabled")
	}
}

func TestRing_ConcurrentSafety(t *testing.T) {
	r, _ := NewRing(100)
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	var wg sync.WaitGroup
	for range 20 {
		wg.Go(func() {
			mustHandle(t, r, slog.NewRecord(now, slog.LevelInfo, "concurrent", 0))
		})
	}
	wg.Wait()

	recs := r.Records()
	if len(recs) == 0 {
		t.Error("expected records after concurrent writes")
	}
}

func TestNew_NoHandlers(t *testing.T) {
	_, err := New()
	if err == nil {
		t.Fatal("expected error with no handlers")
	}
}

func TestNew_SingleHandler(t *testing.T) {
	r, _ := NewRing(5)
	logger, err := New(r)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	logger.Info("hello")
	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}
	if recs[0].Message != "hello" {
		t.Errorf("expected 'hello', got '%s'", recs[0].Message)
	}
}

func TestNew_MultipleHandlers(t *testing.T) {
	r1, _ := NewRing(5)
	r2, _ := NewRing(5)
	logger, err := New(r1, r2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	logger.Info("broadcast")

	if n := len(r1.Records()); n != 1 {
		t.Errorf("r1: expected 1 record, got %d", n)
	}
	if n := len(r2.Records()); n != 1 {
		t.Errorf("r2: expected 1 record, got %d", n)
	}
}

func mustHandle(t *testing.T, r *Ring, rec slog.Record) {
	t.Helper()
	if err := r.Handle(context.Background(), rec); err != nil {
		t.Fatalf("Handle failed: %v", err)
	}
}