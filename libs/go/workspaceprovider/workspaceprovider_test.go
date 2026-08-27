package workspaceprovider_test

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/dependencies/dependenciestest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// Handle round-trip and accessors.

func TestParseHandle_RoundTrips(t *testing.T) {
	t.Parallel()
	prov := workspaceprovidertest.FakeProvider(nil)
	ws, err := prov.Provision(context.Background(), workspaceprovider.WorkspaceSpec{
		Name:   "ws-roundtrip",
		Image:  "busybox:1.36",
		Mounts: []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/workspace"}},
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: "org-7",
			workspaceprovider.LabelProject:      "proj-42",
		},
	})
	if err != nil {
		t.Fatalf("Provision: %v", err)
	}
	handle := ws.Handle()

	parsed, perr := workspaceprovider.ParseHandle(handle.String())
	if perr != nil {
		t.Fatalf("ParseHandle(%q): %v", handle.String(), perr)
	}
	if parsed.String() != handle.String() {
		t.Errorf("round-trip mismatch: got %q want %q", parsed.String(), handle.String())
	}
	if parsed.Substrate() != workspaceprovider.SubstrateDocker {
		t.Errorf("Substrate() = %q, want docker", parsed.Substrate())
	}
	if parsed.Organization() != "org-7" {
		t.Errorf("Organization() = %q, want org-7", parsed.Organization())
	}
	if parsed.Project() != "proj-42" {
		t.Errorf("Project() = %q, want proj-42", parsed.Project())
	}
	if parsed.WorkDir() != "/workspace" {
		t.Errorf("WorkDir() = %q, want /workspace", parsed.WorkDir())
	}
	if parsed.Name() != "ws-roundtrip" {
		t.Errorf("Name() = %q, want ws-roundtrip", parsed.Name())
	}
}

func TestParseHandle_Rejects(t *testing.T) {
	t.Parallel()
	for _, raw := range []string{
		"",                        // empty
		"docker://",               // no segments
		"ftp://a/b/c/name/dir",    // unknown scheme
		"docker://ns/o/p//dir",    // empty name segment
		"docker://only-two/parts", // wrong segment count
	} {
		raw := raw
		t.Run(raw, func(t *testing.T) {
			t.Parallel()
			_, err := workspaceprovider.ParseHandle(raw)
			if err == nil {
				t.Fatalf("ParseHandle(%q): expected an error, got nil", raw)
			}
			if errors.KindOf(err) != errors.KindInvalid {
				t.Errorf("ParseHandle(%q) Kind = %v, want Invalid", raw, errors.KindOf(err))
			}
			if typed, ok := errors.AsType[*workspaceprovider.InvalidHandleError](err); !ok || typed == nil {
				t.Errorf("ParseHandle(%q): want *InvalidHandleError in the chain", raw)
			}
		})
	}
}

func TestHandle_ZeroIsInvalid(t *testing.T) {
	t.Parallel()
	var h workspaceprovider.Handle
	if !h.IsZero() {
		t.Errorf("zero Handle.IsZero() = false, want true")
	}
	if h.String() != "" {
		t.Errorf("zero Handle.String() = %q, want empty", h.String())
	}
}

func TestHandle_WorkDirWithSlashesRoundTrips(t *testing.T) {
	t.Parallel()
	prov := workspaceprovidertest.FakeProvider(nil)
	ws, err := prov.Provision(context.Background(), workspaceprovider.WorkspaceSpec{
		Name:   "ws-deep",
		Image:  "busybox:1.36",
		Mounts: []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/home/coder/project"}},
	})
	if err != nil {
		t.Fatalf("Provision: %v", err)
	}
	if got := ws.Handle().WorkDir(); got != "/home/coder/project" {
		t.Errorf("WorkDir() = %q, want /home/coder/project", got)
	}
	// And it survives a ParseHandle round-trip.
	parsed, perr := workspaceprovider.ParseHandle(ws.Handle().String())
	if perr != nil {
		t.Fatalf("ParseHandle: %v", perr)
	}
	if parsed.WorkDir() != "/home/coder/project" {
		t.Errorf("round-tripped WorkDir() = %q, want /home/coder/project", parsed.WorkDir())
	}
}

// New constructor: pure, validating.

func newDeps() workspaceprovider.Deps {
	set, _, _, _ := dependenciestest.Fakes()
	return workspaceprovider.Deps{
		Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{
			workspaceprovider.SubstrateDocker: workspaceprovidertest.NewAdapter(),
		},
		Secrets: secretstest.New(nil),
		Clock:   set.Clock,
	}
}

func TestNew_RejectsEmptyAdapters(t *testing.T) {
	t.Parallel()
	set, _, _, _ := dependenciestest.Fakes()
	_, err := workspaceprovider.New(workspaceprovider.Config{}, workspaceprovider.Deps{
		Secrets: secretstest.New(nil),
		Clock:   set.Clock,
	})
	if err == nil || errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("New with no adapters: got %v, want a KindInvalid error", err)
	}
}

func TestNew_RejectsNilSecrets(t *testing.T) {
	t.Parallel()
	dependencies := newDeps()
	dependencies.Secrets = nil
	_, err := workspaceprovider.New(workspaceprovider.Config{}, dependencies)
	if err == nil || errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("New with nil Secrets: got %v, want KindInvalid", err)
	}
}

func TestNew_RejectsNilClock(t *testing.T) {
	t.Parallel()
	dependencies := newDeps()
	dependencies.Clock = nil
	_, err := workspaceprovider.New(workspaceprovider.Config{}, dependencies)
	if err == nil || errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("New with nil Clock: got %v, want KindInvalid", err)
	}
}

func TestNew_RejectsDefaultWithNoAdapter(t *testing.T) {
	t.Parallel()
	_, err := workspaceprovider.New(
		workspaceprovider.Config{Default: workspaceprovider.SubstrateKubernetes},
		newDeps(), // only the docker adapter is wired
	)
	if err == nil || errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("New with an unbacked Default: got %v, want KindInvalid", err)
	}
}

func TestNew_Succeeds(t *testing.T) {
	t.Parallel()
	prov, err := workspaceprovider.New(workspaceprovider.Config{Default: workspaceprovider.SubstrateDocker}, newDeps())
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if prov == nil {
		t.Fatalf("New returned a nil *Provisioner with a nil error")
	}
}

// Spec validation (library-owned, before any adapter call).

func TestProvision_RejectsInvalidSpec(t *testing.T) {
	t.Parallel()
	prov := workspaceprovidertest.FakeProvider(nil)
	cases := []struct {
		name string
		spec workspaceprovider.WorkspaceSpec
	}{
		{"no-name", workspaceprovider.WorkspaceSpec{Image: "busybox"}},
		{"no-image", workspaceprovider.WorkspaceSpec{Name: "x"}},
		{"relative-mount", workspaceprovider.WorkspaceSpec{
			Name: "x", Image: "busybox",
			Mounts: []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "relative/path"}},
		}},
		{"secret-mount-no-ref", workspaceprovider.WorkspaceSpec{
			Name: "x", Image: "busybox",
			Mounts: []workspaceprovider.Mount{{Kind: workspaceprovider.MountSecret, Target: "/run/secret"}},
		}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			ws, err := prov.Provision(context.Background(), tc.spec)
			if ws != nil {
				t.Errorf("Provision returned a non-nil Workspace for an invalid spec")
			}
			if err == nil || errors.KindOf(err) != errors.KindInvalid {
				t.Fatalf("Provision(%s): got %v, want a KindInvalid InvalidSpecError", tc.name, err)
			}
			if typed, ok := errors.AsType[*workspaceprovider.InvalidSpecError](err); !ok || typed == nil {
				t.Errorf("Provision(%s): want *InvalidSpecError in the chain", tc.name)
			}
		})
	}
}

func TestProvision_RejectsUnroutableSubstrate(t *testing.T) {
	t.Parallel()
	prov := workspaceprovidertest.FakeProvider(nil) // only docker is wired
	_, err := prov.Provision(context.Background(), workspaceprovider.WorkspaceSpec{
		Name: "x", Image: "busybox", Substrate: workspaceprovider.SubstrateKubernetes,
	})
	if err == nil || errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("Provision with an unrouted substrate: got %v, want KindInvalid", err)
	}
}

// Error taxonomy to Kind mapping (design rationale 6).

func TestErrorKinds(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name string
		err  error
		want errors.Kind
	}{
		{"InvalidSpec", &workspaceprovider.InvalidSpecError{Field: "f", Reason: "r"}, errors.KindInvalid},
		{"Image", &workspaceprovider.ImageError{Image: "i"}, errors.KindInvalid},
		{"NotFound", &workspaceprovider.NotFoundError{}, errors.KindNotFound},
		{"Conflict", &workspaceprovider.ConflictError{Name: "n"}, errors.KindConflict},
		{"Quota", &workspaceprovider.QuotaExceededError{Resource: "cpu"}, errors.KindExhausted},
		{"Isolation", &workspaceprovider.IsolationError{Detail: "d"}, errors.KindPermission},
		{"Unavailable", &workspaceprovider.SubstrateUnavailableError{Substrate: workspaceprovider.SubstrateDocker, Op: "o"}, errors.KindUnavailable},
		{"NotReady", &workspaceprovider.NotReadyError{Op: "Run"}, errors.KindInvalid},
		{"Deadline", &workspaceprovider.DeadlineError{Op: "Exec"}, errors.KindDeadline},
		{"Unsupported", &workspaceprovider.UnsupportedError{Cap: workspaceprovider.CapExecPTY}, errors.KindInvalid},
		{"InvalidHandle", &workspaceprovider.InvalidHandleError{Raw: "x"}, errors.KindInvalid},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			// Each Error() renders non-empty and never panics.
			if tc.err.Error() == "" {
				t.Errorf("%s: Error() is empty", tc.name)
			}
			// Wrapped with its Kind, it classifies (the library wraps with wrapKind).
			wrapped := errors.Wrap(tc.want, "test", tc.err)
			if errors.KindOf(wrapped) != tc.want {
				t.Errorf("%s: wrapped Kind = %v, want %v", tc.name, errors.KindOf(wrapped), tc.want)
			}
		})
	}
}

// Idempotency, teardown, secret-resolution timing (over the fake Provider).

func TestProvision_IsIdempotent(t *testing.T) {
	t.Parallel()
	prov := workspaceprovidertest.FakeProvider(nil)
	spec := workspaceprovider.WorkspaceSpec{
		Name: "ws-idem", Image: "busybox:1.36",
		Labels: map[string]string{workspaceprovider.LabelOrganization: "o", workspaceprovider.LabelProject: "p"},
	}
	a, err := prov.Provision(context.Background(), spec)
	if err != nil {
		t.Fatalf("first Provision: %v", err)
	}
	b, err := prov.Provision(context.Background(), spec)
	if err != nil {
		t.Fatalf("re-Provision: %v", err)
	}
	if a.Handle().String() != b.Handle().String() {
		t.Errorf("idempotent re-Provision returned a different handle")
	}
}

func TestTeardown_IsIdempotent(t *testing.T) {
	t.Parallel()
	prov := workspaceprovidertest.FakeProvider(nil)
	ws, err := prov.Provision(context.Background(), workspaceprovider.WorkspaceSpec{Name: "ws-td", Image: "busybox:1.36"})
	if err != nil {
		t.Fatalf("Provision: %v", err)
	}
	if terr := prov.Teardown(context.Background(), ws.Handle()); terr != nil {
		t.Errorf("first Teardown: %v", terr)
	}
	if terr := prov.Teardown(context.Background(), ws.Handle()); terr != nil {
		t.Errorf("second Teardown must be nil (idempotent), got %v", terr)
	}
	if _, oerr := prov.Open(context.Background(), ws.Handle()); errors.KindOf(oerr) != errors.KindNotFound {
		t.Errorf("Open after Teardown Kind = %v, want NotFound", errors.KindOf(oerr))
	}
}

func TestProvision_ResolvesPullSecretServerSide_NeverLeaks(t *testing.T) {
	t.Parallel()
	const canary = "PULL-SECRET-PLAINTEXT"
	prov := workspaceprovidertest.FakeProvider(map[string]string{"registry-pull": canary})
	ws, err := prov.Provision(context.Background(), workspaceprovider.WorkspaceSpec{
		Name:      "ws-secret",
		Image:     "busybox:1.36",
		ImagePull: secrets.Ref("registry-pull"),
	})
	if err != nil {
		t.Fatalf("Provision with pull-secret: %v", err)
	}
	// The plaintext must appear in NO loggable surface.
	if strings.Contains(ws.Handle().String(), canary) {
		t.Errorf("the pull-secret plaintext leaked into the Handle")
	}
	st, serr := ws.Status(context.Background())
	if serr != nil {
		t.Fatalf("Status: %v", serr)
	}
	if strings.Contains(st.Detail, canary) {
		t.Errorf("the pull-secret plaintext leaked into Status.Detail")
	}
}

func TestProvision_FailureNeverReturnsWorkspaceWithError(t *testing.T) {
	t.Parallel()
	set, _, _, _ := dependenciestest.Fakes()
	fake := workspaceprovidertest.NewAdapter().FailProvisionWith(&workspaceprovider.QuotaExceededError{Resource: "workspaces"})
	prov, err := workspaceprovider.New(
		workspaceprovider.Config{Default: workspaceprovider.SubstrateDocker},
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{workspaceprovider.SubstrateDocker: fake},
			Secrets:  secretstest.New(nil),
			Clock:    set.Clock,
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ws, perr := prov.Provision(context.Background(), workspaceprovider.WorkspaceSpec{Name: "ws-quota", Image: "busybox:1.36"})
	if ws != nil {
		t.Errorf("Provision returned a non-nil Workspace alongside an error")
	}
	if errors.KindOf(perr) != errors.KindExhausted {
		t.Errorf("Provision Kind = %v, want Exhausted", errors.KindOf(perr))
	}
}
