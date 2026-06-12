package cache

import (
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

	val, ok := c.Get("a")
	if !ok || val != "1" {
		t.Fatalf("Get(a) = (%q, %t), want (\"1\", true)", val, ok)
	}
	val, ok = c.Get("b")
	if !ok || val != "2" {
		t.Fatalf("Get(b) = (%q, %t), want (\"2\", true)", val, ok)
	}
}

func TestGetMiss(t *testing.T) {
	c, err := New(Config{Capacity: 3})
	if err != nil {
		t.Fatal(err)
	}

	val, ok := c.Get("nonexistent")
	if ok || val != "" {
		t.Fatalf("Get(nonexistent) = (%q, %t), want (\"\", false)", val, ok)
	}
}

func TestPutUpdateExisting(t *testing.T) {
	c, err := New(Config{Capacity: 3})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("a", "2")

	val, ok := c.Get("a")
	if !ok || val != "2" {
		t.Fatalf("Get(a) after update = (%q, %t), want (\"2\", true)", val, ok)
	}
}

func TestGetMarksMRU(t *testing.T) {
	c, err := New(Config{Capacity: 2})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("b", "2")

	// Access "a", making "b" the LRU.
	c.Get("a")

	// Insert new key; should evict "b".
	c.Put("c", "3")

	if _, ok := c.Get("a"); !ok {
		t.Error("a should still be present")
	}
	if _, ok := c.Get("b"); ok {
		t.Error("b should have been evicted")
	}
	if _, ok := c.Get("c"); !ok {
		t.Error("c should be present")
	}
}

func TestPutMarksMRU(t *testing.T) {
	c, err := New(Config{Capacity: 2})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("b", "2")

	// Put "a" again — marks MRU, so "b" is LRU.
	c.Put("a", "10")

	// Insert new key; should evict "b".
	c.Put("c", "3")

	if _, ok := c.Get("a"); !ok {
		t.Error("a should be present after second Put")
	}
	if _, ok := c.Get("b"); ok {
		t.Error("b should have been evicted")
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

	if _, ok := c.Get("a"); ok {
		t.Error("a should have been evicted")
	}
	if v, ok := c.Get("b"); !ok || v != "2" {
		t.Errorf("b = (%q, %t), want (\"2\", true)", v, ok)
	}
	if v, ok := c.Get("c"); !ok || v != "3" {
		t.Errorf("c = (%q, %t), want (\"3\", true)", v, ok)
	}
}

func TestLen(t *testing.T) {
	c, err := New(Config{Capacity: 2})
	if err != nil {
		t.Fatal(err)
	}

	if got := c.Len(); got != 0 {
		t.Fatalf("Len after New = %d, want 0", got)
	}

	c.Put("a", "1")
	if got := c.Len(); got != 1 {
		t.Fatalf("Len after one Put = %d, want 1", got)
	}

	c.Put("b", "2")
	if got := c.Len(); got != 2 {
		t.Fatalf("Len after two Puts = %d, want 2", got)
	}

	// Update does not change length.
	c.Put("a", "10")
	if got := c.Len(); got != 2 {
		t.Fatalf("Len after update = %d, want 2", got)
	}

	// Evict one.
	c.Put("c", "3")
	if got := c.Len(); got != 2 {
		t.Fatalf("Len after eviction = %d, want 2", got)
	}
}

func TestConcurrency(t *testing.T) {
	c, err := New(Config{Capacity: 100})
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	const goroutines = 20
	const opsPerGoroutine = 100

	for i := range goroutines {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			key := string(rune('a' + id%26))
			for j := range opsPerGoroutine {
				c.Put(key, string(rune('0'+j%10)))
				c.Get(key)
			}
		}(i)
	}

	wg.Wait()

	// No data races should have occurred; Len should be sane.
	if c.Len() > c.cap {
		t.Fatalf("Len %d exceeds capacity %d", c.Len(), c.cap)
	}
}

// BenchmarkGet measures Get on a hit in a warm cache.
func BenchmarkGet(b *testing.B) {
	c, err := New(Config{Capacity: 1000})
	if err != nil {
		b.Fatal(err)
	}
	for i := range 1000 {
		c.Put(string(rune(i)), "v")
	}

	b.ResetTimer()
	for b.Loop() {
		c.Get("a")
	}
}

// BenchmarkPutEviction measures Put into a full cache (every call evicts).
func BenchmarkPutEviction(b *testing.B) {
	c, err := New(Config{Capacity: 1})
	if err != nil {
		b.Fatal(err)
	}
	c.Put("k", "v") // fill the one slot

	b.ResetTimer()
	for b.Loop() {
		c.Put("k", "v")
	}
}