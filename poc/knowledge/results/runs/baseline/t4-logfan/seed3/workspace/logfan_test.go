package logfan

import (
	"context"
	"log/slog"
	"sync"
	"testing"
)

// ---------------------------------------------------------------------------
// NewRing
// ---------------------------------------------------------------------------

func TestNewRing_ZeroCapacity(t *testing.T) {
	r, err := NewRing(0)
	if err == nil {
		t.Fatal("expected error for capacity 0, got nil")
	}
	if r != nil {
		t.Fatal("expected nil Ring on error")
	}
}

func TestNewRing_NegativeCapacity(t *testing.T) {
	r, err := NewRing(-1)
	if err == nil {
		t.Fatal("expected error for negative capacity, got nil")
	}
	if r != nil {
		t.Fatal("expected nil Ring on error")
	}
}

func TestNewRing_Valid(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("expected non-nil Ring")
	}
}

// ---------------------------------------------------------------------------
// Ring basic operations
// ---------------------------------------------------------------------------

func TestRing_Records_Empty(t *testing.T) {
	r := mustRing(t, 5)
	recs := r.Records()
	if len(recs) != 0 {
		t.Fatalf("expected 0 records, got %d", len(recs))
	}
}

func TestRing_StoreAndRetrieve(t *testing.T) {
	r := mustRing(t, 3)
	log := slog.New(r)

	log.Info("first")
	log.Warn("second")
	log.Error("third")

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records, got %d", len(recs))
	}

	// Oldest first.
	checkMsg(t, recs[0], "first")
	checkMsg(t, recs[1], "second")
	checkMsg(t, recs[2], "third")

	// Levels preserved.
	if recs[0].Level != slog.LevelInfo {
		t.Fatalf("expected LevelInfo, got %v", recs[0].Level)
	}
	if recs[1].Level != slog.LevelWarn {
		t.Fatalf("expected LevelWarn, got %v", recs[1].Level)
	}
	if recs[2].Level != slog.LevelError {
		t.Fatalf("expected LevelError, got %v", recs[2].Level)
	}
}

func TestRing_EvictOldest(t *testing.T) {
	r := mustRing(t, 2)
	log := slog.New(r)

	log.Info("keep1")
	log.Info("keep2")
	log.Info("evicted")

	// Capacity 2, so "keep1" gets evicted when "evicted" arrives.
	// Remaining: ["keep2", "evicted"] (oldest first).
	recs := r.Records()
	if len(recs) != 2 {
		t.Fatalf("expected 2 records, got %d", len(recs))
	}
	checkMsg(t, recs[0], "keep2")
	checkMsg(t, recs[1], "evicted")

	// One more eviction removes "keep2", leaving ["evicted", "also_kept"].
	log.Info("also_kept")
	recs = r.Records()
	if len(recs) != 2 {
		t.Fatalf("expected 2 records, got %d", len(recs))
	}
	checkMsg(t, recs[0], "evicted")
	checkMsg(t, recs[1], "also_kept")
}

func TestRing_RecordsAreCopies(t *testing.T) {
	r := mustRing(t, 5)
	log := slog.New(r)

	log.Info("msg")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	// Mutate the returned slice — must not affect ring storage.
	recs[0] = slog.NewRecord(recs[0].Time, recs[0].Level, "tampered", recs[0].PC)

	recs2 := r.Records()
	if len(recs2) != 1 {
		t.Fatalf("expected 1 record in second read, got %d", len(recs2))
	}
	checkMsg(t, recs2[0], "msg")
}

func TestRing_HandlerEnabled(t *testing.T) {
	r := mustRing(t, 3)

	if !r.Enabled(context.Background(), slog.LevelDebug) {
		t.Fatal("expected LevelDebug to be enabled")
	}
	if !r.Enabled(context.Background(), slog.LevelInfo) {
		t.Fatal("expected LevelInfo to be enabled")
	}
	if !r.Enabled(context.Background(), slog.LevelWarn) {
		t.Fatal("expected LevelWarn to be enabled")
	}
	if !r.Enabled(context.Background(), slog.LevelError) {
		t.Fatal("expected LevelError to be enabled")
	}
}

func TestRing_RecordsWithAttrs(t *testing.T) {
	r := mustRing(t, 5)
	log := slog.New(r).With("key1", "val1")

	log.Info("msg1", "key2", "val2")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	// WithAttrs attrs should be present on the stored record.
	var found1, found2 bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "key1" {
			found1 = true
		}
		if a.Key == "key2" {
			found2 = true
		}
		return true
	})
	if !found1 {
		t.Fatal("expected pre-attr key1 from WithAttrs")
	}
	if !found2 {
		t.Fatal("expected attr key2 from log call")
	}
}

func TestRing_WithGroup(t *testing.T) {
	r := mustRing(t, 5)
	log := slog.New(r).WithGroup("g").With("k", "v")

	log.Info("msg")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "g" {
			found = true
		}
		return true
	})
	if !found {
		t.Fatal("expected group attr 'g' on stored record")
	}
}

// ---------------------------------------------------------------------------
// Concurrent safety
// ---------------------------------------------------------------------------

func TestRing_ConcurrentSafety(t *testing.T) {
	r := mustRing(t, 100)
	log := slog.New(r)

	var wg sync.WaitGroup

	// Concurrent writers.
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				log.Info("concurrent")
			}
		}()
	}

	// Concurrent readers.
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				_ = r.Records()
			}
		}()
	}

	wg.Wait()

	recs := r.Records()
	if len(recs) > 100 {
		t.Fatalf("expected at most 100 records, got %d", len(recs))
	}
}

// ---------------------------------------------------------------------------
// New — multi-handler
// ---------------------------------------------------------------------------

func TestNew_NoHandlers(t *testing.T) {
	log, err := New()
	if err == nil {
		t.Fatal("expected error for no handlers, got nil")
	}
	if log != nil {
		t.Fatal("expected nil Logger on error")
	}
}

func TestNew_SingleHandler(t *testing.T) {
	r := mustRing(t, 5)
	log, err := New(r)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if log == nil {
		t.Fatal("expected non-nil Logger")
	}

	log.Info("hello")
	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}
	checkMsg(t, recs[0], "hello")
}

func TestNew_MultipleHandlers(t *testing.T) {
	r1 := mustRing(t, 5)
	r2 := mustRing(t, 5)

	log, err := New(r1, r2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	log.Info("shared")

	recs1 := r1.Records()
	recs2 := r2.Records()

	if len(recs1) != 1 {
		t.Fatalf("handler 1: expected 1 record, got %d", len(recs1))
	}
	if len(recs2) != 1 {
		t.Fatalf("handler 2: expected 1 record, got %d", len(recs2))
	}
	checkMsg(t, recs1[0], "shared")
	checkMsg(t, recs2[0], "shared")
}

func TestNew_WithAttrs(t *testing.T) {
	r1 := mustRing(t, 5)
	r2 := mustRing(t, 5)

	log, err := New(r1, r2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	log = log.With("x", "y")
	log.Info("multi")

	for i, ring := range []*Ring{r1, r2} {
		recs := ring.Records()
		if len(recs) != 1 {
			t.Fatalf("ring %d: expected 1 record, got %d", i, len(recs))
		}
		var found bool
		recs[0].Attrs(func(a slog.Attr) bool {
			if a.Key == "x" {
				found = true
			}
			return true
		})
		if !found {
			t.Fatalf("ring %d: expected attr 'x'", i)
		}
	}
}

// ---------------------------------------------------------------------------
// ringHandle chaining
// ---------------------------------------------------------------------------

func TestRingHandle_WithAttrsThenWithGroup(t *testing.T) {
	r := mustRing(t, 5)

	// WithAttrs then WithGroup — preAttrs stay at top level.
	h := r.WithAttrs([]slog.Attr{slog.String("a", "1")}).WithGroup("g")
	log := slog.New(h)

	log.Info("msg", "b", "2")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	var foundA, foundG bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "a" {
			foundA = true
		}
		if a.Key == "g" {
			foundG = true
		}
		return true
	})
	if !foundA {
		t.Fatal("expected top-level attr 'a'")
	}
	if !foundG {
		t.Fatal("expected group attr 'g'")
	}
}

func TestRingHandle_WithGroupThenWithAttrs(t *testing.T) {
	r := mustRing(t, 5)

	// WithGroup then WithAttrs — attrs should be inside the group.
	h := r.WithGroup("g").WithAttrs([]slog.Attr{slog.String("k", "v")})
	log := slog.New(h)

	log.Info("msg")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "g" {
			found = true
		}
		return true
	})
	if !found {
		t.Fatal("expected group attr 'g' wrapping 'k'/'v'")
	}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func mustRing(t *testing.T, capacity int) *Ring {
	t.Helper()
	r, err := NewRing(capacity)
	if err != nil {
		t.Fatalf("NewRing(%d): %v", capacity, err)
	}
	return r
}

func checkMsg(t *testing.T, r slog.Record, want string) {
	t.Helper()
	if r.Message != want {
		t.Fatalf("expected message %q, got %q", want, r.Message)
	}
}
