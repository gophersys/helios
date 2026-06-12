package cache

import (
	"strconv"
	"sync"
	"testing"
)

func TestNewInvalidCapacity(t *testing.T) {
	_, err := New(Config{Capacity: 0})
	if err == nil {
		t.Fatal("expected error for zero capacity")
	}

	_, err = New(Config{Capacity: -1})
	if err == nil {
		t.Fatal("expected error for negative capacity")
	}
}

func TestPutGet(t *testing.T) {
	c, err := New(Config{Capacity: 3})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	v, ok := c.Get("a")
	if !ok || v != "1" {
		t.Fatalf("expected \"1\", got %q (ok=%v)", v, ok)
	}

	v, ok = c.Get("b")
	if !ok || v != "2" {
		t.Fatalf("expected \"2\", got %q (ok=%v)", v, ok)
	}

	v, ok = c.Get("c")
	if !ok || v != "3" {
		t.Fatalf("expected \"3\", got %q (ok=%v)", v, ok)
	}
}

func TestGetMiss(t *testing.T) {
	c, _ := New(Config{Capacity: 2})
	v, ok := c.Get("missing")
	if ok {
		t.Fatalf("expected miss, got %q", v)
	}
	if v != "" {
		t.Fatalf("expected empty string on miss, got %q", v)
	}
}

func TestUpdateExistingKey(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	c.Put("x", "old")
	c.Put("x", "new")

	v, ok := c.Get("x")
	if !ok || v != "new" {
		t.Fatalf("expected \"new\", got %q (ok=%v)", v, ok)
	}
	if c.Len() != 1 {
		t.Fatalf("expected len 1 after update, got %d", c.Len())
	}
}

func TestEviction(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")
	// Cache: a, b, c (a is LRU)

	// Access b and a to change order
	c.Get("b") // order: b, a, c
	c.Get("a") // order: a, b, c

	// Insert d — should evict c (LRU)
	c.Put("d", "4")

	if _, ok := c.Get("c"); ok {
		t.Fatal("expected c to be evicted")
	}

	if v, ok := c.Get("d"); !ok || v != "4" {
		t.Fatalf("expected d=4, got %q (ok=%v)", v, ok)
	}
}

func TestEvictionWithPutOnExistingKey(t *testing.T) {
	c, _ := New(Config{Capacity: 2})
	c.Put("a", "1")
	c.Put("b", "2")
	// a is LRU

	// Update a — should NOT cause eviction, and a becomes MRU
	c.Put("a", "updated")

	if c.Len() != 2 {
		t.Fatalf("expected len 2 after update, got %d", c.Len())
	}

	// Now b is LRU; insert c should evict b
	c.Put("c", "3")

	if _, ok := c.Get("b"); ok {
		t.Fatal("expected b to be evicted")
	}
	if v, ok := c.Get("a"); !ok || v != "updated" {
		t.Fatalf("expected a=updated, got %q (ok=%v)", v, ok)
	}
	if v, ok := c.Get("c"); !ok || v != "3" {
		t.Fatalf("expected c=3, got %q (ok=%v)", v, ok)
	}
}

func TestLen(t *testing.T) {
	c, _ := New(Config{Capacity: 5})
	if c.Len() != 0 {
		t.Fatalf("expected len 0 for empty cache, got %d", c.Len())
	}

	c.Put("a", "1")
	if c.Len() != 1 {
		t.Fatalf("expected len 1, got %d", c.Len())
	}

	c.Put("b", "2")
	if c.Len() != 2 {
		t.Fatalf("expected len 2, got %d", c.Len())
	}

	// Update should not change length
	c.Put("a", "new")
	if c.Len() != 2 {
		t.Fatalf("expected len 2 after update, got %d", c.Len())
	}
}

func TestConcurrentAccess(t *testing.T) {
	c, _ := New(Config{Capacity: 100})
	var wg sync.WaitGroup

	// Concurrent writers
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			key := strconv.Itoa(n)
			c.Put(key, key)
		}(i)
	}

	// Concurrent readers
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			key := strconv.Itoa(n)
			c.Get(key)
		}(i)
	}

	wg.Wait()
}

func BenchmarkGetHit(b *testing.B) {
	c, _ := New(Config{Capacity: 1000})
	for i := 0; i < 1000; i++ {
		c.Put(strconv.Itoa(i), "value")
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		c.Get("42")
	}
}

func BenchmarkPutWithEviction(b *testing.B) {
	c, _ := New(Config{Capacity: 100})

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		c.Put(strconv.Itoa(i), "value")
	}
}