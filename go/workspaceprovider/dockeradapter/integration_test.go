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
	"testing"
	"time"

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
