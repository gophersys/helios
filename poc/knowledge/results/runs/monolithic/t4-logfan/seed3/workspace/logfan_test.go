package logfan

import (
	"log/slog"
	"sync"
	"testing"
)

// --- NewRing ---

func TestNewRing_negative(t *testing.T) {
	_, err := NewRing(-1)
	if err == nil {
		t.Fatal("NewRing(-1): want error, got nil")
	}
}

func TestNewRing_zero(t *testing.T) {
	_, err := NewRing(0)
	if err == nil {
		t.Fatal("NewRing(0): want error, got nil")
	}
}

func TestNewRing_ok(t *testing.T) {
	r, err := NewRing(5)
	if err != nil {
		t.Fatalf("NewRing(5): unexpected error: %v", err)
	}
	if r == nil {
		t.Fatal("NewRing(5): got nil Ring")
	}
	recs := r.Records()
	if len(recs) != 0 {
		t.Fatalf("empty ring: got %d records, want 0", len(recs))
	}
}

// --- Ring.Records (basic) ---

func TestRing_Records_empty(t *testing.T) {
	r := mustRing(t, 10)
	recs := r.Records()
	if len(recs) != 0 {
		t.Fatalf("empty ring: got %d records", len(recs))
	}
}

func TestRing_Records_one(t *testing.T) {
	r := mustRing(t, 10)
	log := slog.New(r)
	log.Info("hello")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("want 1 record, got %d", len(recs))
	}
	if recs[0].Message != "hello" {
		t.Fatalf("message: want %q, got %q", "hello", recs[0].Message)
	}
}

func TestRing_Records_oldestFirst(t *testing.T) {
	r := mustRing(t, 10)
	log := slog.New(r)

	for i := 0; i < 5; i++ {
		log.Info("msg", "i", i)
	}

	recs := r.Records()
	if len(recs) != 5 {
		t.Fatalf("want 5 records, got %d", len(recs))
	}

	// slog.Handle iteration order isn't guaranteed to be insertion order,
	// but in practice slog itself delivers records synchronously and we
	// store them in insertion order. Verify that records reflect what
	// was logged by checking attrs.
	for idx, rec := range recs {
		var i int64
		rec.Attrs(func(a slog.Attr) bool {
			if a.Key == "i" {
				i = a.Value.Any().(int64)
			}
			return true
		})
		if int(i) != idx {
			t.Fatalf("record %d: want i=%d, got i=%d", idx, idx, i)
		}
	}
}

func TestRing_Records_eviction(t *testing.T) {
	r := mustRing(t, 3)
	log := slog.New(r)

	for i := 0; i < 10; i++ {
		log.Info("msg", "i", i)
	}

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("want 3 records (capacity), got %d", len(recs))
	}

	// Oldest three should be 7, 8, 9.
	for idx, rec := range recs {
		var i int64
		rec.Attrs(func(a slog.Attr) bool {
			if a.Key == "i" {
				i = a.Value.Any().(int64)
			}
			return true
		})
		want := int64(idx + 7)
		if i != want {
			t.Fatalf("record %d: want i=%d, got i=%d", idx, want, i)
		}
	}
}

func TestRing_Records_copy(t *testing.T) {
	r := mustRing(t, 5)
	log := slog.New(r)
	log.Info("a")

	recs := r.Records()
	slog.New(r).Info("b") // add another record; should not affect slice

	if len(recs) != 1 {
		t.Fatalf("returned slice length changed: want 1, got %d", len(recs))
	}
	if recs[0].Message != "a" {
		t.Fatalf("returned slice record mutated: want %q, got %q", "a", recs[0].Message)
	}
}

// --- Ring implements slog.Handler ---

func TestRing_Enabled(t *testing.T) {
	r := mustRing(t, 5)
	if !r.Enabled(nil, slog.LevelDebug) {
		t.Fatal("Enabled(LevelDebug): want true")
	}
	if !r.Enabled(nil, slog.LevelInfo) {
		t.Fatal("Enabled(LevelInfo): want true")
	}
	if !r.Enabled(nil, slog.LevelWarn) {
		t.Fatal("Enabled(LevelWarn): want true")
	}
	if !r.Enabled(nil, slog.LevelError) {
		t.Fatal("Enabled(LevelError): want true")
	}
}

func TestRing_WithAttrs(t *testing.T) {
	r := mustRing(t, 5)
	h := r.WithAttrs([]slog.Attr{slog.String("env", "test")})
	log := slog.New(h)
	log.Info("hello")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("want 1 record, got %d", len(recs))
	}

	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "env" && a.Value.String() == "test" {
			found = true
			return false
		}
		return true
	})
	if !found {
		t.Fatal("record missing 'env' attr from WithAttrs")
	}
}

func TestRing_WithGroup(t *testing.T) {
	r := mustRing(t, 5)
	h := r.WithGroup("g").WithAttrs([]slog.Attr{slog.String("k", "v")})
	log := slog.New(h)
	log.Info("hello")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("want 1 record, got %d", len(recs))
	}

	// The record should have a group "g" containing k=v.
	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "g" && a.Value.Kind() == slog.KindGroup {
			for _, inner := range a.Value.Group() {
				if inner.Key == "k" && inner.Value.String() == "v" {
					found = true
					return false
				}
			}
		}
		return true
	})
	if !found {
		t.Fatal("record missing group 'g' with attr k=v")
	}
}

// --- Concurrent safety ---

func TestRing_concurrent(t *testing.T) {
	r := mustRing(t, 100)
	log := slog.New(r)

	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				log.Info("concurrent", "goroutine", n, "seq", j)
			}
		}(i)
	}
	wg.Wait()

	recs := r.Records()
	if len(recs) != 100 {
		t.Fatalf("ring should hold capacity (100), got %d", len(recs))
	}
	// Verify all records are valid — every one should have a Message.
	for i, rec := range recs {
		if rec.Message == "" {
			t.Fatalf("record %d has empty message", i)
		}
	}
}

func TestRing_Records_concurrent(t *testing.T) {
	r := mustRing(t, 50)
	log := slog.New(r)

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		for j := 0; j < 100; j++ {
			log.Info("write", "j", j)
		}
	}()

	// Read concurrently — should never panic or race.
	for k := 0; k < 20; k++ {
		_ = r.Records()
	}
	wg.Wait()
}

// --- New ---

func TestNew_empty(t *testing.T) {
	_, err := New()
	if err == nil {
		t.Fatal("New(): want error, got nil")
	}
}

func TestNew_oneHandler(t *testing.T) {
	r := mustRing(t, 5)
	l, err := New(r)
	if err != nil {
		t.Fatalf("New(ring): unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("New(ring): got nil logger")
	}
	l.Info("works")
	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("want 1 record, got %d", len(recs))
	}
}

func TestNew_fanOut(t *testing.T) {
	r1 := mustRing(t, 5)
	r2 := mustRing(t, 5)

	l, err := New(r1, r2)
	if err != nil {
		t.Fatalf("New(r1, r2): unexpected error: %v", err)
	}

	l.Info("fanned")

	recs1 := r1.Records()
	recs2 := r2.Records()

	if len(recs1) != 1 {
		t.Fatalf("r1: want 1 record, got %d", len(recs1))
	}
	if len(recs2) != 1 {
		t.Fatalf("r2: want 1 record, got %d", len(recs2))
	}
	if recs1[0].Message != "fanned" {
		t.Fatalf("r1 message: want %q, got %q", "fanned", recs1[0].Message)
	}
	if recs2[0].Message != "fanned" {
		t.Fatalf("r2 message: want %q, got %q", "fanned", recs2[0].Message)
	}
}

func TestNew_fanOut_attrs(t *testing.T) {
	r1 := mustRing(t, 5)
	r2 := mustRing(t, 5)

	l := slog.New(slog.NewMultiHandler(r1, r2))
	l.Info("attrs", "key", "val")

	recs1 := r1.Records()
	recs2 := r2.Records()

	for _, rec := range recs1 {
		var found bool
		rec.Attrs(func(a slog.Attr) bool {
			if a.Key == "key" && a.Value.String() == "val" {
				found = true
				return false
			}
			return true
		})
		if !found {
			t.Fatal("r1 record missing attr 'key'")
		}
	}
	for _, rec := range recs2 {
		var found bool
		rec.Attrs(func(a slog.Attr) bool {
			if a.Key == "key" && a.Value.String() == "val" {
				found = true
				return false
			}
			return true
		})
		if !found {
			t.Fatal("r2 record missing attr 'key'")
		}
	}
}

// --- helpers ---

func mustRing(t testing.TB, capacity int) *Ring {
	t.Helper()
	r, err := NewRing(capacity)
	if err != nil {
		t.Fatalf("NewRing(%d): %v", capacity, err)
	}
	return r
}