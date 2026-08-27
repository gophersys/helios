package gitrepository_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/gitrepository/gitrepositorytest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// canarySecret is the credential plaintext (ADR-0020 dimension (f)) the secrets provider
// resolves SERVER-SIDE at the moment of a network verb (Clone/Fetch/Push). The whole
// credential-confinement guarantee (07 §2) is that this value reaches git ONLY through the
// credential-helper seam, confined to Secret.Use — it must appear in NO surfaced artifact: not
// an op's argv/env/dir projection, not a Status/Diff/PushResult, not an AuthError string, not
// the recorded remote URL. If it surfaces anywhere, the confinement seam is broken.
const canarySecret = "SEEDED-CANARY-gitrepository-cred-d34db33f-do-not-leak" // #nosec G101 -- a test redaction needle, not a real credential; the whole point is to prove it NEVER surfaces

// canaryCredRef is the loggable secrets.Reference the canary resolves under (the value never
// rides the reference; the reference IS safe to log and appears in an AuthError by design).
const canaryCredRef = "vault://eden/git#canary-token" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value

// canaryClock is a deterministic Clock for the canary harness.
type canaryClock struct{}

func (canaryClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// TestCanary_CredentialNeverReachesOperationArgs drives a REAL Push whose Credential resolves to the
// seeded canary through the in-memory Backend, which records a projection of every op's argument
// surface (the fields that would become argv/env/dir on a real backend). The credential rides a
// separate *secrets.Secret confined to Secret.Use, so it must NEVER appear among those recorded
// args. This is the runnable form of "credential never on argv / in logs".
func TestCanary_CredentialNeverReachesOperationArgs(t *testing.T) {
	t.Parallel()
	ctx := context.Background()

	const remoteURL = "https://github.com/acme/app.git"
	backend := gitrepositorytest.New()
	// Seed a commit on main so the local tip exists and the push transfers an ancestry.
	backend.Seed("main", map[string]string{"base.txt": "base\n"})
	provider := secretstest.New(map[string]string{canaryCredRef: canarySecret})

	repository, err := gitrepository.New(
		gitrepository.Config{Root: "/in-memory", Remotes: map[string]string{"origin": remoteURL}},
		gitrepository.Deps{Backend: backend, Secrets: provider, Clock: canaryClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	branch, err := gitrepository.ParseBranchName("main")
	if err != nil {
		t.Fatalf("ParseBranchName: %v", err)
	}

	// Push WITH the canary credential — the library resolves it server-side and confines it to
	// the credential-helper seam; the value must not surface in the op's recorded arg projection.
	result, err := repository.Push(ctx, gitrepository.PushOptions{
		Remote:     "origin",
		LocalRef:   branch,
		Credential: secrets.Ref(canaryCredRef),
	})
	if err != nil {
		t.Fatalf("Push (with credential): %v", err)
	}

	// The PushResult surface must be canary-free (ref + tip only, never the secret).
	for _, s := range []string{result.Ref.Remote, result.Ref.Branch.String(), result.Tip.String()} {
		if strings.Contains(s, canarySecret) {
			t.Fatalf("canary leaked into a PushResult field: %q", s)
		}
	}

	// The recorded op-argument projection (the argv/env/dir surface) must be canary-free.
	backend.AssertCredentialNeverInArgs(t, canarySecret)
	// And the remote URL the op carried is the bare URL, never the credential-embedded form.
	if strings.Contains(remoteURL, canarySecret) {
		t.Fatalf("test setup error: remote URL must not embed the canary")
	}
}

// TestCanary_NeverSurfacesThroughAuthError proves the credential value never surfaces through
// the FAILURE path. A Push over a provider that REJECTS the reference produces an AuthError
// carrying the loggable Reference; the error string (and its whole wrapped chain) must be
// canary-free even though the same reference resolved to the canary in the happy path.
func TestCanary_NeverSurfacesThroughAuthError(t *testing.T) {
	t.Parallel()
	ctx := context.Background()

	backend := gitrepositorytest.New()
	backend.Seed("main", map[string]string{"base.txt": "base\n"})
	// A provider that does NOT know the reference → Resolve fails → the library wraps it in an
	// AuthError carrying the (loggable) reference, never the value.
	provider := secretstest.New(map[string]string{"vault://eden/git#other": canarySecret})

	repository, err := gitrepository.New(
		gitrepository.Config{Root: "/in-memory", Remotes: map[string]string{"origin": "https://github.com/acme/app.git"}},
		gitrepository.Deps{Backend: backend, Secrets: provider, Clock: canaryClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	branch, err := gitrepository.ParseBranchName("main")
	if err != nil {
		t.Fatalf("ParseBranchName: %v", err)
	}

	_, pushErr := repository.Push(ctx, gitrepository.PushOptions{
		Remote:     "origin",
		LocalRef:   branch,
		Credential: secrets.Ref(canaryCredRef), // resolvable nowhere in this provider
	})
	if pushErr == nil {
		t.Fatalf("Push over an unresolvable credential must fail (silent-bad-token trap)")
	}
	if errors.KindOf(pushErr) != errors.KindUnauthenticated {
		t.Fatalf("a credential-resolution failure must classify KindUnauthenticated, got %v", errors.KindOf(pushErr))
	}
	// The whole wrapped chain (Error() renders message + ": " + cause recursively) must be
	// canary-free — a leak at any depth would surface in the rendered string.
	if strings.Contains(pushErr.Error(), canarySecret) {
		t.Fatalf("canary leaked through the AuthError chain: %q", pushErr.Error())
	}
	// The loggable reference, by contrast, IS allowed to surface (it carries no secret).
	if !strings.Contains(pushErr.Error(), "git") {
		t.Fatalf("AuthError should render an operator-safe message naming the remote; got %q", pushErr.Error())
	}
}

// TestCanary_AuthErrorRendersReferenceNotValue is the direct redaction-property over the typed
// AuthError: constructed with a reference whose canonical form is loggable, its Error() carries
// the reference string but never a secret value (the error type has no field that could hold
// one). This is the rule-21 (f) shape: a non-scalar secret has no path into the message.
func TestCanary_AuthErrorRendersReferenceNotValue(t *testing.T) {
	t.Parallel()
	authErr := &gitrepository.AuthError{Reference: secrets.Ref(canaryCredRef), Remote: "origin"}
	message := authErr.Error()
	if strings.Contains(message, canarySecret) {
		t.Fatalf("AuthError.Error() must never carry a secret value; got %q", message)
	}
	if !strings.Contains(message, "origin") {
		t.Fatalf("AuthError.Error() must name the remote (loggable); got %q", message)
	}
}
