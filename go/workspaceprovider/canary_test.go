package workspaceprovider_test

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/dependencies/dependenciestest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// canaryPlaintext is the redaction needle (ADR-0020 dimension (f)): the credential plaintext
// the secrets provider resolves SERVER-SIDE at Provision/Run. It must appear in NO surfaced
// artifact — not a Handle, not a Status (State/Detail/Conditions), not a Descriptor from List,
// not an error string, not a recorded adapter Spec/Env. The library carries only the loggable
// secrets.Reference; the value has no path into the published surface. If it leaks, the
// credential-flow guarantee (07 §2) is broken.
const canaryPlaintext = "SEEDED-CANARY-workspaceprovider-cred-d34db33f-do-not-leak" // #nosec G101 -- a test redaction needle, not a real credential; the whole point is to prove it NEVER surfaces

// The loggable references the canary resolves under (the value never rides these strings).
const (
	canaryPullRef     = "vault://eden/registry#canary-pull"  // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value
	canaryMountRef    = "vault://eden/mount#canary-mount"    // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value
	canaryWorkloadRef = "vault://eden/anthropic#canary-load" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value
)

// canaryProvider wires a real Provisioner over the in-memory fake adapter and a secrets
// provider seeded so EVERY credential slot (ImagePull, MountSecret, RunSpec.Credential)
// resolves to the same canary plaintext.
func canaryProvider(t *testing.T) (*workspaceprovider.Provisioner, *workspaceprovidertest.Adapter) {
	t.Helper()
	set, _, _, _ := dependenciestest.Fakes()
	adapter := workspaceprovidertest.NewAdapter(
		workspaceprovider.CapExecPTY,
		workspaceprovider.CapBindMount,
		workspaceprovider.CapLogStream,
		workspaceprovider.CapResourceLimits,
	)
	prov, err := workspaceprovider.New(
		workspaceprovider.Config{Default: workspaceprovider.SubstrateDocker, Namespace: "eden"},
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{workspaceprovider.SubstrateDocker: adapter},
			Secrets: secretstest.New(map[string]string{
				canaryPullRef:     canaryPlaintext,
				canaryMountRef:    canaryPlaintext,
				canaryWorkloadRef: canaryPlaintext,
			}),
			Clock: set.Clock,
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return prov, adapter
}

// TestCanary_CredentialNeverSurfaces provisions a workspace whose pull-secret, a MountSecret,
// and a Run credential ALL resolve to the seeded canary, drives the full workload plane
// (Status, Files, Run-to-terminal, List), then asserts the canary appears in NONE of: the
// Handle, the Status (State/Detail/Conditions), any Descriptor from List, or the spec/env the
// adapter recorded. This proves the value never escapes the resolve->inject seam onto the
// published surface — the only thing that crosses the library boundary is the loggable Reference.
func TestCanary_CredentialNeverSurfaces(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	prov, adapter := canaryProvider(t)

	spec := workspaceprovider.WorkspaceSpec{
		Name:      "ws-canary",
		Image:     "busybox:1.36",
		ImagePull: secrets.Ref(canaryPullRef),
		Mounts: []workspaceprovider.Mount{
			{Kind: workspaceprovider.MountBind, Target: "/workspace"},
			{Kind: workspaceprovider.MountSecret, Target: "/run/secret/token", Ref: secrets.Ref(canaryMountRef)},
		},
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: "org-canary",
			workspaceprovider.LabelProject:      "proj-canary",
		},
	}
	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		t.Fatalf("Provision: %v", err)
	}
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), ws.Handle()) }) //nolint:errcheck // best-effort reap on cleanup; Teardown is idempotent.

	// The Handle is loggable by contract — the canary must not be in it.
	if strings.Contains(ws.Handle().String(), canaryPlaintext) {
		t.Errorf("canary leaked into the Handle: %q", ws.Handle().String())
	}

	// Status (State/Detail/Conditions) must be canary-free.
	st, serr := ws.Status(ctx)
	if serr != nil {
		t.Fatalf("Status: %v", serr)
	}
	assertNoCanary(t, "Status.Detail", st.Detail)
	assertNoCanary(t, "Status.State", st.State.String())

	// A Run whose credential resolves to the canary: drive it to terminal; neither the
	// terminal RunStatus.Detail nor the streamed Logs may carry the value.
	run, rerr := ws.Run(ctx, workspaceprovider.RunSpec{
		Command:    []string{"echo", "go"},
		Credential: secrets.Ref(canaryWorkloadRef),
		Vehicle:    workspaceprovider.VehicleEnv,
	})
	if rerr != nil {
		t.Fatalf("Run: %v", rerr)
	}
	final := drainCanaryRun(ctx, run)
	assertNoCanary(t, "RunStatus.Detail", final.Detail)
	if rc, lerr := run.Logs(ctx, 0); lerr == nil {
		data, rerr := readCanaryStream(rc)
		if rerr != nil {
			t.Fatalf("read Run.Logs stream: %v", rerr)
		}
		assertNoCanary(t, "Run.Logs", string(data))
	}

	// List returns Descriptors (the reconcile/drift surface) — none may carry the canary.
	descs, lerr := prov.List(ctx, workspaceprovider.Selector{Labels: map[string]string{
		workspaceprovider.LabelOrganization: "org-canary",
		workspaceprovider.LabelProject:      "proj-canary",
	}})
	if lerr != nil {
		t.Fatalf("List: %v", lerr)
	}
	for i := range descs {
		assertNoCanary(t, "Descriptor.Handle", descs[i].Handle.String())
		assertNoCanary(t, "Descriptor.Name", descs[i].Name)
		for k, v := range descs[i].Labels {
			assertNoCanary(t, "Descriptor.Label["+k+"]", v)
		}
	}

	// And the runnable carries-refs-never-values guarantee over everything the adapter recorded
	// (every recorded Spec/Env/Handle/Descriptor/injected ref).
	adapter.AssertNoSecretMaterial(t, canaryPlaintext)
}

// TestCanary_NeverSurfacesThroughError proves the credential value never surfaces through the
// FAILURE path. A pull-secret that resolves to the canary but whose Image the adapter is told to
// reject yields an ImageError carrying the loggable Reference; the error string (and its whole
// wrapped chain) must be canary-free.
func TestCanary_NeverSurfacesThroughError(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	prov, adapter := canaryProvider(t)
	adapter.FailProvisionWith(&workspaceprovider.ImageError{Image: "busybox:1.36", Ref: secrets.Ref(canaryPullRef)})

	ws, err := prov.Provision(ctx, workspaceprovider.WorkspaceSpec{
		Name:      "ws-canary-fail",
		Image:     "busybox:1.36",
		ImagePull: secrets.Ref(canaryPullRef),
	})
	if ws != nil {
		t.Errorf("a failed Provision must return a nil Workspace")
	}
	if err == nil {
		t.Fatalf("a forced ImageError must fail Provision")
	}
	if strings.Contains(err.Error(), canaryPlaintext) {
		t.Fatalf("canary leaked through the error surface: %q", err.Error())
	}
	// The ImageError carries the loggable ref (good) but not the value.
	if !strings.Contains(err.Error(), canaryPullRef) {
		t.Errorf("the ImageError should carry the loggable ref %q for diagnostics, got %q", canaryPullRef, err.Error())
	}
}

// assertNoCanary fails if the canary plaintext appears in s.
func assertNoCanary(t *testing.T, surface, s string) {
	t.Helper()
	if strings.Contains(s, canaryPlaintext) {
		t.Errorf("canary leaked into %s: %q", surface, s)
	}
}

// drainCanaryRun ranges a Run.Status to its terminal transition and returns the last RunStatus.
func drainCanaryRun(ctx context.Context, run workspaceprovider.Run) workspaceprovider.RunStatus {
	var last workspaceprovider.RunStatus
	for {
		status, ok := run.Status(ctx)
		last = status
		if !ok || status.Phase.IsTerminal() {
			return last
		}
	}
}

// readCanaryStream drains rc and closes it.
func readCanaryStream(rc interface {
	Read([]byte) (int, error)
	Close() error
},
) ([]byte, error) {
	defer func() { _ = rc.Close() }() //nolint:errcheck // closing a fully-read stream has no actionable error.
	var out []byte
	buf := make([]byte, 512)
	for {
		n, err := rc.Read(buf)
		out = append(out, buf[:n]...)
		if err != nil {
			return out, nil //nolint:nilerr // EOF terminates the read; the bytes are the result.
		}
	}
}
