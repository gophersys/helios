package logfan
import (

	"log/slog"
	"sync"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// Ring: construction
// ---------------------------------------------------------------------------

func TestNewRing_InvalidCapacity(t *testing.T) {
	tests := []struct {
		name string
		cap  int
	}{
		{"zero", 0},
		{"negative", -1},
		{"negative large", -100},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			r, err := NewRing(tt.cap)
			if err == nil {
				t.Fatal("expected error, got nil")
			}
			if r != nil {
				t.Fatal("expected nil Ring on error")
			}
		})
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

// ---------------------------------------------------------------------------
// Ring: records lifecycle
// ---------------------------------------------------------------------------

func TestRing_Records_Empty(t *testing.T) {
	r, _ := NewRing(5)
	recs := r.Records()
	if len(recs) != 0 {
		t.Fatalf("expected 0 records, got %d", len(recs))
	}
}

func TestRing_Records_FewerThanCapacity(t *testing.T) {
	r, _ := NewRing(10)
	logger := slog.New(r)
	logger.Info("msg1")
	logger.Info("msg2")
	logger.Info("msg3")

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records, got %d", len(recs))
	}
	if recs[0].Message != "msg1" {
		t.Errorf("expected msg1, got %q", recs[0].Message)
	}
	if recs[1].Message != "msg2" {
		t.Errorf("expected msg2, got %q", recs[1].Message)
	}
	if recs[2].Message != "msg3" {
		t.Errorf("expected msg3, got %q", recs[2].Message)
	}
}

func TestRing_Records_FullBuffer(t *testing.T) {
	r, _ := NewRing(3)
	logger := slog.New(r)
	for i := range 3 {
		logger.Info("msg", "i", i)
	}

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records, got %d", len(recs))
	}

	// overflow by one
	logger.Info("overflow")

	recs = r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records after overflow, got %d", len(recs))
	}
	if recs[0].Message != "msg" {
		t.Errorf("expected first message to be oldest kept (msg), got %q", recs[0].Message)
	}
	if recs[2].Message != "overflow" {
		t.Errorf("expected last message to be newest (overflow), got %q", recs[2].Message)
	}
}

func TestRing_Records_EvictionOrder(t *testing.T) {
	r, _ := NewRing(2)
	logger := slog.New(r)

	logger.Info("a")
	logger.Info("b")
	logger.Info("c") // evicts a

	recs := r.Records()
	if len(recs) != 2 {
		t.Fatalf("expected 2 records, got %d", len(recs))
	}
	if recs[0].Message != "b" {
		t.Errorf("expected 'b', got %q", recs[0].Message)
	}
	if recs[1].Message != "c" {
		t.Errorf("expected 'c', got %q", recs[1].Message)
	}

	logger.Info("d") // evicts b

	recs = r.Records()
	if recs[0].Message != "c" {
		t.Errorf("expected 'c', got %q", recs[0].Message)
	}
	if recs[1].Message != "d" {
		t.Errorf("expected 'd', got %q", recs[1].Message)
	}
}

func TestRing_Records_MultipleWrap(t *testing.T) {
	r, _ := NewRing(4)
	logger := slog.New(r)

	for i := range 12 {
		logger.Info("msg", "i", i)
	}

	recs := r.Records()
	if len(recs) != 4 {
		t.Fatalf("expected 4 records, got %d", len(recs))
	}
	// Should have indices 8,9,10,11 (the last 4 out of 0..11)
	for j, want := range []int{8, 9, 10, 11} {
		var found bool
		recs[j].Attrs(func(a slog.Attr) bool {
			if a.Key == "i" && a.Value.Int64() == int64(want) {
				found = true
			}
			return true
		})
		if !found {
			t.Errorf("record %d: expected i=%d, not found in attrs", j, want)
		}
	}
}

func TestRing_Records_IsCopy(t *testing.T) {
	r, _ := NewRing(5)
	logger := slog.New(r)
	logger.Info("m")

	recs1 := r.Records()
	recs2 := r.Records()

	// Mutating recs1 must not affect recs2
	recs1[0].Message = "hacked"
	if recs2[0].Message == "hacked" {
		t.Error("returned slice shares state with underlying buffer")
	}
}

// ---------------------------------------------------------------------------
// Ring: concurrent safety (exercised with -race)
// ---------------------------------------------------------------------------

func TestRing_Concurrent(t *testing.T) {
	r, _ := NewRing(50)
	var wg sync.WaitGroup

	// Writer goroutines
	for range 10 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for range 100 {
				slog.New(r).Info("concurrent")
			}
		}()
	}

	// Reader goroutines
	for range 5 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for range 50 {
				_ = r.Records()
			}
		}()
	}

	wg.Wait()

	recs := r.Records()
	if len(recs) != 50 {
		t.Logf("ring should have 50 records (full), got %d", len(recs))
	}
}

// ---------------------------------------------------------------------------
// New: construction
// ---------------------------------------------------------------------------

func TestNew_NoHandlers(t *testing.T) {
	l, err := New()
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if l != nil {
		t.Fatal("expected nil Logger on error")
	}
}

func TestNew_OneHandler(t *testing.T) {
	r, _ := NewRing(5)
	l, err := New(r)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if l == nil {
		t.Fatal("expected non-nil Logger")
	}
	l.Info("hello")
	recs := r.Records()
	if len(recs) != 1 || recs[0].Message != "hello" {
		t.Fatalf("expected 1 record with message 'hello', got %d records, first=%q", len(recs), recs[0].Message)
	}
}

func TestNew_MultipleHandlers(t *testing.T) {
	r1, _ := NewRing(5)
	r2, _ := NewRing(5)

	l, err := New(r1, r2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	l.Info("fanout")
	time.Sleep(10 * time.Millisecond) // no async, but be safe

	if len(r1.Records()) != 1 || r1.Records()[0].Message != "fanout" {
		t.Error("r1 did not receive the record")
	}
	if len(r2.Records()) != 1 || r2.Records()[0].Message != "fanout" {
		t.Error("r2 did not receive the record")
	}
}

// ---------------------------------------------------------------------------
// Ring: WithAttrs and WithGroup
// ---------------------------------------------------------------------------

func TestRing_WithAttrs(t *testing.T) {
	r, _ := NewRing(5)
	logger := slog.New(r.WithAttrs([]slog.Attr{slog.String("key1", "val1")}))
	logger.Info("m", "key2", "val2")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	attrs := attrsToMap(recs[0])
	if attrs["key1"] != "val1" {
		t.Errorf("expected key1=val1, got %q", attrs["key1"])
	}
	if attrs["key2"] != "val2" {
		t.Errorf("expected key2=val2, got %q", attrs["key2"])
	}
}

func TestRing_WithGroup(t *testing.T) {
	r, _ := NewRing(5)
	logger := slog.New(r.WithGroup("g").WithAttrs([]slog.Attr{slog.String("k", "v")}))
	logger.Info("m")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	var foundGroup bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "g" && a.Value.Kind() == slog.KindGroup {
			foundGroup = true
			for _, inner := range a.Value.Group() {
				if inner.Key == "k" && inner.Value.String() == "v" {
					return false // done
				}
			}
			t.Error("expected inner attr k=v inside group g")
		}
		return true
	})
	if !foundGroup {
		t.Error("expected group attr 'g'")
	}
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

func attrsToMap(r slog.Record) map[string]string {
	m := make(map[string]string)
	r.Attrs(func(a slog.Attr) bool {
		m[a.Key] = a.Value.String()
		return true
	})
	return m
}
