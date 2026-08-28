# Rule — Error handling

> Neutral principle (10 §9 layer A). Enforced mechanically by `golangci-lint` (errcheck,
> wrapcheck, errorlint, err113, errname, nilerr, nilnil) and the `errors` library contract.

An error is data the caller is entitled to inspect and act on. It is **typed**, **wrapped
with context as it crosses a boundary**, and **inspected by type, never by string**. An
error is never silently dropped.

## Principles

- **No swallowed errors.** Every returned error is handled — checked, wrapped and
  returned, or (rarely, and explicitly) deliberately ignored with a comment saying why.
  An error discarded silently is a bug the caller can never diagnose.
- **Typed, with a stable `Kind`.** Errors carry a stable, inspectable classification, not
  just a message. The classification is part of the contract — wire and telemetry depend on
  it — so it does not drift.
- **Wrap with context, preserve the chain.** When an error crosses a boundary, wrap it so
  the cause stays reachable (in Go: `%w`). Each layer adds *what it was doing*; no layer
  flattens the chain into an opaque string.
- **Inspect by type, not by string.** Decisions branch on the error's *type/kind* via
  typed inspection (in Go: `errors.As` / the library's `AsType`), never by matching
  substrings of a message. Message text is for humans and may change; type is the contract.
- **Redaction-safe.** An error never embeds a secret value. Secrets are referenced, not
  inlined, so an error is safe to log and telemeter by construction.
- **Sentinels are declared, not invented inline.** A comparable error value is a named,
  exported declaration — not an ad-hoc `New("...")` at the throw site that no caller can
  match against.

## Why

If errors are strings, every call site that needs to react becomes a fragile pattern-match,
and refactoring a message silently breaks callers. A typed, wrapped, inspectable error
model makes failure handling part of the compiled contract: the caller branches on `Kind`,
the chain stays intact for diagnosis, and no secret ever leaks through the failure path.
