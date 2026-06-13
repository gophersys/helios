package errorstest

import (
	"context"
	stderrors "errors"
	"reflect"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// allKinds enumerates every shipped Kind in declaration order. Append-only: a new
// Kind constant must be added here too, which is the intended forcing function.
var allKinds = []struct {
	kind  errors.Kind
	token string
}{
	{errors.KindUnknown, "unknown"},
	{errors.KindInvalid, "invalid"},
	{errors.KindNotFound, "not-found"},
	{errors.KindConflict, "conflict"},
	{errors.KindExhausted, "exhausted"},
	{errors.KindUnavailable, "unavailable"},
	{errors.KindDeadline, "deadline"},
	{errors.KindCanceled, "canceled"},
	{errors.KindUnauthenticated, "unauthenticated"},
	{errors.KindPermission, "permission"},
	{errors.KindInternal, "internal"},
}

// Declared sentinel fixtures for the conformance suite. conformance.go is
// production code in the fakes package (it exports RunConformance), so it is held
// to the production error bar: a comparable fixture error is a named, declared
// sentinel, never minted inline at the assertion site (the error-handling rule).
var (
	errForeign  = stderrors.New("conformance: foreign error")
	errSentinel = stderrors.New("conformance: wrapped sentinel cause")
)

// RunConformance asserts the errors contract holds for the production verbs.
func RunConformance(t *testing.T) {
	t.Helper()
	t.Run("KindTotality", conformanceKindTotality)
	t.Run("KindTokenStability", conformanceKindTokenStability)
	t.Run("WrapNilEliding", conformanceWrapNilEliding)
	t.Run("WrapChainPreservation", conformanceWrapChainPreservation)
	t.Run("KindInheritance", conformanceKindInheritance)
	t.Run("ImmutabilityCopyOnWrite", conformanceImmutability)
	t.Run("RedactionSafety", conformanceRedactionSafety)
	t.Run("ContextMapping", conformanceContextMapping)
	t.Run("AsTypeReExportEquivalence", conformanceAsTypeEquivalence)
	t.Run("TypedNilHazard", conformanceTypedNilHazard)
	t.Run("NilReceiverSafety", conformanceNilReceiverSafety)
}

// Kind totality — KindOf returns a defined Kind for every *Error, KindUnknown for
// a foreign error and for nil; never panics.
func conformanceKindTotality(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("KindOf panicked: %v", r)
		}
	}()
	for _, kc := range allKinds {
		err := errors.New(kc.kind, "msg")
		if got := errors.KindOf(err); got != kc.kind {
			t.Errorf("KindOf(New(%v)) = %v, want %v", kc.kind, got, kc.kind)
		}
	}
	if got := errors.KindOf(nil); got != errors.KindUnknown {
		t.Errorf("KindOf(nil) = %v, want KindUnknown", got)
	}
	if got := errors.KindOf(errForeign); got != errors.KindUnknown {
		t.Errorf("KindOf(foreign) = %v, want KindUnknown", got)
	}
}

// Kind token stability — Kind.String() returns the exact lower-kebab token for
// every enumerator and "unknown" out of range.
func conformanceKindTokenStability(t *testing.T) {
	for _, kc := range allKinds {
		if got := kc.kind.String(); got != kc.token {
			t.Errorf("Kind(%d).String() = %q, want %q", kc.kind, got, kc.token)
		}
	}
	for _, v := range []errors.Kind{200, 255} {
		if got := v.String(); got != "unknown" {
			t.Errorf("out-of-range Kind(%d).String() = %q, want %q", v, got, "unknown")
		}
	}
}

// Wrap nil-eliding — Wrap(k, msg, nil) == nil for every Kind.
func conformanceWrapNilEliding(t *testing.T) {
	for _, kc := range allKinds {
		if got := errors.Wrap(kc.kind, "msg", nil); got != nil {
			t.Errorf("Wrap(%v, _, nil) = %v, want nil", kc.kind, got)
		}
	}
}

// Wrap chain preservation — AsType/Is reach an inner sentinel across a Wrap
// boundary; the cause is never flattened into a string.
func conformanceWrapChainPreservation(t *testing.T) {
	chain := errors.Wrap(errors.KindInternal, "outer", errSentinel)
	if !errors.Is(chain, errSentinel) {
		t.Error("Is(chain, sentinel) = false; cause was flattened")
	}
	if got := chain.Unwrap(); !errors.Is(got, errSentinel) {
		t.Errorf("Unwrap() = %v, want sentinel", got)
	}
	// A typed inner *Error must be extractable.
	innerTyped := errors.New(errors.KindNotFound, "inner")
	chain2 := errors.Wrap(errors.KindInternal, "outer", innerTyped)
	if got, ok := errors.AsType[*errors.Error](chain2); !ok || got == nil {
		t.Error("AsType[*Error] failed to reach a typed cause across Wrap")
	}
}

// Kind inheritance — Wrap(KindUnknown, msg, cause) inherits the cause's *Error
// Kind; an explicit Kind always overrides.
func conformanceKindInheritance(t *testing.T) {
	cause := errors.New(errors.KindNotFound, "inner")
	inherited := errors.Wrap(errors.KindUnknown, "outer", cause)
	if got := errors.KindOf(inherited); got != errors.KindNotFound {
		t.Errorf("inherited KindOf = %v, want KindNotFound", got)
	}
	overridden := errors.Wrap(errors.KindInternal, "outer", cause)
	if got := errors.KindOf(overridden); got != errors.KindInternal {
		t.Errorf("explicit KindOf = %v, want KindInternal", got)
	}
	// Foreign cause: nothing to inherit, stays Unknown.
	foreign := errors.Wrap(errors.KindUnknown, "outer", errForeign)
	if got := errors.KindOf(foreign); got != errors.KindUnknown {
		t.Errorf("foreign-cause KindOf = %v, want KindUnknown", got)
	}
}

// Immutability / copy-on-write — WithCode/WithField leave the receiver unchanged
// and return a distinct *Error; Fields() returns a copy.
func conformanceImmutability(t *testing.T) {
	base := errors.New(errors.KindInvalid, "base")
	dCode := base.WithCode("c")
	dField := base.WithField("k", "v")
	if base.Code() != "" {
		t.Errorf("WithCode mutated receiver: Code() = %q", base.Code())
	}
	if len(base.Fields()) != 0 {
		t.Errorf("WithField mutated receiver: Fields() = %v", base.Fields())
	}
	if dCode == base || dField == base {
		t.Error("derivation returned the same pointer; want a distinct copy")
	}
	// Fields() defensive copy.
	withField := errors.New(errors.KindInvalid, "x").WithField("k", "v")
	f := withField.Fields()
	f["k"] = "MUTATED"
	if withField.Fields()["k"] != "v" {
		t.Error("Fields() did not return a defensive copy")
	}
}

// Redaction safety — a constructed/wrapped/field-annotated *Error never renders a
// needle passed only as a structured value; WithField of a non-scalar yields
// "[unredactable]", not the value.
func conformanceRedactionSafety(t *testing.T) {
	const secret = "s3cr3t-value"
	type creds struct{ Password string }

	// The secret is carried ONLY as a non-scalar structured value, so the type's
	// redaction guarantee must collapse it to the marker, never render it.
	e := errors.New(errors.KindInternal, "operation failed").
		WithField("creds", creds{Password: secret})
	RequireNoSecret(t, e, secret)

	wrapped := errors.Wrap(errors.KindUnavailable, "downstream failed", e)
	RequireNoSecret(t, wrapped, secret)

	red := errors.New(errors.KindInternal, "x").
		WithField("creds", creds{Password: secret})
	if got := red.Fields()["creds"]; got != "[unredactable]" {
		t.Errorf("non-scalar field = %#v, want \"[unredactable]\"", got)
	}
	RequireNoSecret(t, red, secret)
}

// Context mapping — FromContext yields KindCanceled / KindDeadline for a
// canceled / deadline-exceeded ctx and nil otherwise.
func conformanceContextMapping(t *testing.T) {
	if e := errors.FromContext(context.Background()); e != nil {
		t.Errorf("FromContext(live) = %v, want nil", e)
	}

	cctx, cancel := context.WithCancel(context.Background())
	cancel()
	if got := errors.FromContext(cctx); got == nil || got.Kind() != errors.KindCanceled {
		t.Errorf("FromContext(canceled).Kind() = %v, want KindCanceled", kindOrNil(got))
	}

	dctx, dcancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Hour))
	defer dcancel()
	<-dctx.Done()
	if got := errors.FromContext(dctx); got == nil || got.Kind() != errors.KindDeadline {
		t.Errorf("FromContext(deadline).Kind() = %v, want KindDeadline", kindOrNil(got))
	}
}

// AsType re-export equivalence — errors.AsType[E] agrees with stderrors.AsType[E]
// over the same chain.
func conformanceAsTypeEquivalence(t *testing.T) {
	leaf := errors.New(errors.KindNotFound, "leaf")
	chain := errors.Wrap(errors.KindInternal, "outer", leaf)

	a, aok := errors.AsType[*errors.Error](chain)
	b, bok := stderrors.AsType[*errors.Error](chain)
	if aok != bok || a != b {
		t.Errorf("AsType disagreement: re-export=(%p,%v) stdlib=(%p,%v)", a, aok, b, bok)
	}
}

// Typed-nil hazard â Wrap/FromContext return the concrete *Error and elide to a
// TYPED nil; boxed into an error it is NOT interface-nil, yet KindOf still
// classifies it KindUnknown and never panics. Asserted via reflection so the
// check is dynamic (a true interface-nil yields an invalid reflect.Value; a typed
// nil yields a valid Value whose underlying pointer IsNil).
func conformanceTypedNilHazard(t *testing.T) {
	thruIface := wrapEliding(nil)
	rv := reflect.ValueOf(thruIface)
	if !rv.IsValid() {
		t.Fatal("Wrap(_, _, nil) boxed into error is interface-nil; the *Error " +
			"return type changed - amend the contract and this conformance case")
	}
	if rv.Kind() != reflect.Pointer || !rv.IsNil() {
		t.Fatalf("boxed typed nil: kind=%v, want a nil *Error pointer", rv.Kind())
	}
	if got := errors.KindOf(thruIface); got != errors.KindUnknown {
		t.Errorf("KindOf(typed-nil) = %v, want KindUnknown", got)
	}
}

// Nil-receiver safety â no accessor or derivation verb panics on a nil *Error: a
// leaked typed nil renders "<nil>", unwraps to nil, and reports KindUnknown / "" /
// empty fields, while WithCode/WithField yield a fresh leaf.
func conformanceNilReceiverSafety(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("nil *Error method panicked: %v", r)
		}
	}()
	var n *errors.Error
	if got := n.Error(); got != "<nil>" {
		t.Errorf("nil.Error() = %q, want %q", got, "<nil>")
	}
	if got := n.Unwrap(); got != nil {
		t.Errorf("nil.Unwrap() = %v, want nil", got)
	}
	if got := n.Kind(); got != errors.KindUnknown {
		t.Errorf("nil.Kind() = %v, want KindUnknown", got)
	}
	if got := n.Code(); got != "" {
		t.Errorf("nil.Code() = %q, want empty", got)
	}
	if got := n.Fields(); got == nil || len(got) != 0 {
		t.Errorf("nil.Fields() = %v, want non-nil empty map", got)
	}
	if d := n.WithCode("c"); d == nil || d.Code() != "c" {
		t.Errorf("nil.WithCode(c) = %v, want a fresh *Error with code c", d)
	}
	if d := n.WithField("k", "v"); d == nil || d.Fields()["k"] != "v" {
		t.Errorf("nil.WithField(k,v) = %v, want a fresh *Error carrying k=v", d)
	}
}

// wrapEliding reproduces the typed-nil footgun: it returns errors.Wrap's concrete
// *Error through an error signature, so a nil cause yields a boxed (typed) nil
// that is NOT interface-nil.
func wrapEliding(cause error) error {
	return errors.Wrap(errors.KindUnavailable, "eliding wrap", cause)
}

func kindOrNil(e *errors.Error) any {
	if e == nil {
		return "<nil>"
	}
	return e.Kind()
}
