package cache

import (
	"container/list"
	"errors"
	"sync"
)

// Config holds the cache configuration.
type Config struct {
	Capacity int
}

type entry struct {
	key   string
	value string
}

// Cache is a fixed-capacity, least-recently-used cache safe for concurrent use.
type Cache struct {
	mu       sync.Mutex
	capacity int
	ll       *list.List
	items    map[string]*list.Element
}

// New creates a new Cache with the given configuration.
// Returns an error if Capacity <= 0.
func New(config Config) (*Cache, error) {
	if config.Capacity <= 0 {
		return nil, errors.New("cache: capacity must be positive")
	}
	return &Cache{
		capacity: config.Capacity,
		ll:       list.New(),
		items:    make(map[string]*list.Element, config.Capacity),
	}, nil
}

// Get retrieves the value for the given key.
// Returns the value and true on a hit (marking the key most recently used),
// or ("", false) on a miss.
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

// Put inserts or updates the value for the given key.
// The key is marked most recently used. If the cache is full, the
// least-recently-used entry is evicted.
func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if elem, ok := c.items[key]; ok {
		elem.Value.(*entry).value = value
		c.ll.MoveToFront(elem)
		return
	}

	if c.ll.Len() >= c.capacity {
		back := c.ll.Back()
		if back != nil {
			e := back.Value.(*entry)
			delete(c.items, e.key)
			c.ll.Remove(back)
		}
	}

	e := &entry{key: key, value: value}
	c.items[key] = c.ll.PushFront(e)
}

// Len returns the current number of entries in the cache.
func (c *Cache) Len() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.ll.Len()
}