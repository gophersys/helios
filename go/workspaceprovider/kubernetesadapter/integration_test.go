//go:build integration

// Package kubernetesadapter_test's integration suite runs against a REAL ephemeral kubernetes
// cluster (ADR-0016 §2: conformance is never a mock). It is gated behind the `integration`
// build tag so the default `go test` (and the pre-commit hook) stays fast; run it explicitly:
//
//	go test -tags integration ./kubernetesadapter/... -count=1
//
// Every test stands up an ACTUAL k3d cluster (k3s-in-docker — the DEFAULT distro, ADR-0016 §4)
// under a UNIQUE name (eden-wp-<tool>-<ts>-<n>) and DELETES THE WHOLE CLUSTER on t.Cleanup (on
// failure too), so parallel or abandoned runs never collide and a leaked cluster is impossible.
// The SAME workspaceprovidertest.ProviderSuite the docker adapter passes runs here against the
// kubernetes adapter — that the identical suite is green on docker AND k3d IS the
// distro-transparency proof (05 §3/§6, ADR-0012 "zero special code paths").
package kubernetesadapter_test

import (
	"bytes"
	"context"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	edentesting "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/kubernetesadapter"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// testImage is a tiny, ubiquitous image the integration tests provision. It is pre-imported
// into the cluster nodes once by the harness so per-test pod provisions are fast and
// offline-safe after the first run.
const testImage = "busybox:1.36"

// TestK3d_Conforms runs THE one ProviderSuite over the REAL kubernetes adapter on an ephemeral
// k3d cluster (ADR-0016 §4: the same suite the in-memory fake and the docker adapter pass, now
// against an actual cluster). The K3dCluster harness `k3d cluster delete`s the cluster on
// t.Cleanup. This is the k3d binding of the four (fake + docker + k3d + kind).
//
// SERIAL BY DESIGN (no t.Parallel): a real cluster conformance is heavy (a full 17-case suite
// against a k3d cluster). Running it in PARALLEL with TestKind_Conforms stood up TWO real clusters
// serving the suite at once, and the contention tipped the k3d serverlb into "connection refused"
// mid-run (apiserver unreachable) — a real-substrate reliability flake, not a code defect (the same
// cases pass on docker AND kind). One heavyweight cluster conformance at a time keeps the integration
// lane reliable; the ~50s a serial second cluster costs is worth it.
//
//nolint:paralleltest // serial by design — see the doc comment above (two real clusters at once flaked the k3d serverlb).
func TestK3d_Conforms(t *testing.T) {
	adapter := workspaceprovidertest.K3dCluster(t, workspaceprovidertest.WithImages(testImage))
	workspaceprovidertest.RunProviderSuite(t, func(_ context.Context, _ edentesting.Harness) (workspaceprovider.Adapter, error) {
		return adapter, nil
	})
}

// TestKind_Conforms runs THE one ProviderSuite over the REAL kubernetes adapter on an ephemeral
// kind cluster (the SECOND conformance target, ADR-0016 §4). The SAME suite green on k3d AND
// kind is the EMPIRICAL distro-transparency proof — one adapter, two distros, identical code
// path, divergence visible ONLY as declared CapStatus (ADR-0012). The KindCluster harness
// `kind delete cluster`s it on t.Cleanup. SKIPS when kind/docker is unavailable.
//
// SERIAL BY DESIGN (no t.Parallel), like TestK3d_Conforms: the two heavyweight cluster conformances
// must not stand up two real clusters serving the full suite at once — that contention caused a k3d
// apiserver "connection refused" flake. One cluster at a time keeps the lane reliable.
//
//nolint:paralleltest // serial by design — see TestK3d_Conforms (two real clusters at once flaked the k3d serverlb).
func TestKind_Conforms(t *testing.T) {
	adapter := workspaceprovidertest.KindCluster(t, workspaceprovidertest.WithImages(testImage))
	workspaceprovidertest.RunProviderSuite(t, func(_ context.Context, _ edentesting.Harness) (workspaceprovider.Adapter, error) {
		return adapter, nil
	})
}

// TestK3d_ProvisionRunExecFilesTeardown drives the FULL workload plane against a real pod
// end-to-end: provision -> Exec -> Files round-trip -> Run to terminal -> Status -> Teardown ->
// no orphan namespace. It is the concrete "exercise the port (run/exec/mount per contract)" the
// brief requires, distinct from the suite so the apiserver path is asserted directly.
//
//nolint:gocognit,cyclop,paralleltest // a deliberate linear real-cluster end-to-end walk over one pod; serial by design (spins a real cluster).
func TestK3d_ProvisionRunExecFilesTeardown(t *testing.T) {
	adapter := workspaceprovidertest.K3dCluster(t, workspaceprovidertest.WithImages(testImage))
	prov := newProvider(t, adapter)
	ctx := t.Context()

	spec := workspaceprovider.WorkspaceSpec{
		Name:      "ws-e2e",
		Substrate: workspaceprovider.SubstrateKubernetes,
		Image:     testImage,
		Mounts:    []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/workspace"}},
		Resources: workspaceprovider.Resources{CPUMilli: 250, MemoryBytes: 128 << 20},
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: "org-e2e",
			workspaceprovider.LabelProject:      "proj-e2e",
		},
	}

	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		t.Fatalf("Provision against real k3d: %v", err)
	}
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), ws.Handle()) }) //nolint:errcheck // best-effort cleanup teardown; Teardown is idempotent and the harness reaps the cluster regardless.

	// Status: the real pod reports a normalized State.
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
	res, eerr := ws.Exec(ctx, workspaceprovider.ExecSpec{Command: []string{"echo", "hello-from-k3d"}, Stdout: &out, Timeout: 60 * time.Second})
	if eerr != nil {
		t.Fatalf("Exec: %v", eerr)
	}
	if res.ExitCode != 0 {
		t.Errorf("Exec exit code = %d, want 0", res.ExitCode)
	}
	if got := bytes.TrimSpace(out.Bytes()); string(got) != "hello-from-k3d" {
		t.Errorf("Exec stdout = %q, want hello-from-k3d", got)
	}

	// A non-zero command surfaces its real exit code.
	failRes, ferr := ws.Exec(ctx, workspaceprovider.ExecSpec{Command: []string{"sh", "-c", "exit 7"}, Timeout: 60 * time.Second})
	if ferr != nil {
		t.Fatalf("Exec(exit 7): %v", ferr)
	}
	if failRes.ExitCode != 7 {
		t.Errorf("Exec(exit 7) exit code = %d, want 7", failRes.ExitCode)
	}

	// Files: Put then Get round-trips through the real tar-over-exec plane.
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

	// Teardown reclaims the namespace; Open then yields NotFoundError; no orphan namespace.
	if terr := prov.Teardown(ctx, ws.Handle()); terr != nil {
		t.Fatalf("Teardown: %v", terr)
	}
	if _, oerr := prov.Open(ctx, ws.Handle()); oerr == nil {
		t.Errorf("Open after Teardown: expected NotFoundError, got nil")
	}
	if owner, ok := adapter.(*kubernetesadapter.Adapter); ok {
		if owned, cerr := owner.CountOwned(ctx); cerr != nil {
			t.Errorf("CountOwned: %v", cerr)
		} else if owned != 0 {
			t.Errorf("Teardown left %d orphaned namespace(s)", owned)
		}
	}
}

// TestK3d_PrivateImagePullSecret proves the B7 fix on a REAL cluster against a REAL authenticated
// registry: it spins a registry:2 with htpasswd auth, pushes a tiny PRIVATE image, JOINS the k3d
// node containers to the registry's docker network (so an in-cluster pod can reach it), then
// asserts (a) provisioning WITH the resolved pull-secret SUCCEEDS — the kubelet authenticated the
// pull via the dockerconfigjson Secret the adapter created and the Pod.Spec.ImagePullSecrets it
// wired — and the Secret type + ImagePullSecrets objects ARE present on the cluster; and (b)
// provisioning the SAME private image WITHOUT a pull-secret FAILS with an ImageError carrying the
// ref, never the value. No mock. SKIPS when k3d/docker/htpasswd is unavailable.
//
//nolint:gocognit,cyclop,paralleltest // a deliberate linear real-cluster + real-registry end-to-end walk; serial by design.
func TestK3d_PrivateImagePullSecret(t *testing.T) {
	adapter, registry := workspaceprovidertest.K3dClusterWithRegistry(t, testImage, workspaceprovidertest.WithImages(testImage))
	ctx := t.Context()

	const pullSecretRef = "private-registry-password"
	prov := newProviderWithSecrets(t, adapter, map[string]string{pullSecretRef: registry.Password})

	// (a) WITH the pull-secret: the authenticated in-cluster pull SUCCEEDS and the pod is Ready.
	withSecret := workspaceprovider.WorkspaceSpec{
		Name:      "ws-private-ok",
		Substrate: workspaceprovider.SubstrateKubernetes,
		Image:     registry.ClusterReference(),
		ImagePull: secrets.Ref(pullSecretRef),
	}
	ws, err := prov.Provision(ctx, withSecret)
	if err != nil {
		t.Fatalf("Provision of a private image WITH the pull-secret must succeed, got: %v", err)
	}
	t.Cleanup(func() { _ = prov.Teardown(context.WithoutCancel(ctx), ws.Handle()) }) //nolint:errcheck // best-effort cleanup; Teardown is idempotent and the harness reaps the cluster regardless.

	// Assert the dockerconfigjson Secret + ImagePullSecrets objects ARE on the cluster (the B7
	// fix's concrete artifacts — substitutable with the docker adapter's registryAuth).
	if owner, ok := adapter.(*kubernetesadapter.Adapter); ok {
		pullSecrets, psErr := owner.ImagePullSecretsForTest(ctx, ws.Handle())
		if psErr != nil {
			t.Errorf("read Pod.Spec.ImagePullSecrets: %v", psErr)
		} else if len(pullSecrets) == 0 {
			t.Errorf("the pod has no ImagePullSecrets (B7: the kubernetes adapter did not wire the pull-secret)")
		}
		secretType, stErr := owner.PullSecretTypeForTest(ctx, ws.Handle())
		if stErr != nil {
			t.Errorf("read pull-secret type: %v", stErr)
		} else if secretType != "kubernetes.io/dockerconfigjson" {
			t.Errorf("pull-secret type = %q, want kubernetes.io/dockerconfigjson", secretType)
		}
	}

	// (b) WITHOUT the pull-secret: the unauthenticated in-cluster pull is DENIED → ImageError, and
	// the error carries the ref/image, NEVER the password.
	withoutSecret := workspaceprovider.WorkspaceSpec{
		Name:      "ws-private-denied",
		Substrate: workspaceprovider.SubstrateKubernetes,
		Image:     registry.ClusterReference(),
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
