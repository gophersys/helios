---
name: api-design
description: This skill should be used when authoring or reviewing Go code in the Eden libs (libs/go/*) — designing an interface or port, writing a New(Config, Deps) constructor, naming a package/type, or shaping an error type. It renders the neutral library design rules (interface design, HNS-1 naming, error handling) into concrete Go and names the golangci-lint + hnslint checks that enforce each one.
---

# Go API design — the Eden library rendering

This skill is layer (B) of the three-layer model (10 §9): it renders the neutral
principles in `libs/.claude/rules/` into Go. Layer (C) — `golangci-lint` + `hnslint` —
mechanically enforces every rule named below. **Knowledge guides; the linters decide.**

## The constructor spine

Every library component is constructed the same way and the constructor is **pure**:

```go
// Config is the immutable, fully-resolved input (parsed once at the edge, then frozen).
// Deps is the injected record of ports (Clock, RandomSource, Sink, ...). New does NO
// I/O, reads no clock, reads no environment, touches no global.
func New(configuration Config, dependencies Deps) (*Provider, error) { ... }
```

- `New` returns a **concrete** type (`*Provider`), never an interface.
- The exported type names `Config` and `Deps` are the sanctioned idiomatic exemption to
  HNS-1 — they are type names, not pattern/package names. The package is still
  `package configuration`, never `package config`.

## Interfaces: small, composable, consumer-defined

- **≤ 5 methods.** Enforced by `interfacebloat` (max 5). A larger interface means two
  roles are tangled; split it into composable single-purpose interfaces.
- **Accept interfaces, return concrete.** Enforced by `ireturn`. Functions accept the
  narrowest interface they need and return concrete types.
- **Consumer-defined ports.** Declare the interface in the package that *uses* it,
  describing exactly the behaviour needed — do not re-export an interface from the package
  that implements it. A port is a need, not a mirror.

```go
// GOOD — declared where consumed, 1 method, accepts interface / returns concrete.
type Clock interface{ Now() time.Time }

func New(_ Config, deps Deps) (*Engine, error) { // returns concrete *Engine
    return &Engine{clock: deps.Clock}, nil       // depends on the narrow Clock port
}
```

Enforced also by `revive` (exported-symbol doc comments, receiver consistency, naming).

## Naming (HNS-1)

- Package = the separator-free lowercase slug; module = `github.com/gophersys/libs/go/<slug>`;
  directory = the slug. Enforced **structurally** by `hnslint`.
- Banned identifier tokens — `cfg`/`config`, `deps`, `k8s`, `mgmt`, `obsv`/`o11y`,
  `golang`, `util`/`utils`/`common`/`core`/`misc` — are rejected by `forbidigo`. Use the
  full form (`configuration`, `dependencies`, `kubernetes`, `management`, `observability`,
  `go`); for `util`/`common`/`core`/`misc` there is no full form — name the real concept.
- The fakes package for a library is `<slug>test` (e.g. `configurationtest`), never an
  abbreviation-based name like `cfgtest` — `hnslint` rejects the latter specifically.

## Errors: typed, wrapped, inspected by type

- **Never swallow.** Every error is checked, wrapped-and-returned, or explicitly ignored
  with a `//nolint`-style justification. Enforced by `errcheck`, `nilerr`, `nilnil`.
- **Wrap with `%w`** at boundaries so the chain stays inspectable. Enforced by `wrapcheck`,
  `errorlint`.
- **Inspect by type, not string:** branch with `errors.As` / the library's `AsType`, never
  on message substrings. Enforced by `errorlint`.
- **No ad-hoc errors at the throw site:** declare sentinels / typed errors. Enforced by
  `err113` (no dynamic `errors.New` in-line where a typed error belongs) and `errname`
  (sentinel/typed-error naming).
- Errors are **redaction-safe** — a `Secret` is un-printable by type, so it can never leak
  through an error string.

```go
var ErrNotFound = errors.New(errors.KindNotFound, "resource not found") // declared sentinel

func load(id string) (*Thing, error) {
    t, err := store.Get(id)
    if err != nil {
        return nil, fmt.Errorf("load thing %q: %w", id, err) // wrap, preserve chain
    }
    return t, nil
}

// caller inspects by type/kind, not by string:
if errors.AsType[*errors.Error](err) != nil && errors.KindOf(err) == errors.KindNotFound { ... }
```

## The discipline in one line

Small consumer-owned interfaces, a pure `New(Config, Deps)` spine, fully-spelled names,
and typed-wrapped-inspected errors — and a linter for every one of those words, so the
contract is compiled in, not hoped for.
