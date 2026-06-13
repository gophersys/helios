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
	"testing"
	"time"

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
func TestK3d_Conforms(t *testing.T) {
	t.Parallel()
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
func TestKind_Conforms(t *testing.T) {
	t.Parallel()
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
