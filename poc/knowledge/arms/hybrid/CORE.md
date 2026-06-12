# Go knowledge core (toolchain 1.26)

Mandatory rules. The deterministic checker (`bash ./check.sh`) enforces all of them — run it and fix findings until it exits 0.

- **go/constructor-purity** — A constructor (any exported function whose name is New or starts with New) must be pure: it must not directly call time.Now, time.Sleep, timers, os.Getenv/LookupEnv/Environ, file I/O (os.Open/ReadFile/WriteFile/Create), network I/O (net.Dial*, http.Get/Post/...), or randomness (math/rand, crypto/rand.Read). All environmental effects enter through injected dependencies.
- **go/environment-confinement** — os.Getenv, os.LookupEnv and os.Environ may be called only in package main (the composition root). Library packages receive configuration as values or through an injected source function — never by reading the process environment themselves.
- **go/error-wrapping** — When propagating an error with added context use fmt.Errorf with the %w verb (or errors.Join for aggregation). Never format an error with %v/%s into a new error and never concatenate err.Error() — both destroy the error tree, so errors.Is/As/AsType stop working for callers.
- **go/interface-size** — An exported interface declares at most 4 methods. Bigger contracts must be split into composable single-purpose interfaces (io.Reader/io.Writer style).
- **go/return-concrete** — Exported functions and constructors return concrete types (or error), not project-defined interface types. "Accept interfaces, return structs": the consumer decides which interface to view the value through.
- **go/context-first** — If a function takes a context.Context it is the first parameter and it is named ctx. Contexts are never stored in structs and never replaced by a package-level context.

## Go 1.24–1.26 APIs you must use (newer than your training data)

- **go/errors-astype** (Go 1.26+) — To extract a typed error from an error tree use the generic errors.AsType[E](err) (Go 1.26), not errors.As(err, &target). AsType is type-safe at compile time, needs no pre-declared target variable, and is faster.
```go
if transient, ok := errors.AsType[*TransientError](err); ok {
    delay = transient.RetryAfter
}
```
- **go/slog-multihandler** (Go 1.26+) — To send log records to several slog handlers, use slog.NewMultiHandler (Go 1.26). Do not hand-roll a fan-out type that holds a slice of handlers and loops over them in Handle.
```go
logger := slog.New(slog.NewMultiHandler(jsonHandler, ringHandler))
```
- **go/benchmark-loop** (Go 1.24+) — Benchmarks iterate with `for b.Loop()` (Go 1.24), not `for i := 0; i < b.N; i++` and not `for range b.N`. b.Loop keeps setup and cleanup outside the measured region exactly once and prevents the compiler from optimizing the benchmarked call away.
```go
func BenchmarkGet(b *testing.B) {
    c := mustCache(b)
    for b.Loop() { c.Get("k") }
}
```
- **go/waitgroup-go** (Go 1.25+) — When spawning one goroutine per task, use sync.WaitGroup.Go(f) (Go 1.25) instead of the wg.Add(1) / go func() { defer wg.Done(); ... }() triple.
```go
var wg sync.WaitGroup
for _, input := range inputs {
    wg.Go(func() { process(input) })
}
wg.Wait()
```
