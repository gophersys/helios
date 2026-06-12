# Go knowledge base — full guide

You are writing Go (toolchain 1.26). Every rule below is mandatory unless one of its listed exceptions applies.

## go/constructor-purity

**Rule.** A constructor (any exported function whose name is New or starts with New) must be pure: it must not directly call time.Now, time.Sleep, timers, os.Getenv/LookupEnv/Environ, file I/O (os.Open/ReadFile/WriteFile/Create), network I/O (net.Dial*, http.Get/Post/...), or randomness (math/rand, crypto/rand.Read). All environmental effects enter through injected dependencies.

**Why.** New(configuration, dependencies) is the helios spine: a pure constructor makes every component substitutable, deterministic to test, and forces the composition root to own all wiring. A constructor that reads the clock or the environment hides an input and makes behavior untestable without patching globals.

**Applies when.** Any non-main, non-test package that defines an exported constructor.

**Exceptions.**
- Defaulting a missing dependency to a real adapter (e.g. if deps.Clock == nil { deps.Clock = systemClock{} }) is allowed: the adapter's methods may touch the environment at call time, but the constructor itself stays pure.
- package main / composition roots are exempt — wiring is their job.

**Do.**
```go
type Clock interface{ Now() time.Time }
func New(cfg Config, deps Dependencies) (*Limiter, error) {
    if deps.Clock == nil { deps.Clock = systemClock{} } // adapter default: allowed
    return &Limiter{clock: deps.Clock, capacity: cfg.Capacity}, nil
}
```

**Don't.**
```go
func New(cfg Config) (*Limiter, error) {
    return &Limiter{last: time.Now(), capacity: cfg.Capacity}, nil // hidden input
}
```

## go/environment-confinement

**Rule.** os.Getenv, os.LookupEnv and os.Environ may be called only in package main (the composition root). Library packages receive configuration as values or through an injected source function — never by reading the process environment themselves.

**Why.** Environment reads scattered through libraries create hidden global inputs: tests interfere with each other, behavior differs between hosts, and the composition root loses authority over wiring. 12-factor "config in the environment" applies to the deployable, not to every package.

**Applies when.** Any library (non-main) package; binds whenever configuration values are needed.

**Exceptions.**
- package main and cmd/* composition roots — reading the environment is exactly their job.
- test files using t.Setenv to exercise a composition root.

**Do.**
```go
// library
type Source func(key string) (value string, found bool)
func Load(source Source) (Config, error) { v, ok := source("HELIOS_PORT"); ... }
// main
cfg, err := configuration.Load(func(k string) (string, bool) { return os.LookupEnv(k) })
```

**Don't.**
```go
// library
func Load() (Config, error) {
    port := os.Getenv("HELIOS_PORT") // hidden global input in a library
    ...
}
```

## go/error-wrapping

**Rule.** When propagating an error with added context use fmt.Errorf with the %w verb (or errors.Join for aggregation). Never format an error with %v/%s into a new error and never concatenate err.Error() — both destroy the error tree, so errors.Is/As/AsType stop working for callers.

**Why.** Wrapped errors keep sentinel and typed errors inspectable across package boundaries. A %v-formatted error is a dead string: callers can no longer branch on the cause, which forces string matching — the canonical Go anti-pattern.

**Applies when.** Any code path that returns an error derived from another error.

**Exceptions.**
- Deliberate boundary opacity: when an error must NOT be inspectable (e.g. redacting internal detail at an API boundary), formatting with %v and documenting the opacity is correct.
- Log messages (not returned errors) may format errors with %v freely.

**Do.**
```go
if err != nil {
    return fmt.Errorf("load configuration: %w", err)
}
```

**Don't.**
```go
if err != nil {
    return fmt.Errorf("load configuration: %v", err) // breaks errors.Is/As
}
```

## go/interface-size

**Rule.** An exported interface declares at most 4 methods. Bigger contracts must be split into composable single-purpose interfaces (io.Reader/io.Writer style).

**Why.** The bigger the interface, the weaker the abstraction (Go proverb). Small interfaces are satisfiable by fakes, decorators and adapters; fat interfaces force every implementation to stub methods it does not care about and make conformance suites combinatorial.

**Applies when.** Any exported interface type in a library package.

**Exceptions.**
- Interfaces mirroring an external wire contract (a generated client, a protocol surface) may exceed the limit; isolate them in the adapter layer.
- Unexported interfaces are not scored — internal seams may be pragmatic.

**Do.**
```go
type Reader interface{ Read(p []byte) (int, error) }
type Closer interface{ Close() error }
type ReadCloser interface { Reader; Closer }
```

**Don't.**
```go
type Store interface { // 7 methods: unfakeable, unsplittable
    Get(...); Put(...); Delete(...); List(...); Watch(...); Compact(...); Stats(...)
}
```

## go/return-concrete

**Rule.** Exported functions and constructors return concrete types (or error), not project-defined interface types. "Accept interfaces, return structs": the consumer decides which interface to view the value through.

**Why.** Returning an interface erases the concrete API surface, blocks method additions without breaking callers, defeats inlining, and inverts ownership: interfaces belong to consumers, not producers. Returning the struct keeps the full API available and lets each caller declare its own narrow seam.

**Applies when.** Any exported function in a library package whose result is a project-defined named interface.

**Exceptions.**
- error and context.Context are interfaces by design — always allowed.
- Standard-library interfaces (io.Reader, slog.Handler, http.Handler, ...) are established contracts; returning them is allowed when the function's purpose is to produce that contract.
- Factories that genuinely select among implementations at runtime may return an interface; document why.

**Do.**
```go
func New(cfg Config) (*Cache, error) { ... }   // caller sees the full *Cache API
```

**Don't.**
```go
type Cacher interface{ Get(string) (string, bool); Put(string, string) }
func New(cfg Config) (Cacher, error) { ... }   // producer-owned interface
```

## go/context-first

**Rule.** If a function takes a context.Context it is the first parameter and it is named ctx. Contexts are never stored in structs and never replaced by a package-level context.

**Why.** A uniform context position makes cancellation auditable at a glance and composes with every API in the ecosystem. Struct-stored contexts outlive their request scope and leak cancellation semantics.

**Applies when.** Any function or method that performs cancellable or deadline-bound work.

**Exceptions.**
- Methods implementing a third-party interface whose signature fixes a different parameter order.
- A struct field holding a context is acceptable only for the documented http.Request-style carrier pattern.

**Do.**
```go
func (r *Retrier) Do(ctx context.Context, operation func(ctx context.Context) error) error
```

**Don't.**
```go
func (r *Retrier) Do(operation func() error, ctx context.Context) error // ctx buried
```

## go/errors-astype

**Rule.** To extract a typed error from an error tree use the generic errors.AsType[E](err) (Go 1.26), not errors.As(err, &target). AsType is type-safe at compile time, needs no pre-declared target variable, and is faster.

**Why.** errors.As takes any (interface{}) and panics at runtime on a mis-typed target; the 1.26 generic form moves that to compile time and reads as a single expression. The Go release notes describe it as a "type-safe, faster alternative to As". New code on Go >= 1.26 has no reason to use the old form.

**Applies when.** Code on Go >= 1.26 that branches on a typed error in an error tree.

**Exceptions.**
- Code that must build on Go < 1.26 keeps errors.As.
- Matching against an interface type with errors.As where the target type is only known dynamically.

**Do.**
```go
if transient, ok := errors.AsType[*TransientError](err); ok {
    delay = transient.RetryAfter
}
```

**Don't.**
```go
var transient *TransientError
if errors.As(err, &transient) { delay = transient.RetryAfter }
```

## go/slog-multihandler

**Rule.** To send log records to several slog handlers, use slog.NewMultiHandler (Go 1.26). Do not hand-roll a fan-out type that holds a slice of handlers and loops over them in Handle.

**Why.** Hand-rolled multi-handlers were the standard workaround before 1.26 and they routinely get the contract wrong: Enabled short-circuiting, WithAttrs/ WithGroup cloning, and error joining across children. The stdlib version handles all four correctly and is the single obvious way.

**Applies when.** Code on Go >= 1.26 that needs one logger writing to multiple sinks.

**Exceptions.**
- Code that must build on Go < 1.26 may hand-roll (or vendor) a fan-out handler.
- A custom Handler that filters/transforms per child (not a plain fan-out) is real logic, not a multi-handler — allowed.

**Do.**
```go
logger := slog.New(slog.NewMultiHandler(jsonHandler, ringHandler))
```

**Don't.**
```go
type multiHandler struct{ handlers []slog.Handler }
func (m *multiHandler) Handle(ctx context.Context, r slog.Record) error {
    for _, h := range m.handlers { h.Handle(ctx, r) } // wrong on 4 contract points
    return nil
}
```

## go/benchmark-loop

**Rule.** Benchmarks iterate with `for b.Loop()` (Go 1.24), not `for i := 0; i < b.N; i++` and not `for range b.N`. b.Loop keeps setup and cleanup outside the measured region exactly once and prevents the compiler from optimizing the benchmarked call away.

**Why.** The b.N pattern re-runs setup on every benchmark restart, silently measures dead code when the compiler proves results unused, and is the single most copied stale idiom in Go. b.Loop fixes all three; since Go 1.26 it no longer even inhibits inlining.

**Applies when.** Any *_test.go benchmark on Go >= 1.24.

**Exceptions.**
- Code that must build on Go < 1.24 keeps b.N.
- Benchmarks that intentionally index by iteration (e.g. pre-generated inputs[i]) may keep a manual counter alongside b.Loop.

**Do.**
```go
func BenchmarkGet(b *testing.B) {
    c := mustCache(b)
    for b.Loop() { c.Get("k") }
}
```

**Don't.**
```go
func BenchmarkGet(b *testing.B) {
    c := mustCache(b)
    for i := 0; i < b.N; i++ { c.Get("k") } // stale idiom: setup re-runs, dead-code risk
}
```

## go/waitgroup-go

**Rule.** When spawning one goroutine per task, use sync.WaitGroup.Go(f) (Go 1.25) instead of the wg.Add(1) / go func() { defer wg.Done(); ... }() triple.

**Why.** The Add/go/Done triple has two classic failure modes — Add inside the goroutine (race with Wait) and a forgotten Done on an early return (deadlock). WaitGroup.Go makes both unrepresentable and reads as one line.

**Applies when.** Code on Go >= 1.25 that spawns goroutines tracked by a sync.WaitGroup, where the goroutine is created at the call site.

**Exceptions.**
- Code that must build on Go < 1.25 keeps Add/Done.
- Decoupled lifecycles — when Add happens in one place and the goroutine is started elsewhere (worker pools handing tasks to pre-started workers), Add/Done remains the correct primitive.

**Do.**
```go
var wg sync.WaitGroup
for _, input := range inputs {
    wg.Go(func() { process(input) })
}
wg.Wait()
```

**Don't.**
```go
var wg sync.WaitGroup
for _, input := range inputs {
    wg.Add(1)
    go func() { defer wg.Done(); process(input) }()
}
wg.Wait()
```

