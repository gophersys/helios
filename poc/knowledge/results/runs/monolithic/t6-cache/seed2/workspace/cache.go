package cache

import (
	"container/list"
	"errors"
	"sync"
)

// Config holds cache configuration.
type Config struct {
	Capacity int
}

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

// New creates a Cache with the given capacity. Returns an error if capacity <= 0.
func New(cfg Config) (*Cache, error) {
	if cfg.Capacity <= 0 {
		return nil, errors.New("cache: capacity must be positive")
	}
	return &Cache{
		capacity: cfg.Capacity,
		ll:       list.New(),
		items:    make(map[string]*list.Element, cfg.Capacity),
	}, nil
}

// Get retrieves the value for key. The second result reports whether the key
// was found. A hit marks the key as most recently used.
func (c *Cache) Get(key string) (string, bool) {
	c.mu.RLock()
	elem, ok := c.items[key]
	c.mu.RUnlock()
	if !ok {
		return "", false
	}

	c.mu.Lock()
	c.ll.MoveToFront(elem)
	c.mu.Unlock()

	return elem.Value.(*entry).value, true
}

// Put inserts or updates key with value. If the cache is full the
// least-recently-used entry is evicted. An update marks the key as most
// recently used.
func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Update existing entry.
	if elem, ok := c.items[key]; ok {
		elem.Value.(*entry).value = value
		c.ll.MoveToFront(elem)
		return
	}

	// Evict LRU entry if at capacity.
	if c.ll.Len() >= c.capacity {
		back := c.ll.Back()
		if back != nil {
			e := back.Value.(*entry)
			delete(c.items, e.key)
			c.ll.Remove(back)
		}
	}

	// Insert new entry at front (most recently used).
	elem := c.ll.PushFront(&entry{key: key, value: value})
	c.items[key] = elem
}

// Len returns the number of entries in the cache.
func (c *Cache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.ll.Len()
}