package cache

import (
	"strconv"
	"sync"
	"testing"
)

// --- Unit tests ---

func TestNew_InvalidCapacity(t *testing.T) {
	tests := []struct {
		capacity int
	}{
		{0},
		{-1},
		{-100},
	}
	for _, tc := range tests {
		c, err := New(Config{Capacity: tc.capacity})
		if err == nil {
			t.Errorf("New(Config{Capacity: %d}) expected error, got %+v", tc.capacity, c)
		}
	}
}

func TestNew_ValidCapacity(t *testing.T) {
	c, err := New(Config{Capacity: 1})
	if err != nil {
		t.Fatalf("New(Config{Capacity: 1}) unexpected error: %v", err)
	}
	if c.Len() != 0 {
		t.Fatalf("expected empty cache, got Len() = %d", c.Len())
	}
}

func TestGet_Miss(t *testing.T) {
	c := mustNew(t, 3)
	_, ok := c.Get("missing")
	if ok {
		t.Fatal("expected false on miss")
	}
}

func TestPut_Get_Hit(t *testing.T) {
	c := mustNew(t, 3)
	c.Put("a", "1")
	v, ok := c.Get("a")
	if !ok {
		t.Fatal("expected true on hit")
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
	c.Put("a", "updated")
	if c.Len() != 2 { // update does not change count
		t.Fatalf("expected 2 after update, got %d", c.Len())
	}
}

func TestEviction(t *testing.T) {
	c := mustNew(t, 2)
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3") // should evict "a" (insert order: a, b → a is LRU)

	if c.Len() != 2 {
		t.Fatalf("expected Len() = 2 after eviction, got %d", c.Len())
	}
	if _, ok := c.Get("a"); ok {
		t.Fatal("expected 'a' to be evicted")
	}
	if v, ok := c.Get("b"); !ok || v != "2" {
		t.Fatalf("expected 'b'/'2', got ok=%v, v=%q", ok, v)
	}
	if v, ok := c.Get("c"); !ok || v != "3" {
		t.Fatalf("expected 'c'/'3', got ok=%v, v=%q", ok, v)
	}
}

func TestLRU_Order_GetPromotes(t *testing.T) {
	c := mustNew(t, 3)
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	// Access "a", making it most recently used.
	c.Get("a")

	// Insert "d" — should evict "b" (LRU after promotion).
	c.Put("d", "4")

	if _, ok := c.Get("b"); ok {
		t.Fatal("expected 'b' to be evicted (accessed last before get)")
	}
	if _, ok := c.Get("a"); !ok {
		t.Fatal("expected 'a' to still be present (promoted by Get)")
	}
	if _, ok := c.Get("d"); !ok {
		t.Fatal("expected 'd' to be present")
	}
}

func TestLRU_Order_PutPromotes(t *testing.T) {
	c := mustNew(t, 2)
	c.Put("a", "1")
	c.Put("b", "2")

	// Update "a" — makes it most recently used.
	c.Put("a", "updated")

	// Insert "c" — should evict "b" (LRU now).
	c.Put("c", "3")

	if _, ok := c.Get("b"); ok {
		t.Fatal("expected 'b' to be evicted (not touched)")
	}
	if v, ok := c.Get("a"); !ok || v != "updated" {
		t.Fatalf("expected 'a'/'updated', got ok=%v, v=%q", ok, v)
	}
	if _, ok := c.Get("c"); !ok {
		t.Fatal("expected 'c' to be present")
	}
}

func TestConcurrency(t *testing.T) {
	c := mustNew(t, 100)
	var wg sync.WaitGroup

	// Concurrent writers.
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			c.Put(strconv.Itoa(i), strconv.Itoa(i))
		}(i)
	}
	wg.Wait()

	// Concurrent readers + writers.
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			c.Get(strconv.Itoa(i))
			c.Put(strconv.Itoa(i+50), strconv.Itoa(i+50))
		}(i)
	}
	wg.Wait()

	// Ensure no panics and Len is sensible.
	if n := c.Len(); n == 0 || n > 100 {
		t.Fatalf("unexpected Len() = %d", n)
	}
}

// --- Benchmarks ---

func BenchmarkGet(b *testing.B) {
	c := mustNew(b, 1000)
	for i := 0; i < 1000; i++ {
		c.Put(strconv.Itoa(i), strconv.Itoa(i))
	}

	b.ResetTimer()
	for b.Loop() {
		c.Get("500")
	}
}

func BenchmarkPutWithEviction(b *testing.B) {
	c := mustNew(b, 1000)
	// Fill the cache.
	for i := 0; i < 1000; i++ {
		c.Put(strconv.Itoa(i), strconv.Itoa(i))
	}

	b.ResetTimer()
	for b.Loop() {
		// Insert a new key each iteration to trigger eviction
		// of the LRU entry (key "0" initially, then sequential).
		c.Put("benchmark-key", "benchmark-value")
	}
}

// mustNew is a test helper; accepts testing.TB for use in both tests and benchmarks.
func mustNew(tb testing.TB, capacity int) *Cache {
	tb.Helper()
	c, err := New(Config{Capacity: capacity})
	if err != nil {
		tb.Fatalf("New(Config{Capacity: %d}) failed: %v", capacity, err)
	}
	return c
}