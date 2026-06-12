package cache

import (
	"container/list"
	"fmt"
	"sync"
)

type Config struct {
	Capacity int
}

type Cache struct {
	mu       sync.Mutex
	capacity int
	items    map[string]*list.Element
	list     *list.List
}

type entry struct {
	key   string
	value string
}

func New(config Config) (*Cache, error) {
	if config.Capacity <= 0 {
		return nil, fmt.Errorf("cache: capacity must be positive, got %d", config.Capacity)
	}
	return &Cache{
		capacity: config.Capacity,
		items:    make(map[string]*list.Element),
		list:     list.New(),
	}, nil
}

func (c *Cache) Get(key string) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()

	el, ok := c.items[key]
	if !ok {
		return "", false
	}
	c.list.MoveToFront(el)
	return el.Value.(*entry).value, true
}

func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if el, ok := c.items[key]; ok {
		el.Value.(*entry).value = value
		c.list.MoveToFront(el)
		return
	}

	if c.list.Len() >= c.capacity {
		tail := c.list.Back()
		if tail != nil {
			c.list.Remove(tail)
			delete(c.items, tail.Value.(*entry).key)
		}
	}

	e := &entry{key: key, value: value}
	c.items[key] = c.list.PushFront(e)
}

func (c *Cache) Len() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.items)
}