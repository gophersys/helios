package cache

import (
	"strconv"
	"sync"
	"testing"
)

func TestNewInvalidCapacity(t *testing.T) {
	_, err := New(Config{Capacity: 0})
	if err == nil {
		t.Fatal("expected error for Capacity=0")
	}
	_, err = New(Config{Capacity: -1})
	if err == nil {
		t.Fatal("expected error for Capacity=-1")
	}
}

func TestNewValidCapacity(t *testing.T) {
	c, err := New(Config{Capacity: 5})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if c.Len() != 0 {
		t.Fatalf("expected empty cache, got Len=%d", c.Len())
	}
}

func TestGetMissing(t *testing.T) {
	c := mustNew(Config{Capacity: 5})
	v, ok := c.Get("missing")
	if ok {
		t.Fatal("expected false for missing key")
	}
	if v != "" {
		t.Fatalf("expected empty string, got %q", v)
	}
}

func TestPutAndGet(t *testing.T) {
	c := mustNew(Config{Capacity: 5})
	c.Put("a", "1")
	c.Put("b", "2")

	v, ok := c.Get("a")
	if !ok {
		t.Fatal("expected true for key 'a'")
	}
	if v != "1" {
		t.Fatalf("expected '1', got %q", v)
	}

	v, ok = c.Get("b")
	if !ok {
		t.Fatal("expected true for key 'b'")
	}
	if v != "2" {
		t.Fatalf("expected '2', got %q", v)
	}
}

func TestPutUpdateExisting(t *testing.T) {
	c := mustNew(Config{Capacity: 5})
	c.Put("k", "old")
	c.Put("k", "new")

	v, ok := c.Get("k")
	if !ok {
		t.Fatal("expected true for key 'k'")
	}
	if v != "new" {
		t.Fatalf("expected 'new', got %q", v)
	}
}

func TestEviction(t *testing.T) {
	c := mustNew(Config{Capacity: 3})

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	// Cache is now full. "a" is LRU.
	c.Put("d", "4") // evicts "a"

	if _, ok := c.Get("a"); ok {
		t.Fatal("expected 'a' to be evicted")
	}
	if _, ok := c.Get("b"); !ok {
		t.Fatal("expected 'b' to be present")
	}
	if _, ok := c.Get("c"); !ok {
		t.Fatal("expected 'c' to be present")
	}
	v, ok := c.Get("d")
	if !ok {
		t.Fatal("expected 'd' to be present")
	}
	if v != "4" {
		t.Fatalf("expected '4', got %q", v)
	}
}

func TestGetPromotes(t *testing.T) {
	c := mustNew(Config{Capacity: 3})

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	// Access "a" — it becomes MRU.
	c.Get("a")

	// Now "b" is LRU. Inserting "d" should evict "b".
	c.Put("d", "4")

	if _, ok := c.Get("b"); ok {
		t.Fatal("expected 'b' to be evicted (a was promoted)")
	}
	if _, ok := c.Get("a"); !ok {
		t.Fatal("expected 'a' to be present")
	}
}

func TestPutPromotesExisting(t *testing.T) {
	c := mustNew(Config{Capacity: 3})

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	// Update "a" — it becomes MRU.
	c.Put("a", "updated")

	// Now "b" is LRU. Inserting "d" should evict "b".
	c.Put("d", "4")

	if _, ok := c.Get("b"); ok {
		t.Fatal("expected 'b' to be evicted (a was promoted by Put)")
	}
}

func TestLen(t *testing.T) {
	c := mustNew(Config{Capacity: 5})

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

	// Update should not change length.
	c.Put("a", "new")
	if c.Len() != 2 {
		t.Fatalf("expected 2 after update, got %d", c.Len())
	}
}

func TestConcurrency(t *testing.T) {
	c := mustNew(Config{Capacity: 1000})

	var wg sync.WaitGroup
	for range 20 {
		wg.Go(func() {
			for range 100 {
				c.Put("k", "v")
				c.Get("k")
				c.Len()
			}
		})
	}
	wg.Wait()
}

func BenchmarkGet(b *testing.B) {
	c := mustNew(Config{Capacity: 1000})

	for range 1000 {
		c.Put("key", "value")
	}

	b.ResetTimer()
	for b.Loop() {
		c.Get("key")
	}
}

func BenchmarkPut(b *testing.B) {
	c := mustNew(Config{Capacity: 1000})

	// Pre-fill to capacity so each new-key Put triggers eviction.
	for range 1000 {
		c.Put("fill", "v")
	}

	b.ResetTimer()

	var i int
	for b.Loop() {
		c.Put(strconv.Itoa(i), "v")
		i++
	}
}