package cache

import (
	"sync"
	"testing"
)

// --- unit tests ---

func TestNewInvalidCapacity(t *testing.T) {
	tests := []struct {
		cap int
	}{
		{0},
		{-1},
		{-100},
	}
	for _, tc := range tests {
		_, err := New(Config{Capacity: tc.cap})
		if err == nil {
			t.Errorf("New with capacity %d: expected error, got nil", tc.cap)
		}
	}
}

func TestNewValidCapacity(t *testing.T) {
	c, err := New(Config{Capacity: 1})
	if err != nil {
		t.Fatalf("New: unexpected error: %v", err)
	}
	if c.Len() != 0 {
		t.Errorf("Len: expected 0, got %d", c.Len())
	}
}

func TestGetEmpty(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	_, ok := c.Get("missing")
	if ok {
		t.Error("Get on empty cache: expected false")
	}
}

func TestPutGet(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	c.Put("a", "1")
	c.Put("b", "2")

	val, ok := c.Get("a")
	if !ok {
		t.Fatal("Get a: expected hit")
	}
	if val != "1" {
		t.Errorf("Get a: expected '1', got %q", val)
	}

	val, ok = c.Get("b")
	if !ok {
		t.Fatal("Get b: expected hit")
	}
	if val != "2" {
		t.Errorf("Get b: expected '2', got %q", val)
	}
}

func TestPutUpdate(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	c.Put("a", "1")
	c.Put("a", "2")

	val, ok := c.Get("a")
	if !ok {
		t.Fatal("Get a: expected hit")
	}
	if val != "2" {
		t.Errorf("Get a: expected '2', got %q", val)
	}

	if c.Len() != 1 {
		t.Errorf("Len: expected 1 after update, got %d", c.Len())
	}
}

func TestEviction(t *testing.T) {
	c, _ := New(Config{Capacity: 2})
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3") // should evict "a"

	if c.Len() != 2 {
		t.Errorf("Len: expected 2 after eviction, got %d", c.Len())
	}

	_, ok := c.Get("a")
	if ok {
		t.Error("Get a: expected miss after eviction")
	}

	val, ok := c.Get("b")
	if !ok || val != "2" {
		t.Errorf("Get b: expected ('2', true), got (%q, %v)", val, ok)
	}

	val, ok = c.Get("c")
	if !ok || val != "3" {
		t.Errorf("Get c: expected ('3', true), got (%q, %v)", val, ok)
	}
}

func TestGetMarksMRU(t *testing.T) {
	c, _ := New(Config{Capacity: 2})
	c.Put("a", "1")
	c.Put("b", "2")
	c.Get("a")           // mark a most recently used
	c.Put("c", "3")      // should evict "b" (LRU)

	_, ok := c.Get("b")
	if ok {
		t.Error("Get b: expected miss after Get caused reorder")
	}

	val, ok := c.Get("a")
	if !ok || val != "1" {
		t.Errorf("Get a: expected ('1', true), got (%q, %v)", val, ok)
	}
	val, ok = c.Get("c")
	if !ok || val != "3" {
		t.Errorf("Get c: expected ('3', true), got (%q, %v)", val, ok)
	}
}

func TestPutMarksMRU(t *testing.T) {
	c, _ := New(Config{Capacity: 2})
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("a", "42")     // update a, marking it MRU
	c.Put("c", "3")      // should evict "b"

	_, ok := c.Get("b")
	if ok {
		t.Error("Get b: expected miss after Put reorder")
	}

	val, ok := c.Get("a")
	if !ok || val != "42" {
		t.Errorf("Get a: expected ('42', true), got (%q, %v)", val, ok)
	}
}

func TestConcurrency(t *testing.T) {
	c, _ := New(Config{Capacity: 100})
	var wg sync.WaitGroup

	// Concurrent puts.
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			key := string(rune('a' + i%26))
			c.Put(key, "v")
		}(i)
	}

	// Concurrent gets.
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			key := string(rune('a' + i%26))
			c.Get(key)
		}(i)
	}

	wg.Wait()
	// No deadlock and Len is consistent.
	if c.Len() > 26 {
		t.Errorf("Len: expected ≤ 26, got %d", c.Len())
	}
}

// --- benchmarks ---

func BenchmarkGet(b *testing.B) {
	c, _ := New(Config{Capacity: 1000})
	for i := 0; i < 1000; i++ {
		c.Put(string(rune(i)), "value")
	}
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		c.Get(string(rune(i % 1000)))
	}
}

func BenchmarkPut(b *testing.B) {
	c, _ := New(Config{Capacity: 100})
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		c.Put(string(rune(i%200)), "value")
	}
}