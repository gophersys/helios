package cache

import (
	"container/list"
	"fmt"
	"sync"
)

// Config holds the cache configuration.
type Config struct {
	// Capacity is the maximum number of entries the cache may hold.
	// Must be positive.
	Capacity int
}

// Cache is a fixed-capacity, concurrent-safe LRU cache mapping string keys
// to string values.
type Cache struct {
	mu    sync.RWMutex
	cap   int
	items map[string]*list.Element
	lru   *list.List
}

type entry struct {
	key   string
	value string
}

// New creates a Cache with the given configuration.
// Returns an error if Capacity <= 0.
func New(cfg Config) (*Cache, error) {
	if cfg.Capacity <= 0 {
		return nil, fmt.Errorf("cache: capacity must be positive, got %d", cfg.Capacity)
	}
	return &Cache{
		cap:   cfg.Capacity,
		items: make(map[string]*list.Element),
		lru:   list.New(),
	}, nil
}

// Get retrieves the value for key. The second return value is true on a hit.
// On a hit the key is marked most recently used.
func (c *Cache) Get(key string) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()

	elem, ok := c.items[key]
	if !ok {
		return "", false
	}
	c.lru.MoveToFront(elem)
	return elem.Value.(*entry).value, true
}

// Put inserts or updates key with value. The key is marked most recently
// used. If the cache is full, the least-recently-used entry is evicted.
func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if elem, ok := c.items[key]; ok {
		// Update existing.
		elem.Value.(*entry).value = value
		c.lru.MoveToFront(elem)
		return
	}

	if c.lru.Len() >= c.cap {
		// Evict the LRU entry (back of list).
		back := c.lru.Back()
		if back != nil {
			e := back.Value.(*entry)
			delete(c.items, e.key)
			c.lru.Remove(back)
		}
	}

	elem := c.lru.PushFront(&entry{key: key, value: value})
	c.items[key] = elem
}

// Len returns the current number of entries in the cache.
func (c *Cache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.lru.Len()
}