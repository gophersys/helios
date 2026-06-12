# Task: LRU cache with benchmarks

Implement package `cache` (in this module, package files at the module
root) — a fixed-capacity least-recently-used cache.

## Contract (exported API — must exist with exactly these signatures)

```go
package cache

type Config struct {
    Capacity int
}

func New(configuration Config) (*Cache, error)

func (c *Cache) Get(key string) (string, bool)
func (c *Cache) Put(key string, value string)
func (c *Cache) Len() int
```

You may add further exported API of your own design around this contract if
you find it useful.

## Semantics

- `New` returns an error if `Capacity <= 0`.
- `Put` on an existing key updates its value and marks it most recently
  used. `Get` on a hit marks the key most recently used.
- Inserting into a full cache evicts the least-recently-used entry.
- `Len` reports the current number of entries.
- The cache must be safe for concurrent use.

## Benchmarks

Include benchmarks for `Get` (on a hit) and for `Put` (with eviction) in a
`_test.go` file.

## Deliverables

- The implementation, your own tests, and the two benchmarks.
- No third-party dependencies.
