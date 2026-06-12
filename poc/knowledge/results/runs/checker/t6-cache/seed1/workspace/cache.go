package cache

import (
	"container/list"
	"errors"
	"sync"
)

// Config holds configuration for the cache.
type Config struct {
	Capacity int
}

type entry struct {
	key   string
	value string
}

// Cache is a fixed-capacity least-recently-used cache safe for concurrent use.
type Cache struct {
	mu    sync.RWMutex
	cap   int
	ll    *list.List
	items map[string]*list.Element
}

// New creates a new Cache with the given configuration.
// Returns an error if Capacity <= 0.
func New(config Config) (*Cache, error) {
	if config.Capacity <= 0 {
		return nil, errors.New("capacity must be positive")
	}
	return &Cache{
		cap:   config.Capacity,
		ll:    list.New(),
		items: make(map[string]*list.Element),
	}, nil
}

// Get retrieves the value for the given key, reporting whether it was found.
// On a hit the key is marked most recently used.
func (c *Cache) Get(key string) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()

	elem, ok := c.items[key]
	if !ok {
		return "", false
	}
	c.ll.MoveToFront(elem)
	return elem.Value.(*entry).value, true
}

// Put inserts or updates the value for the given key and marks it most
// recently used. If the cache is full, the least-recently-used entry is
// evicted first.
func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if elem, ok := c.items[key]; ok {
		// Update existing entry.
		elem.Value.(*entry).value = value
		c.ll.MoveToFront(elem)
		return
	}

	// Evict LRU entry if at capacity.
	if c.ll.Len() >= c.cap {
		back := c.ll.Back()
		if back != nil {
			e := back.Value.(*entry)
			delete(c.items, e.key)
			c.ll.Remove(back)
		}
	}

	elem := c.ll.PushFront(&entry{key: key, value: value})
	c.items[key] = elem
}

// Len returns the current number of entries in the cache.
func (c *Cache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.ll.Len()
}
