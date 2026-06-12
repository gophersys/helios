package cache

import (
	"container/list"
	"fmt"
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
	mu    sync.Mutex
	cap   int
	ll    *list.List
	items map[string]*list.Element
}

func New(configuration Config) (*Cache, error) {
	if configuration.Capacity <= 0 {
		return nil, fmt.Errorf("cache: capacity must be positive, got %d", configuration.Capacity)
	}
	return &Cache{
		cap:   configuration.Capacity,
		ll:    list.New(),
		items: make(map[string]*list.Element, configuration.Capacity),
	}, nil
}

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

func (c *Cache) Put(key string, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if elem, ok := c.items[key]; ok {
		c.ll.MoveToFront(elem)
		elem.Value.(*entry).value = value
		return
	}

	if c.ll.Len() >= c.cap {
		back := c.ll.Back()
		if back != nil {
			ent := back.Value.(*entry)
			delete(c.items, ent.key)
			c.ll.Remove(back)
		}
	}

	ent := &entry{key: key, value: value}
	elem := c.ll.PushFront(ent)
	c.items[key] = elem
}

func (c *Cache) Len() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.ll.Len()
}