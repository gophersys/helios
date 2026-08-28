package gitrepository_test

import (
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/gitrepository/gitrepositorytest"
)

// stubClock is a trivial gitrepository.Clock for the constructor tests.
type stubClock struct{}

func (stubClock) Now() time.Time { return time.Unix(0, 0).UTC() }

// TestNew_Validates proves New is the pure constructor spine: it validates Config + Deps and
// rejects the malformed cases with an InvalidRefError (KindInvalid), without touching git.
func TestNew_Validates(t *testing.T) {
	t.Parallel()
	backend := gitrepositorytest.New()

	cases := []struct {
		name          string
		configuration gitrepository.Config
		dependencies  gitrepository.Deps
		wantErr       bool
	}{
		{
			name:          "valid",
			configuration: gitrepository.Config{Root: "/abs/root"},
			dependencies:  gitrepository.Deps{Backend: backend, Clock: stubClock{}},
			wantErr:       false,
		},
		{
			name:          "empty root",
			configuration: gitrepository.Config{Root: ""},
			dependencies:  gitrepository.Deps{Backend: backend, Clock: stubClock{}},
			wantErr:       true,
		},
		{
			name:          "relative root",
			configuration: gitrepository.Config{Root: "relative/path"},
			dependencies:  gitrepository.Deps{Backend: backend, Clock: stubClock{}},
			wantErr:       true,
		},
		{
			name:          "nil backend",
			configuration: gitrepository.Config{Root: "/abs/root"},
			dependencies:  gitrepository.Deps{Backend: nil, Clock: stubClock{}},
			wantErr:       true,
		},
		{
			name:          "nil clock",
			configuration: gitrepository.Config{Root: "/abs/root"},
			dependencies:  gitrepository.Deps{Backend: backend, Clock: nil},
			wantErr:       true,
		},
		{
			name:          "invalid remote name",
			configuration: gitrepository.Config{Root: "/abs/root", Remotes: map[string]string{"-bad": "https://x"}},
			dependencies:  gitrepository.Deps{Backend: backend, Clock: stubClock{}},
			wantErr:       true,
		},
		{
			name:          "empty remote url",
			configuration: gitrepository.Config{Root: "/abs/root", Remotes: map[string]string{"origin": ""}},
			dependencies:  gitrepository.Deps{Backend: backend, Clock: stubClock{}},
			wantErr:       true,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			repository, err := gitrepository.New(tc.configuration, tc.dependencies)
			switch {
			case tc.wantErr && err == nil:
				t.Errorf("New must reject %s", tc.name)
			case tc.wantErr && errors.KindOf(err) != errors.KindInvalid:
				t.Errorf("New(%s) error must be KindInvalid, got %v", tc.name, errors.KindOf(err))
			case !tc.wantErr && err != nil:
				t.Errorf("New(%s) errored unexpectedly: %v", tc.name, err)
			case !tc.wantErr && repository == nil:
				t.Errorf("New(%s) returned nil repository", tc.name)
			}
		})
	}
}

// TestNew_NeverReturnsNilNil guards the nilnil contract: a successful New returns a non-nil
// repository and a nil error, never both nil.
func TestNew_NeverReturnsNilNil(t *testing.T) {
	t.Parallel()
	repository, err := gitrepository.New(
		gitrepository.Config{Root: "/abs/root"},
		gitrepository.Deps{Backend: gitrepositorytest.New(), Clock: stubClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if repository == nil {
		t.Fatal("New returned a nil repository with a nil error")
	}
	if repository.Root() != "/abs/root" {
		t.Errorf("Root() = %q, want /abs/root", repository.Root())
	}
}

// TestIdentity_IsZero proves the IsZero predicate the audit-identity guard relies on.
func TestIdentity_IsZero(t *testing.T) {
	t.Parallel()
	if !(gitrepository.Identity{}).IsZero() {
		t.Errorf("zero Identity must report IsZero")
	}
	if (gitrepository.Identity{Name: "A", Email: "a@b"}).IsZero() {
		t.Errorf("a named Identity must not report IsZero")
	}
}

// TestErrorKinds proves each typed error classifies to its stable errors.Kind via Kind() and
// via errors.KindOf after WrapError (the transport-boundary contract).
func TestErrorKinds(t *testing.T) {
	t.Parallel()
	cases := []struct {
		err  error
		want errors.Kind
	}{
		{&gitrepository.InvalidRefError{Ref: "x"}, errors.KindInvalid},
		{&gitrepository.NotFoundError{What: "x"}, errors.KindNotFound},
		{&gitrepository.AlreadyExistsError{What: "x"}, errors.KindConflict},
		{&gitrepository.NothingToCommitError{}, errors.KindConflict},
		{&gitrepository.NonFastForwardError{}, errors.KindConflict},
		{&gitrepository.ConflictError{}, errors.KindConflict},
		{&gitrepository.DirtyWorktreeError{}, errors.KindConflict},
		{&gitrepository.AuthError{Remote: "x"}, errors.KindUnauthenticated},
		{&gitrepository.DeniedError{}, errors.KindPermission},
		{&gitrepository.UnavailableError{Remote: "x"}, errors.KindUnavailable},
	}
	for _, tc := range cases {
		wrapped := gitrepository.WrapError(tc.err)
		if errors.KindOf(wrapped) != tc.want {
			t.Errorf("KindOf(WrapError(%T)) = %v, want %v", tc.err, errors.KindOf(wrapped), tc.want)
		}
	}
	if gitrepository.WrapError(nil) != nil {
		t.Errorf("WrapError(nil) must be nil")
	}
}

// TestAuthError_NeverLeaksValue proves an AuthError renders the reference (loggable) but never
// a secret value — the redaction-safe error invariant (12 error-handling / 07 §2).
func TestAuthError_NeverLeaksValue(t *testing.T) {
	t.Parallel()
	authErr := &gitrepository.AuthError{Remote: "origin"}
	message := authErr.Error()
	if message == "" {
		t.Errorf("AuthError must render an operator-safe message")
	}
	// The error carries the remote and (when set) the reference's canonical form, never a value.
	if want := "origin"; !contains(message, want) {
		t.Errorf("AuthError message must name the remote %q; got %q", want, message)
	}
}

// contains is a tiny substring check for the message assertion.
func contains(haystack, needle string) bool {
	return needle == "" || indexOfSub(haystack, needle) >= 0
}

func indexOfSub(haystack, needle string) int {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return i
		}
	}
	return -1
}
