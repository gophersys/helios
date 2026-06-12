package cache

import (
	"container/list"
	"fmt"
	"sync"
)

// Config configures the cache.
type Config struct {
	Capacity int
}

// entry is a key-value pair stored in the linked list.
type entry struct {
	key   string
	value string
}

// Cache is a fixed-capacity least-recently-used cache safe for concurrent use.
type Cache struct {
	mu       sync.RWMutex
	capacity int
	ll       *list.List
	items    map[string]*list.Element
}

// New creates a new cache with the given configuration.
// Returns an error if Capacity <= 0.
func New(configuration Config) (*Cache, error) {
	if configuration.Capacity <= 0 {
		return nil, fmt.Errorf("cache: capacity must be positive, got %d", configuration.Capacity)
	}
	return &Cache{
		capacity: configuration.Capacity,
		ll:       list.New(),
		items:    make(map[string]*list.Element),
	}, nil
}

// Get retrieves a value by key and marks it most recently used.
// Returns the value and true on hit, or ("", false) on miss.
func (c *Cache) Get(key string) (string, bool) {
	c.mu.RLock()
	elem, ok := c.items[key]
	if !ok {
		c.mu.RUnlock()
		return "", false
	}
	// Move to front — need write lock for modification.
	// We optimistically read with RLock first, then promote under write lock.
	c.mu.RUnlock()

	c.mu.Lock()
	// Re-check after acquiring write lock (element could have been evicted).
	elem, ok = c.items[key]
	if !ok {
		c.mu.Unlock()
		return "", false
	}
	c.ll.MoveToFront(elem)
	val := elem.Value.(*entry).value
	c.mu.Unlock()
	return val, true
}

// Put inserts or updates a key-value pair and marks it most recently used.
// If the cache is full, the least-recently-used entry is evicted.
func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Update existing entry.
	if elem, ok := c.items[key]; ok {
		c.ll.MoveToFront(elem)
		elem.Value.(*entry).value = value
		return
	}

	// Evict if at capacity.
	if c.ll.Len() >= c.capacity {
		back := c.ll.Back()
		if back != nil {
			e := back.Value.(*entry)
			delete(c.items, e.key)
			c.ll.Remove(back)
		}
	}

	// Insert new entry.
	elem := c.ll.PushFront(&entry{key: key, value: value})
	c.items[key] = elem
}

// Len returns the current number of entries in the cache.
func (c *Cache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.ll.Len()
}