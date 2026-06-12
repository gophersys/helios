package cache
import (
	"sync"
	"testing"
)

func TestNew(t *testing.T) {
	t.Run("zero capacity", func(t *testing.T) {
		c, err := New(Config{Capacity: 0})
		if err == nil {
			t.Fatal("expected error for zero capacity")
		}
		if c != nil {
			t.Fatal("expected nil cache on error")
		}
	})

	t.Run("negative capacity", func(t *testing.T) {
		c, err := New(Config{Capacity: -1})
		if err == nil {
			t.Fatal("expected error for negative capacity")
		}
		if c != nil {
			t.Fatal("expected nil cache on error")
		}
	})

	t.Run("valid capacity", func(t *testing.T) {
		c, err := New(Config{Capacity: 5})
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if c == nil {
			t.Fatal("expected non-nil cache")
		}
		if c.Len() != 0 {
			t.Fatalf("expected Len 0, got %d", c.Len())
		}
	})
}

func TestPutAndGet(t *testing.T) {
	c, err := New(Config{Capacity: 3})
	if err != nil {
		t.Fatal(err)
	}

	// Insert and retrieve
	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	val, ok := c.Get("a")
	if !ok || val != "1" {
		t.Fatalf("Get(a) = (%q, %t), want (\"1\", true)", val, ok)
	}

	val, ok = c.Get("b")
	if !ok || val != "2" {
		t.Fatalf("Get(b) = (%q, %t), want (\"2\", true)", val, ok)
	}

	val, ok = c.Get("c")
	if !ok || val != "3" {
		t.Fatalf("Get(c) = (%q, %t), want (\"3\", true)", val, ok)
	}
}

func TestGetMiss(t *testing.T) {
	c, err := New(Config{Capacity: 3})
	if err != nil {
		t.Fatal(err)
	}

	val, ok := c.Get("nonexistent")
	if ok {
		t.Fatalf("expected miss, got (%q, true)", val)
	}
	if val != "" {
		t.Fatalf("expected empty string on miss, got %q", val)
	}
}

func TestPutUpdatesExisting(t *testing.T) {
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

	if c.Len() != 1 {
		t.Fatalf("Len after update = %d, want 1", c.Len())
	}
}

func TestPutUpdatesExistingMarksMRU(t *testing.T) {
	c, err := New(Config{Capacity: 3})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	// "a" is LRU — updating "a" makes it MRU
	c.Put("a", "10")

	// Now inserting "d" should evict "b" (the new LRU)
	c.Put("d", "4")

	val, ok := c.Get("a")
	if !ok || val != "10" {
		t.Fatalf("Get(a) = (%q, %t), want (\"10\", true)", val, ok)
	}

	val, ok = c.Get("b")
	if ok {
		t.Fatalf("b should have been evicted, got (%q, true)", val)
	}

	val, ok = c.Get("c")
	if !ok || val != "3" {
		t.Fatalf("Get(c) = (%q, %t), want (\"3\", true)", val, ok)
	}
}

func TestGetMarksMRU(t *testing.T) {
	c, err := New(Config{Capacity: 3})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")

	// Access "a" — makes it MRU
	c.Get("a")

	// Insert "d" — should evict "b" (now LRU)
	c.Put("d", "4")

	val, ok := c.Get("a")
	if !ok || val != "1" {
		t.Fatalf("Get(a) = (%q, %t), want (\"1\", true)", val, ok)
	}

	val, ok = c.Get("b")
	if ok {
		t.Fatalf("b should have been evicted, got (%q, true)", val)
	}

	val, ok = c.Get("d")
	if !ok || val != "4" {
		t.Fatalf("Get(d) = (%q, %t), want (\"4\", true)", val, ok)
	}
}

func TestEviction(t *testing.T) {
	c, err := New(Config{Capacity: 3})
	if err != nil {
		t.Fatal(err)
	}

	c.Put("a", "1")
	c.Put("b", "2")
	c.Put("c", "3")
	c.Put("d", "4") // evicts "a"

	if c.Len() != 3 {
		t.Fatalf("Len after eviction = %d, want 3", c.Len())
	}

	val, ok := c.Get("a")
	if ok {
		t.Fatalf("a should have been evicted, got (%q, true)", val)
	}

	for _, k := range []string{"b", "c", "d"} {
		if _, ok := c.Get(k); !ok {
			t.Fatalf("%s should still be present", k)
		}
	}
}

func TestLen(t *testing.T) {
	c, err := New(Config{Capacity: 5})
	if err != nil {
		t.Fatal(err)
	}

	if c.Len() != 0 {
		t.Fatalf("Len on empty = %d, want 0", c.Len())
	}

	c.Put("a", "1")
	if c.Len() != 1 {
		t.Fatalf("Len after 1 put = %d, want 1", c.Len())
	}

	c.Put("b", "2")
	if c.Len() != 2 {
		t.Fatalf("Len after 2 puts = %d, want 2", c.Len())
	}

	c.Put("b", "22") // update, no change
	if c.Len() != 2 {
		t.Fatalf("Len after update = %d, want 2", c.Len())
	}
}

func TestConcurrency(t *testing.T) {
	c, err := New(Config{Capacity: 100})
	if err != nil {
		t.Fatal(err)
	}

	var wg sync.WaitGroup
	const goroutines = 10
	const ops = 100
	for i := range goroutines {
		wg.Go(func() {
			for j := 0; j < ops; j++ {
				key := string(rune('a' + (i*ops+j)%26))
				c.Put(key, "v")
				c.Get(key)
				c.Len()
			}
		})
	}
	wg.Wait()

	// No panics and Len is reasonable
	_ = c.Len()
}

func BenchmarkGet(b *testing.B) {
	c, err := New(Config{Capacity: 1024})
	if err != nil {
		b.Fatal(err)
	}

	// Fill the cache
	for i := 0; i < 1024; i++ {
		c.Put(string(rune(i)), "value")
	}

	b.ResetTimer()
	for b.Loop() {
		c.Get(string(rune(42)))
	}
}

func BenchmarkPut(b *testing.B) {
	c, err := New(Config{Capacity: 128})
	if err != nil {
		b.Fatal(err)
	}

	// Pre-fill to capacity
	for i := 0; i < 128; i++ {
		c.Put(string(rune(i)), "value")
	}

	b.ResetTimer()
	for b.Loop() {
		c.Put("key", "value")
	}
}