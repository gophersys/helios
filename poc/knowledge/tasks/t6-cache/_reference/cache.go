// Package cache is the reference implementation used to validate the
// held-out verify suite. It is never shown to the agent.
package cache

import (
	"container/list"
	"errors"
	"sync"
)

type Config struct {
	Capacity int
}

type entry struct {
	key   string
	value string
}

type Cache struct {
	mu       sync.Mutex
	capacity int
	order    *list.List
	items    map[string]*list.Element
}

func New(configuration Config) (*Cache, error) {
	if configuration.Capacity <= 0 {
		return nil, errors.New("cache: Capacity must be > 0")
	}
	return &Cache{
		capacity: configuration.Capacity,
		order:    list.New(),
		items:    make(map[string]*list.Element),
	}, nil
}

func (c *Cache) Get(key string) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	element, ok := c.items[key]
	if !ok {
		return "", false
	}
	c.order.MoveToFront(element)
	return element.Value.(*entry).value, true
}

func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if element, ok := c.items[key]; ok {
		element.Value.(*entry).value = value
		c.order.MoveToFront(element)
		return
	}
	if c.order.Len() >= c.capacity {
		if oldest := c.order.Back(); oldest != nil {
			c.order.Remove(oldest)
			delete(c.items, oldest.Value.(*entry).key)
		}
	}
	c.items[key] = c.order.PushFront(&entry{key: key, value: value})
}

func (c *Cache) Len() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.order.Len()
}
