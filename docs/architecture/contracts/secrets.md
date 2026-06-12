# Contract draft — secrets

> Status: Draft for negotiation (WS1, not frozen) · 2026-06-12 · Reconciled from independent producer/consumer drafts (09 §4). Freezes at the contract-PR gate after review.

## 1. Scope

`secrets` is the port that resolves an opaque, loggable `Reference` to a short-lived
`Secret` **at point of use**. The discipline lives in the TYPE (10 §4, 07 §2): a `Secret` is
constructed un-printable — `String`/`GoString`/`Format`/`MarshalText`/`MarshalJSON`/`LogValue`
all redact — so values cannot reach logs, telemetry, or transcripts by construction, not by
filter list. `Use(fn)` scopes exposure to a single call frame; `Zeroize()` wipes. References
are loggable and live in `configuration`.

It does **not** provide: a value accessor (`Bytes()`/`Value()`); secret writing, rotation, or
listing (operator/adapter concerns, off the consumer port); a consumer-reachable way to mint a
`Secret` from raw bytes; any stage detection or env read (the scheme→adapter table is injected at
the composition root, 10 §2).

## 2. Contract

```go
// Package secrets is the port for resolving opaque references to short-lived secret
// values at point of use. Its discipline lives in the TYPE: a Secret is constructed
// un-printable — String/GoString/Format/MarshalText/MarshalJSON and slog.LogValue all
// redact — so values cannot reach logs, telemetry, or transcripts by construction (07 §2,
// 10 §4), not by a filter list. References are loggable and live in configuration; values
// never do.
package secrets

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/gophersys/libs/go/errors"
)

// Reference is the opaque, loggable handle to a secret. It lives in configuration and is
// safe to print, serialize, telemeter, and persist. It names a secret; it never carries the
// value. It is comparable (usable as a map key for routing and for dependency records).
// The zero value is the invalid reference, which Resolve rejects.
//
// The unexported field makes every Reference pass through ParseReference / Ref, so each is
// shape-validated and the struct stays comparable without an addressable field. Zero value:
// invalid (IsZero reports true). Safe for concurrent use (immutable value).
type Reference struct {
	// raw is the canonical form, e.g. "vault://eden/connectors/github#token" or a bare
	// stable name like "anthropic-api-key" (the implicit-scheme form).
	raw string
}

// ParseReference validates and constructs a Reference from its canonical string form. PURE:
// no I/O, no resolution — it checks shape only. A bare name with no "scheme://" is accepted
// and routed via Config.DefaultScheme at Resolve time. The scheme selects the adapter at the
// composition root; this package does not interpret it. Returns a wrapped error
// (errors.AsType[InvalidReferenceError]) for malformed input.
func ParseReference(s string) (Reference, error)

// Ref is the ergonomic constructor for the common bare-name case (e.g.
// Ref("anthropic-api-key")), where the scheme is supplied by Config.DefaultScheme. It panics
// only on a name that cannot be a valid Reference under any scheme; for config-driven input
// prefer ParseReference. Pure; no I/O.
func Ref(name string) Reference

// String returns the canonical form. A Reference is loggable by design.
func (r Reference) String() string

// Scheme returns the leading scheme (the substring before "://"), used at the composition
// root to route a Reference to an adapter. Empty when the Reference carries no explicit
// scheme (DefaultScheme applies) and for the zero value.
func (r Reference) Scheme() string

// IsZero reports whether r is the invalid zero Reference.
func (r Reference) IsZero() bool

// Provider resolves references to secrets. It is the ONLY port a consumer depends on;
// adapters (vault, env-for-development, keychain) implement it and are bound at the
// composition root. Accept this interface; return the concrete adapter (or *Mediator).
// Implementations MUST be safe for concurrent use by multiple goroutines.
type Provider interface {
	// Resolve mints/fetches the current value for ref and returns a fresh Secret the caller
	// owns and must Zeroize (defer sec.Zeroize() is the idiom). Resolve is the only blocking
	// method, so context is first. On failure it returns a wrapped error inspectable via
	// errors.AsType for InvalidReferenceError / NotFoundError / DeniedError / UnavailableError;
	// the error message carries the Reference, never the value. It never returns a non-nil
	// Secret together with a non-nil error.
	Resolve(ctx context.Context, ref Reference) (*Secret, error)
}

// Secret holds secret bytes and is un-printable by construction. It is a pointer type with a
// non-copyable payload (noCopy makes `go vet` flag value copies that would duplicate bytes
// past a Zeroize). The only legitimate read path is Use; there is no Bytes() or Value().
//
// Concurrency: a Secret is NOT safe for concurrent mutation. Use is reentrant-safe for reads,
// but Zeroize must not race with Use. Treat one Secret as owned by one goroutine for its
// lifetime — which is the point-of-use scope. Zero value: not constructible by consumers;
// only adapters and secretstest mint Secrets (via an internal hook).
type Secret struct {
	_ noCopy // unexported; see internal impl for the bytes + zeroed state
}

// Use grants fn the only legitimate window onto the plaintext. The slice passed to fn is
// valid ONLY for the duration of the call and is read-only by contract; fn must not retain it.
// Use returns fn's error, or a wrapped error (errors.AsType[ZeroizedError]) if the secret was
// already wiped. This is the sole read path — there is no Bytes().
func (s *Secret) Use(fn func(plaintext []byte) error) error

// Zeroize best-effort wipes the backing bytes and marks the secret spent. Idempotent. The
// idiom is `defer sec.Zeroize()` at point of use. After Zeroize, Use returns a wrapped
// ZeroizedError. Mandatory on embedded (10 §4); advisory-but-wired here.
func (s *Secret) Zeroize()

// The redaction surface — every standard stringification/marshaling path is overridden to
// emit the single Redacted sentinel. There is NO method that returns the value as a string.
func (s *Secret) String() string               // == Redacted
func (s *Secret) GoString() string             // == Redacted
func (s *Secret) Format(f fmt.State, verb rune) // ignores verb; writes Redacted (defeats %v/%+v/%#v/%q)
func (s *Secret) MarshalText() ([]byte, error)  // ([]byte(Redacted), nil)
func (s *Secret) MarshalJSON() ([]byte, error)  // ([]byte(`"`+Redacted+`"`), nil)
func (s *Secret) LogValue() slog.Value          // slog.StringValue(Redacted)

// TelemetryValue returns the telemetry-safe projection of a Secret — always Redacted, never
// the value. It structurally satisfies observability.Valuer (TelemetryValue() any) WITHOUT
// importing observability, so a *Secret can ride observability.Any(key, valuer) as nothing but
// its sentinel. secrets stays a leaf library (no upward dependency); Go interface satisfaction
// is implicit, so the seam needs no shared type. (observability.md Q9.)
func (s *Secret) TelemetryValue() any           // returns Redacted

// Redacted is the single sentinel every formatting/marshaling path on Secret returns.
const Redacted = "secrets.Secret(REDACTED)"

// Use1 is a typed convenience over Use for the common "derive exactly one value out" case
// (e.g. a signed token, an HMAC, a sealed request) without widening to a retainable accessor.
// V MUST NOT be the secret itself — the closure must transform, not copy through. It is a free
// function (not a method) because Go methods cannot carry their own type parameter.
func Use1[V any](s *Secret, fn func(plaintext []byte) (V, error)) (V, error)

// New is the constructor spine. PURE: no I/O, no clocks, no env reads. It validates
// configuration and wires the (already-constructed) adapters from dependencies into the
// routing Mediator. Adapters do the I/O, lazily, on Resolve. Returns the concrete *Mediator.
func New(configuration Config, dependencies Deps) (*Mediator, error)

// Config is the immutable, fully-resolved input. The only knob the routing Mediator needs is
// the default scheme; references themselves arrive at Resolve time.
type Config struct {
	// DefaultScheme routes a Reference that carries no explicit scheme. Empty means "require
	// an explicit scheme" (a schemeless Reference then resolves to InvalidReferenceError).
	DefaultScheme string
}

// Deps is the injected hexagon: the resolver adapters keyed by scheme. Accepting Provider (an
// interface) here is the accept-interfaces rule; the Mediator returned is concrete.
type Deps struct {
	// Resolvers maps a Reference scheme to the adapter that serves it. At least one entry is
	// required; New returns an error otherwise.
	Resolvers map[string]Provider
}

// Mediator is the concrete Provider returned by New: it routes each Reference to the
// Deps.Resolvers entry for its scheme (or DefaultScheme) and is the type apps hold. Safe for
// concurrent use. Zero value is not usable; construct via New.
type Mediator struct{ /* unexported */ }

// Resolve implements Provider by routing ref to its scheme's adapter.
func (m *Mediator) Resolve(ctx context.Context, ref Reference) (*Secret, error)

// The error taxonomy. Each is a distinct type carrying the offending Reference (never the
// value), inspectable via errors.AsType[...] — never by string match. Adapters return these
// wrapped with %w so callers branch on kind across rewordings.
type (
	InvalidReferenceError struct{ Ref Reference } // ref malformed or zero
	NotFoundError         struct{ Ref Reference } // ref well-formed, no such secret
	DeniedError           struct{ Ref Reference } // caller lacks scope for ref
	UnavailableError      struct{ Ref Reference } // backing store unreachable (retryable)
	ZeroizedError         struct{}                // Use after Zeroize
)

func (e InvalidReferenceError) Error() string
func (e NotFoundError) Error() string
func (e DeniedError) Error() string
func (e UnavailableError) Error() string
func (e ZeroizedError) Error() string
```

## 3. Fake

```go
// Package secretstest provides the canonical in-memory fake Provider and a constructor for
// test Secrets, so consumers never hand-roll a fake that breaks the un-printable invariant.
// It mints genuine, real secrets.Secret values via an internal hook the library shares only
// with this package — the fake weakens the SOURCE of bytes, never the type.
package secretstest

import (
	"context"

	"github.com/gophersys/libs/go/secrets"
)

// Provider is a deterministic, in-memory secrets.Provider for tests. Zero value resolves
// nothing (every ref → NotFoundError), so tests opt in explicitly. Deterministic; no clock,
// no I/O. Safe for concurrent use.
type Provider struct {
	// Resolved is an append-only log of the references asked for — refs only, never values —
	// for "was this credential requested?" assertions.
	Resolved []secrets.Reference
}

// New returns a fake seeded from name→plaintext. It copies the bytes, so callers cannot alias
// the seed; each Resolve returns an independent Secret so a SUT-side Zeroize cannot corrupt it.
func New(seed map[string]string) *Provider

// Set seeds (or overrides) one reference. Fluent for table tests.
func (p *Provider) Set(name, plaintext string) *Provider

// FailWith forces Resolve(ref) to return err — pass a secrets error value, e.g.
// secrets.DeniedError{Ref: ...} or secrets.UnavailableError{Ref: ...}.
func (p *Provider) FailWith(name string, err error) *Provider

// Resolve implements secrets.Provider. It records ref, then returns a fresh, real,
// un-printable *secrets.Secret (via the package's internal test hook) or the forced error.
func (p *Provider) Resolve(ctx context.Context, ref secrets.Reference) (*secrets.Secret, error)

// MintSecret builds a standalone, real *secrets.Secret from literal bytes without a Provider —
// for unit tests of code that consumes a Secret directly. It is the only place outside an
// adapter that can produce a Secret, and it produces a genuine un-printable one.
func MintSecret(plaintext []byte) *secrets.Secret

// AssertNotLeaked fails t if value appears verbatim in haystack (a captured log buffer or
// rendered transcript) — giving the redaction guarantee a runnable assertion.
func AssertNotLeaked(t TestingT, haystack, value string)

// TestingT is the minimal testing surface AssertNotLeaked needs (satisfied by *testing.T).
type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
}
```

> Minting note (settled): `secretstest.MintSecret` and `Provider.Resolve` mint a `*secrets.Secret`
> through an **internal package shared by `secrets` and `secretstest`** (no `//go:linkname`, no
> public constructor). Minting a raw `Secret` is never a consumer-reachable surface — the only
> public producers are `Provider` adapters and this test package.

## 4. Conformance suite

The suite proves any `secrets.Provider` (real adapter or `secretstest.Provider`) is
substitutable and that the `Secret` type holds the line. It lives in `secretstest` per the
testing pattern (10 §4, 08 §2).

```go
// RunProviderSuite asserts the Provider port contract against a freshly-constructed Provider.
// newProvider returns a Provider pre-seeded so that `present` resolves and `absent` does not.
func RunProviderSuite(t *testing.T, newProvider func() secrets.Provider, present, absent secrets.Reference)
```

Properties asserted:

- **Resolve happy path** returns a non-nil `*Secret` and nil error for `present`.
- **Never both non-nil:** on any error, the returned `*Secret` is nil (and vice versa).
- **Typed errors:** resolving `absent` yields an error matched by `errors.AsType[NotFoundError]`;
  a forced denial/outage yields `DeniedError`/`UnavailableError`; the zero `Reference` yields
  `InvalidReferenceError`.
- **Error carries the Reference, never the value:** the error string contains the ref's canonical
  form and does NOT contain the seeded plaintext.
- **Use is the only read path:** `Use(fn)` invokes fn with the seeded bytes; `Use` after
  `Zeroize` returns `errors.AsType[ZeroizedError]`.
- **Redaction is total:** `fmt.Sprintf("%s %v %+v %#v %q", sec, ...)`, `slog` rendering,
  `json.Marshal`, and `encoding.TextMarshaler` all yield `Redacted` and never the plaintext.
- **Zeroize is idempotent** and a second call is a no-op.
- **Independence:** two `Resolve` calls for the same ref return independent `Secret`s — zeroizing
  one does not affect the other.
- **Reference round-trips:** `ParseReference(r.String())` reproduces `r`; the zero `Reference`
  reports `IsZero()`.

## 5. Usage

```go
// --- composition root (the ONLY place adapters bind and the ONLY stage switch; New stays pure) ---
func wiringFor(stage environment.Stage) secrets.Provider {
	var resolvers map[string]secrets.Provider
	switch stage {
	case environment.Production, environment.Staging:
		resolvers = map[string]secrets.Provider{"vault": vaultadapter} // concrete, built elsewhere
	default:
		resolvers = map[string]secrets.Provider{"env": envadapter} // reads os env at Resolve, never at New
	}
	prov, _ := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: resolvers},
	)
	return prov // a *secrets.Mediator, held as the Provider port downstream
}

// --- in-library usage: agentconfiguration holds the loggable Reference, never the key ---
type ModelBinding struct {
	Model  string
	APIKey secrets.Reference // e.g. secrets.Ref("anthropic-api-key") — safe in configuration & logs
}

// engine resolves at point of use, scopes exposure to the request build, wipes on the way out.
func (e *Engine) callModel(ctx context.Context, b ModelBinding, body []byte) (*Response, error) {
	sec, err := e.secrets.Resolve(ctx, b.APIKey)
	if err != nil {
		if denied := (secrets.DeniedError{}); errors.AsType(err, &denied) {
			return nil, fmt.Errorf("model %q: credential %s unauthorized: %w", b.Model, b.APIKey, err)
		}
		return nil, fmt.Errorf("resolve %s: %w", b.APIKey, err) // ref in the message, never the value
	}
	defer sec.Zeroize()

	req := newRequest(ctx, body)
	if err := sec.Use(func(key []byte) error { // key valid only inside this closure
		req.Header.Set("Authorization", "Bearer "+string(key))
		return nil
	}); err != nil {
		return nil, err
	}

	// safe by construction: the ref prints its name; the secret cannot be printed at all.
	e.log.Info("model call", "model", b.Model, "credential", b.APIKey)
	_ = fmt.Sprintf("%s %v %#v", sec, sec, sec) // all render Redacted
	return e.do(req)
}
```

## 6. Design rationale

1. **One port, one method.** `Provider.Resolve` is the whole interface (1 of ≤5, 10 §9). Listing,
   rotating, and writing secrets are operator/adapter concerns, off the consumer-facing port to
   resist speculative generality. Both drafts agreed; kept verbatim.
2. **`Reference` is a validated value type, not a `string` alias.** Unexported field +
   `ParseReference`/`Ref` constructors mean every `Reference` is shape-checked, stays comparable
   (a routing/dependency-record map key), and its zero value is unambiguously invalid. It is
   loggable by contract — the half of the discipline that *must* be printable (07 §2). It is the
   join key between `configuration` (refs parsed) and this port (refs resolved).
3. **`Secret` is a pointer with `noCopy` and no `Bytes()`.** The sole read path `Use(fn)` bounds
   plaintext to one call frame and forbids retention by slice invalidation + convention; `noCopy`
   makes `go vet` flag copies that would defeat `Zeroize` (10 §4). Removing `Bytes()` removes the
   obvious leak. Both drafts treat this as the load-bearing, non-negotiable constraint.
4. **The redaction surface is exhaustive and identical.** `String/GoString/Format/MarshalText/
   MarshalJSON/LogValue` all emit `Redacted`. Covering `slog.LogValuer` is non-negotiable because
   `observability`/`logging` are slog-based (10 §6.1); `Format` defeats `%v/%+v/%#v/%q`; the
   marshalers defeat `encoding/json` and text encoders — the three leak surfaces logs/telemetry/
   transcripts (07 §2). Filter lists / verbose modes are explicitly rejected.
5. **`New(Config, Deps)` is pure; the `Mediator` is the routing layer.** `Config` carries only the
   default-scheme knob; `Deps` injects pre-built adapters keyed by scheme; the `Mediator` picks the
   adapter per reference at `Resolve` time. All I/O is lazy in adapters — the spine reads no env,
   opens no connection, touches no clock (10 §2, §4). New returns the concrete `*Mediator`
   (return-concrete), held downstream as the `Provider` port (accept-interface).
6. **Errors are typed structs carrying a `Reference`, inspected via `errors.AsType`.** The ground
   rule names `errors.AsType` and the `errors` pattern commits to a stable taxonomy (10 §4); typed
   structs (`NotFoundError`/`DeniedError`/`UnavailableError`/`InvalidReferenceError`/`ZeroizedError`)
   give `AsType[T]` a target and let adapters reword messages without a breaking change. The error
   carries the `Reference`, never the value. `Unavailable` is the one retryable signal.
7. **Minting stays internal.** Nothing public constructs a `Secret` from raw bytes except adapters
   (bytes from their backing store inside `Resolve`) and `secretstest.MintSecret` (via the shared
   internal package). A consumer cannot fabricate a `Secret`, so the type is the only ingress and
   the invariant holds end to end (07 §2).
8. **`Use1` is a free generic helper, not a method.** Go methods cannot carry their own type
   parameter, so the consumer's "derive exactly one value out" need (auth header / signed token) is
   a package-level `Use1[V]` constrained by the same closure-scoped discipline — it never widens to
   a retainable accessor.

## 7. Open questions

| # | question / conflict | producer position | consumer position | reconciler resolution 🧩 |
|---|---|---|---|---|
| 1 | `Reference` shape — validated URI with scheme routing, or a bare stable name? | `ParseReference` + `Scheme()`; scheme selects the adapter at the composition root | `Ref(name)` over a bare name (`"anthropic-api-key"`); routing is the adapter's problem | 🧩 **Kept both.** `Reference` is the validated value type with `Scheme()`; a schemeless `Reference` is legal and routes via `Config.DefaultScheme`, so the consumer's `Ref("anthropic-api-key")` ergonomics survive while the producer's scheme-routing `Mediator` keeps a real composition-root job. `ParseReference` is the config-driven path; `Ref` the literal path. |
| 2 | Error model — a `Kind int` enum, or typed error structs? | `Kind` enum carried on a wrapped error, branched via `errors.AsType` | typed structs `NotFoundError`/`Forbidden`/`Unavailable` via `errors.AsType[T]` | 🧩 **Typed structs win.** The ground rule and the consumer call sites use `errors.AsType[T]`, which needs a *type* target; an `int` enum would force a wrapper-and-getter dance. Each error carries the `Reference` (the producer's "value never in the message" demand holds), and the set is the producer's taxonomy renamed to types: `InvalidReferenceError`/`NotFoundError`/`DeniedError`/`UnavailableError` (+ `ZeroizedError`). `KindUnspecified` is dropped — an untyped/unwrapped error is the unspecified case. |
| 3 | `Secret.Close() io.Closer`, or `Zeroize()` only? | add `Close()` so `defer sec.Close()` is idiomatic and `Secret` is an `io.Closer` | `defer sec.Zeroize()`; no `Close` | 🧩 **Rejected `Close()`.** `defer sec.Zeroize()` reads just as well and `Close` would add a second wipe method (two ways to do one thing) plus an `io.Closer`-shaped affordance that invites treating a `Secret` like a stream. `Zeroize` is the single semantic operation. Producer demand declined here. |
| 4 | `New` return type — concrete `*Mediator` or the `Provider` interface? | return concrete `*Mediator` | `New` returns `Provider` | 🧩 **Concrete `*Mediator`.** "Return concrete" is the ground rule (10 §9); callers store it as `Provider`. The consumer's interface return is the only spot that violated return-concrete, so the producer's form is taken. |
| 5 | Typed convenience over `Use` (`UseString`/`UseValue`/`Use1`)? | not included (only `Use(fn) error`) | wants `UseString[V]`/`UseValue` for the one-derived-value case | 🧩 **Adopted as `Use1[V]`.** Leak-safe (V must be a *derived* value, never the secret) and grounded in the real auth-header/token call site. Named `Use1` (one value out) and shipped as a free function since methods can't be generic. The producer's "no accessor" demand is preserved — `Use1` is a closure, not an accessor. |
| 6 | Routing — a package `Mediator` keyed by scheme, or per-stage adapter selection at the root? | `Mediator` routes by scheme inside the package | composition root switches the adapter per stage; the `Provider` flows downstream | 🧩 **Both compose.** The `Mediator` is one concrete `Provider` that routes by scheme; the composition root still does the per-stage switch by deciding which adapters populate `Deps.Resolvers`. A single-adapter app can also bind that adapter directly as the `Provider` and skip the `Mediator`. No conflict once `Deps.Resolvers` is the seam. |
| 7 | Test minting hook — exported `NewForTest`, `//go:linkname`, or a shared internal package? | shared internal package, no linkname, never public | same demand; producer to pick the mechanism | 🧩 **Shared internal package.** `secrets` and `secretstest` both import an unexported `internal/...` minting hook; no `//go:linkname`, no exported `NewForTest`. `secretstest.MintSecret` is the only public, test-only surface that yields a `Secret`, and it yields a genuine un-printable one. Both sides already agreed in substance; mechanism fixed here. |
| 8 | Redaction sentinel value — `"***REDACTED***"` or `"secrets.Secret(REDACTED)"`? | `"secrets.Secret(REDACTED)"` (typed, greppable) | `"***REDACTED***"` | 🧩 **`"secrets.Secret(REDACTED)"`.** Names the type at the leak site, so a grep over logs/transcripts points at the offending field, and `%#v` stays self-describing. Exported as `secrets.Redacted` so tests/`AssertNotLeaked` reference the constant, not a literal. Minor; recorded so the consumer's literal is not silently dropped. |
| 9 | `observability.Valuer` conformance: should `Secret` carry `TelemetryValue() any` so it can ride `observability.Any(key, Valuer)` (the seam observability.md depends on)? | n/a | n/a | 🧩 **cross-contract reconciliation, post-draft.** Added `func (s *Secret) TelemetryValue() any` returning `Redacted`. It structurally satisfies `observability.Valuer` *without* `secrets` importing `observability` (Go interface satisfaction is implicit), so `secrets` stays a leaf library and the seam closes from this side. Resolves observability.md Q9. |
