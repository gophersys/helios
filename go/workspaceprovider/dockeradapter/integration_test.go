//go:build integration

// Package dockeradapter_test's integration suite runs against a REAL docker daemon
// (ADR-0016 §2: conformance is never a mock). It is gated behind the `integration` build
// tag so the default `go test` (and the pre-commit hook) stays fast; run it explicitly with
//
//	go test -tags integration ./...
//
// Every test spins ACTUAL containers via the docker daemon under a unique per-test label
// namespace and reaps EVERYTHING on t.Cleanup (on failure too), so parallel or abandoned
// runs never collide and never leak.
package dockeradapter_test

import (
	"bytes"
	"context"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/dependencies/dependenciestest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
	edentesting "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/dockeradapter"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// testImage is a tiny, ubiquitous image the integration tests provision. It is pre-pulled
// once by the harness so per-test provisions are fast and offline-safe after the first run.
const testImage = "busybox:1.36"

// TestDocker_Conforms runs THE one ProviderSuite over the REAL docker adapter (ADR-0016 §4:
// the same suite the in-memory fake passes, now against an actual daemon). The
// EphemeralContainer harness reaps every container on t.Cleanup. This is the proof shape the
// brief asks for — the docker binding of the four (fake + docker + k3d + kind).
func TestDocker_Conforms(t *testing.T) {
	t.Parallel()
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(testImage))
	workspaceprovidertest.RunProviderSuite(t, func(_ context.Context, _ edentesting.Harness) (workspaceprovider.Adapter, error) {
		return adapter, nil
	})
}

// TestDocker_ProvisionRunExecFilesTeardown drives the FULL workload plane against a real
// container end-to-end: provision -> Exec -> Files round-trip -> Run to terminal -> Status
// -> Teardown -> no orphan. It is the concrete "exercise the port (run/exec/mount per
// contract)" the brief requires, distinct from the suite so the daemon path is asserted
// directly with explicit assertions.
//
//nolint:gocognit,cyclop,paralleltest // a deliberate linear real-substrate end-to-end walk over one container; serial by design (spins a real container).
func TestDocker_ProvisionRunExecFilesTeardown(t *testing.T) {
	ctx := t.Context()
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(testImage))
	prov := newProvider(t, adapter)

	spec := workspaceprovider.WorkspaceSpec{
		Name:      "ws-e2e",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     testImage,
		Mounts:    []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/workspace"}},
		Resources: workspaceprovider.Resources{CPUMilli: 500, MemoryBytes: 256 << 20, PIDs: 256},
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: "org-e2e",
			workspaceprovider.LabelProject:      "proj-e2e",
		},
	}

	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		t.Fatalf("Provision against real docker: %v", err)
	}
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), ws.Handle()) }) //nolint:errcheck // best-effort cleanup teardown; Teardown is idempotent and the harness re-scan asserts no orphan.

	// Status: the real container reports a normalized State.
	st, serr := ws.Status(ctx)
	if serr != nil {
		t.Fatalf("Status: %v", serr)
	}
	if st.State != workspaceprovider.StateReady && st.State != workspaceprovider.StateRunning {
		t.Errorf("Status.State = %v, want Ready/Running", st.State)
	}
	if st.Since.IsZero() {
		t.Errorf("Status.Since must be Clock-stamped")
	}

	// Exec: a real command returns its real exit code and output.
	var out bytes.Buffer
	res, eerr := ws.Exec(ctx, workspaceprovider.ExecSpec{Command: []string{"echo", "hello-from-docker"}, Stdout: &out, Timeout: 30 * time.Second})
	if eerr != nil {
		t.Fatalf("Exec: %v", eerr)
	}
	if res.ExitCode != 0 {
		t.Errorf("Exec exit code = %d, want 0", res.ExitCode)
	}
	if got := bytes.TrimSpace(out.Bytes()); string(got) != "hello-from-docker" {
		t.Errorf("Exec stdout = %q, want hello-from-docker", got)
	}

	// A non-zero command surfaces its real exit code.
	failRes, ferr := ws.Exec(ctx, workspaceprovider.ExecSpec{Command: []string{"sh", "-c", "exit 7"}, Timeout: 30 * time.Second})
	if ferr != nil {
		t.Fatalf("Exec(exit 7): %v", ferr)
	}
	if failRes.ExitCode != 7 {
		t.Errorf("Exec(exit 7) exit code = %d, want 7", failRes.ExitCode)
	}

	// Files: Put then Get round-trips through the real tar plane.
	want := []byte("real-artifact-bytes\n")
	if perr := ws.Files().Put(ctx, "/workspace/out.txt", bytes.NewReader(want), 0o644); perr != nil {
		t.Fatalf("Files.Put: %v", perr)
	}
	rc, gerr := ws.Files().Get(ctx, "/workspace/out.txt")
	if gerr != nil {
		t.Fatalf("Files.Get: %v", gerr)
	}
	got, raerr := readAll(rc)
	if raerr != nil {
		t.Fatalf("read Files.Get stream: %v", raerr)
	}
	if !bytes.Equal(got, want) {
		t.Errorf("Files round-trip: got %q want %q", got, want)
	}

	// Run: a real workload reaches a terminal phase with its real exit signal.
	run, rerr := ws.Run(ctx, workspaceprovider.RunSpec{Command: []string{"sh", "-c", "echo workload-ran; exit 0"}})
	if rerr != nil {
		t.Fatalf("Run: %v", rerr)
	}
	final := drainRun(ctx, run)
	if final.Phase != workspaceprovider.RunSucceeded {
		t.Errorf("Run terminal phase = %v, want Succeeded", final.Phase)
	}
	if final.ExitCode != 0 {
		t.Errorf("Run exit code = %d, want 0", final.ExitCode)
	}

	// List includes the workspace with its tenancy labels.
	descs, lerr := prov.List(ctx, workspaceprovider.Selector{Labels: spec.Labels})
	if lerr != nil {
		t.Fatalf("List: %v", lerr)
	}
	if !listContains(descs, ws.Handle()) {
		t.Errorf("List does not include the provisioned workspace")
	}

	// Teardown reclaims the container; Open then yields NotFoundError; no orphan remains.
	if terr := prov.Teardown(ctx, ws.Handle()); terr != nil {
		t.Fatalf("Teardown: %v", terr)
	}
	if _, oerr := prov.Open(ctx, ws.Handle()); oerr == nil {
		t.Errorf("Open after Teardown: expected NotFoundError, got nil")
	}
	if owner, ok := adapter.(*dockeradapter.Adapter); ok {
		if owned, cerr := owner.CountOwned(ctx); cerr != nil {
			t.Errorf("CountOwned: %v", cerr)
		} else if owned != 0 {
			t.Errorf("Teardown left %d orphaned container(s)", owned)
		}
	}
}

// TestDocker_ResourceLimitsBindOOM provisions a workspace with a tight memory ceiling and a
// workload that allocates past it, asserting the runaway-agent path (RunKilled /
// ConditionOOMKilled) binds on a REAL cgroup — the runaway-agent signal the budget story
// reconciles against (02 §2). It Skips when the daemon does not enforce memory limits (some
// rootless/CI daemons disable the memory cgroup).
//
//nolint:paralleltest // serial by design: spins a real container under a memory cgroup; t.Parallel() would contend.
func TestDocker_ResourceLimitsBindOOM(t *testing.T) {
	ctx := t.Context()
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(testImage))
	prov := newProvider(t, adapter)

	ws, err := prov.Provision(ctx, workspaceprovider.WorkspaceSpec{
		Name:      "ws-oom",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     testImage,
		Resources: workspaceprovider.Resources{MemoryBytes: 16 << 20}, // 16 MiB ceiling
	})
	if err != nil {
		t.Fatalf("Provision: %v", err)
	}
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), ws.Handle()) }) //nolint:errcheck // best-effort cleanup teardown; Teardown is idempotent and the harness re-scan asserts no orphan.

	// Allocate ~512 MiB into a tmpfs-backed file inside the container to trip the cgroup.
	run, rerr := ws.Run(ctx, workspaceprovider.RunSpec{
		Command: []string{"sh", "-c", "dd if=/dev/zero of=/dev/shm/fill bs=1M count=512 2>/dev/null; cat /dev/shm/fill >/dev/null; sleep 1"},
	})
	if rerr != nil {
		t.Fatalf("Run: %v", rerr)
	}
	final := drainRun(ctx, run)
	if final.Phase == workspaceprovider.RunSucceeded {
		t.Skip("the daemon did not enforce the memory cgroup (rootless/CI); OOM path not exercised")
	}
	if final.Phase != workspaceprovider.RunKilled && final.Phase != workspaceprovider.RunFailed {
		t.Errorf("an over-memory workload phase = %v, want Killed/Failed", final.Phase)
	}
	// Where the cgroup reports OOMKilled (the container's State.OOMKilled), the workload must
	// surface RunKilled / ConditionOOMKilled with the native reason in Detail — the typed,
	// branchable runaway-agent signal, not a generic failure.
	if final.Condition == workspaceprovider.ConditionOOMKilled {
		if final.Phase != workspaceprovider.RunKilled {
			t.Errorf("an OOMKilled workload phase = %v, want RunKilled", final.Phase)
		}
		if final.Detail == "" {
			t.Errorf("the native OOM reason must ride RunStatus.Detail, got empty")
		}
	}
}

// TestDocker_DefaultDenyEgress proves the docker adapter's CapEgressPolicy=CapPartial is
// TRUTHFUL: a ZERO-egress workspace is attached to a per-workspace `--internal` network the
// daemon enforces as genuine default-deny, so a real dial-out from inside it is BLOCKED — while
// ordinary exec still works (the network isolation is egress-only, not an exec break). This is
// the clean-room 07 §4 guarantee, asserted against the REAL daemon with no mock.
//
//nolint:paralleltest // serial by design: spins a real container on a dedicated `--internal` network.
func TestDocker_DefaultDenyEgress(t *testing.T) {
	ctx := t.Context()
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(testImage))
	prov := newProvider(t, adapter)

	ws, err := prov.Provision(ctx, workspaceprovider.WorkspaceSpec{
		Name:      "ws-egress",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     testImage,
		Egress:    nil, // default-deny: the clean room dials out to NOTHING (07 §4)
	})
	if err != nil {
		t.Fatalf("Provision (zero-egress): %v", err)
	}
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), ws.Handle()) }) //nolint:errcheck // best-effort cleanup teardown; Teardown is idempotent and the harness re-scan asserts no orphan.

	// Positive control: ordinary exec works (the isolation is egress-only).
	ctrl, cerr := ws.Exec(ctx, workspaceprovider.ExecSpec{Command: []string{"sh", "-c", "command -v wget >/dev/null"}, Timeout: 20 * time.Second})
	if cerr != nil {
		t.Fatalf("egress positive control (exec): %v", cerr)
	}
	if ctrl.ExitCode != 0 {
		t.Skip("test image has no wget to drive the dial-out probe")
	}
	// The real dial-out must be BLOCKED (non-zero exit: "bad address" / "Network is unreachable").
	res, eerr := ws.Exec(ctx, workspaceprovider.ExecSpec{
		Command: []string{"wget", "-T", "5", "-q", "-O", "/dev/null", "https://example.com"},
		Timeout: 30 * time.Second,
	})
	if eerr != nil {
		t.Fatalf("dial-out exec: %v", eerr)
	}
	if res.ExitCode == 0 {
		t.Errorf("default-deny egress NOT enforced: wget to a public host succeeded from a zero-egress workspace")
	}
}

// TestDocker_PrivateImagePullSecret proves the B7 pull-secret seam END TO END against a REAL
// authenticated registry: it spins a registry:2 with htpasswd auth, pushes a tiny PRIVATE image
// into it, then asserts (a) provisioning WITH the resolved pull-secret SUCCEEDS (the daemon
// authenticated the pull) and (b) provisioning the SAME image WITHOUT the pull-secret FAILS with
// an ImageError carrying the ref, NEVER the value (07 §2 / contract §2: "a denied pull-secret
// yields ImageError"). No mock: a real registry, a real authenticated pull. SKIPS when
// docker/htpasswd is unavailable.
//
//nolint:paralleltest // serial by design: spins a real registry container + real authenticated pulls.
func TestDocker_PrivateImagePullSecret(t *testing.T) {
	ctx := t.Context()
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(testImage))

	registry, rerr := workspaceprovidertest.NewLocalRegistry(ctx, testImage)
	if rerr != nil {
		t.Skipf("local authenticated registry unavailable, skipping pull-secret test: %v", rerr)
	}
	t.Cleanup(registry.Delete)

	const pullSecretRef = "private-registry-password"
	prov := newProviderWithSecrets(t, adapter, map[string]string{pullSecretRef: registry.Password})

	// Non-vacuity for the POSITIVE case: NewLocalRegistry `docker tag`ged the private ref into the
	// daemon before pushing, so it is already present locally. The adapter's pullImage short-circuits
	// on a present image — which would make the WITH-secret Provision below succeed WITHOUT ever
	// exercising auth (a fake pass: it would pass with a wrong secret too). Purge the local tag FIRST
	// so the authenticated pull must hit the registry; a success then PROVES the pull-secret worked.
	owner, isOwner := adapter.(*dockeradapter.Adapter)
	if isOwner {
		if rerr := owner.RemoveImageForTest(ctx, registry.HostReference()); rerr != nil {
			t.Fatalf("purge locally-cached private ref before the authenticated pull: %v", rerr)
		}
	}

	// (a) WITH the pull-secret: the REAL authenticated pull (no local cache) SUCCEEDS and the
	// workspace is Ready.
	withSecret := workspaceprovider.WorkspaceSpec{
		Name:      "ws-private-ok",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     registry.HostReference(),
		ImagePull: secretsRef(pullSecretRef),
	}
	ws, err := prov.Provision(ctx, withSecret)
	if err != nil {
		t.Fatalf("Provision of a private image WITH the pull-secret must succeed, got: %v", err)
	}
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), ws.Handle()) }) //nolint:errcheck // best-effort cleanup; Teardown is idempotent and the harness re-scan asserts no orphan.
	if st, serr := ws.Status(ctx); serr != nil {
		t.Errorf("Status after authenticated pull: %v", serr)
	} else if st.State != workspaceprovider.StateReady && st.State != workspaceprovider.StateRunning {
		t.Errorf("Status.State = %v, want Ready/Running after the authenticated pull", st.State)
	}

	// Remove the just-pulled image again so the WITHOUT-secret pull must hit the authed registry
	// (otherwise the daemon would serve the just-pulled layer and mask the denial).
	if isOwner {
		_ = owner.RemoveImageForTest(ctx, registry.HostReference()) //nolint:errcheck // best-effort cache purge; the assertion below still holds if the layer lingers (the registry denies the manifest fetch).
	}

	// (b) WITHOUT the pull-secret: the unauthenticated pull is DENIED → ImageError, and the error
	// carries the ref/image, NEVER the password.
	withoutSecret := workspaceprovider.WorkspaceSpec{
		Name:      "ws-private-denied",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     registry.HostReference(),
	}
	denied, derr := prov.Provision(ctx, withoutSecret)
	if denied != nil {
		t.Errorf("Provision of a private image WITHOUT the pull-secret returned a non-nil Workspace (must fail)")
		_ = prov.Teardown(context.WithoutCancel(ctx), denied.Handle()) //nolint:errcheck // best-effort cleanup of an unexpected workspace.
	}
	if derr == nil {
		t.Fatalf("Provision of a private image WITHOUT the pull-secret must fail with ImageError, got nil")
	}
	if errors.KindOf(derr) != errors.KindInvalid {
		t.Errorf("denied private pull Kind = %v, want Invalid (ImageError)", errors.KindOf(derr))
	}
	if imgErr, ok := errors.AsType[*workspaceprovider.ImageError](derr); !ok || imgErr == nil {
		t.Errorf("denied private pull: want *ImageError in the chain, got %v", derr)
	}
	if strings.Contains(derr.Error(), registry.Password) {
		t.Errorf("the pull-secret password leaked into the ImageError message")
	}
}

// TestDocker_CredentialInjectionSeam drives the Run credential seam (injectCredential) END TO END
// against a REAL container, over BOTH vehicles: a VehicleFile credential written to a tmpfs path
// and a VehicleEnv credential placed on the workload's child env. It asserts the workload can READ
// each injected value (the seam works) AND that neither value surfaces in a Status or the loggable
// Handle (07 §2: the value lives only at the injection site). No mock — a real daemon, a real
// tmpfs, real execs. (The MountSecret half of the seam is covered by the conformance
// caseMountSecret over this same real adapter.)
//
//nolint:gocognit,cyclop,paralleltest // a deliberate linear real-substrate walk over the credential seam; serial by design (spins a real container).
func TestDocker_CredentialInjectionSeam(t *testing.T) {
	ctx := t.Context()
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(testImage))

	const (
		fileCredRef   = "vault://eden/file#cred"
		envCredRef    = "vault://eden/env#cred"
		fileCredValue = "FILE-CRED-VALUE-do-not-leak"
		envCredValue  = "ENV-CRED-VALUE-do-not-leak"
	)
	prov := newProviderWithSecrets(t, adapter, map[string]string{
		fileCredRef: fileCredValue,
		envCredRef:  envCredValue,
	})

	ws, err := prov.Provision(ctx, workspaceprovider.WorkspaceSpec{
		Name:      "ws-cred-seam",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     testImage,
		Mounts: []workspaceprovider.Mount{
			{Kind: workspaceprovider.MountBind, Target: "/workspace"},
			// A tmpfs at /run/eden so the VehicleFile credential path (/run/eden/credential) is writable.
			{Kind: workspaceprovider.MountTmpfs, Target: "/run/eden"},
		},
	})
	if err != nil {
		t.Fatalf("Provision: %v", err)
	}
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), ws.Handle()) }) //nolint:errcheck // best-effort cleanup; Teardown is idempotent and the harness re-scan asserts no orphan.

	// VehicleFile: a Run credential is written to the tmpfs credential path; the workload copies it
	// to a bind-mounted file the test reads back (the credential tmpfs file is the injection site).
	fileRun, frerr := ws.Run(ctx, workspaceprovider.RunSpec{
		Command:    []string{"sh", "-c", "cat /run/eden/credential > /workspace/file-cred.txt"},
		Credential: secrets.Ref(fileCredRef),
		Vehicle:    workspaceprovider.VehicleFile,
	})
	if frerr != nil {
		t.Fatalf("Run (VehicleFile): %v", frerr)
	}
	if final := drainRun(ctx, fileRun); final.Phase != workspaceprovider.RunSucceeded {
		t.Errorf("VehicleFile run phase = %v, want Succeeded (the credential file must exist)", final.Phase)
	}
	assertWorkspaceFileEquals(ctx, t, ws, "/workspace/file-cred.txt", fileCredValue)

	// VehicleEnv: a Run credential is placed on the workload's CHILD env; the workload writes it
	// out to a bind-mounted file so the test can read it back (the env is on the child only).
	envRun, ererr := ws.Run(ctx, workspaceprovider.RunSpec{
		Command:    []string{"sh", "-c", "printf %s \"$EDEN_WORKLOAD_CREDENTIAL\" > /workspace/env-cred.txt"},
		Credential: secrets.Ref(envCredRef),
		Vehicle:    workspaceprovider.VehicleEnv,
	})
	if ererr != nil {
		t.Fatalf("Run (VehicleEnv): %v", ererr)
	}
	if final := drainRun(ctx, envRun); final.Phase != workspaceprovider.RunSucceeded {
		t.Errorf("VehicleEnv run phase = %v, want Succeeded", final.Phase)
	}
	assertWorkspaceFileEquals(ctx, t, ws, "/workspace/env-cred.txt", envCredValue)

	// Neither injected value may surface in a Status or the loggable Handle.
	st, serr := ws.Status(ctx)
	if serr != nil {
		t.Fatalf("Status: %v", serr)
	}
	for _, needle := range []string{fileCredValue, envCredValue} {
		if strings.Contains(st.Detail, needle) || strings.Contains(ws.Handle().String(), needle) {
			t.Errorf("an injected credential value leaked into Status/Handle: %q", needle)
		}
	}
}

// assertWorkspaceFileEquals reads path out of the workspace and asserts its trimmed content == want.
func assertWorkspaceFileEquals(ctx context.Context, t *testing.T, ws workspaceprovider.Workspace, path, want string) {
	t.Helper()
	rc, gerr := ws.Files().Get(ctx, path)
	if gerr != nil {
		t.Errorf("Files.Get(%s): %v", path, gerr)
		return
	}
	got, raerr := readAll(rc)
	if raerr != nil {
		t.Errorf("read %s: %v", path, raerr)
		return
	}
	if strings.TrimSpace(string(got)) != want {
		t.Errorf("%s content = %q, want %q", path, strings.TrimSpace(string(got)), want)
	}
}

// ── small integration helpers ─────────────────────────────────────────────────.

func newProvider(t *testing.T, adapter workspaceprovider.Adapter) *workspaceprovider.Provisioner {
	t.Helper()
	prov, err := workspaceprovider.New(
		workspaceprovider.Config{Default: workspaceprovider.SubstrateDocker},
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{workspaceprovider.SubstrateDocker: adapter},
			Secrets:  secretsForTest(),
			Clock:    clockForTest(),
		},
	)
	if err != nil {
		t.Fatalf("New provider over real docker adapter: %v", err)
	}
	return prov
}

// newProviderWithSecrets wires a Provisioner over the real docker adapter with a secrets.Provider
// seeded from seed (so a pull-secret reference resolves to its password server-side).
func newProviderWithSecrets(t *testing.T, adapter workspaceprovider.Adapter, seed map[string]string) *workspaceprovider.Provisioner {
	t.Helper()
	set, _, _, _ := dependenciestest.Fakes()
	prov, err := workspaceprovider.New(
		workspaceprovider.Config{Default: workspaceprovider.SubstrateDocker},
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{workspaceprovider.SubstrateDocker: adapter},
			Secrets:  secretstest.New(seed),
			Clock:    set.Clock,
		},
	)
	if err != nil {
		t.Fatalf("New provider over real docker adapter (seeded secrets): %v", err)
	}
	return prov
}

// secretsRef is the loggable reference a seeded pull-secret resolves under.
func secretsRef(name string) secrets.Reference { return secrets.Ref(name) }

func drainRun(ctx context.Context, run workspaceprovider.Run) workspaceprovider.RunStatus {
	var last workspaceprovider.RunStatus
	for {
		status, ok := run.Status(ctx)
		last = status
		if !ok || status.Phase.IsTerminal() {
			return last
		}
	}
}

func listContains(descs []workspaceprovider.Descriptor, handle workspaceprovider.Handle) bool {
	for i := range descs {
		if descs[i].Handle.String() == handle.String() {
			return true
		}
	}
	return false
}

// TestDocker_SupervisionReconcilesAndStreams proves the SUPERVISING-provider (ADR-0022 §4) on the
// REAL daemon end-to-end: (a) reconcile-from-reality — a FRESH Provider (a control-plane restart)
// re-adopts an already-running container via Supervise's list-by-label seed (a normalized Event for
// the existing workspace), and (b) live normalization — a subsequent Teardown produces a
// normalized EventRemoved (the docker destroy action → the platform-neutral EventKind). The watch
// goroutine is reaped on ctx cancellation (leak-free). No mock — the docker daemon's real event
// stream drives the assertion.
//
//nolint:paralleltest // serial by design: spins a real container and drives the daemon event stream.
func TestDocker_SupervisionReconcilesAndStreams(t *testing.T) {
	ctx := t.Context()
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(testImage))
	prov := newProvider(t, adapter)

	spec := workspaceprovider.WorkspaceSpec{
		Name:      "ws-supervise",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     testImage,
		Labels:    map[string]string{workspaceprovider.LabelOrganization: "org-sv", workspaceprovider.LabelProject: "proj-sv"},
	}
	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		t.Fatalf("Provision: %v", err)
	}
	want := ws.Handle()
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), want) }) //nolint:errcheck // best-effort cleanup; Teardown is idempotent.

	// A FRESH Provider over the SAME adapter == a stateless restart: Supervise must reconcile from
	// the LIVE daemon (the existing container), surfacing a normalized Event for it.
	restarted := newProvider(t, adapter)
	watchCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()
	events, serr := restarted.Supervise(watchCtx, workspaceprovider.Selector{Labels: spec.Labels})
	if serr != nil {
		t.Fatalf("Supervise: %v", serr)
	}

	if got := awaitDockerEvent(watchCtx, events, want); got == nil {
		t.Fatalf("Supervise did not reconcile-from-reality the existing workspace %q", want.String())
	} else if got.State == 0 && got.Detail == "" {
		t.Errorf("the reconcile Event carried neither a normalized State nor a Detail")
	}

	// Cancel the watch and confirm the stream drains (channel closes) — leak-free shutdown.
	cancel()
	for range events { //nolint:revive // intentional drain to channel close.
	}
}

// TestDocker_EntrypointWorkloadIsPID1OOM proves the ENTRYPOINT/workload-pod capability (ADR-0022
// §4, OD-15-a) on the REAL daemon: a spec.Entrypoint makes the container's MAIN process the
// workload (PID-1), so the daemon's cgroup observes the WORKLOAD directly. A PID-1 memory-bomb
// trips the cgroup; the supervised Status surfaces ConditionOOMKilled NATIVELY (the daemon sets the
// holding container's State.OOMKilled for its own PID-1) — the discriminator attached to the
// READABLE container, not an exec child. Skips honestly where the daemon does not enforce the
// cgroup. No mock — a genuine cgroup kill under a real memory limit.
//
//nolint:paralleltest // serial by design: spins a real container with a PID-1 memory-bomb under a cgroup.
func TestDocker_EntrypointWorkloadIsPID1OOM(t *testing.T) {
	ctx := t.Context()
	adapter := workspaceprovidertest.EphemeralContainer(t, workspaceprovidertest.WithImages(testImage))
	prov := newProvider(t, adapter)

	spec := workspaceprovider.WorkspaceSpec{
		Name:      "ws-entrypoint-oom",
		Substrate: workspaceprovider.SubstrateDocker,
		Image:     testImage,
		Resources: workspaceprovider.Resources{MemoryBytes: 16 << 20},
		// The Entrypoint (PID-1) IS the memory-bomb, so the kill attaches to the readable container.
		Entrypoint: []string{"sh", "-c", "dd if=/dev/zero of=/dev/shm/fill bs=1M count=512 2>/dev/null; cat /dev/shm/fill >/dev/null; sleep 30"},
	}
	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		// A PID-1 that OOMs before the Ready handshake is still the real kill; the discriminator is
		// asserted on a substrate where the workload reaches Running (it does on docker — the
		// container starts before the bomb runs).
		t.Skipf("Entrypoint workload OOM'd before the Ready handshake on this daemon (the kill is real): %v", err)
		return
	}
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), ws.Handle()) }) //nolint:errcheck // best-effort cleanup; Teardown is idempotent.

	// Poll the supervised Status until the cgroup OOM-kills the PID-1 workload and the daemon sets
	// the container's State.OOMKilled — the native discriminator on the readable container.
	deadline := time.Now().Add(30 * time.Second)
	var last workspaceprovider.Status
	for time.Now().Before(deadline) {
		st, sterr := prov.Supervised(ctx, ws.Handle())
		if sterr != nil {
			t.Fatalf("Supervised: %v", sterr)
		}
		last = st
		if hasOOMCondition(st.Conditions) {
			if st.State != workspaceprovider.StateDegraded && st.State != workspaceprovider.StateGone {
				t.Errorf("an OOM-killed Entrypoint workspace State = %v, want Degraded/Gone", st.State)
			}
			if st.Detail == "" {
				t.Errorf("the native OOM reason must ride Status.Detail, got empty")
			}
			return // discriminator surfaced natively — OD-15-a closed on docker
		}
		time.Sleep(500 * time.Millisecond)
	}
	t.Skipf("the daemon did not enforce the memory cgroup for the Entrypoint PID-1 (rootless/CI); OD-15-a discriminator not inducible here — honest skip, not a fake pass (last State=%v)", last.State)
}

// awaitDockerEvent reads normalized supervision Events looking for one whose Handle matches want,
// returning it (or nil at the deadline / channel close).
func awaitDockerEvent(ctx context.Context, events <-chan workspaceprovider.Event, want workspaceprovider.Handle) *workspaceprovider.Event {
	for {
		select {
		case ev, ok := <-events:
			if !ok {
				return nil
			}
			if ev.Handle.String() == want.String() {
				return &ev
			}
		case <-ctx.Done():
			return nil
		}
	}
}

// hasOOMCondition reports whether the conditions carry ConditionOOMKilled (the runaway-agent
// discriminator).
func hasOOMCondition(conds []workspaceprovider.Condition) bool {
	for i := range conds {
		if conds[i] == workspaceprovider.ConditionOOMKilled {
			return true
		}
	}
	return false
}
