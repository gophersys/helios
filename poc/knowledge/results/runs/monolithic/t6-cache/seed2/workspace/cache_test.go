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

func TestPutAndGet(t *testing.T) {
	c, err := New(Config{Capacity: 2})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("b", "2")

	v, ok := c.Get("a")
	if !ok || v != "1" {
		t.Fatalf("expected '1', got %q, %v", v, ok)
	}

	v, ok = c.Get("b")
	if !ok || v != "2" {
		t.Fatalf("expected '2', got %q, %v", v, ok)
	}
}

func TestGetMiss(t *testing.T) {
	c, err := New(Config{Capacity: 2})
	if err != nil {
		t.Fatal(err)
	}

	v, ok := c.Get("nonexistent")
	if ok {
		t.Fatalf("expected miss, got %q", v)
	}
}

func TestGetEmptyCache(t *testing.T) {
	c, err := New(Config{Capacity: 1})
	if err != nil {
		t.Fatal(err)
	}

	_, ok := c.Get("x")
	if ok {
		t.Fatal("expected miss on empty cache")
	}
}

func TestUpdateValue(t *testing.T) {
	c, err := New(Config{Capacity: 2})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("a", "2")

	v, ok := c.Get("a")
	if !ok || v != "2" {
		t.Fatalf("expected '2', got %q, %v", v, ok)
	}

	if c.Len() != 1 {
		t.Fatalf("expected len 1 after update, got %d", c.Len())
	}
}

func TestEviction(t *testing.T) {
	c, err := New(Config{Capacity: 2})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3") // evicts "a"

	_, ok := c.Get("a")
	if ok {
		t.Fatal("expected 'a' to be evicted")
	}

	v, ok := c.Get("b")
	if !ok || v != "2" {
		t.Fatalf("expected '2', got %q, %v", v, ok)
	}

	v, ok = c.Get("c")
	if !ok || v != "3" {
		t.Fatalf("expected '3', got %q, %v", v, ok)
	}

	if c.Len() != 2 {
		t.Fatalf("expected len 2 after eviction, got %d", c.Len())
	}
}

func TestGetMakesMostRecent(t *testing.T) {
	c, err := New(Config{Capacity: 2})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("b", "2")
	c.Get("a")          // "a" becomes most recently used
	c.Put("c", "3")     // evicts "b" (LRU)

	_, ok := c.Get("b")
	if ok {
		t.Fatal("expected 'b' to be evicted")
	}

	v, ok := c.Get("a")
	if !ok || v != "1" {
		t.Fatalf("expected '1', got %q, %v", v, ok)
	}

	v, ok = c.Get("c")
	if !ok || v != "3" {
		t.Fatalf("expected '3', got %q, %v", v, ok)
	}
}

func TestPutMakesMostRecent(t *testing.T) {
	c, err := New(Config{Capacity: 2})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("a", "3")     // update, making "a" most recent
	c.Put("c", "4")     // evicts "b" (LRU)

	_, ok := c.Get("b")
	if ok {
		t.Fatal("expected 'b' to be evicted")
	}

	v, ok := c.Get("a")
	if !ok || v != "3" {
		t.Fatalf("expected '3', got %q, %v", v, ok)
	}

	v, ok = c.Get("c")
	if !ok || v != "4" {
		t.Fatalf("expected '4', got %q, %v", v, ok)
	}
}

func TestCapacityOne(t *testing.T) {
	c, err := New(Config{Capacity: 1})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	v, ok := c.Get("a")
	if !ok || v != "1" {
		t.Fatalf("expected '1', got %q, %v", v, ok)
	}

	c.Put("b", "2") // evicts "a"

	_, ok = c.Get("a")
	if ok {
		t.Fatal("expected 'a' to be evicted")
	}

	v, ok = c.Get("b")
	if !ok || v != "2" {
		t.Fatalf("expected '2', got %q, %v", v, ok)
	}
}

func TestLen(t *testing.T) {
	c, err := New(Config{Capacity: 5})
	if err != nil {
		t.Fatal(err)
	}

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

	// Update should not increase length.
	c.Put("a", "10")
	if c.Len() != 2 {
		t.Fatalf("expected 2 after update, got %d", c.Len())
	}

	// Fill to capacity.
	c.Put("c", "3")
	c.Put("d", "4")
	c.Put("e", "5")
	if c.Len() != 5 {
		t.Fatalf("expected 5 at capacity, got %d", c.Len())
	}

	// Evictions keep length at capacity.
	c.Put("f", "6")
	if c.Len() != 5 {
		t.Fatalf("expected 5 after eviction, got %d", c.Len())
	}
}

func TestConcurrency(t *testing.T) {
	c, err := New(Config{Capacity: 100})
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	const n = 50

	for i := range n {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			key := strconv.Itoa(i)
			c.Put(key, key)
			c.Get(key)
		}(i)
	}
	wg.Wait()

	if c.Len() != n {
		t.Fatalf("expected %d entries, got %d", n, c.Len())
	}
}

func BenchmarkGet(b *testing.B) {
	c, err := New(Config{Capacity: 1000})
	if err != nil {
		b.Fatal(err)
	}
	for i := range 1000 {
		c.Put(strconv.Itoa(i), strconv.Itoa(i))
	}

	b.ResetTimer()
	for b.Loop() {
		c.Get("42")
	}
}

func BenchmarkPut(b *testing.B) {
	c, err := New(Config{Capacity: 100})
	if err != nil {
		b.Fatal(err)
	}
	// Pre-fill to capacity.
	for i := range 100 {
		c.Put(strconv.Itoa(i), strconv.Itoa(i))
	}

	// Evict on each iteration by using a unique key.
	b.ResetTimer()
	i := 100
	for b.Loop() {
		c.Put(strconv.Itoa(i), "v")
		i++
	}
}