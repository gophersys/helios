# Rule — Interface design

> Neutral principle (10 §9 layer A). The per-ecosystem rendering and the linters that
> enforce it live in `plugins/project-<ecosystem>`; this file states the contract once.

Interfaces are the library's load-bearing surface. Breaking a published interface is the
most severe violation in the system, so an interface is designed to be **small enough to
be right the first time** and **owned by its consumer**, not its implementer.

## Principles

- **Small and composable.** An interface declares **at most 5 methods**. A larger surface
  is a sign that two roles are tangled — split it. Prefer several single-purpose interfaces
  that compose over one broad one.
- **Accept interfaces, return concrete.** A constructor and a function **accept** the
  narrowest interface they need and **return** a concrete type. Callers depend on the
  abstraction; they receive something they can use without further indirection.
- **Consumer-defined.** The interface is declared where it is *used*, expressing exactly
  the behaviour that caller needs — not re-exported from where the implementation lives. A
  port is the shape of a need, not a mirror of an implementation.
- **The constructor spine.** Every component is built the same way:

  ```
  New(configuration, dependencies) -> (Component, error)
  ```

  `configuration` is the immutable, fully-resolved input; `dependencies` is the injected
  record of ports (the hexagon). `New` is **pure**: no I/O, no clock reads, no environment
  reads, no globals. Everything the component touches arrives through one of those two
  parameters. This is what makes a component trivially fakeable and the composition root
  the only place wiring is chosen.
- **One concept, one home.** A type or port is defined once and cited elsewhere, never
  redefined. Duplication of a contract is duplication of the bug surface.

## Why

Hexagonal architecture is only as strong as its narrowest seam. A 5-method ceiling, the
accept-interfaces/return-concrete rule, and the pure `New(configuration, dependencies)`
spine together guarantee that any adapter is substitutable by a fake, that the dependency
graph flows one way, and that the published surface stays small enough to keep stable
across versions.
