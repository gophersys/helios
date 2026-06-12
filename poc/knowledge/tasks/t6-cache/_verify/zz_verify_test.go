package cache_test

import (
	"fmt"
	"sync"
	"testing"

	cache "example.helios/cache"
)

func mustCache(t *testing.T, capacity int) *cache.Cache {
	t.Helper()
	c, err := cache.New(cache.Config{Capacity: capacity})
	if err != nil {
		t.Fatalf("New(%d): %v", capacity, err)
	}
	return c
}

func TestVerifyPutGetLen(t *testing.T) {
	c := mustCache(t, 3)
	c.Put("a", "1")
	c.Put("b", "2")
	if v, ok := c.Get("a"); !ok || v != "1" {
		t.Fatalf(`Get("a") = %q, %v; want "1", true`, v, ok)
	}
	if _, ok := c.Get("missing"); ok {
		t.Fatal(`Get("missing") = hit; want miss`)
	}
	if c.Len() != 2 {
		t.Fatalf("Len = %d; want 2", c.Len())
	}
}

func TestVerifyUpdateExistingKey(t *testing.T) {
	c := mustCache(t, 2)
	c.Put("a", "1")
	c.Put("a", "2")
	if v, _ := c.Get("a"); v != "2" {
		t.Fatalf(`Get("a") = %q; want "2" (updated)`, v)
	}
	if c.Len() != 1 {
		t.Fatalf("Len = %d; want 1 (update is not an insert)", c.Len())
	}
}

func TestVerifyEvictsLeastRecentlyUsed(t *testing.T) {
	c := mustCache(t, 2)
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3") // evicts "a"
	if _, ok := c.Get("a"); ok {
		t.Fatal(`"a" survived; want evicted (LRU)`)
	}
	if _, ok := c.Get("b"); !ok {
		t.Fatal(`"b" evicted; want present`)
	}
}

func TestVerifyGetRefreshesRecency(t *testing.T) {
	c := mustCache(t, 2)
	c.Put("a", "1")
	c.Put("b", "2")
	if _, ok := c.Get("a"); !ok { // refresh "a"
		t.Fatal(`Get("a") missed`)
	}
	c.Put("c", "3") // must evict "b", not "a"
	if _, ok := c.Get("a"); !ok {
		t.Fatal(`"a" evicted despite being recently used`)
	}
	if _, ok := c.Get("b"); ok {
		t.Fatal(`"b" survived; want evicted`)
	}
}

func TestVerifyPutRefreshesRecency(t *testing.T) {
	c := mustCache(t, 2)
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("a", "updated") // refresh "a" via Put
	c.Put("c", "3")       // must evict "b"
	if _, ok := c.Get("a"); !ok {
		t.Fatal(`"a" evicted despite Put refresh`)
	}
	if _, ok := c.Get("b"); ok {
		t.Fatal(`"b" survived; want evicted`)
	}
}

func TestVerifyValidation(t *testing.T) {
	if _, err := cache.New(cache.Config{Capacity: 0}); err == nil {
		t.Fatal("Capacity 0: want error")
	}
}

func TestVerifyConcurrentUse(t *testing.T) {
	c := mustCache(t, 128)
	var wg sync.WaitGroup
	for w := 0; w < 8; w++ {
		wg.Go(func() {
			for i := 0; i < 500; i++ {
				key := fmt.Sprintf("k%d", i%200)
				c.Put(key, "v")
				c.Get(key)
			}
		})
	}
	wg.Wait()
	if got := c.Len(); got > 128 {
		t.Fatalf("Len = %d; want <= capacity 128", got)
	}
}
