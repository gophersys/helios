package errorstest_test

import (
	stderrors "errors"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/errors/errorstest"
)

func TestLeaf(t *testing.T) {
	t.Parallel()
	e := errorstest.Leaf(errors.KindNotFound, "missing")
	if e.Kind() != errors.KindNotFound {
		t.Errorf("Leaf Kind = %v, want KindNotFound", e.Kind())
	}
	if e.Error() != "missing" {
		t.Errorf("Leaf message = %q, want %q", e.Error(), "missing")
	}
}

func TestWrapping(t *testing.T) {
	t.Parallel()
	inner := errorstest.Leaf(errors.KindNotFound, "inner")
	w := errorstest.Wrapping(errors.KindInternal, inner)
	if w.Kind() != errors.KindInternal {
		t.Errorf("Wrapping outer Kind = %v, want KindInternal", w.Kind())
	}
	if !errors.Is(w, inner) {
		t.Error("Wrapping did not preserve the inner error in the chain")
	}
}

func TestRequireKindPasses(t *testing.T) {
	t.Parallel()
	// Use a sub-test recorder: RequireKind on a matching Kind must not fail.
	rt := &recordingTB{TB: t}
	errorstest.RequireKind(rt, errors.New(errors.KindInvalid, "x"), errors.KindInvalid)
	if rt.failed {
		t.Error("RequireKind reported failure on a matching Kind")
	}
}

func TestRequireKindFails(t *testing.T) {
	t.Parallel()
	rt := &recordingTB{TB: t, swallowFatal: true}
	runGuarded(func() {
		errorstest.RequireKind(rt, errors.New(errors.KindInvalid, "x"), errors.KindNotFound)
	})
	if !rt.failed {
		t.Error("RequireKind did not report failure on a Kind mismatch")
	}
}

func TestRequireNoSecretPasses(t *testing.T) {
	t.Parallel()
	rt := &recordingTB{TB: t}
	type creds struct{ Password string }
	// Secret carried only as a non-scalar value collapses to the marker, so the
	// probe must NOT see it.
	e := errors.New(errors.KindInternal, "boom").WithField("creds", creds{Password: "sekret"})
	errorstest.RequireNoSecret(rt, e, "sekret")
	if rt.failed {
		t.Error("RequireNoSecret failed though the secret was only a structured value")
	}
}

func TestRequireNoSecretCatchesLeakInMessage(t *testing.T) {
	t.Parallel()
	rt := &recordingTB{TB: t, swallowFatal: true}
	// A caller who interpolates a secret into the message (anti-pattern) is caught.
	e := errors.New(errors.KindInternal, "failed with token=leaked-value")
	runGuarded(func() {
		errorstest.RequireNoSecret(rt, e, "leaked-value")
	})
	if !rt.failed {
		t.Error("RequireNoSecret did not catch a secret leaked into the message")
	}
}

func TestRequireNoSecretWalksChain(t *testing.T) {
	t.Parallel()
	rt := &recordingTB{TB: t, swallowFatal: true}
	inner := errors.New(errors.KindNotFound, "inner with leaked-value here")
	outer := errors.Wrap(errors.KindInternal, "outer", inner)
	runGuarded(func() {
		errorstest.RequireNoSecret(rt, outer, "leaked-value")
	})
	if !rt.failed {
		t.Error("RequireNoSecret did not walk the chain to find a leak in the inner cause")
	}
}

func TestRequireNoSecretNilIsSafe(t *testing.T) {
	t.Parallel()
	rt := &recordingTB{TB: t}
	errorstest.RequireNoSecret(rt, nil, "anything")
	if rt.failed {
		t.Error("RequireNoSecret(nil) should never fail")
	}
}

func TestAssertUnwrapsTo(t *testing.T) {
	t.Parallel()
	leaf := errors.New(errors.KindNotFound, "leaf")
	chain := errors.Wrap(errors.KindInternal, "outer", leaf)
	got := errorstest.AssertUnwrapsTo[*errors.Error](t, chain)
	if got == nil {
		t.Fatal("AssertUnwrapsTo returned nil")
	}
}

// absentError is a typed error never placed in any chain under test.
type absentError struct{}

func (*absentError) Error() string { return "absent" }

func TestAssertUnwrapsToForeignChain(t *testing.T) {
	t.Parallel()
	rt := &recordingTB{TB: t, swallowFatal: true}
	// Asserting a type that is not in the chain must fail the test.
	runGuarded(func() {
		// The return is deliberately unused: this negative case only verifies that
		// AssertUnwrapsTo calls Fatalf for an absent target type.
		//nolint:errcheck // see above: the extracted value is irrelevant on the fatal path.
		errorstest.AssertUnwrapsTo[*absentError](rt, errors.New(errors.KindNotFound, "x"))
	})
	if !rt.failed {
		t.Error("AssertUnwrapsTo did not fail for an absent target type")
	}
}

// recordingTB captures Fatalf/Errorf calls so we can test the assertions without
// actually failing the host test. When swallowFatal is set it intercepts the
// goroutine-killing behavior of Fatalf via runtime.Goexit emulation by panicking
// and recovering, which is sufficient for these single-statement assertions.
type recordingTB struct {
	testing.TB
	failed       bool
	swallowFatal bool
}

func (r *recordingTB) Helper() {}

func (r *recordingTB) Errorf(format string, args ...any) {
	r.failed = true
}

func (r *recordingTB) Fatalf(format string, args ...any) {
	r.failed = true
	if r.swallowFatal {
		panic(errFatalSentinel)
	}
}

var errFatalSentinel = stderrors.New("recordingTB fatal sentinel")

// runGuarded invokes fn and recovers the sentinel panic raised by a swallowed
// Fatalf, emulating runtime.Goexit's "abort this call, continue the test" shape.
// Any non-sentinel panic is re-raised so real failures are never swallowed.
func runGuarded(fn func()) {
	defer func() {
		r := recover()
		if r == nil {
			return
		}
		if err, ok := r.(error); ok && stderrors.Is(err, errFatalSentinel) {
			return
		}
		panic(r)
	}()
	fn()
}
