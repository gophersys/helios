# Contract draft — errors

> Status: Draft for negotiation (WS1, not frozen) · 2026-06-12 · Reconciled from independent producer/consumer drafts (09 §4). Freezes at the contract-PR gate after review.

## 1. Scope

`errors` is the universal typed-error model: a stable, closed `Kind` taxonomy, `%w`-wrapping
discipline, `errors.AsType`-first inspection (Go 1.26), and redaction safety by construction. It is
a **leaf** library — it imports only the standard library and never imports `secrets`,
`observability`, `transport`, `connect`, or `genproto`, so every kernel and control-plane library
can depend on it without inheriting weight (10 §4, §12).

It explicitly does **not**: hold transport codes, map `Kind`→`connect.Code`/`google.rpc.Status`
(that table lives once at the transport boundary, 10 §9), capture stack traces, carry severity,
localize messages, or guarantee a careless caller cannot pass a secret into a message — it
guarantees the *type* never auto-captures one and ships an enforceable probe for the rest.

## 2. Contract

```go
// Package errors is the Eden universal error model: typed, wrappable, inspectable,
// redaction-safe, with a stable Kind. It is a leaf library — it imports only the
// standard library and never imports observability, secrets, or any transport
// package. Transport mapping (Kind -> Connect code / google.rpc.Status) lives at
// the transport boundary (10 §9), NOT here.
//
// Module: github.com/gophersys/libs/go/errors
//
// Concurrency: *Error is immutable after construction; no method mutates the
// receiver, so a shared *Error is safe across goroutines. Derivation verbs
// (WithCode/WithField) are copy-on-write and return a new *Error.
//
// Zero value: the zero Error is not constructed via the verbs and must not be
// used; callers always hold an *Error via the error interface and inspect with
// AsType/KindOf. KindUnknown (the zero Kind) means "unclassified", never silently
// "internal".
package errors

import (
	"context"
	stderrors "errors"
)

// Kind is the stable, closed classification axis. Its string tokens are part of
// the wire/telemetry contract and never change once shipped; new Kinds may only
// be APPENDED (new constant, never reordered or renamed). Kind is the single
// dimension the transport boundary switches on, so it maps 1:1 onto the AIP-193
// google.rpc.Code surface (10 §9). The zero value is KindUnknown so a forgotten
// classification is visibly unclassified, not masquerading as KindInternal.
type Kind uint8

const (
	KindUnknown         Kind = iota // unclassified; the edge maps it to INTERNAL/UNKNOWN
	KindInvalid                     // malformed/invalid argument        -> INVALID_ARGUMENT
	KindNotFound                    // named resource does not exist     -> NOT_FOUND
	KindConflict                    // state/version/uniqueness conflict -> ALREADY_EXISTS / ABORTED
	KindExhausted                   // quota/budget/rate ceiling hit     -> RESOURCE_EXHAUSTED
	KindUnavailable                 // transient; retry may succeed      -> UNAVAILABLE
	KindDeadline                    // deadline exceeded (ctx)           -> DEADLINE_EXCEEDED
	KindCanceled                    // operation canceled (ctx)          -> CANCELLED
	KindUnauthenticated             // caller identity not established   -> UNAUTHENTICATED
	KindPermission                  // caller not authorized             -> PERMISSION_DENIED
	KindInternal                    // invariant we own broken; our bug  -> INTERNAL
)

// String returns the stable lower-kebab token (e.g. "not-found"). Stable across
// versions; safe for telemetry labels and structured-log fields. Total: returns
// "unknown" for any out-of-range value.
func (k Kind) String() string

// Error is the concrete project error and the return type of every constructor
// (accept interfaces, return concrete — 10 §9). It is immutable after
// construction and carries a Kind, an optional fine-grained machine Code, an
// operator-safe message, a redaction-safe scalar field set, and an optional
// wrapped cause. It deliberately holds NO stack trace, NO secret values, and NO
// transport codes. Fields are unexported; callers must not construct Error{}
// literals or depend on field layout.
type Error struct {
	// unexported; constructed only via the verbs below.
}

// Error implements error. It renders the operator-safe message and, if a cause
// is present, ": <cause>". The message is never a secret value.
func (e *Error) Error() string

// Unwrap exposes the wrapped cause for errors.Is / errors.AsType / errors.Join.
func (e *Error) Unwrap() error

// Kind returns THIS node's classification (KindUnknown if unset). The top-level
// KindOf walks the chain; prefer it at inspection sites.
func (e *Error) Kind() Kind

// Code returns the optional fine-grained machine token ("" if unset), e.g.
// "workspace_quota_exceeded". It is finer than Kind and is NOT what the transport
// boundary switches on.
func (e *Error) Code() string

// Fields returns a defensive copy of the redaction-safe structured context
// (never the internal map).
func (e *Error) Fields() map[string]any

// --- Construction spine (verbs) ------------------------------------------
//
// The component spine New(configuration, dependencies) -> (Component, error) is
// N/A: errors is a leaf VALUE library, not a hexagonal component — it has no
// ports, clock, or I/O (10 §4). The PURITY half of the spine is honored: every
// verb below is pure (no I/O, no clock, no env reads).

// New mints a leaf *Error with a Kind and an operator-safe message. The message
// MUST NOT interpolate secret values (caller contract). Pure.
func New(kind Kind, message string) *Error

// Wrap annotates and classifies an existing error, preserving the chain under %w
// for AsType/Is/Join traversal. If cause is nil, Wrap returns nil — so happy-path
// returns read linearly. If the caller passes KindUnknown and the cause already
// carries an *Error Kind, the cause's Kind is INHERITED (no clobbering a
// meaningful classification with Unknown). Pure.
func Wrap(kind Kind, message string, cause error) *Error

// WithCode returns a derived *Error with the fine-grained machine token set
// (copy-on-write; the receiver is unchanged).
func (e *Error) WithCode(code string) *Error

// WithField returns a derived *Error with one redaction-safe structured field
// attached (copy-on-write). value MUST be a safe scalar (string/int/bool/Kind);
// a non-scalar value is stored as the marker "[unredactable]" rather than leaked
// — fail safe, never panic at a call site. WithField is the ONLY field path, so
// the safe-scalar invariant lives in one enforcement point.
func (e *Error) WithField(key string, value any) *Error

// FromContext maps a canceled/expired context to the right Kind
// (KindCanceled / KindDeadline) from ctx.Err(), else returns nil. Pure given
// ctx.Err().
func FromContext(ctx context.Context) *Error

// --- Inspection (AsType-first, Go 1.26) + re-exported verbs ---------------

// KindOf is the canonical, TOTAL classifier the rest of Eden calls (transport
// boundary, engine Gate, retry logic). It reports the Kind of the first *Error
// in err's chain, KindUnknown for foreign or nil errors. Never panics.
func KindOf(err error) Kind

// AsType is the inspection primitive — a thin generic re-export of the stdlib so
// every call site imports ONE errors package and never reaches for stdlib
// errors.As. Prefer this over Is for typed extraction.
func AsType[E error](err error) (E, bool) { return stderrors.AsType[E](err) }

// Is and Join are re-exported for sentinel comparison and aggregation (swarm /
// fan-out FileLease verification, 02 §2). Is reports whether the chain matches a
// target sentinel; for "does the chain carry Kind k", call KindOf(err) == k.
func Is(err, target error) bool { return stderrors.Is(err, target) }
func Join(errs ...error) error  { return stderrors.Join(errs...) }
```

## 3. Fake

```go
// Package errorstest provides deterministic builders, conformance assertions, and
// the redaction-safety probe for consumers writing table tests against the errors
// contract. There is no port to stub (errors is a pure value library), so the
// surface is builders + assertions over testing.TB.
package errorstest

import (
	"testing"

	"github.com/gophersys/libs/go/errors"
)

// Leaf mints a deterministic *errors.Error of the given Kind and message, so
// tests arrange inputs without importing the verb set at every call site.
func Leaf(kind errors.Kind, message string) *errors.Error

// Wrapping builds a two-level chain (outer Kind over inner) so tests can assert
// AsType/Unwrap traversal and Kind precedence/inheritance.
func Wrapping(outer errors.Kind, inner error) *errors.Error

// RequireKind fails the test unless errors.KindOf(err) == want, reporting the
// actual Kind and the rendered error.
func RequireKind(t testing.TB, err error, want errors.Kind)

// RequireNoSecret fails if err.Error() or any attached Field's rendered value
// contains any of the needles. It walks the whole Unwrap chain — the canonical
// redaction-safety conformance check every consumer runs over its error paths.
func RequireNoSecret(t testing.TB, err error, needles ...string)

// AssertUnwrapsTo asserts the cause is reachable via errors.AsType[E] and returns
// the extracted value for further assertions.
func AssertUnwrapsTo[E error](t testing.TB, err error) E
```

## 4. Conformance suite

The suite is exported from `errorstest` so any future adapter or alternative
construction path proves substitutability against the same properties.

```go
// RunConformance asserts the errors contract holds for the production verbs.
func RunConformance(t *testing.T)
```

Properties asserted:

- **Kind totality** — `KindOf(err)` returns a defined `Kind` for every `*Error`, `KindUnknown` for a foreign error and for `nil`; never panics.
- **Kind token stability** — `Kind.String()` returns the exact lower-kebab token for every enumerator and `"unknown"` out of range (the wire/telemetry contract).
- **Wrap nil-eliding** — `Wrap(k, msg, nil) == nil` for every `Kind`.
- **Wrap chain preservation** — `AsType`/`Is` reach an inner sentinel across a `Wrap` boundary; the cause is never flattened into a string.
- **Kind inheritance** — `Wrap(KindUnknown, msg, cause)` where `cause` carries an `*Error` Kind reports the cause's Kind via `KindOf`; an explicit Kind always overrides.
- **Immutability / copy-on-write** — `WithCode`/`WithField` leave the receiver unchanged and return a distinct `*Error`; `Fields()` returns a copy (mutating it does not affect the source).
- **Redaction safety** — a constructed/wrapped/field-annotated `*Error` never renders a needle passed only as a structured value; `WithField` of a non-scalar yields `"[unredactable]"`, not the value.
- **Context mapping** — `FromContext` yields `KindCanceled` / `KindDeadline` for a canceled / deadline-exceeded ctx and `nil` otherwise.
- **AsType re-export equivalence** — `errors.AsType[E]` agrees with `stderrors.AsType[E]` over the same chain.

## 5. Usage

```go
// --- In-library producer: classify at the failure site, keep secrets out -----
func (r *workspaceRepository) Get(ctx context.Context, id WorkspaceID) (*Workspace, error) {
	if err := errors.FromContext(ctx); err != nil {
		return nil, err // canceled / deadline -> correct Kind, no manual mapping
	}
	row, err := r.store.fetch(ctx, id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, errors.New(errors.KindNotFound, "workspace not found").
				WithCode("workspace_not_found").
				WithField("workspace_id", id.String()) // id is non-secret
		}
		return nil, errors.Wrap(errors.KindUnavailable, "workspace store read failed", err)
	}
	return row, nil
}

// --- Kernel testharness, anti-reward-hack (07 §4): budget != wrong code ------
func (h *Harness) Exercise(ctx context.Context, run RunRef) (Evidence, error) {
	out, err := h.provision(ctx, run)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "provision clean environment", err)
	}
	if out.TokensSpent > out.Budget {
		return nil, errors.New(errors.KindExhausted, "token budget exceeded during exercise").
			WithField("tokens_spent", out.TokensSpent).
			WithField("budget", out.Budget)
	}
	return out.Evidence, nil
}

// --- Another library inspecting, AsType-first: retry iff transient -----------
func (c *Coder) shouldRetry(err error) bool {
	if _, ok := errors.AsType[*backoff.Transient](err); ok {
		return true
	}
	switch errors.KindOf(err) {
	case errors.KindUnavailable, errors.KindDeadline:
		return true
	default: // KindExhausted, KindInvalid, KindInternal, ... -> do not retry
		return false
	}
}

// --- Transport boundary (10 §9): the ONLY place Kind -> wire code lives -------
// The table is OUTSIDE errors. It is exhaustive over Kind (a missing arm is a
// lint failure), so the boundary never silently defaults a classified error.
func toConnectError(err error) *connect.Error {
	switch errors.KindOf(err) {
	case errors.KindNotFound:
		return connect.NewError(connect.CodeNotFound, err)
	case errors.KindInvalid:
		return connect.NewError(connect.CodeInvalidArgument, err)
	case errors.KindExhausted:
		return connect.NewError(connect.CodeResourceExhausted, err)
	// ...one arm per Kind, lint-checked exhaustive...
	default:
		return connect.NewError(connect.CodeInternal, err) // KindUnknown / KindInternal
	}
}

// --- Composition root (10 §7.1): classify wiring failures --------------------
func run(ctx context.Context) error {
	stage, err := environment.Detect(os.Getenv)
	if err != nil {
		return errors.Wrap(errors.KindInvalid, "detect environment stage", err)
	}
	if _, err := environment.Resolve(stage, deps); err != nil {
		// secrets.Secret stringifies redacted, so this is safe even if resolution
		// touched a credential reference.
		return errors.Wrap(errors.KindUnavailable, "resolve environment wiring", err).
			WithField("stage", stage.String())
	}
	return nil
}
```

## 6. Design rationale

1. **`errors` is a leaf VALUE library, not a hexagonal component.** The `New(configuration,
   dependencies)` spine assumes a port-backed component; an error model has none (10 §4). We honor
   the *purity* half (verbs take no `Deps`, read no env, touch no clock) and document the component
   spine as N/A — a forced empty `Deps{}` here would be cargo-culting.
2. **Closed `uint8` `Kind`, `KindUnknown` as zero, append-only.** It is the single switch axis at the
   transport boundary, mapping 1:1 onto AIP-193 / `google.rpc.Code` (10 §9). A closed set lets the
   boundary mapper be exhaustive (lint-checkable). Zero = unclassified surfaces a forgotten
   classification visibly rather than as a silent `KindInternal`.
3. **Transport codes live OUTSIDE this library.** Embedding `connect.Code` or `google.rpc.Status`
   would make `errors` import a transport package and leak the wire concern into domain code,
   breaking the leaf guarantee for every consumer (10 §4, §12). The boundary owns the one
   lint-exhaustive `Kind`→code table (10 §9); the model owns only `Kind`. See Q1.
4. **AsType-first inspection (Go 1.26, ADR-0003).** `KindOf`/`AsType` wrap `stderrors.AsType[*Error]`
   so consumers get type-safe generic inspection and never import two `errors` packages. `KindOf` is
   the load-bearing, total classifier; the rest is sugar.
5. **`Wrap(kind, message, cause)` with nil-eliding and Kind inheritance.** Signature ordering puts the
   `cause` last to read as an annotation of the trailing call; `Wrap(_, _, nil) == nil` keeps thousands
   of kernel call sites flat; inheriting the cause's Kind on `KindUnknown` stops a wrap from clobbering
   a meaningful classification deep in a chain (engine walks many layers). See Q2.
6. **Immutable `*Error`; copy-on-write `WithCode`/`WithField`.** No method mutates the receiver, so a
   shared `*Error` is goroutine-safe and `Fields()` returns a defensive copy. `WithField` is the sole
   field path, so the safe-scalar invariant has one enforcement point and fails safe
   (`"[unredactable]"`) rather than panicking or leaking at a call site (10 §9). See Q3.
7. **Redaction is a *contract* + an enforceable probe, not a transport-layer import.** `errors` cannot
   import `secrets` (leaf rule), and `secrets.Secret` already redacts in any string context (10 §4).
   The model's job: carry only operator-facing messages and scalar fields, never reflect/`%+v`
   arbitrary structs, and ship `errorstest.RequireNoSecret` as the per-consumer conformance check
   (07 §2).
8. **No stack traces, no severity, no i18n, no `code int`.** Stacks belong to `observability` capture,
   severity to logging, the numeric wire code to transport, i18n to presentation. Speculative
   generality excluded.
9. **The concrete type carries 7 methods; the 5-method cap does not bind it.** `interfacebloat(max 5)`
   governs *interfaces* (10 §9). `*Error` is concrete (accept interfaces, return concrete); the only
   interface in the surface is `errorstest`'s use of `testing.TB`. No interface split needed.

## 7. Open questions

| # | question / conflict | producer position | consumer position | reconciler resolution 🧩 |
|---|---|---|---|---|
| Q1 | Should `errors` expose an abstract `StatusCode` codomain + `StatusCodeOf` so the mapping lives below transport? | No — the `Kind`→code table lives ONLY at the transport boundary (10 §9); `errors` imports stdlib only and must not own a transport-shaped surface. | Yes — an abstract `StatusCode` enum + total, lint-exhaustive `StatusCodeOf` in `errors`, depending on neither `connect` nor `genproto`. | 🧩 **Rejected the in-`errors` `StatusCode`.** It duplicates `Kind` (a parallel closed enum that must stay 1:1) and pulls a wire-shaped concern into the leaf, violating one-concept-one-home (README §4) and 10 §9's "the boundary owns the table." The consumer's *real* need — **totality + lint-exhaustiveness so an error never silently becomes Unknown at the wire** — is met by the boundary's `switch errors.KindOf(err)` being exhaustive over the closed `Kind` (lint-checked), demonstrated in §5. `errors` stays mapping-free. |
| Q2 | `Wrap` argument order and Kind-inheritance. | `Wrap(cause, kind, format, args...)` — printf-style, cause first. | `Wrap(kind, message, cause)` — cause last, message a constant-style string, inherit cause Kind on `KindUnknown`. | 🧩 **Took the consumer signature `Wrap(kind, message, cause)` + Kind inheritance.** Cause-last reads as annotating the trailing call and matches the dominant in-repo call shape; a constant-style `message` (no `args...`) keeps interpolation — the classic secret-leak vector — out of the wrapping path by default (callers needing interpolation pre-format a non-secret string). Kind inheritance is the consumer's load-bearing demand for deep chains. `New` likewise drops `format, args...` for the same redaction reason. |
| Q3 | Field model: typed `Field` free-function `With(err, ...Field)` vs `*Error.WithField(k, v)` method. | `WithField(key, value any)` copy-on-write method; `map[string]any`. | `With(err *Error, ...Field)` free function; explicit `Field{Key,Value}` struct; non-scalar → `"[unredactable]"`. | 🧩 **Took the producer's `WithField` method shape, with the consumer's fail-safe semantics.** A copy-on-write method chains fluently with `New(...).WithCode(...).WithField(...)` (the call sites in §5) and avoids exporting a `Field` struct that becomes a second public type to version. The consumer's non-negotiable — single field path + safe-scalar enforcement + fail-safe `"[unredactable]"` marker, never panic/leak — is adopted verbatim into `WithField`'s contract. The `Field` struct demand is rejected (subsumed). |
| Q4 | Fine-grained `Code` / `WithCode` — keep or drop? | Keep — optional stable machine token for call sites branching below `Kind` (e.g. `workspace_quota_exceeded`). | Omitted from the consumer surface. | 🧩 **Kept `WithCode`/`Code`.** It is additive, costs the consumer nothing (optional, `""` default), and serves a real producer need to distinguish causes that share a `Kind` without inflating the closed, wire-mapped taxonomy. It is explicitly NOT what the transport boundary switches on (Q1). |
| Q5 | `FromContext` (ctx → Kind) — include? | Yes — maps canceled/deadline ctx to the right Kind, returns nil otherwise; flattens repetitive ctx-error handling. | Not in the consumer draft. | 🧩 **Kept `FromContext`.** Pure (depends only on `ctx.Err()`), eliminates hand-rolled `Canceled`/`Deadline` mapping at every blocking call site, and `context.Context` as first parameter satisfies the ground rule. Returns `nil` when ctx is live, preserving flat call sites. |
| Q6 | `Join` re-export — include? | Not in the producer draft. | Yes — load-bearing for swarm / fan-out (FileLease) aggregation (02 §2). | 🧩 **Kept the consumer's `Join` re-export.** It is the live Go 1.26 idiom, costs nothing, and keeps swarm aggregation on the single `errors` import seam. `AsType`/`Is`/`Join` are all re-exported so consumers never reach for stdlib `errors`. |
| Q7 | Kind enumerator set — producer's 11 vs consumer's 10. | Includes both `KindUnauthenticated` and `KindPermission` (authn vs authz split). | Single `KindUnauthorized` (identity/authn-authz folded). | 🧩 **Took the producer's split (`KindUnauthenticated` + `KindPermission`).** AIP-193 / `google.rpc.Code` distinguishes `UNAUTHENTICATED` from `PERMISSION_DENIED`; folding them would force the transport boundary to *lose* information it must carry (10 §9), and `identity` (10 §5) deliberately separates authN from authZ. The taxonomy is append-only, so this is the safe-to-freeze superset. |
