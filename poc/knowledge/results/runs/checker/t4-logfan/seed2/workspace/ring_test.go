package logfan

import (
	"context"
	"log/slog"
	"sync"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// Ring tests
// ---------------------------------------------------------------------------

func TestNewRing_InvalidCapacity(t *testing.T) {
	tests := []struct {
		name string
		c    int
	}{
		{"zero", 0},
		{"negative", -1},
		{"negative large", -42},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := NewRing(tt.c)
			if err == nil {
				t.Fatal("expected error for capacity", tt.c)
			}
		})
	}
}

func TestNewRing_ValidCapacity(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatal("unexpected error:", err)
	}
	if r == nil {
		t.Fatal("expected non-nil Ring")
	}
	recs := r.Records()
	if len(recs) != 0 {
		t.Fatalf("expected empty records, got %d", len(recs))
	}
}

func TestRing_StoreAndRetrieve(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}
	log := slog.New(r)
	log.Info("first")
	log.Warn("second")
	log.Error("third")

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records, got %d", len(recs))
	}
	if recs[0].Message != "first" {
		t.Errorf("expected msg[0]=first, got %q", recs[0].Message)
	}
	if recs[1].Message != "second" {
		t.Errorf("expected msg[1]=second, got %q", recs[1].Message)
	}
	if recs[2].Message != "third" {
		t.Errorf("expected msg[2]=third, got %q", recs[2].Message)
	}
	if recs[0].Level != slog.LevelInfo {
		t.Errorf("expected level info, got %v", recs[0].Level)
	}
	if recs[2].Level != slog.LevelError {
		t.Errorf("expected level error, got %v", recs[2].Level)
	}
}

func TestRing_Eviction(t *testing.T) {
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}
	log := slog.New(r)
	log.Info("keep1")
	log.Info("keep2")
	log.Info("evicted")

	recs := r.Records()
	// With capacity=2 and 3 records, the oldest ("keep1") is evicted.
	// Remaining: ["keep2", "evicted"] (oldest first).
	if len(recs) != 2 {
		t.Fatalf("expected 2 records, got %d", len(recs))
	}
	if recs[0].Message != "keep2" {
		t.Errorf("expected msg[0]=keep2, got %q", recs[0].Message)
	}
	if recs[1].Message != "evicted" {
		t.Errorf("expected msg[1]=evicted, got %q", recs[1].Message)
	}
}

func TestRing_EvictionOverwriteOldest(t *testing.T) {
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}
	log := slog.New(r)
	log.Info("a")
	log.Info("b")
	log.Info("c") // evicts "a"
	log.Info("d") // evicts "b"

	recs := r.Records()
	if len(recs) != 2 {
		t.Fatalf("expected 2 records, got %d", len(recs))
	}
	if recs[0].Message != "c" {
		t.Errorf("expected msg[0]=c, got %q", recs[0].Message)
	}
	if recs[1].Message != "d" {
		t.Errorf("expected msg[1]=d, got %q", recs[1].Message)
	}
}

func TestRing_RecordsCopy(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}
	log := slog.New(r)
	log.Info("msg")

	recs := r.Records()
	recs[0].Message = "mutated"

	recs2 := r.Records()
	if recs2[0].Message != "msg" {
		t.Errorf("original record was mutated; got %q", recs2[0].Message)
	}
}

func TestRing_ConcurrentAccess(t *testing.T) {
	r, err := NewRing(100)
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Go(func() {
			for j := 0; j < 100; j++ {
				r.Handle(context.Background(), slog.NewRecord(
					time.Time{}, slog.LevelInfo, "concurrent", 0,
				))
			}
		})
	}
	for i := 0; i < 5; i++ {
		wg.Go(func() {
			for j := 0; j < 50; j++ {
				_ = r.Records()
			}
		})
	}
	wg.Wait()

	recs := r.Records()
	if len(recs) != 100 {
		t.Fatalf("expected 100 records in ring, got %d", len(recs))
	}
}

func TestRing_WithAttrs(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	h := r.WithAttrs([]slog.Attr{slog.String("key", "val")})
	log := slog.New(h)
	log.Info("msg")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatal("expected 1 record")
	}
	attrs := collectAttrs(recs[0])
	if attrs["key"] != "val" {
		t.Errorf("expected key=val, got %v", attrs["key"])
	}
}

func TestRing_WithGroup(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	h := r.WithGroup("g").WithAttrs([]slog.Attr{slog.Int("x", 42)})
	log := slog.New(h)
	log.Info("msg")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatal("expected 1 record")
	}
	attrs := collectAttrs(recs[0])
	if _, ok := attrs["g"]; !ok {
		t.Fatal("expected group 'g'")
	}
}

// ---------------------------------------------------------------------------
// New / fan-out tests
// ---------------------------------------------------------------------------

func TestNew_NoHandlers(t *testing.T) {
	_, err := New()
	if err == nil {
		t.Fatal("expected error for no handlers")
	}
}

func TestNew_SingleHandler(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	log, err := New(r)
	if err != nil {
		t.Fatal("unexpected error:", err)
	}
	log.Info("hello")
	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}
}

func TestNew_FanOut(t *testing.T) {
	r1, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	r2, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	log, err := New(r1, r2)
	if err != nil {
		t.Fatal("unexpected error:", err)
	}
	log.Info("fanout")

	recs1 := r1.Records()
	recs2 := r2.Records()
	if len(recs1) != 1 {
		t.Fatalf("r1: expected 1 record, got %d", len(recs1))
	}
	if len(recs2) != 1 {
		t.Fatalf("r2: expected 1 record, got %d", len(recs2))
	}
	if recs1[0].Message != "fanout" || recs2[0].Message != "fanout" {
		t.Errorf("message mismatch: r1=%q r2=%q", recs1[0].Message, recs2[0].Message)
	}
}

func TestNew_FanOutMultipleRecords(t *testing.T) {
	r1, err := NewRing(10)
	if err != nil {
		t.Fatal(err)
	}
	r2, err := NewRing(10)
	if err != nil {
		t.Fatal(err)
	}
	log, err := New(r1, r2)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 5; i++ {
		log.Info("msg", slog.Int("i", i))
	}

	recs1 := r1.Records()
	recs2 := r2.Records()
	if len(recs1) != 5 || len(recs2) != 5 {
		t.Fatalf("both should have 5 records; r1=%d r2=%d", len(recs1), len(recs2))
	}
}

func TestNew_FanOutWithAttrs(t *testing.T) {
	r1, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	r2, err := NewRing(5)
	if err != nil {
		t.Fatal(err)
	}
	log, err := New(r1, r2)
	if err != nil {
		t.Fatal(err)
	}
	log.Info("a", slog.Int("n", 1))
	log.Warn("b")

	check := func(name string, recs []slog.Record) {
		if len(recs) != 2 {
			t.Fatalf("%s: expected 2 records, got %d", name, len(recs))
		}
		if recs[0].Message != "a" || recs[1].Message != "b" {
			t.Errorf("%s: messages mismatch", name)
		}
	}
	check("r1", r1.Records())
	check("r2", r2.Records())
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func collectAttrs(r slog.Record) map[string]any {
	m := make(map[string]any)
	r.Attrs(func(a slog.Attr) bool {
		if a.Value.Kind() == slog.KindGroup {
			sub := make(map[string]any)
			for _, sa := range a.Value.Group() {
				sub[sa.Key] = sa.Value.Any()
			}
			m[a.Key] = sub
		} else {
			m[a.Key] = a.Value.Any()
		}
		return true
	})
	return m
}