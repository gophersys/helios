package logfan

import (
	"context"
	"log/slog"
	"sync"
	"testing"
)

// Compile-time check: *Ring implements slog.Handler.
var _ slog.Handler = (*Ring)(nil)

func TestNewRing_ValidCapacity(t *testing.T) {
	r, err := NewRing(10)
	if err != nil {
		t.Fatalf("NewRing(10) unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("NewRing(10) returned nil")
	}
}

func TestNewRing_ZeroCapacity(t *testing.T) {
	_, err := NewRing(0)
	if err == nil {
		t.Fatal("NewRing(0) expected error")
	}
}

func TestNewRing_NegativeCapacity(t *testing.T) {
	_, err := NewRing(-1)
	if err == nil {
		t.Fatal("NewRing(-1) expected error")
	}
}

func TestRing_HandleAndRecords(t *testing.T) {
	r, _ := NewRing(3)

	rec := slog.NewRecord(slog.LevelInfo, "test message", 0)
	rec.AddAttrs(slog.String("key", "val"))
	if err := r.Handle(context.Background(), rec); err != nil {
		t.Fatalf("Handle error: %v", err)
	}

	records := r.Records()
	if len(records) != 1 {
		t.Fatalf("expected 1 record, got %d", len(records))
	}
	if records[0].Message != "test message" {
		t.Errorf("expected message %q, got %q", "test message", records[0].Message)
	}
	if records[0].Level != slog.LevelInfo {
		t.Errorf("expected level %v, got %v", slog.LevelInfo, records[0].Level)
	}
}

func TestRing_Eviction(t *testing.T) {
	r, _ := NewRing(3)

	for i := range 5 {
		rec := slog.NewRecord(slog.LevelInfo, "", 0)
		rec.AddAttrs(slog.Int("i", i))
		r.Handle(context.Background(), rec)
	}

	records := r.Records()
	if len(records) != 3 {
		t.Fatalf("expected 3 records, got %d", len(records))
	}

	// Oldest should be records 2, 3, 4
	var got []int
	for _, rec := range records {
		var val int
		rec.Attrs(func(a slog.Attr) bool {
			if a.Key == "i" {
				val = a.Value.Int64()
			}
			return true
		})
		got = append(got, int(val))
	}
	want := []int{2, 3, 4}
	if !equal(got, want) {
		t.Errorf("expected oldest first %v, got %v", want, got)
	}
}

func TestRing_RecordsReturnsCopy(t *testing.T) {
	r, _ := NewRing(2)
	rec := slog.NewRecord(slog.LevelInfo, "msg", 0)
	r.Handle(context.Background(), rec)

	records := r.Records()
	records[0].Message = "tampered"

	// Original should be unaffected
	records2 := r.Records()
	if records2[0].Message != "msg" {
		t.Errorf("records copy was not isolated; got message %q", records2[0].Message)
	}
}

func TestRing_ConcurrentSafety(t *testing.T) {
	r, _ := NewRing(100)
	var wg sync.WaitGroup
	for i := range 50 {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			rec := slog.NewRecord(slog.LevelInfo, "", 0)
			rec.AddAttrs(slog.Int("n", n))
			r.Handle(context.Background(), rec)

			// Read concurrently too
			r.Records()
		}(i)
	}
	wg.Wait()

	// At least some records made it through
	if rc := len(r.Records()); rc == 0 {
		t.Error("expected at least one record after concurrent writes, got 0")
	}
}

func TestRing_EnabledAlways(t *testing.T) {
	r, _ := NewRing(1)
	if !r.Enabled(context.Background(), slog.LevelDebug) {
		t.Error("expected Enabled to return true for Debug")
	}
	if !r.Enabled(context.Background(), slog.LevelInfo) {
		t.Error("expected Enabled to return true for Info")
	}
	if !r.Enabled(context.Background(), slog.LevelWarn) {
		t.Error("expected Enabled to return true for Warn")
	}
	if !r.Enabled(context.Background(), slog.LevelError) {
		t.Error("expected Enabled to return true for Error")
	}
}

func TestRing_RecordsWhenEmpty(t *testing.T) {
	r, _ := NewRing(5)
	records := r.Records()
	if len(records) != 0 {
		t.Fatalf("expected 0 records on empty ring, got %d", len(records))
	}
}

func TestNew_WithHandlers(t *testing.T) {
	r, _ := NewRing(2)
	logger, err := New(r)
	if err != nil {
		t.Fatalf("New error: %v", err)
	}
	if logger == nil {
		t.Fatal("New returned nil logger")
	}

	logger.Info("hello")
	if len(r.Records()) != 1 {
		t.Fatalf("expected 1 record, got %d", len(r.Records()))
	}
}

func TestNew_NoHandlers(t *testing.T) {
	_, err := New()
	if err == nil {
		t.Fatal("New() expected error")
	}
}

func TestNew_MultipleHandlers(t *testing.T) {
	r1, _ := NewRing(5)
	r2, _ := NewRing(5)

	logger, err := New(r1, r2)
	if err != nil {
		t.Fatalf("New error: %v", err)
	}

	logger.Info("broadcast")

	if len(r1.Records()) != 1 {
		t.Errorf("expected 1 record in r1, got %d", len(r1.Records()))
	}
	if len(r2.Records()) != 1 {
		t.Errorf("expected 1 record in r2, got %d", len(r2.Records()))
	}

	if r1.Records()[0].Message != "broadcast" {
		t.Errorf("r1 message = %q, want %q", r1.Records()[0].Message, "broadcast")
	}
	if r2.Records()[0].Message != "broadcast" {
		t.Errorf("r2 message = %q, want %q", r2.Records()[0].Message, "broadcast")
	}
}

func TestRing_WithAttrs(t *testing.T) {
	r, _ := NewRing(5)
	h := r.WithAttrs([]slog.Attr{slog.String("app", "test")})
	logger := slog.New(h)
	logger.Info("msg", slog.Int("count", 42))

	records := r.Records()
	if len(records) != 1 {
		t.Fatalf("expected 1 record, got %d", len(records))
	}

	// Record should have both "app" and "count" attrs
	var keys []string
	records[0].Attrs(func(a slog.Attr) bool {
		keys = append(keys, a.Key)
		return true
	})
	has := func(k string) bool {
		for _, kk := range keys {
			if kk == k {
				return true
			}
		}
		return false
	}
	if !has("app") {
		t.Errorf("expected attr 'app' in %v", keys)
	}
	if !has("count") {
		t.Errorf("expected attr 'count' in %v", keys)
	}
}

func TestRing_WithAttrsChains(t *testing.T) {
	r, _ := NewRing(5)
	h := r.WithAttrs([]slog.Attr{slog.String("a", "1")}).WithAttrs([]slog.Attr{slog.String("b", "2")})
	logger := slog.New(h)
	logger.Info("msg")

	records := r.Records()
	if len(records) != 1 {
		t.Fatalf("expected 1 record, got %d", len(records))
	}

	var keys []string
	records[0].Attrs(func(a slog.Attr) bool {
		keys = append(keys, a.Key)
		return true
	})

	if len(keys) != 2 {
		t.Fatalf("expected 2 attrs, got %v", keys)
	}
}

func TestRing_WithGroup(t *testing.T) {
	r, _ := NewRing(5)
	h := r.WithGroup("req")
	logger := slog.New(h)
	logger.Info("msg", slog.String("id", "abc"))

	// Record is stored with attrs; group is a formatting concern
	// We just verify the record is stored
	records := r.Records()
	if len(records) != 1 {
		t.Fatalf("expected 1 record, got %d", len(records))
	}
	if records[0].Message != "msg" {
		t.Errorf("message = %q, want %q", records[0].Message, "msg")
	}

	var keys []string
	records[0].Attrs(func(a slog.Attr) bool {
		keys = append(keys, a.Key)
		return true
	})
	if len(keys) != 1 || keys[0] != "id" {
		t.Errorf("expected attr [id], got %v", keys)
	}
}

func equal(a, b []int) bool {
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