package cache

import (
	"fmt"
	"sync"
	"testing"
)

func mustCache(tb testing.TB, cfg Config) *Cache {
	tb.Helper()
	c, err := New(cfg)
	if err != nil {
		tb.Fatal(err)
	}
	return c
}

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

func TestPutGet(t *testing.T) {
	c := mustCache(t, Config{Capacity: 3})
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	v, ok := c.Get("a")
	if !ok || v != "1" {
		t.Fatalf("Get(a) = %q, %v; want %q, true", v, ok, "1")
	}
}

func TestGetMiss(t *testing.T) {
	c := mustCache(t, Config{Capacity: 3})
	v, ok := c.Get("missing")
	if ok {
		t.Fatalf("Get(missing) = %q, %v; want %q, false", v, ok, "")
	}
}

func TestPutUpdate(t *testing.T) {
	c := mustCache(t, Config{Capacity: 3})
	c.Put("a", "1")
	c.Put("a", "2")

	v, ok := c.Get("a")
	if !ok || v != "2" {
		t.Fatalf("Get(a) = %q, %v; want %q, true", v, ok, "2")
	}
}

func TestEviction(t *testing.T) {
	c := mustCache(t, Config{Capacity: 3})
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")
	c.Put("d", "4") // should evict "a"

	_, ok := c.Get("a")
	if ok {
		t.Fatal("expected a to be evicted")
	}

	for _, k := range []string{"b", "c", "d"} {
		_, ok := c.Get(k)
		if !ok {
			t.Fatalf("expected %s to be present", k)
		}
	}
}

func TestGetMarksMRU(t *testing.T) {
	c := mustCache(t, Config{Capacity: 3})
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	// Access "a" — moves it to front
	c.Get("a")

	// Insert "d" — should evict "b" (the LRU after "a" was promoted)
	c.Put("d", "4")

	_, ok := c.Get("b")
	if ok {
		t.Fatal("expected b to be evicted (a was MRU'd)")
	}
}

func TestLen(t *testing.T) {
	c := mustCache(t, Config{Capacity: 5})
	if got := c.Len(); got != 0 {
		t.Fatalf("Len = %d; want 0", got)
	}
	c.Put("a", "1")
	if got := c.Len(); got != 1 {
		t.Fatalf("Len = %d; want 1", got)
	}
	c.Put("b", "2")
	if got := c.Len(); got != 2 {
		t.Fatalf("Len = %d; want 2", got)
	}
}

func TestConcurrentAccess(t *testing.T) {
	c := mustCache(t, Config{Capacity: 100})
	var wg sync.WaitGroup
	for i := range 10 {
		wg.Go(func() {
			key := fmt.Sprintf("k%d", i)
			c.Put(key, "v")
			c.Get(key)
		})
	}
	wg.Wait()
}

func BenchmarkGet(b *testing.B) {
	c := mustCache(b, Config{Capacity: 100})
	c.Put("key", "value")
	for b.Loop() {
		c.Get("key")
	}
}

func BenchmarkPut(b *testing.B) {
	c := mustCache(b, Config{Capacity: 100})
	// Pre-fill to capacity so each Put causes eviction
	for i := range 100 {
		c.Put(fmt.Sprintf("k%d", i), "v")
	}
	i := 100
	for b.Loop() {
		c.Put(fmt.Sprintf("k%d", i), "v")
		i++
	}
}
