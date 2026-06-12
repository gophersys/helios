package cache

import (
	"container/list"
	"fmt"
	"sync"
)

// Config configures the cache capacity.
type Config struct {
	Capacity int
}

// Cache is a fixed-capacity least-recently-used cache safe for concurrent use.
type Cache struct {
	mu       sync.RWMutex
	capacity int
	ll       *list.List                         // front = most recently used
	items    map[string]*list.Element
}

type entry struct {
	key   string
	value string
}

// New creates a Cache. Returns an error if capacity <= 0.
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

// Get retrieves the value for key. Marks the key most recently used on a hit.
func (c *Cache) Get(key string) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if elem, ok := c.items[key]; ok {
		c.ll.MoveToFront(elem)
		return elem.Value.(*entry).value, true
	}
	return "", false
}

// Put inserts or updates a key-value pair. Marks the key most recently used.
// Evicts the least-recently-used entry when the cache is full.
func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Update existing entry.
	if elem, ok := c.items[key]; ok {
		c.ll.MoveToFront(elem)
		elem.Value.(*entry).value = value
		return
	}

	// Evict LRU if at capacity.
	if c.ll.Len() >= c.capacity {
		back := c.ll.Back()
		if back != nil {
			c.ll.Remove(back)
			delete(c.items, back.Value.(*entry).key)
		}
	}

	// Insert new entry at the front (most recently used).
	elem := c.ll.PushFront(&entry{key: key, value: value})
	c.items[key] = elem
}

// Len returns the current number of entries.
func (c *Cache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.ll.Len()
}
