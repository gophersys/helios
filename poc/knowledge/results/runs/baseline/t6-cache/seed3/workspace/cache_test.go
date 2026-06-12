package cache

import (
	"sync"
	"testing"
)

func TestNew_InvalidCapacity(t *testing.T) {
	_, err := New(Config{Capacity: 0})
	if err == nil {
		t.Fatal("expected error for capacity 0")
	}
	_, err = New(Config{Capacity: -1})
	if err == nil {
		t.Fatal("expected error for capacity -1")
	}
}

func TestNew_ValidCapacity(t *testing.T) {
	c, err := New(Config{Capacity: 1})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if c.Len() != 0 {
		t.Fatalf("expected empty cache, got Len=%d", c.Len())
	}
}

func TestGet_Miss(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	_, ok := c.Get("a")
	if ok {
		t.Fatal("expected miss for empty cache")
	}
}

func TestPut_Get_Hit(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	c.Put("a", "1")
	v, ok := c.Get("a")
	if !ok {
		t.Fatal("expected hit")
	}
	if v != "1" {
		t.Fatalf("expected '1', got %q", v)
	}
}

func TestPut_Update(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	c.Put("a", "1")
	c.Put("a", "2")
	v, ok := c.Get("a")
	if !ok {
		t.Fatal("expected hit")
	}
	if v != "2" {
		t.Fatalf("expected '2', got %q", v)
	}
}

func TestEviction_OldestEvicted(t *testing.T) {
	c, _ := New(Config{Capacity: 2})
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3") // should evict "a"

	_, ok := c.Get("a")
	if ok {
		t.Fatal("expected 'a' to be evicted")
	}
	v, ok := c.Get("b")
	if !ok {
		t.Fatal("expected 'b' to be present")
	}
	if v != "2" {
		t.Fatalf("expected '2', got %q", v)
	}
	v, ok = c.Get("c")
	if !ok {
		t.Fatal("expected 'c' to be present")
	}
	if v != "3" {
		t.Fatalf("expected '3', got %q", v)
	}
}

func TestEviction_GetRefreshesLRU(t *testing.T) {
	c, _ := New(Config{Capacity: 2})
	c.Put("a", "1")
	c.Put("b", "2")
	// Access "a" making it most recent.
	c.Get("a")
	// Now inserting "c" should evict "b" (the LRU).
	c.Put("c", "3")

	_, ok := c.Get("b")
	if ok {
		t.Fatal("expected 'b' to be evicted")
	}
	v, ok := c.Get("a")
	if !ok {
		t.Fatal("expected 'a' to be present")
	}
	if v != "1" {
		t.Fatalf("expected '1', got %q", v)
	}
	v, ok = c.Get("c")
	if !ok {
		t.Fatal("expected 'c' to be present")
	}
	if v != "3" {
		t.Fatalf("expected '3', got %q", v)
	}
}

func TestEviction_PutRefreshesLRU(t *testing.T) {
	c, _ := New(Config{Capacity: 2})
	c.Put("a", "1")
	c.Put("b", "2")
	// Update "a" making it most recent.
	c.Put("a", "10")
	// Now inserting "c" should evict "b".
	c.Put("c", "3")

	_, ok := c.Get("b")
	if ok {
		t.Fatal("expected 'b' to be evicted")
	}
	v, ok := c.Get("a")
	if !ok {
		t.Fatal("expected 'a' to be present")
	}
	if v != "10" {
		t.Fatalf("expected '10', got %q", v)
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
	// Update should not change length.
	c.Put("a", "10")
	if c.Len() != 2 {
		t.Fatalf("expected 2, got %d", c.Len())
	}
}

func TestConcurrency(t *testing.T) {
	c, _ := New(Config{Capacity: 100})
	var wg sync.WaitGroup

	// Concurrent puts.
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			key := string(rune('a' + n))
			c.Put(key, key)
		}(i)
	}
	wg.Wait()

	if c.Len() != 50 {
		t.Fatalf("expected 50 entries, got %d", c.Len())
	}

	// Concurrent gets.
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			key := string(rune('a' + n))
			c.Get(key)
		}(i)
	}
	wg.Wait()

	// Concurrent gets and puts interleaved.
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			key := string(rune('z' - n))
			c.Get(key)
			c.Put("extra", "x")
			c.Get("extra")
		}(i)
	}
	wg.Wait()
}

func BenchmarkGet(b *testing.B) {
	c, _ := New(Config{Capacity: b.N})
	for i := 0; i < b.N; i++ {
		key := string(rune('a' + i%26))
		c.Put(key, key)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		key := string(rune('a' + i%26))
		c.Get(key)
	}
}

func BenchmarkPut(b *testing.B) {
	c, _ := New(Config{Capacity: 100})

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		key := string(rune('a' + i%26))
		c.Put(key, key)
	}
}
