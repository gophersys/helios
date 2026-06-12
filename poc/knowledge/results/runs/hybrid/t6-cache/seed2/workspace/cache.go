package cache

import (
	"container/list"
	"fmt"
	"sync"
)

// Config configures a Cache instance.
type Config struct {
	// Capacity is the maximum number of entries the cache may hold.
	Capacity int
}

type entry struct {
	key   string
	value string
}

// Cache is a fixed-capacity least-recently-used cache safe for concurrent use.
type Cache struct {
	mu       sync.Mutex
	capacity int
	items    map[string]*list.Element
	order    *list.List
}

// New creates a Cache. It returns an error if cfg.Capacity <= 0.
func New(cfg Config) (*Cache, error) {
	if cfg.Capacity <= 0 {
		return nil, fmt.Errorf("cache: capacity must be positive, got %d", cfg.Capacity)
	}
	c := &Cache{
		capacity: cfg.Capacity,
		items:    make(map[string]*list.Element),
		order:    list.New(),
	}
	return c, nil
}

// mustNew creates a Cache and panics on error. Intended for tests and benchmarks.
func mustNew(cfg Config) *Cache {
	c, err := New(cfg)
	if err != nil {
		panic(fmt.Sprintf("cache.New: %v", err))
	}
	return c
}

// Get retrieves the value for key. The second return value reports whether
// the key was found. On a hit the key is marked most recently used.
func (c *Cache) Get(key string) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()

	elem, ok := c.items[key]
	if !ok {
		return "", false
	}
	c.order.MoveToFront(elem)
	return elem.Value.(*entry).value, true
}

// Put inserts or updates key with value. If the cache is full the
// least-recently-used entry is evicted. On an update the key is marked
// most recently used.
func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Update existing entry.
	if elem, ok := c.items[key]; ok {
		elem.Value.(*entry).value = value
		c.order.MoveToFront(elem)
		return
	}

	// Evict the LRU entry when full.
	if c.order.Len() >= c.capacity {
		back := c.order.Back()
		if back != nil {
			e := back.Value.(*entry)
			delete(c.items, e.key)
			c.order.Remove(back)
		}
	}

	// Insert new entry at front.
	e := &entry{key: key, value: value}
	c.items[key] = c.order.PushFront(e)
}

// Len returns the number of entries currently in the cache.
func (c *Cache) Len() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.order.Len()
}