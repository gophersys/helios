package logfan

import (
	"context"
	"log/slog"
	"sync"
	"testing"
	"time"
)

func TestNewRingInvalidCapacity(t *testing.T) {
	tests := []struct {
		cap  int
		desc string
	}{
		{0, "zero"},
		{-1, "negative"},
		{-100, "large negative"},
	}
	for _, tt := range tests {
		_, err := NewRing(tt.cap)
		if err == nil {
			t.Errorf("NewRing(%d) (%s): expected error", tt.cap, tt.desc)
		}
	}
}

func TestRingRecordsEmpty(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	if recs := r.Records(); recs != nil {
		t.Errorf("expected nil for empty ring, got %v", recs)
	}
}

func TestRingCaptureOrder(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}

	msgs := []string{"one", "two", "three", "four", "five"}
	for _, m := range msgs {
		r.Handle(context.Background(), slog.NewRecord(time.Now(), slog.LevelInfo, m, 0))
	}

	recs := r.Records()
	if len(recs) != len(msgs) {
		t.Fatalf("expected %d records, got %d", len(msgs), len(recs))
	}
	for i, m := range msgs {
		if recs[i].Message != m {
			t.Errorf("records[%d].Message = %q, want %q", i, recs[i].Message, m)
		}
	}
}

func TestRingEviction(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}

	for _, m := range []string{"one", "two", "three", "four"} {
		r.Handle(context.Background(), slog.NewRecord(time.Now(), slog.LevelInfo, m, 0))
	}

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records (capacity) after eviction, got %d", len(recs))
	}
	expected := []string{"two", "three", "four"}
	for i, m := range expected {
		if recs[i].Message != m {
			t.Errorf("records[%d].Message = %q, want %q", i, recs[i].Message, m)
		}
	}
}

func TestRingEvictionMultipleWraps(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}

	for _, m := range []string{"one", "two", "three", "four", "five", "six", "seven"} {
		r.Handle(context.Background(), slog.NewRecord(time.Now(), slog.LevelInfo, m, 0))
	}

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records, got %d", len(recs))
	}
	expected := []string{"five", "six", "seven"}
	for i, m := range expected {
		if recs[i].Message != m {
			t.Errorf("records[%d].Message = %q, want %q", i, recs[i].Message, m)
		}
	}
}

func TestRingRecordsCopy(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}

	r.Handle(context.Background(), slog.NewRecord(time.Now(), slog.LevelInfo, "original", 0))

	recs := r.Records()
	recs[0] = slog.NewRecord(time.Now(), slog.LevelError, "hacked", 0)

	original := r.Records()
	if original[0].Message == "hacked" {
		t.Error("Records() did not return a copy; modifying returned slice affected the ring")
	}
}

func TestRingConcurrentSafe(t *testing.T) {
	r, err := NewRing(100)
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 20; j++ {
				r.Handle(context.Background(), slog.NewRecord(time.Now(), slog.LevelInfo, "test", 0))
			}
		}()
	}
	wg.Wait()

	// Concurrent reads should also be safe
	var readWg sync.WaitGroup
	for i := 0; i < 5; i++ {
		readWg.Add(1)
		go func() {
			defer readWg.Done()
			recs := r.Records()
			_ = recs
		}()
	}
	readWg.Wait()

	recs := r.Records()
	if len(recs) != 100 {
		t.Errorf("expected 100 records (capacity), got %d", len(recs))
	}
}

func TestNewNoHandlers(t *testing.T) {
	_, err := New()
	if err == nil {
		t.Error("New() with no handlers: expected error")
	}
}

func TestNewSendsToAllHandlers(t *testing.T) {
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
		t.Fatal(err)
	}

	logger.Info("test message", "key", "val")

	recs1 := r1.Records()
	recs2 := r2.Records()

	if len(recs1) != 1 {
		t.Fatalf("r1: expected 1 record, got %d", len(recs1))
	}
	if len(recs2) != 1 {
		t.Fatalf("r2: expected 1 record, got %d", len(recs2))
	}
	if recs1[0].Message != "test message" {
		t.Errorf("r1 message = %q, want %q", recs1[0].Message, "test message")
	}
	if recs2[0].Message != "test message" {
		t.Errorf("r2 message = %q, want %q", recs2[0].Message, "test message")
	}
}

func TestRingImplementsSlogHandler(t *testing.T) {
	r, err := NewRing(1)
	if err != nil {
		t.Fatal(err)
	}
	var _ slog.Handler = r
}

func TestRingEnabled(t *testing.T) {
	r, err := NewRing(1)
	if err != nil {
		t.Fatal(err)
	}
	if !r.Enabled(context.Background(), slog.LevelDebug) {
		t.Error("Enabled returned false for LevelDebug")
	}
	if !r.Enabled(context.Background(), slog.LevelInfo) {
		t.Error("Enabled returned false for LevelInfo")
	}
}

func TestRingWithAttrsAndGroup(t *testing.T) {
	r, err := NewRing(1)
	if err != nil {
		t.Fatal(err)
	}

	h1 := r.WithAttrs(nil)
	if _, ok := h1.(*Ring); !ok {
		t.Error("WithAttrs returned a non-Ring handler")
	}

	h2 := r.WithGroup("testgroup")
	if _, ok := h2.(*Ring); !ok {
		t.Error("WithGroup returned a non-Ring handler")
	}
}

func TestRingPartialFillNotWrapped(t *testing.T) {
	r, err := NewRing(10)
	if err != nil {
		t.Fatal(err)
	}

	// Fill less than capacity, verify order
	for _, m := range []string{"a", "b", "c"} {
		r.Handle(context.Background(), slog.NewRecord(time.Now(), slog.LevelInfo, m, 0))
	}

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records, got %d", len(recs))
	}
	if recs[0].Message != "a" || recs[1].Message != "b" || recs[2].Message != "c" {
		t.Errorf("unexpected order: got %q, %q, %q", recs[0].Message, recs[1].Message, recs[2].Message)
	}
}

func TestRingRecordsAreCloned(t *testing.T) {
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}

	// Store record, then modify the original (via Handle getting it again as a different record)
	r.Handle(context.Background(), slog.NewRecord(time.Now(), slog.LevelInfo, "first", 0))
	r.Handle(context.Background(), slog.NewRecord(time.Now(), slog.LevelInfo, "second", 0))

	recs := r.Records()
	if recs[0].Message != "first" {
		t.Errorf("record 0 message changed: got %q, want %q", recs[0].Message, "first")
	}
}
