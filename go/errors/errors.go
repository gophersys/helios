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

// The Kind enumerators. Append-only and never reordered or renamed once shipped:
// the numeric order and the String() tokens are both part of the wire/telemetry
// contract (see Kind and kindTokens).
const (
	KindUnknown     Kind = iota // unclassified; the edge maps it to INTERNAL/UNKNOWN
	KindInvalid                 // malformed/invalid argument        -> INVALID_ARGUMENT
	KindNotFound                // named resource does not exist     -> NOT_FOUND
	KindConflict                // state/version/uniqueness conflict -> ALREADY_EXISTS / ABORTED
	KindExhausted               // quota/budget/rate ceiling hit     -> RESOURCE_EXHAUSTED
	KindUnavailable             // transient; retry may succeed      -> UNAVAILABLE
	KindDeadline                // deadline exceeded (ctx)           -> DEADLINE_EXCEEDED
	//nolint:misspell // "CANCELLED" (double-L) is the canonical google.rpc.Code enumerator the contract freezes (errors.md Â§2); the US-locale misspell linter wrongly flags the British spelling. The Go identifier and String() token stay "Canceled"/"canceled".
	KindCanceled        // operation canceled (ctx)          -> CANCELLED
	KindUnauthenticated // caller identity not established   -> UNAUTHENTICATED
	KindPermission      // caller not authorized             -> PERMISSION_DENIED
	KindInternal        // invariant we own broken; our bug  -> INTERNAL
)

// kindTokens holds the stable lower-kebab token for each Kind, indexed by the
// Kind's numeric value. The order is the wire/telemetry contract: append-only,
// never reordered or renamed.
var kindTokens = [...]string{
	KindUnknown:         "unknown",
	KindInvalid:         "invalid",
	KindNotFound:        "not-found",
	KindConflict:        "conflict",
	KindExhausted:       "exhausted",
	KindUnavailable:     "unavailable",
	KindDeadline:        "deadline",
	KindCanceled:        "canceled",
	KindUnauthenticated: "unauthenticated",
	KindPermission:      "permission",
	KindInternal:        "internal",
}

// String returns the stable lower-kebab token (e.g. "not-found"). Stable across
// versions; safe for telemetry labels and structured-log fields. Total: returns
// "unknown" for any out-of-range value.
func (k Kind) String() string {
	if int(k) < len(kindTokens) {
		return kindTokens[k]
	}
	return "unknown"
}

// Error is the concrete project error and the return type of every constructor
// (accept interfaces, return concrete — 10 §9). It is immutable after
// construction and carries a Kind, an optional fine-grained machine Code, an
// operator-safe message, a redaction-safe scalar field set, and an optional
// wrapped cause. It deliberately holds NO stack trace, NO secret values, and NO
// transport codes. Fields are unexported; callers must not construct Error{}
// literals or depend on field layout.
type Error struct {
	kind    Kind
	code    string
	message string
	fields  map[string]any
	cause   error
}

// Error implements error. It renders the operator-safe message and, if a cause
// is present, ": <cause>". The message is never a secret value.
//
// Nil-safe: a nil *Error renders "<nil>" instead of panicking. Wrap/FromContext
// return the concrete *Error and elide to a (typed) nil, so a caller that boxes
// that nil into an error interface (the typed-nil footgun documented on Wrap)
// must not crash if it nonetheless reaches a render site. All accessors below are
// nil-safe for the same reason.
func (e *Error) Error() string {
	if e == nil {
		return "<nil>"
	}
	if e.cause == nil {
		return e.message
	}
	if e.message == "" {
		return e.cause.Error()
	}
	return e.message + ": " + e.cause.Error()
}

// Unwrap exposes the wrapped cause for errors.Is / errors.AsType / errors.Join.
// Nil-safe: a nil *Error unwraps to nil.
func (e *Error) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.cause
}

// Kind returns THIS node's classification (KindUnknown if unset). The top-level
// KindOf walks the chain; prefer it at inspection sites. Nil-safe: a nil *Error
// reports KindUnknown.
func (e *Error) Kind() Kind {
	if e == nil {
		return KindUnknown
	}
	return e.kind
}

// Code returns the optional fine-grained machine token ("" if unset), e.g.
// "workspace_quota_exceeded". It is finer than Kind and is NOT what the transport
// boundary switches on. Nil-safe: a nil *Error reports "".
func (e *Error) Code() string {
	if e == nil {
		return ""
	}
	return e.code
}

// Fields returns a defensive copy of the redaction-safe structured context
// (never the internal map). Nil-safe: a nil *Error reports an empty (non-nil) map.
func (e *Error) Fields() map[string]any {
	if e == nil {
		return map[string]any{}
	}
	out := make(map[string]any, len(e.fields))
	for k, v := range e.fields {
		out[k] = v
	}
	return out
}

// --- Construction spine (verbs) ------------------------------------------
//
// The component spine New(configuration, dependencies) -> (Component, error) is
// N/A: errors is a leaf VALUE library, not a hexagonal component — it has no
// ports, clock, or I/O (10 §4). The PURITY half of the spine is honored: every
// verb below is pure (no I/O, no clock, no env reads).

// New mints a leaf *Error with a Kind and an operator-safe message. The message
// MUST NOT interpolate secret values (caller contract). Pure.
func New(kind Kind, message string) *Error {
	return &Error{kind: kind, message: message}
}

// Wrap annotates and classifies an existing error, preserving the chain under %w
// for AsType/Is/Join traversal. If cause is nil, Wrap returns nil — so happy-path
// returns read linearly. If the caller passes KindUnknown and the cause already
// carries an *Error Kind, the cause's Kind is INHERITED (no clobbering a
// meaningful classification with Unknown). Pure.
//
// TYPED-NIL FOOTGUN: Wrap returns the concrete *Error (accept interfaces, return
// concrete â 10 Â§9), so its nil for a nil cause is a TYPED nil. Do NOT write
//
//	func f() error { return errors.Wrap(k, m, maybeNilCause) } // WRONG on success
//
// because a (*Error)(nil) boxed into the error interface is NOT interface-nil, so
// the caller's "if err != nil" fires on success. Guard the cause first:
//
//	if cause != nil { return errors.Wrap(k, m, cause) }
//	return nil
//
// KindOf and every accessor are nil-receiver-safe (a leaked typed nil never
// panics), but the interface-comparison hazard is intrinsic to the concrete
// return type the frozen contract mandates.
func Wrap(kind Kind, message string, cause error) *Error {
	if cause == nil {
		return nil
	}
	if kind == KindUnknown {
		if inherited := KindOf(cause); inherited != KindUnknown {
			kind = inherited
		}
	}
	return &Error{kind: kind, message: message, cause: cause}
}

// WithCode returns a derived *Error with the fine-grained machine token set
// (copy-on-write; the receiver is unchanged).
func (e *Error) WithCode(code string) *Error {
	clone := e.clone()
	clone.code = code
	return clone
}

// WithField returns a derived *Error with one redaction-safe structured field
// attached (copy-on-write). value MUST be a safe scalar (string/int/bool/Kind);
// a non-scalar value is stored as the marker "[unredactable]" rather than leaked
// — fail safe, never panic at a call site. WithField is the ONLY field path, so
// the safe-scalar invariant lives in one enforcement point.
func (e *Error) WithField(key string, value any) *Error {
	clone := e.clone()
	if clone.fields == nil {
		clone.fields = make(map[string]any, 1)
	} else {
		copied := make(map[string]any, len(clone.fields)+1)
		for k, v := range clone.fields {
			copied[k] = v
		}
		clone.fields = copied
	}
	clone.fields[key] = safeScalar(value)
	return clone
}

// safeScalar enforces the redaction-safe invariant: only the named safe scalars
// (string/int/bool/Kind) pass through; anything else collapses to the marker
// "[unredactable]" so a non-scalar value can never be leaked through a field.
func safeScalar(value any) any {
	switch value.(type) {
	case string, bool, Kind,
		int, int8, int16, int32, int64,
		uint, uint8, uint16, uint32, uint64:
		return value
	default:
		return "[unredactable]"
	}
}

// FromContext maps a canceled/expired context to the right Kind
// (KindCanceled / KindDeadline) from ctx.Err(), else returns nil. Pure given
// ctx.Err().
//
// TYPED-NIL FOOTGUN: like Wrap, FromContext returns the concrete *Error, so its
// nil for a live ctx is a TYPED nil. Do NOT return it directly through an error
// signature on a live ctx â the boxed (*Error)(nil) is not interface-nil and the
// caller's "if err != nil" fires. Use the guarded idiom (see Â§5 usage):
//
//	if err := errors.FromContext(ctx); err != nil { return err }
func FromContext(ctx context.Context) *Error {
	switch err := ctx.Err(); {
	case err == nil:
		return nil
	case stderrors.Is(err, context.Canceled):
		return Wrap(KindCanceled, "context canceled", err)
	case stderrors.Is(err, context.DeadlineExceeded):
		return Wrap(KindDeadline, "context deadline exceeded", err)
	default:
		return Wrap(KindUnknown, "context error", err)
	}
}

// clone returns a shallow copy of the receiver. The fields map is shared by
// reference until a mutating verb copies it (copy-on-write), so derivations that
// do not touch fields stay allocation-light while never mutating the source.
// Nil-safe: deriving from a nil *Error yields a fresh zero-value *Error (a
// KindUnknown leaf) rather than dereferencing nil, so WithCode/WithField on a
// leaked typed nil never panic.
func (e *Error) clone() *Error {
	if e == nil {
		return &Error{}
	}
	c := *e
	return &c
}

// Inspection (AsType-first, Go 1.26) and re-exported verbs follow.

// KindOf is the canonical, TOTAL classifier the rest of Eden calls (transport
// boundary, engine Gate, retry logic). It reports the Kind of the first *Error
// in err's chain, KindUnknown for foreign or nil errors. Never panics.
func KindOf(err error) Kind {
	if err == nil {
		return KindUnknown
	}
	if e, ok := stderrors.AsType[*Error](err); ok && e != nil {
		return e.kind
	}
	return KindUnknown
}

// AsType is the inspection primitive — a thin generic re-export of the stdlib so
// every call site imports ONE errors package and never reaches for stdlib
// errors.As. Prefer this over Is for typed extraction.
func AsType[E error](err error) (E, bool) { return stderrors.AsType[E](err) }

// Is is re-exported for sentinel comparison so consumers never reach for stdlib
// errors. It reports whether the chain matches a target sentinel; for "does the
// chain carry Kind k", call KindOf(err) == k.
func Is(err, target error) bool { return stderrors.Is(err, target) }

// Join is re-exported for error aggregation (swarm / fan-out FileLease
// verification, 02 §2), keeping aggregation on the single errors import seam.
// Contract §2 (Q6) freezes Join as a thin re-export of stderrors.Join; wrapping
// its result would change the published surface and defeat the re-export.
//
//nolint:wrapcheck // see above: the frozen contract requires a thin re-export.
func Join(errs ...error) error { return stderrors.Join(errs...) }
