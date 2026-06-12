package logfan

import (
	"context"
	"log/slog"
	"sync"
	"testing"
	"time"
)

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
				t.Fatal("expected error for invalid capacity")
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
	recs := r.Records()
	if len(recs) != 0 {
		t.Fatalf("expected 0 records, got %d", len(recs))
	}
}

func TestRing_Basic(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	rec1 := slog.NewRecord(now, slog.LevelInfo, "msg1", 0)
	rec2 := slog.NewRecord(now, slog.LevelWarn, "msg2", 0)
	rec3 := slog.NewRecord(now, slog.LevelError, "msg3", 0)

	if err := r.Handle(ctx, rec1); err != nil {
		t.Fatal(err)
	}
	if err := r.Handle(ctx, rec2); err != nil {
		t.Fatal(err)
	}
	if err := r.Handle(ctx, rec3); err != nil {
		t.Fatal(err)
	}

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records, got %d", len(recs))
	}
	if recs[0].Message != "msg1" {
		t.Fatalf("expected msg1, got %s", recs[0].Message)
	}
	if recs[1].Message != "msg2" {
		t.Fatalf("expected msg2, got %s", recs[1].Message)
	}
	if recs[2].Message != "msg3" {
		t.Fatalf("expected msg3, got %s", recs[2].Message)
	}
}

func TestRing_EvictsOldest(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	for i := range 5 {
		rec := slog.NewRecord(now, slog.LevelInfo, slog.IntValue(i).String(), 0)
		if err := r.Handle(ctx, rec); err != nil {
			t.Fatal(err)
		}
	}

	recs := r.Records()
	if len(recs) != 3 {
		t.Fatalf("expected 3 records, got %d", len(recs))
	}
	// Oldest should be msg "2", "3", "4".
	if recs[0].Message != "2" {
		t.Fatalf("expected oldest to be '2', got %s", recs[0].Message)
	}
	if recs[1].Message != "3" {
		t.Fatalf("expected middle to be '3', got %s", recs[1].Message)
	}
	if recs[2].Message != "4" {
		t.Fatalf("expected newest to be '4', got %s", recs[2].Message)
	}
}

func TestRing_RecordsReturnsCopy(t *testing.T) {
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	rec := slog.NewRecord(now, slog.LevelInfo, "msg", 0)
	if err := r.Handle(ctx, rec); err != nil {
		t.Fatal(err)
	}

	recs1 := r.Records()
	recs2 := r.Records()

	// Mutate the first returned slice
	recs1[0].Message = "hacked"

	if recs2[0].Message != "msg" {
		t.Fatal("mutating returned Records slice affected the ring buffer")
	}

	// Verify the ring still holds the original
	recs3 := r.Records()
	if recs3[0].Message != "msg" {
		t.Fatal("mutating returned Records slice corrupted internal state")
	}
}

func TestRing_EnabledAlwaysTrue(t *testing.T) {
	r, err := NewRing(1)
	if err != nil {
		t.Fatal(err)
	}
	if !r.Enabled(context.Background(), slog.LevelDebug) {
		t.Fatal("Ring should be enabled for Debug")
	}
	if !r.Enabled(context.Background(), slog.LevelInfo) {
		t.Fatal("Ring should be enabled for Info")
	}
	if !r.Enabled(context.Background(), slog.LevelError) {
		t.Fatal("Ring should be enabled for Error")
	}
}

func TestRing_WithAttrs(t *testing.T) {
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	h := r.WithAttrs([]slog.Attr{slog.String("key1", "val1")})
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	rec := slog.NewRecord(now, slog.LevelInfo, "msg", 0)
	if err := h.Handle(ctx, rec); err != nil {
		t.Fatal(err)
	}

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "key1" && a.Value.String() == "val1" {
			found = true
			return false
		}
		return true
	})
	if !found {
		t.Fatal("expected key1=val1 attr on record")
	}
}

func TestRing_WithGroup(t *testing.T) {
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	h := r.WithGroup("g")
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)
	rec := slog.NewRecord(now, slog.LevelInfo, "msg", 0)
	rec.AddAttrs(slog.String("k", "v"))
	if err := h.Handle(ctx, rec); err != nil {
		t.Fatal(err)
	}

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "g" && a.Value.Kind() == slog.KindGroup {
			// Verify the group contains the record's attr.
			for _, child := range a.Value.Group() {
				if child.Key == "k" {
					found = true
					break
				}
			}
			return false
		}
		return true
	})
	if !found {
		t.Fatal("expected group 'g' to wrap record attrs")
	}
}

func TestRing_WithAttrsThenGroup(t *testing.T) {
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	// Chain: WithAttrs(a1) -> WithGroup("g") -> WithAttrs(a2)
	h := r.WithAttrs([]slog.Attr{slog.String("top", "t")})
	h = h.WithGroup("g")
	h = h.WithAttrs([]slog.Attr{slog.String("inner", "i")})

	rec := slog.NewRecord(now, slog.LevelInfo, "msg", 0)
	if err := h.Handle(ctx, rec); err != nil {
		t.Fatal(err)
	}

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	// Should have "top" at top level and group "g" containing "inner".
	var topFound, groupFound bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "top" {
			topFound = true
		}
		if a.Key == "g" && a.Value.Kind() == slog.KindGroup {
			groupFound = true
		}
		return true
	})
	if !topFound {
		t.Fatal("expected top-level attr 'top'")
	}
	if !groupFound {
		t.Fatal("expected group 'g'")
	}
}

func TestRing_ConcurrentSafe(t *testing.T) {
	r, err := NewRing(100)
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	var wg sync.WaitGroup
	n := 50

	// Concurrent writes
	for i := range n {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			rec := slog.NewRecord(now, slog.LevelInfo, slog.IntValue(i).String(), 0)
			_ = r.Handle(ctx, rec) //nolint:errcheck
		}(i)
	}

	// Concurrent reads
	for range n {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = r.Records() //nolint:errcheck
		}()
	}

	wg.Wait()

	// After all writes, there should be some records
	recs := r.Records()
	if len(recs) == 0 {
		t.Fatal("expected at least some records after concurrent writes")
	}
}

func TestRing_ChainWithGroupThenAttrs(t *testing.T) {
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	// Chain: WithGroup("g") -> WithAttrs(a)
	h := r.WithGroup("g")
	h = h.WithAttrs([]slog.Attr{slog.String("k", "v")})

	rec := slog.NewRecord(now, slog.LevelInfo, "msg", 0)
	if err := h.Handle(ctx, rec); err != nil {
		t.Fatal(err)
	}

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	// Should have group "g" containing "k=v".
	var group *slog.Attr
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "g" && a.Value.Kind() == slog.KindGroup {
			group = &a
			return false
		}
		return true
	})
	if group == nil {
		t.Fatal("expected group 'g'")
	}

	var innerFound bool
	for _, a := range group.Value.Group() {
		if a.Key == "k" {
			innerFound = true
		}
	}
	if !innerFound {
		t.Fatal("expected attr 'k' inside group 'g'")
	}
}

func TestRing_WithAttrsChained(t *testing.T) {
	r, err := NewRing(2)
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	now := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)

	h := r.WithAttrs([]slog.Attr{slog.String("a", "1")})
	h = h.WithAttrs([]slog.Attr{slog.String("b", "2")})

	rec := slog.NewRecord(now, slog.LevelInfo, "msg", 0)
	if err := h.Handle(ctx, rec); err != nil {
		t.Fatal(err)
	}

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	var aFound, bFound bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "a" {
			aFound = true
		}
		if a.Key == "b" {
			bFound = true
		}
		return true
	})
	if !aFound {
		t.Fatal("expected attr 'a'")
	}
	if !bFound {
		t.Fatal("expected attr 'b'")
	}
}