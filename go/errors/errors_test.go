package errors_test

import (
	"context"
	stderrors "errors"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// --- Kind.String token stability (the wire/telemetry contract) ---------------

func TestKindStringTokens(t *testing.T) {
	cases := []struct {
		kind errors.Kind
		want string
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
	for _, tc := range cases {
		if got := tc.kind.String(); got != tc.want {
			t.Errorf("Kind(%d).String() = %q, want %q", tc.kind, got, tc.want)
		}
	}
}

func TestKindStringOutOfRange(t *testing.T) {
	// Total: any out-of-range value renders "unknown".
	for _, v := range []errors.Kind{11, 12, 100, 255} {
		if got := v.String(); got != "unknown" {
			t.Errorf("out-of-range Kind(%d).String() = %q, want %q", v, got, "unknown")
		}
	}
}

func TestKindZeroValueIsUnknown(t *testing.T) {
	var z errors.Kind
	if z != errors.KindUnknown {
		t.Fatalf("zero Kind = %d, want KindUnknown (%d)", z, errors.KindUnknown)
	}
	if z.String() != "unknown" {
		t.Fatalf("zero Kind string = %q, want %q", z.String(), "unknown")
	}
}

// --- New ---------------------------------------------------------------------

func TestNew(t *testing.T) {
	e := errors.New(errors.KindNotFound, "workspace not found")
	if e == nil {
		t.Fatal("New returned nil")
	}
	if e.Kind() != errors.KindNotFound {
		t.Errorf("Kind() = %v, want KindNotFound", e.Kind())
	}
	if e.Error() != "workspace not found" {
		t.Errorf("Error() = %q, want %q", e.Error(), "workspace not found")
	}
	if e.Code() != "" {
		t.Errorf("Code() = %q, want empty", e.Code())
	}
	if e.Unwrap() != nil {
		t.Errorf("Unwrap() = %v, want nil", e.Unwrap())
	}
	if len(e.Fields()) != 0 {
		t.Errorf("Fields() = %v, want empty", e.Fields())
	}
}

// --- Wrap --------------------------------------------------------------------

func TestWrapNilEliding(t *testing.T) {
	for k := errors.KindUnknown; k <= errors.KindInternal; k++ {
		if got := errors.Wrap(k, "annotate", nil); got != nil {
			t.Errorf("Wrap(%v, _, nil) = %v, want nil", k, got)
		}
	}
}

func TestWrapMessageRendersCause(t *testing.T) {
	cause := stderrors.New("disk gone")
	e := errors.Wrap(errors.KindUnavailable, "store read failed", cause)
	want := "store read failed: disk gone"
	if e.Error() != want {
		t.Errorf("Error() = %q, want %q", e.Error(), want)
	}
}

func TestWrapEmptyMessageRendersOnlyCause(t *testing.T) {
	cause := stderrors.New("disk gone")
	e := errors.Wrap(errors.KindUnavailable, "", cause)
	if e.Error() != "disk gone" {
		t.Errorf("Error() = %q, want %q (no leading colon)", e.Error(), "disk gone")
	}
}

func TestWrapPreservesChain(t *testing.T) {
	sentinel := stderrors.New("sentinel cause")
	e := errors.Wrap(errors.KindInternal, "outer", sentinel)
	if !errors.Is(e, sentinel) {
		t.Errorf("Is(wrapped, sentinel) = false, want true (chain not preserved)")
	}
	if e.Unwrap() != sentinel {
		t.Errorf("Unwrap() = %v, want sentinel", e.Unwrap())
	}
}

func TestWrapKindInheritance(t *testing.T) {
	// cause carries a meaningful *Error Kind; Wrap with KindUnknown inherits it.
	cause := errors.New(errors.KindNotFound, "inner not found")
	e := errors.Wrap(errors.KindUnknown, "outer annotation", cause)
	if got := errors.KindOf(e); got != errors.KindNotFound {
		t.Errorf("KindOf(Wrap(Unknown, _, NotFound-cause)) = %v, want KindNotFound (inheritance)", got)
	}
	// This node's own Kind should reflect the inherited classification too.
	if e.Kind() != errors.KindNotFound {
		t.Errorf("e.Kind() = %v, want KindNotFound (inherited)", e.Kind())
	}
}

func TestWrapExplicitKindOverrides(t *testing.T) {
	cause := errors.New(errors.KindNotFound, "inner not found")
	e := errors.Wrap(errors.KindInternal, "outer", cause)
	if got := errors.KindOf(e); got != errors.KindInternal {
		t.Errorf("KindOf = %v, want KindInternal (explicit overrides)", got)
	}
}

func TestWrapKindInheritanceNonErrorCause(t *testing.T) {
	// A foreign cause carries no *Error Kind: KindUnknown stays Unknown.
	cause := stderrors.New("foreign")
	e := errors.Wrap(errors.KindUnknown, "outer", cause)
	if got := errors.KindOf(e); got != errors.KindUnknown {
		t.Errorf("KindOf = %v, want KindUnknown (nothing to inherit)", got)
	}
}

// --- WithCode ----------------------------------------------------------------

func TestWithCode(t *testing.T) {
	base := errors.New(errors.KindExhausted, "budget exceeded")
	derived := base.WithCode("workspace_quota_exceeded")
	if derived.Code() != "workspace_quota_exceeded" {
		t.Errorf("Code() = %q, want %q", derived.Code(), "workspace_quota_exceeded")
	}
	// copy-on-write: receiver unchanged, distinct pointer.
	if base.Code() != "" {
		t.Errorf("receiver Code() = %q, want empty (mutated!)", base.Code())
	}
	if derived == base {
		t.Errorf("WithCode returned the same pointer; want a distinct copy")
	}
}

// --- WithField ---------------------------------------------------------------

func TestWithFieldScalar(t *testing.T) {
	base := errors.New(errors.KindInvalid, "bad input")
	derived := base.
		WithField("workspace_id", "ws-123").
		WithField("attempt", 3).
		WithField("forced", true).
		WithField("kind_field", errors.KindInvalid)

	f := derived.Fields()
	if f["workspace_id"] != "ws-123" {
		t.Errorf("field workspace_id = %v, want ws-123", f["workspace_id"])
	}
	if f["attempt"] != 3 {
		t.Errorf("field attempt = %v, want 3", f["attempt"])
	}
	if f["forced"] != true {
		t.Errorf("field forced = %v, want true", f["forced"])
	}
	if f["kind_field"] != errors.KindInvalid {
		t.Errorf("field kind_field = %v, want KindInvalid", f["kind_field"])
	}
}

func TestWithFieldCopyOnWrite(t *testing.T) {
	base := errors.New(errors.KindInvalid, "bad input")
	derived := base.WithField("k", "v")
	if len(base.Fields()) != 0 {
		t.Errorf("receiver Fields() = %v, want empty (mutated!)", base.Fields())
	}
	if derived == base {
		t.Errorf("WithField returned the same pointer; want a distinct copy")
	}
	// Adding a second field must not mutate the first derived value.
	derived2 := derived.WithField("k2", "v2")
	if _, ok := derived.Fields()["k2"]; ok {
		t.Errorf("first derived was mutated by second WithField")
	}
	if len(derived2.Fields()) != 2 {
		t.Errorf("derived2 Fields len = %d, want 2", len(derived2.Fields()))
	}
}

func TestWithFieldNonScalarIsRedacted(t *testing.T) {
	type secretStruct struct{ Password string }
	base := errors.New(errors.KindInternal, "boom")

	// Each is a non-safe-scalar and must collapse to the marker, never panic.
	cases := map[string]any{
		"struct_field": secretStruct{Password: "hunter2"},
		"slice_field":  []string{"a", "b"},
		"map_field":    map[string]string{"x": "y"},
		"ptr_field":    &secretStruct{Password: "hunter2"},
		"func_field":   func() {},
		"float_field":  3.14, // float is not in the named safe-scalar set (string/int/bool/Kind)
	}
	for key, val := range cases {
		e := base.WithField(key, val)
		got := e.Fields()[key]
		if got != "[unredactable]" {
			t.Errorf("WithField(%q, non-scalar) stored %#v, want %q", key, got, "[unredactable]")
		}
	}
}

func TestFieldsReturnsDefensiveCopy(t *testing.T) {
	e := errors.New(errors.KindInvalid, "x").WithField("k", "v")
	f := e.Fields()
	f["k"] = "MUTATED"
	f["new"] = "injected"
	again := e.Fields()
	if again["k"] != "v" {
		t.Errorf("mutating Fields() result leaked into source: k = %v", again["k"])
	}
	if _, ok := again["new"]; ok {
		t.Errorf("mutating Fields() result added a key to the source map")
	}
}

func TestFieldsNeverNilForUsability(t *testing.T) {
	// A defensive copy of an empty/absent field set must be safe to range over.
	e := errors.New(errors.KindInvalid, "x")
	f := e.Fields()
	if f == nil {
		t.Fatal("Fields() returned nil; want a non-nil empty map")
	}
}

// --- Immutability across the whole verb chain --------------------------------

func TestImmutabilityOfReceiverAcrossVerbs(t *testing.T) {
	base := errors.New(errors.KindNotFound, "base")
	_ = base.WithCode("c").WithField("k", "v")
	if base.Code() != "" || len(base.Fields()) != 0 || base.Kind() != errors.KindNotFound {
		t.Errorf("base was mutated by derived chain: code=%q fields=%v kind=%v",
			base.Code(), base.Fields(), base.Kind())
	}
}

// --- FromContext -------------------------------------------------------------

func TestFromContextLive(t *testing.T) {
	if e := errors.FromContext(context.Background()); e != nil {
		t.Errorf("FromContext(live) = %v, want nil", e)
	}
}

func TestFromContextCanceled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	e := errors.FromContext(ctx)
	if e == nil {
		t.Fatal("FromContext(canceled) = nil, want *Error")
	}
	if e.Kind() != errors.KindCanceled {
		t.Errorf("FromContext(canceled).Kind() = %v, want KindCanceled", e.Kind())
	}
}

func TestFromContextDeadline(t *testing.T) {
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Hour))
	defer cancel()
	// Ensure the deadline has actually fired.
	<-ctx.Done()
	e := errors.FromContext(ctx)
	if e == nil {
		t.Fatal("FromContext(deadline) = nil, want *Error")
	}
	if e.Kind() != errors.KindDeadline {
		t.Errorf("FromContext(deadline).Kind() = %v, want KindDeadline", e.Kind())
	}
}

func TestFromContextNonStandardErrMapsToUnknown(t *testing.T) {
	// A context whose Err() is neither Canceled nor DeadlineExceeded maps to the
	// default arm: a classified *Error with KindUnknown, preserving the cause.
	odd := stderrors.New("custom ctx failure")
	ctx := errCtx{err: odd}
	e := errors.FromContext(ctx)
	if e == nil {
		t.Fatal("FromContext(odd) = nil, want *Error")
	}
	if e.Kind() != errors.KindUnknown {
		t.Errorf("Kind() = %v, want KindUnknown", e.Kind())
	}
	if !errors.Is(e, odd) {
		t.Error("FromContext default arm dropped the underlying cause")
	}
}

// errCtx is a context.Context whose Err() returns an arbitrary error, exercising
// FromContext's default classification arm.
type errCtx struct {
	context.Context
	err error
}

func (c errCtx) Err() error { return c.err }

// --- KindOf ------------------------------------------------------------------

func TestKindOfNil(t *testing.T) {
	if got := errors.KindOf(nil); got != errors.KindUnknown {
		t.Errorf("KindOf(nil) = %v, want KindUnknown", got)
	}
}

func TestKindOfForeign(t *testing.T) {
	if got := errors.KindOf(stderrors.New("foreign")); got != errors.KindUnknown {
		t.Errorf("KindOf(foreign) = %v, want KindUnknown", got)
	}
}

func TestKindOfFindsFirstErrorInChain(t *testing.T) {
	inner := errors.New(errors.KindNotFound, "inner")
	mid := stderrors.Join(stderrors.New("noise"), inner)
	outer := stderrors.New("foreign top") // not in chain of mid
	_ = outer
	if got := errors.KindOf(mid); got != errors.KindNotFound {
		t.Errorf("KindOf(join with NotFound) = %v, want KindNotFound", got)
	}
}

func TestKindOfNeverPanics(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("KindOf panicked: %v", r)
		}
	}()
	_ = errors.KindOf(nil)
	_ = errors.KindOf(stderrors.New("x"))
	var typedNil *errors.Error
	_ = errors.KindOf(typedNil)
}

// --- AsType / Is / Join re-exports -------------------------------------------

func TestAsTypeReExportEquivalence(t *testing.T) {
	leaf := errors.New(errors.KindNotFound, "leaf")
	chain := errors.Wrap(errors.KindInternal, "outer", leaf)

	a, aok := errors.AsType[*errors.Error](chain)
	b, bok := stderrors.AsType[*errors.Error](chain)
	if aok != bok {
		t.Fatalf("AsType ok mismatch: re-export=%v stdlib=%v", aok, bok)
	}
	if a != b {
		t.Errorf("AsType value mismatch: re-export=%p stdlib=%p", a, b)
	}
}

func TestAsTypeExtractsTypedCause(t *testing.T) {
	leaf := errors.New(errors.KindNotFound, "leaf")
	chain := errors.Wrap(errors.KindInternal, "outer", leaf)
	got, ok := errors.AsType[*errors.Error](chain)
	if !ok {
		t.Fatal("AsType[*Error] failed on a wrapped *Error chain")
	}
	// The first *Error in the chain is the outer node itself.
	if got != chain {
		t.Errorf("AsType returned %p, want outermost *Error %p", got, chain)
	}
}

func TestIsReExport(t *testing.T) {
	sentinel := stderrors.New("sentinel")
	chain := errors.Wrap(errors.KindUnavailable, "wrap", sentinel)
	if !errors.Is(chain, sentinel) {
		t.Error("Is re-export failed to match sentinel in chain")
	}
	if errors.Is(chain, stderrors.New("other")) {
		t.Error("Is re-export matched an unrelated error")
	}
}

func TestJoinReExport(t *testing.T) {
	a := errors.New(errors.KindNotFound, "a")
	b := errors.New(errors.KindInvalid, "b")
	joined := errors.Join(a, b)
	if joined == nil {
		t.Fatal("Join returned nil for non-nil inputs")
	}
	if !errors.Is(joined, a) || !errors.Is(joined, b) {
		t.Error("Join did not preserve both members in the chain")
	}
	if errors.Join(nil, nil) != nil {
		t.Error("Join(nil, nil) should be nil")
	}
}

// --- Redaction safety on the production surface ------------------------------

func TestRenderNeverLeaksFieldValue(t *testing.T) {
	const secret = "s3cr3t-token-value"
	e := errors.New(errors.KindInternal, "operation failed").
		WithField("token", secret)
	if strings.Contains(e.Error(), secret) {
		t.Errorf("Error() leaked a field value: %q contains %q", e.Error(), secret)
	}
}
