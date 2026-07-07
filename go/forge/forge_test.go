package forge_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/forge"
	"github.com/gophersys/libs/go/secrets"
)

// TestClassify maps every taxonomy type to its stable Kind and a foreign error to
// KindUnknown — the one home for the type→Kind contract.
func TestClassify(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name string
		err  error
		want errors.Kind
	}{
		{"invalid", forge.InvalidRequestError{Owner: "o", Name: "n", Reason: "x"}, errors.KindInvalid},
		{"unauthenticated", forge.UnauthenticatedError{Owner: "o", Name: "n"}, errors.KindUnauthenticated},
		{"conflict", forge.ConflictError{Owner: "o", Name: "n", Reason: "x"}, errors.KindConflict},
		{"notfound", forge.NotFoundError{Owner: "o", Name: "n"}, errors.KindNotFound},
		{"unavailable", forge.UnavailableError{Owner: "o", Name: "n", Reason: "x"}, errors.KindUnavailable},
		{"foreign", stubError("plain"), errors.KindUnknown},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			if got := forge.Classify(testCase.err); got != testCase.want {
				t.Errorf("Classify: got %v, want %v", got, testCase.want)
			}
		})
	}
}

// TestWrap preserves both the cause chain (AsType reaches the taxonomy type) and
// classifies the Kind; a nil error stays nil.
func TestWrap(t *testing.T) {
	t.Parallel()
	if forge.Wrap(nil) != nil {
		t.Fatal("Wrap(nil) must be nil")
	}
	wrapped := forge.Wrap(forge.ConflictError{Owner: "o", Name: "n", Reason: "taken"})
	if errors.KindOf(wrapped) != errors.KindConflict {
		t.Errorf("Kind: got %v, want KindConflict", errors.KindOf(wrapped))
	}
	if !errors.IsType[forge.ConflictError](wrapped) {
		t.Error("wrapped error lost its taxonomy type in the chain")
	}
}

// TestErrorMessagesNeverFabricateValues proves the messages render the loggable
// identity (owner/name, reference) and never crash on a zero reference.
func TestErrorMessagesNeverFabricateValues(t *testing.T) {
	t.Parallel()
	authErr := forge.UnauthenticatedError{Owner: "eden", Name: "svc", Credential: secrets.Ref("vault://x#t")}
	if !strings.Contains(authErr.Error(), "eden/svc") {
		t.Errorf("message should carry the slug: %q", authErr.Error())
	}
	if !strings.Contains(authErr.Error(), "vault://x#t") {
		t.Errorf("message should carry the loggable reference: %q", authErr.Error())
	}
	// A zero reference renders the explicit token, never a panic.
	zeroAuth := forge.UnauthenticatedError{Owner: "o", Name: "n"}
	if !strings.Contains(zeroAuth.Error(), "<zero>") {
		t.Errorf("zero reference should render <zero>: %q", zeroAuth.Error())
	}
}

// TestRequestAndRepositoryIsZero guards the zero-value sentinels the port contract
// relies on at the boundary.
func TestRequestAndRepositoryIsZero(t *testing.T) {
	t.Parallel()
	if !(forge.CreateRepositoryRequest{}).IsZero() {
		t.Error("zero CreateRepositoryRequest must report IsZero")
	}
	if (forge.CreateRepositoryRequest{Owner: "o"}).IsZero() {
		t.Error("a populated request must not report IsZero")
	}
	if !(forge.Repository{}).IsZero() {
		t.Error("zero Repository must report IsZero")
	}
	if (forge.Repository{Name: "n"}).IsZero() {
		t.Error("a populated repository must not report IsZero")
	}
}

// TestErrorRenderings exercises every taxonomy Error() string and the slug edge
// cases, proving each renders an operator-safe identity and degrades legibly when a
// field is missing — never a bare "/" and never a panic.
func TestErrorRenderings(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name      string
		err       error
		wantParts []string
	}{
		{
			"invalid-request",
			forge.InvalidRequestError{Owner: "eden", Name: "svc", Reason: "Name is required"},
			[]string{"eden/svc", "Name is required"},
		},
		{
			"invalid-missing-owner",
			forge.InvalidRequestError{Name: "svc", Reason: "Owner is required"},
			[]string{"<unspecified>/svc", "Owner is required"},
		},
		{
			"invalid-missing-name",
			forge.InvalidRequestError{Owner: "eden", Reason: "Name is required"},
			[]string{"eden/<unspecified>", "Name is required"},
		},
		{
			"invalid-missing-both",
			forge.InvalidRequestError{Reason: "empty"},
			[]string{"<unspecified>", "empty"},
		},
		{
			"conflict",
			forge.ConflictError{Owner: "eden", Name: "svc", Reason: "name is reserved"},
			[]string{"eden/svc", "name is reserved"},
		},
		{
			"notfound",
			forge.NotFoundError{Owner: "eden", Name: "svc"},
			[]string{"eden/svc", "not found"},
		},
		{
			"unavailable",
			forge.UnavailableError{Owner: "eden", Name: "svc", Reason: "transport error"},
			[]string{"eden/svc", "transport error"},
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			message := testCase.err.Error()
			for _, part := range testCase.wantParts {
				if !strings.Contains(message, part) {
					t.Errorf("message %q should contain %q", message, part)
				}
			}
		})
	}
}

// TestErrorUnwrap proves the two cause-bearing taxonomy errors expose their wrapped
// cause for chain traversal, and render it in their message, while a cause-less one
// unwraps to nil.
func TestErrorUnwrap(t *testing.T) {
	t.Parallel()
	cause := stubError("underlying boom")

	authError := forge.UnauthenticatedError{Owner: "o", Name: "n", Credential: secrets.Ref("vault://x#t"), Cause: cause}
	if !errors.Is(authError, cause) {
		t.Error("UnauthenticatedError must unwrap to its cause")
	}
	if !strings.Contains(authError.Error(), "underlying boom") {
		t.Errorf("message should render the cause: %q", authError.Error())
	}

	unavailable := forge.UnavailableError{Owner: "o", Name: "n", Reason: "store down", Cause: cause}
	if !errors.Is(unavailable, cause) {
		t.Error("UnavailableError must unwrap to its cause")
	}
	if !strings.Contains(unavailable.Error(), "underlying boom") {
		t.Errorf("message should render the cause: %q", unavailable.Error())
	}

	// A cause-less taxonomy error unwraps to nil (no chain beyond it).
	bare := forge.UnavailableError{Owner: "o", Name: "n", Reason: "x"}
	if bare.Unwrap() != nil {
		t.Error("a cause-less UnavailableError must unwrap to nil")
	}
}

// stubError is a foreign error type (not in the forge taxonomy) for the Classify
// fallthrough case and as an Unwrap cause.
type stubError string

func (e stubError) Error() string { return string(e) }
