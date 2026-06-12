package cache

import (
	"sync"
	"testing"
)

func TestNew_InvalidCapacity(t *testing.T) {
	tests := []struct {
		name string
		cap  int
	}{
		{"zero", 0},
		{"negative", -1},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			c, err := New(Config{Capacity: tt.cap})
			if err == nil {
				t.Fatal("expected error for invalid capacity")
			}
			if c != nil {
				t.Fatal("expected nil cache on error")
			}
		})
	}
}

func TestNew_ValidCapacity(t *testing.T) {
	c, err := New(Config{Capacity: 1})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if c == nil {
		t.Fatal("expected non-nil cache")
	}
	if c.Len() != 0 {
		t.Fatalf("expected empty cache, got %d", c.Len())
	}
}

func TestGet_Miss(t *testing.T) {
	c := mustNew(t, 2)
	v, ok := c.Get("missing")
	if ok {
		t.Fatal("expected miss")
	}
	if v != "" {
		t.Fatalf("expected empty string, got %q", v)
	}
}

func TestPutAndGet(t *testing.T) {
	c := mustNew(t, 2)

	c.Put("a", "1")
	c.Put("b", "2")

	v, ok := c.Get("a")
	if !ok {
		t.Fatal("expected hit for a")
	}
	if v != "1" {
		t.Fatalf("expected '1', got %q", v)
	}

	v, ok = c.Get("b")
	if !ok {
		t.Fatal("expected hit for b")
	}
	if v != "2" {
		t.Fatalf("expected '2', got %q", v)
	}
}

func TestPut_UpdateExisting(t *testing.T) {
	c := mustNew(t, 2)

	c.Put("a", "1")
	c.Put("a", "2")

	v, ok := c.Get("a")
	if !ok {
		t.Fatal("expected hit for a")
	}
	if v != "2" {
		t.Fatalf("expected '2', got %q", v)
	}

	if c.Len() != 1 {
		t.Fatalf("expected length 1, got %d", c.Len())
	}
}

func TestEviction_LRU(t *testing.T) {
	c := mustNew(t, 2)

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3") // evicts "a"

	_, ok := c.Get("a")
	if ok {
		t.Fatal("expected 'a' to be evicted")
	}

	v, ok := c.Get("b")
	if !ok {
		t.Fatal("expected hit for b")
	}
	if v != "2" {
		t.Fatalf("expected '2', got %q", v)
	}

	v, ok = c.Get("c")
	if !ok {
		t.Fatal("expected hit for c")
	}
	if v != "3" {
		t.Fatalf("expected '3', got %q", v)
	}
}

func TestEviction_AccessPromotes(t *testing.T) {
	c := mustNew(t, 2)

	c.Put("a", "1")
	c.Put("b", "2")
	// Access "a" makes "b" the LRU.
	c.Get("a")
	c.Put("c", "3") // evicts "b"

	_, ok := c.Get("b")
	if ok {
		t.Fatal("expected 'b' to be evicted")
	}

	v, ok := c.Get("a")
	if !ok {
		t.Fatal("expected hit for a")
	}
	if v != "1" {
		t.Fatalf("expected '1', got %q", v)
	}
}

func TestLen(t *testing.T) {
	c := mustNew(t, 3)

	if c.Len() != 0 {
		t.Fatalf("expected 0, got %d", c.Len())
	}

	c.Put("a", "1")
	if c.Len() != 1 {
		t.Fatalf("expected 1, got %d", c.Len())
	}

	c.Put("b", "2")
	if c.Len() != 2 {
		t.Fatalf("expected 2, got %d", c.Len())
	}

	c.Put("c", "3")
	if c.Len() != 3 {
		t.Fatalf("expected 3, got %d", c.Len())
	}
}

func TestConcurrency(t *testing.T) {
	c := mustNew(t, 100)

	var wg sync.WaitGroup
	for i := range 50 {
		wg.Go(func() {
			key := string(rune('a' + i))
			c.Put(key, "v")
			c.Get(key)
			c.Len()
		})
	}
	wg.Wait()
}

// mustNew creates a cache for testing, failing the test on error.
func mustNew(t testing.TB, capacity int) *Cache {
	t.Helper()
	c, err := New(Config{Capacity: capacity})
	if err != nil {
		t.Fatalf("New(%d): %v", capacity, err)
	}
	return c
}

// BenchmarkGet measures Get on a hit.
func BenchmarkGet(b *testing.B) {
	c := mustNew(b, 1000)
	for i := range 1000 {
		c.Put(string(rune(i)), "value")
	}
	b.ResetTimer()
	for b.Loop() {
		c.Get("key0")
	}
}

// BenchmarkPutEviction measures Put when the cache is full (with eviction).
func BenchmarkPutEviction(b *testing.B) {
	c := mustNew(b, 100)
	// Fill to capacity.
	for i := range 100 {
		c.Put(string(rune(i)), "value")
	}
	b.ResetTimer()
	for b.Loop() {
		c.Put("evict-key", "value")
	}
}