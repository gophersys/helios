package cache

import (
	"container/list"
	"fmt"
	"sync"
)

// Config configures the cache. Capacity must be positive.
type Config struct {
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
	ll       *list.List
	items    map[string]*list.Element
}

// New creates a new Cache. Returns an error if Capacity <= 0.
func New(config Config) (*Cache, error) {
	if config.Capacity <= 0 {
		return nil, fmt.Errorf("capacity must be positive, got %d", config.Capacity)
	}
	return &Cache{
		capacity: config.Capacity,
		ll:       list.New(),
		items:    make(map[string]*list.Element),
	}, nil
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
	c.ll.MoveToFront(elem)
	return elem.Value.(*entry).value, true
}

// Put inserts or updates key with value. If the key already exists its value
// is updated and it is marked most recently used. Inserting into a full
// cache evicts the least-recently-used entry.
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

	// Insert new entry.
	elem := c.ll.PushFront(&entry{key: key, value: value})
	c.items[key] = elem
}

// Len returns the current number of entries in the cache.
func (c *Cache) Len() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.ll.Len()
}