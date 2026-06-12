package cache

import (
	"sync"
	"testing"
)

func TestNewWithInvalidCapacity(t *testing.T) {
	_, err := New(Config{Capacity: 0})
	if err == nil {
		t.Fatal("expected error for zero capacity")
	}

	_, err = New(Config{Capacity: -1})
	if err == nil {
		t.Fatal("expected error for negative capacity")
	}
}

func TestNewWithValidCapacity(t *testing.T) {
	c, err := New(Config{Capacity: 1})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if c == nil {
		t.Fatal("expected non-nil cache")
	}
}

func TestGetOnEmpty(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	_, ok := c.Get("missing")
	if ok {
		t.Fatal("expected false on missing key")
	}
}

func TestPutAndGet(t *testing.T) {
	c, _ := New(Config{Capacity: 3})

	c.Put("a", "1")
	val, ok := c.Get("a")
	if !ok {
		t.Fatal("expected true for existing key")
	}
	if val != "1" {
		t.Fatalf("expected '1', got %q", val)
	}
}

func TestPutUpdatesExisting(t *testing.T) {
	c, _ := New(Config{Capacity: 3})

	c.Put("a", "1")
	c.Put("a", "2")

	val, ok := c.Get("a")
	if !ok {
		t.Fatal("expected true for existing key")
	}
	if val != "2" {
		t.Fatalf("expected '2', got %q", val)
	}

	if c.Len() != 1 {
		t.Fatalf("expected length 1, got %d", c.Len())
	}
}

func TestEviction(t *testing.T) {
	c, _ := New(Config{Capacity: 2})

	c.Put("a", "1")
	c.Put("b", "2")
	// Cache: [b (MRU), a (LRU)]

	// Access 'a' to make it MRU.
	c.Get("a")
	// Cache: [a (MRU), b (LRU)]

	c.Put("c", "3")
	// Should evict 'b'.

	_, ok := c.Get("b")
	if ok {
		t.Fatal("expected 'b' to be evicted")
	}

	val, ok := c.Get("a")
	if !ok || val != "1" {
		t.Fatalf("expected 'a'='1', got %q/%v", val, ok)
	}

	val, ok = c.Get("c")
	if !ok || val != "3" {
		t.Fatalf("expected 'c'='3', got %q/%v", val, ok)
	}

	if c.Len() != 2 {
		t.Fatalf("expected length 2, got %d", c.Len())
	}
}

func TestEvictionUpdatesKey(t *testing.T) {
	c, _ := New(Config{Capacity: 2})

	// Fill cache.
	c.Put("a", "1")
	c.Put("b", "2")
	// Cache: [b (MRU), a (LRU)] — 'a' is LRU.

	// Insert 'c' with eviction: 'a' should be evicted.
	c.Put("c", "3")

	_, ok := c.Get("a")
	if ok {
		t.Fatal("expected 'a' to be evicted")
	}

	val, ok := c.Get("b")
	if !ok || val != "2" {
		t.Fatalf("expected 'b'='2', got %q/%v", val, ok)
	}

	val, ok = c.Get("c")
	if !ok || val != "3" {
		t.Fatalf("expected 'c'='3', got %q/%v", val, ok)
	}
}

func TestLen(t *testing.T) {
	c, _ := New(Config{Capacity: 5})

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

	// Update existing — len should not change.
	c.Put("a", "3")
	if c.Len() != 2 {
		t.Fatalf("expected 2 after update, got %d", c.Len())
	}

	// Fill to capacity.
	c.Put("c", "4")
	c.Put("d", "5")
	c.Put("e", "6")
	// Cache is full (capacity 5). Next insert evicts.
	c.Put("f", "7")
	if c.Len() != 5 {
		t.Fatalf("expected 5 after eviction, got %d", c.Len())
	}
}

func TestConcurrency(t *testing.T) {
	c, _ := New(Config{Capacity: 100})

	var wg sync.WaitGroup

	// Concurrent writers.
	for i := range 20 {
		i := i
		wg.Go(func() {
			key := string(rune('a' + i))
			c.Put(key, key)
		})
	}
	wg.Wait()

	// Concurrent readers and writers.
	for i := range 20 {
		i := i
		wg.Go(func() {
			key := string(rune('a' + i))
			c.Get(key)
			c.Put(key, key)
		})
	}

	// Ensure Len doesn't panic and gives a sensible value.
	if n := c.Len(); n <= 0 || n > 100 {
		t.Fatalf("unexpected length %d", n)
	}
}

func BenchmarkGet(b *testing.B) {
	c, _ := New(Config{Capacity: 1000})

	// Pre-populate with keys that will be found.
	for i := 0; i < 1000; i++ {
		key := string(rune(i))
		c.Put(key, "value")
	}

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		var i int
		for pb.Next() {
			key := string(rune(i % 1000))
			c.Get(key)
			i++
		}
	})
}

func BenchmarkPut(b *testing.B) {
	c, _ := New(Config{Capacity: 100})

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		var i int
		for pb.Next() {
			key := string(rune(i % 200))
			c.Put(key, "value")
			i++
		}
	})
}
