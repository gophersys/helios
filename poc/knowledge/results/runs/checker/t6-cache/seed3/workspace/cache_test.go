package cache

import (
	"fmt"
	"sync"
	"testing"
)

func TestNewInvalidCapacity(t *testing.T) {
	_, err := New(Config{Capacity: 0})
	if err == nil {
		t.Error("expected error for capacity 0")
	}
	_, err = New(Config{Capacity: -1})
	if err == nil {
		t.Error("expected error for capacity -1")
	}
}

func TestNewValid(t *testing.T) {
	c, err := New(Config{Capacity: 1})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if c.Len() != 0 {
		t.Errorf("expected 0, got %d", c.Len())
	}
}

func TestPutGet(t *testing.T) {
	c, _ := New(Config{Capacity: 3})

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	if c.Len() != 3 {
		t.Errorf("expected 3, got %d", c.Len())
	}

	val, ok := c.Get("a")
	if !ok || val != "1" {
		t.Errorf("expected ('1', true), got (%q, %v)", val, ok)
	}

	val, ok = c.Get("b")
	if !ok || val != "2" {
		t.Errorf("expected ('2', true), got (%q, %v)", val, ok)
	}

	val, ok = c.Get("c")
	if !ok || val != "3" {
		t.Errorf("expected ('3', true), got (%q, %v)", val, ok)
	}
}

func TestGetMissing(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	_, ok := c.Get("nonexistent")
	if ok {
		t.Error("expected false for missing key")
	}
}

func TestUpdateExisting(t *testing.T) {
	c, _ := New(Config{Capacity: 3})
	c.Put("a", "1")
	c.Put("a", "2")

	val, ok := c.Get("a")
	if !ok || val != "2" {
		t.Errorf("expected ('2', true), got (%q, %v)", val, ok)
	}

	if c.Len() != 1 {
		t.Errorf("expected 1, got %d", c.Len())
	}
}

func TestEviction(t *testing.T) {
	c, _ := New(Config{Capacity: 2})

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3") // should evict "a"

	_, ok := c.Get("a")
	if ok {
		t.Error("expected 'a' to be evicted")
	}

	val, ok := c.Get("b")
	if !ok || val != "2" {
		t.Errorf("expected ('2', true), got (%q, %v)", val, ok)
	}

	val, ok = c.Get("c")
	if !ok || val != "3" {
		t.Errorf("expected ('3', true), got (%q, %v)", val, ok)
	}
}

func TestLRUOrder(t *testing.T) {
	c, _ := New(Config{Capacity: 3})

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	// Access "a" to make it most recently used
	c.Get("a")

	// Insert a new key, should evict "b" (the least recently used)
	c.Put("d", "4")

	_, ok := c.Get("b")
	if ok {
		t.Error("expected 'b' to be evicted")
	}

	_, ok = c.Get("a")
	if !ok {
		t.Error("expected 'a' to still exist")
	}
}

func TestConcurrency(t *testing.T) {
	c, _ := New(Config{Capacity: 100})
	var wg sync.WaitGroup
	wg.Go(func() {
		for i := 0; i < 100; i++ {
			c.Put("key", "value")
		}
	})
	wg.Go(func() {
		for i := 0; i < 100; i++ {
			c.Get("key")
		}
	})
	wg.Go(func() {
		for i := 0; i < 100; i++ {
			c.Len()
		}
	})
	wg.Wait()
}

func BenchmarkGet(b *testing.B) {
	c, _ := New(Config{Capacity: 1000})
	for i := 0; i < 1000; i++ {
		c.Put(fmt.Sprintf("k%d", i), fmt.Sprintf("v%d", i))
	}

	b.ResetTimer()
	for b.Loop() {
		c.Get("k500")
	}
}

func BenchmarkPut(b *testing.B) {
	c, _ := New(Config{Capacity: 100})

	b.ResetTimer()
	var i int
	for b.Loop() {
		c.Put(fmt.Sprintf("k%d", i), "v")
		i++
	}
}