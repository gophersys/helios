package logfan

import (
	"context"
	"log/slog"
	"sync"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// NewRing
// ---------------------------------------------------------------------------

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

func TestNewRing_Ok(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	if r.Records() != nil {
		t.Fatal("new ring should have nil records")
	}
}

// ---------------------------------------------------------------------------
// Ring basic store/retrieve
// ---------------------------------------------------------------------------

func TestRing_StoreSingle(t *testing.T) {
	r, _ := NewRing(3)
	rec := slog.NewRecord(time.Now(), slog.LevelInfo, "hello", 0)
	if err := r.Handle(context.Background(), rec); err != nil {
		t.Fatal(err)
	}
	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("want 1 record, got %d", len(recs))
	}
	if recs[0].Message != "hello" {
		t.Fatalf("want message 'hello', got %q", recs[0].Message)
	}
}

func TestRing_OldestFirst(t *testing.T) {
	r, _ := NewRing(5)
	for _, msg := range []string{"a", "b", "c"} {
		rec := slog.NewRecord(time.Now(), slog.LevelInfo, msg, 0)
		r.Handle(context.Background(), rec)
	}
	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("want 3 records, got %d", len(recs))
	}
	for i, want := range []string{"a", "b", "c"} {
		if recs[i].Message != want {
			t.Fatalf("record %d: want %q, got %q", i, want, recs[i].Message)
		}
	}
}

func TestRing_EvictsOldest(t *testing.T) {
	r, _ := NewRing(3)
	for _, msg := range []string{"a", "b", "c", "d", "e"} {
		rec := slog.NewRecord(time.Now(), slog.LevelInfo, msg, 0)
		r.Handle(context.Background(), rec)
	}
	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("want 3 records, got %d", len(recs))
	}
	// "c", "d", "e" should remain; "a", "b" evicted
	for i, want := range []string{"c", "d", "e"} {
		if recs[i].Message != want {
			t.Fatalf("record %d: want %q, got %q", i, want, recs[i].Message)
		}
	}
}

func TestRing_EvictWraparound(t *testing.T) {
	// capacity 2, write 7 + 1 = 8 records to force multiple wraparounds
	r, _ := NewRing(2)
	for i := 0; i < 8; i++ {
		rec := slog.NewRecord(time.Now(), slog.LevelInfo, "x", 0)
		r.Handle(context.Background(), rec)
	}
	recs := r.Records()
	if len(recs) != 2 {
		t.Fatalf("want 2 records, got %d", len(recs))
	}
}

// ---------------------------------------------------------------------------
// Records deep-copy
// ---------------------------------------------------------------------------

func TestRing_RecordsCopy(t *testing.T) {
	r, _ := NewRing(3)
	rec := slog.NewRecord(time.Now(), slog.LevelInfo, "msg", 0)
	rec.AddAttrs(slog.String("k", "original"))
	r.Handle(context.Background(), rec)

	recs := r.Records()
	// mutate the returned record
	recs[0] = slog.NewRecord(time.Now(), slog.LevelInfo, "tampered", 0)

	// ring should still hold the original
	recs2 := r.Records()
	if recs2[0].Message != "msg" {
		t.Fatalf("ring was mutated: got %q, want %q", recs2[0].Message, "msg")
	}
}

// ---------------------------------------------------------------------------
// Concurrent safety
// ---------------------------------------------------------------------------

func TestRing_ConcurrentSafe(t *testing.T) {
	r, _ := NewRing(100)
	var wg sync.WaitGroup

	// 20 concurrent writers
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				rec := slog.NewRecord(time.Now(), slog.LevelInfo, "test", 0)
				r.Handle(context.Background(), rec)
			}
		}(i)
	}

	// 10 concurrent readers
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 20; j++ {
				r.Records()
			}
		}()
	}

	wg.Wait()

	recs := r.Records()
	if len(recs) != 100 {
		t.Fatalf("want 100 records, got %d", len(recs))
	}
}

// ---------------------------------------------------------------------------
// Enabled
// ---------------------------------------------------------------------------

func TestRing_Enabled(t *testing.T) {
	r, _ := NewRing(3)
	if !r.Enabled(context.Background(), slog.LevelDebug) {
		t.Fatal("Enabled should return true for Debug")
	}
	if !r.Enabled(context.Background(), slog.LevelError) {
		t.Fatal("Enabled should return true for Error")
	}
}

// ---------------------------------------------------------------------------
// WithAttrs / WithGroup
// ---------------------------------------------------------------------------

func TestRing_WithAttrs(t *testing.T) {
	r, _ := NewRing(3)
	h := r.WithAttrs([]slog.Attr{slog.String("tag", "a")})
	rec := slog.NewRecord(time.Now(), slog.LevelInfo, "with-attrs", 0)
	if err := h.Handle(context.Background(), rec); err != nil {
		t.Fatal(err)
	}
	// Ring handler doesn't persist attrs across instances,
	// but the returned handler is a working Ring.
	rr := h.(*Ring)
	recs := rr.Records()
	if len(recs) != 1 || recs[0].Message != "with-attrs" {
		t.Fatal("WithAttrs handler lost record")
	}
}

func TestRing_WithGroup(t *testing.T) {
	r, _ := NewRing(3)
	h := r.WithGroup("g")
	rec := slog.NewRecord(time.Now(), slog.LevelInfo, "with-group", 0)
	if err := h.Handle(context.Background(), rec); err != nil {
		t.Fatal(err)
	}
	rr := h.(*Ring)
	recs := rr.Records()
	if len(recs) != 1 || recs[0].Message != "with-group" {
		t.Fatal("WithGroup handler lost record")
	}
}

// ---------------------------------------------------------------------------
// slog.Logger integration
// ---------------------------------------------------------------------------

func TestRing_LoggerIntegration(t *testing.T) {
	r, _ := NewRing(5)
	logger := slog.New(r)
	logger.Info("integration test")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("want 1 record, got %d", len(recs))
	}
	if recs[0].Message != "integration test" {
		t.Fatalf("want message 'integration test', got %q", recs[0].Message)
	}
	if recs[0].Level != slog.LevelInfo {
		t.Fatalf("want level Info, got %v", recs[0].Level)
	}
}

func TestRing_LoggerWithAttrs(t *testing.T) {
	r, _ := NewRing(5)
	// slog.Logger.With() calls handler.WithAttrs(), returning a new Ring.
	// Capture it via type assertion to verify attrs flow through.
	h := r.WithAttrs([]slog.Attr{slog.String("key", "value")})
	logger := slog.New(h)
	logger.Info("with attrs")

	r2 := h.(*Ring)
	recs := r2.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}
	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "key" && a.Value.String() == "value" {
			found = true
			return false
		}
		return true
	})
	if !found {
		t.Fatal("expected attr 'key=value' in record")
	}
}

// ---------------------------------------------------------------------------
// New (fan-out)
// ---------------------------------------------------------------------------

func TestNew_NoHandlers(t *testing.T) {
	_, err := New()
	if err == nil {
		t.Fatal("expected error for zero handlers")
	}
}

func TestNew_FanOut(t *testing.T) {
	r1, _ := NewRing(5)
	r2, _ := NewRing(5)

	logger, err := New(r1, r2)
	if err != nil {
		t.Fatal(err)
	}

	logger.Info("fan-out test")

	recs1 := r1.Records()
	recs2 := r2.Records()

	if len(recs1) != 1 || recs1[0].Message != "fan-out test" {
		t.Fatal("r1 didn't receive the record")
	}
	if len(recs2) != 1 || recs2[0].Message != "fan-out test" {
		t.Fatal("r2 didn't receive the record")
	}
}

func TestNew_FanOutWithHandlerAttrs(t *testing.T) {
	r1, _ := NewRing(5)
	r2, _ := NewRing(5)

	// slog.Logger.With() calls handler.WithAttrs(). To verify fan-out
	// with attrs, we build the multiHandler directly and call WithAttrs
	// on it, then verify the derived handlers.
	mh := &multiHandler{handlers: []slog.Handler{r1, r2}}
	mh2 := mh.WithAttrs([]slog.Attr{slog.String("shared", "val")})
	logger := slog.New(mh2)
	logger.Info("fan-out with attrs")

	// mh2 wraps new Rings from WithAttrs — extract and verify them
	for i, h := range mh2.(*multiHandler).handlers {
		rr := h.(*Ring)
		recs := rr.Records()
		if len(recs) != 1 {
			t.Fatalf("handler %d: expected 1 record, got %d", i, len(recs))
		}
		var found bool
		recs[0].Attrs(func(a slog.Attr) bool {
			if a.Key == "shared" && a.Value.String() == "val" {
				found = true
				return false
			}
			return true
		})
		if !found {
			t.Fatalf("handler %d: expected attr 'shared=val' in record", i)
		}
	}
}

func TestMultiHandler_Enabled(t *testing.T) {
	r1, _ := NewRing(1)
	r2, _ := NewRing(1)
	mh := &multiHandler{handlers: []slog.Handler{r1, r2}}

	if !mh.Enabled(context.Background(), slog.LevelDebug) {
		t.Fatal("multiHandler.Enabled should be true")
	}
}

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

func TestRing_ExactCapacity(t *testing.T) {
	r, _ := NewRing(3)
	for _, msg := range []string{"a", "b", "c"} {
		r.Handle(context.Background(), slog.NewRecord(time.Now(), slog.LevelInfo, msg, 0))
	}
	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("want 3, got %d", len(recs))
	}
}

func TestRing_Levels(t *testing.T) {
	levels := []slog.Level{slog.LevelDebug, slog.LevelInfo, slog.LevelWarn, slog.LevelError}
	r, _ := NewRing(len(levels))
	for _, lvl := range levels {
		r.Handle(context.Background(), slog.NewRecord(time.Now(), lvl, "test", 0))
	}
	recs := r.Records()
	for i, lvl := range levels {
		if recs[i].Level != lvl {
			t.Fatalf("record %d: want level %v, got %v", i, lvl, recs[i].Level)
		}
	}
}

func TestRing_Timestamps(t *testing.T) {
	times := []time.Time{
		time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC),
		time.Date(2024, 6, 15, 12, 30, 0, 0, time.UTC),
	}
	r, _ := NewRing(2)
	for _, tm := range times {
		r.Handle(context.Background(), slog.NewRecord(tm, slog.LevelInfo, "ts", 0))
	}
	recs := r.Records()
	for i, tm := range times {
		if !recs[i].Time.Equal(tm) {
			t.Fatalf("record %d: want time %v, got %v", i, tm, recs[i].Time)
		}
	}
}