# Task: bounded-concurrency batch processor

Implement package `fetchall` (in this module, package files at the module
root).

## Contract (exported API — must exist with exactly these signatures)

```go
package fetchall

type Result struct {
    Index  int    // position of the input that produced this output
    Output string
}

func Process(
    ctx context.Context,
    inputs []string,
    concurrency int,
    operation func(ctx context.Context, input string) (string, error),
) ([]Result, error)
```

## Semantics

- `concurrency < 1` is an error. Empty `inputs` returns `(nil, nil)`.
- `operation` runs once per input. **At most `concurrency` operations may be
  in flight at any moment.**
- Results are returned ordered by `Index` ascending and contain an entry for
  every input that succeeded.
- When one or more operations fail, `Process` still runs everything and then
  returns the successful results together with a single aggregated error in
  which **every individual failure remains reachable via `errors.Is` /
  `errors.As`**.
- The `ctx` given to `Process` is the parent of every per-operation `ctx`.

## Deliverables

- The implementation.
- Your own tests for the behavior you consider important.
- No third-party dependencies.
