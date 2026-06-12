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
	mu    sync.Mutex
	cap   int
	ll    *list.List
	items map[string]*list.Element
}

func New(config Config) (*Cache, error) {
	if config.Capacity <= 0 {
		return nil, errors.New("cache: capacity must be positive")
	}
	return &Cache{
		cap:   config.Capacity,
		ll:    list.New(),
		items: make(map[string]*list.Element, config.Capacity),
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
			e := back.Value.(*entry)
			delete(c.items, e.key)
			c.ll.Remove(back)
		}
	}

	e := &entry{key: key, value: value}
	elem := c.ll.PushFront(e)
	c.items[key] = elem
}

func (c *Cache) Len() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.ll.Len()
}