package cache

import (
	"container/list"
	"errors"
	"sync"
)

// Config specifies the capacity for a Cache.
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

// New returns an initialized Cache with the given capacity, or an error if
// capacity is not positive.
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

// Get retrieves the value for key. The second return value indicates whether
// the key was found. On a hit the key is marked most recently used.
func (c *Cache) Get(key string) (string, bool) {
	c.mu.RLock()
	elem, ok := c.items[key]
	c.mu.RUnlock()
	if !ok {
		return "", false
	}

	c.mu.Lock()
	// Re-check: the element may have been evicted between the RUnlock and Lock.
	elem, ok = c.items[key]
	if !ok {
		c.mu.Unlock()
		return "", false
	}
	c.ll.MoveToFront(elem)
	v := elem.Value.(*entry).value
	c.mu.Unlock()
	return v, true
}

// Put associates value with key. If the key already exists its value is
// updated and it is marked most recently used. Inserting into a full cache
// evicts the least-recently-used entry.
func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if elem, ok := c.items[key]; ok {
		// Update existing entry.
		c.ll.MoveToFront(elem)
		elem.Value.(*entry).value = value
		return
	}

	// Evict LRU entry when at capacity.
	if c.ll.Len() >= c.capacity {
		back := c.ll.Back()
		if back != nil {
			e := back.Value.(*entry)
			delete(c.items, e.key)
			c.ll.Remove(back)
		}
	}

	e := &entry{key: key, value: value}
	elem := c.ll.PushFront(e)
	c.items[key] = elem
}

// Len returns the number of entries currently in the cache.
func (c *Cache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.ll.Len()
}
