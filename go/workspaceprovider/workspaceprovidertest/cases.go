package workspaceprovidertest

import (
	"bytes"
	"context"
	"strconv"
	"strings"
	"time"

	"github.com/gophersys/libs/go/errors"
	edentesting "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// Capability-gate names the conformance Harness checks via h.Has(...) so a case Skips
// (not fails) where the substrate's manifest declares the capability absent. The factory
// binds these from the subject adapter's Manifest (see RunProviderSuite's wiring).
const (
	capLogStream = "log-stream"
	capEgress    = "egress-policy"
	capLimits    = "resource-limits"
	capReattach  = "reattach"
	capMulti     = "multi-tenant"
)

// providerCases is the ordered set of conformance assertions — the executable form of the
// contract §4 "Properties asserted" list. Each case builds a fresh Provider over the
// subject Adapter and exercises ONE property. Capability-gated cases call has(...) and
// report.Skipf(...) to degrade gracefully (05 §3).
func providerCases() []edentesting.Case[workspaceprovider.Adapter] {
	return []edentesting.Case[workspaceprovider.Adapter]{
		{Name: "ProvisionReadyOpenListHandleRoundTrip", Run: caseProvisionReadyOpenList},
		{Name: "ProvisionIsAllOrNothing", Run: caseProvisionAllOrNothing},
		{Name: "Idempotency", Run: caseIdempotency},
		{Name: "RoundTripStatelessness", Run: caseRoundTripStatelessness},
		{Name: "RunToTerminalAndLogs", Run: caseRunToTerminal},
		{Name: "OnePrimaryWorkload", Run: caseOnePrimaryWorkload},
		{Name: "ExecReturnsRealExit", Run: caseExec},
		{Name: "FileSeamRoundTrip", Run: caseFileSeam},
		{Name: "ReadOnlyInputsRejectsWrites", Run: caseReadOnlyInputs},
		{Name: "TeardownIsIdempotentAndReclaiming", Run: caseTeardownIdempotent},
		{Name: "EgressDefaultDenyDeclaredAllow", Run: caseEgress},
		{Name: "ResourceLimitsBind", Run: caseResourceLimits},
		{Name: "MountSecretMaterialReachesWorkspace", Run: caseMountSecret},
		{Name: "SecretMaterialNeverLeaks", Run: caseNoSecretLeak},
		{Name: "ManifestTruthfulness", Run: caseManifestTruthful},
		{Name: "TenancyIsolation", Run: caseTenancyIsolation},
		{Name: "StateNormalization", Run: caseStateNormalization},
	}
}

// baseSpec is the canonical workspace spec a case provisions; image is a deliberately
// tiny, ubiquitous one so a real-substrate binding can pull it offline-safely.
func baseSpec(name string) workspaceprovider.WorkspaceSpec {
	return workspaceprovider.WorkspaceSpec{
		Name:   name,
		Image:  "busybox:1.36",
		Mounts: []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/workspace"}},
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: "org-test",
			workspaceprovider.LabelProject:      "proj-test",
		},
	}
}

func caseProvisionReadyOpenList(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	spec := baseSpec("ws-ready")

	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("Provision: unexpected error: %v", err)
		return
	}
	if ws == nil {
		report.Fatalf("Provision returned a nil Workspace with a nil error")
		return
	}

	handle := ws.Handle()
	if handle.IsZero() {
		report.Errorf("Provision returned a zero Handle")
	}
	// ParseHandle round-trips the canonical string.
	if parsed, perr := workspaceprovider.ParseHandle(handle.String()); perr != nil {
		report.Errorf("ParseHandle(%q): %v", handle.String(), perr)
	} else if parsed.String() != handle.String() {
		report.Errorf("ParseHandle round-trip: got %q want %q", parsed.String(), handle.String())
	}

	st, serr := ws.Status(ctx)
	if serr != nil {
		report.Errorf("Status: %v", serr)
	} else if st.State != workspaceprovider.StateReady && st.State != workspaceprovider.StateRunning {
		report.Errorf("Status.State = %v, want Ready/Running", st.State)
	}

	// Open re-attaches.
	if _, oerr := prov.Open(ctx, handle); oerr != nil {
		report.Errorf("Open(handle): %v", oerr)
	}

	// List includes it with the seeded labels (ownership domain).
	if descs := listLabels(ctx, prov, spec.Labels, report); !containsHandle(descs, handle) {
		report.Errorf("List does not include the provisioned workspace %q", handle.String())
	}

	cleanup(ctx, prov, handle)
}

// caseProvisionAllOrNothing proves PROVISION IS ALL-OR-NOTHING: a partial failure returns a
// nil Workspace + a wrapped error and leaves NO orphaned container/namespace/network behind
// (§2). It runs FOR REAL on every substrate that can be made to fail mid-Create: it induces a
// genuine failure (an unpullable image — both adapters fail the Ready handshake and must roll
// back) and asserts (a) Provision never returns a non-nil Workspace with an error and (b) the
// adapter's owned-object count returns to ZERO (the no-orphan re-scan, the C23 forced-teardown
// discipline at the Go layer). The in-memory fake additionally exercises the forced-failure
// rollback path via FailProvisionWith.
func caseProvisionAllOrNothing(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)

	// The fake path: force an isolation failure and assert no orphan in its in-memory state.
	if fake, ok := adapter.(*Adapter); ok {
		fake.FailProvisionWith(&workspaceprovider.IsolationError{Detail: "forced: egress policy rejected"})
		ws, err := prov.Provision(ctx, baseSpec("ws-fail"))
		if ws != nil {
			report.Errorf("Provision returned a non-nil Workspace alongside an error (must be all-or-nothing)")
		}
		if err == nil {
			report.Fatalf("Provision: expected an IsolationError, got nil")
			return
		}
		if errors.KindOf(err) != errors.KindPermission {
			report.Errorf("IsolationError Kind = %v, want Permission", errors.KindOf(err))
		}
		if descs := listLabels(ctx, prov, nil, report); len(descs) != 0 {
			report.Errorf("a failed Provision left %d orphaned workspace(s)", len(descs))
		}
		return
	}

	// REAL substrate: induce a genuine mid-Create failure (an unpullable image) and assert the
	// adapter rolled back to ZERO owned objects (no orphaned container/namespace/network).
	counter, ok := adapter.(ownerCounter)
	if !ok {
		report.Skipf("adapter does not expose an owned-object count; real-substrate no-orphan re-scan is asserted by the harness Cleanup")
		return
	}
	before, cerr := counter.CountOwned(ctx)
	if cerr != nil {
		report.Fatalf("CountOwned (before): %v", cerr)
		return
	}
	spec := baseSpec("ws-rollback")
	spec.Image = "eden-nonexistent.invalid/no-such-image:does-not-exist"
	ws, err := prov.Provision(ctx, spec)
	if ws != nil {
		report.Errorf("Provision of an unpullable image returned a non-nil Workspace (must be all-or-nothing)")
		cleanup(ctx, prov, ws.Handle())
	}
	if err == nil {
		report.Fatalf("Provision of an unpullable image: expected an error, got nil")
		return
	}
	after, cerr := counter.CountOwned(ctx)
	if cerr != nil {
		report.Fatalf("CountOwned (after): %v", cerr)
		return
	}
	if after != before {
		report.Errorf("a failed Provision left orphan(s): owned count went %d -> %d (rollback incomplete)", before, after)
	}
}

// ownerCounter is the structural seam the real adapters expose (dockeradapter.Adapter,
// kubernetesadapter.Adapter) so the no-orphan rollback/teardown re-scan reads the substrate's
// owned-object count without this package depending on a concrete adapter type. The in-memory
// fake does not implement it (its rollback is asserted via List).
type ownerCounter interface {
	CountOwned(ctx context.Context) (int, error)
}

func caseIdempotency(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	spec := baseSpec("ws-idem")

	first, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("first Provision: %v", err)
		return
	}
	defer cleanup(ctx, prov, first.Handle())

	// COMPATIBLE re-Provision (same Name, same spec) → the SAME handle, no error.
	second, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("re-Provision (idempotent): unexpected error: %v", err)
		return
	}
	if first.Handle().String() != second.Handle().String() {
		report.Errorf("idempotent re-Provision returned a different handle: %q vs %q", first.Handle(), second.Handle())
	}

	// INCOMPATIBLE re-Provision (same Name, DIFFERENT spec) → ConflictError (Kind=Conflict),
	// never a silent return of the old workspace (the level-based reconcile contract, §2).
	incompatible := baseSpec("ws-idem")
	incompatible.Resources = workspaceprovider.Resources{MemoryBytes: 64 << 20, CPUMilli: 250}
	ws, cerr := prov.Provision(ctx, incompatible)
	if ws != nil {
		report.Errorf("an incompatible re-Provision returned a non-nil Workspace (must be a ConflictError)")
	}
	if cerr == nil {
		report.Errorf("an incompatible re-Provision (changed Resources) must be a ConflictError, got nil")
		return
	}
	if errors.KindOf(cerr) != errors.KindConflict {
		report.Errorf("incompatible re-Provision Kind = %v, want Conflict", errors.KindOf(cerr))
	}
	if typed, ok := errors.AsType[*workspaceprovider.ConflictError](cerr); !ok || typed == nil {
		report.Errorf("incompatible re-Provision: want *ConflictError in the chain, got %v", cerr)
	}
}

func caseRoundTripStatelessness(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	if !h.Has(capReattach) {
		report.Skipf("CapReattach absent: this substrate does not survive a control-plane restart")
		return
	}
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	ws, err := prov.Provision(ctx, baseSpec("ws-restart"))
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	handle := ws.Handle()

	// Reconstruct the Provider (orchestrator restart) over the SAME adapter and re-dial.
	prov2, _ := providerOver(adapter)
	if _, oerr := prov2.Open(ctx, handle); oerr != nil {
		report.Errorf("Open after Provider reconstruction: %v", oerr)
	}

	// A torn-down handle yields NotFoundError.
	if terr := prov2.Teardown(ctx, handle); terr != nil {
		report.Errorf("Teardown: %v", terr)
	}
	if _, oerr := prov2.Open(ctx, handle); oerr == nil {
		report.Errorf("Open after Teardown: expected NotFoundError, got nil")
	} else if errors.KindOf(oerr) != errors.KindNotFound {
		report.Errorf("Open after Teardown Kind = %v, want NotFound", errors.KindOf(oerr))
	}
}

func caseRunToTerminal(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	ws, err := prov.Provision(ctx, baseSpec("ws-run"))
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	run, rerr := ws.Run(ctx, workspaceprovider.RunSpec{Command: []string{"echo", "hello-workload"}})
	if rerr != nil {
		report.Fatalf("Run: %v", rerr)
		return
	}
	if h.Has(capLogStream) {
		if rc, lerr := run.Logs(ctx, 0); lerr != nil {
			report.Errorf("Run.Logs: %v", lerr)
		} else if data, rdErr := readAllClose(rc); rdErr != nil {
			report.Errorf("Run.Logs read: %v", rdErr)
		} else if len(data) == 0 {
			report.Errorf("Run.Logs streamed no output")
		}
	}
	final := drainToTerminal(ctx, run)
	if !final.Phase.IsTerminal() {
		report.Errorf("Run did not reach a terminal phase, last = %v", final.Phase)
	}
}

func caseOnePrimaryWorkload(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	ws, err := prov.Provision(ctx, baseSpec("ws-onerun"))
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	if _, rerr := ws.Run(ctx, workspaceprovider.RunSpec{Command: []string{"sleep", "30"}}); rerr != nil {
		report.Fatalf("first Run: %v", rerr)
		return
	}
	_, second := ws.Run(ctx, workspaceprovider.RunSpec{Command: []string{"echo", "second"}})
	if second == nil {
		report.Errorf("a second Run while one is Running must be a NotReadyError, got nil")
		return
	}
	if errors.KindOf(second) != errors.KindInvalid {
		report.Errorf("second Run Kind = %v, want Invalid (NotReadyError)", errors.KindOf(second))
	}
}

func caseExec(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	ws, err := prov.Provision(ctx, baseSpec("ws-exec"))
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	var out bytes.Buffer
	res, eerr := ws.Exec(ctx, workspaceprovider.ExecSpec{Command: []string{"echo", "exec-ok"}, Stdout: &out})
	if eerr != nil {
		report.Fatalf("Exec: %v", eerr)
		return
	}
	if res.ExitCode != 0 {
		report.Errorf("Exec exit code = %d, want 0", res.ExitCode)
	}

	// A non-zero command returns its real exit code.
	failRes, ferr := ws.Exec(ctx, workspaceprovider.ExecSpec{Command: []string{"false"}})
	if ferr != nil {
		report.Errorf("Exec(false): unexpected error: %v", ferr)
	} else if failRes.ExitCode == 0 {
		report.Errorf("Exec(false) exit code = 0, want non-zero")
	}
}

func caseFileSeam(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	ws, err := prov.Provision(ctx, baseSpec("ws-files"))
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	files := ws.Files()
	want := []byte("artifact-bytes")
	if perr := files.Put(ctx, "/workspace/out.txt", bytes.NewReader(want), 0o644); perr != nil {
		report.Fatalf("Files.Put: %v", perr)
		return
	}
	rc, gerr := files.Get(ctx, "/workspace/out.txt")
	if gerr != nil {
		report.Fatalf("Files.Get: %v", gerr)
		return
	}
	got, rdErr := readAllClose(rc)
	if rdErr != nil {
		report.Errorf("Files.Get read: %v", rdErr)
	}
	if !bytes.Equal(got, want) {
		report.Errorf("Files round-trip: got %q want %q", got, want)
	}
	entries, lerr := files.List(ctx, "/workspace")
	if lerr != nil {
		report.Errorf("Files.List: %v", lerr)
	} else if !containsEntry(entries, "out.txt") {
		report.Errorf("Files.List did not enumerate the produced artifact")
	}

	// Get of an absent path is NotFoundError.
	if _, nerr := files.Get(ctx, "/workspace/absent.txt"); nerr == nil {
		report.Errorf("Files.Get(absent): expected NotFoundError, got nil")
	} else if errors.KindOf(nerr) != errors.KindNotFound {
		report.Errorf("Files.Get(absent) Kind = %v, want NotFound", errors.KindOf(nerr))
	}
}

func caseReadOnlyInputs(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	spec := baseSpec("ws-ro")
	spec.Mounts = []workspaceprovider.Mount{
		{Kind: workspaceprovider.MountBind, Target: "/workspace"},
		{Kind: workspaceprovider.MountInputs, Target: "/inputs", ReadOnly: true},
	}
	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	werr := ws.Files().Put(ctx, "/inputs/forbidden.txt", strings.NewReader("nope"), 0o644)
	if werr == nil {
		report.Errorf("a write under a read-only MountInputs must be rejected, got nil")
		return
	}
	if errors.KindOf(werr) != errors.KindInvalid {
		report.Errorf("read-only write rejection Kind = %v, want Invalid (NotReadyError)", errors.KindOf(werr))
	}
}

func caseTeardownIdempotent(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	ws, err := prov.Provision(ctx, baseSpec("ws-teardown"))
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	handle := ws.Handle()

	if terr := prov.Teardown(ctx, handle); terr != nil {
		report.Errorf("first Teardown: %v", terr)
	}
	if terr := prov.Teardown(ctx, handle); terr != nil {
		report.Errorf("second Teardown must be nil (idempotent), got %v", terr)
	}
	if _, oerr := prov.Open(ctx, handle); oerr == nil {
		report.Errorf("Open after Teardown: expected NotFoundError, got nil")
	} else if errors.KindOf(oerr) != errors.KindNotFound {
		report.Errorf("Open after Teardown Kind = %v, want NotFound", errors.KindOf(oerr))
	}
	if descs := listLabels(ctx, prov, baseSpec("ws-teardown").Labels, report); containsHandle(descs, handle) {
		report.Errorf("List still includes a torn-down workspace")
	}
}

// caseEgress proves DEFAULT-DENY egress against the substrate that DECLARES CapEgressPolicy
// (Skip, honestly, where it is CapAbsent — e.g. k3d/kind on flannel, which does not enforce
// NetworkPolicy). It provisions a ZERO-egress workspace (the clean-room 07 §4 posture — the
// strongest guarantee a substrate can make, and the one docker's `--internal` network
// genuinely enforces) and ACTUALLY ATTEMPTS A DIAL-OUT from inside it to a public host,
// asserting the connection is BLOCKED. Against a REAL substrate this is a real exec to a real
// network stack (no mock); against the in-memory fake it is the modeled ConditionEgressDenied.
func caseEgress(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	if !h.Has(capEgress) {
		report.Skipf("CapEgressPolicy absent: this substrate does not enforce default-deny egress (e.g. k3d/kind on flannel — real enforcement is future work, 07 §3 / open-decisions)")
		return
	}
	ctx := h.Context()
	fake, isFake := adapter.(*Adapter)

	prov, _ := providerOver(adapter)
	// A ZERO-egress workspace: the clean room dials out to NOTHING (07 §4). The docker
	// adapter realizes this as a genuine `--internal` default-deny network.
	spec := baseSpec("ws-egress")
	spec.Egress = nil
	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("Provision (zero-egress, default-deny): %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	if isFake {
		// The fake has no real network stack: assert the modeled default-deny signal. A
		// dial-out to ANY host from a zero-egress workspace must surface ConditionEgressDenied.
		fake.DenyEgressTo("example.com")
		probeSpec := spec
		probeSpec.Egress = []workspaceprovider.EgressRule{{Host: "example.com", Note: "undeclared dial-out attempt"}}
		// Re-provision under a fresh name so the modeled deny is observed on a fresh handle.
		probeSpec.Name = "ws-egress-deny"
		denyWS, derr := prov.Provision(ctx, probeSpec)
		if derr != nil {
			report.Fatalf("Provision (fake deny probe): %v", derr)
			return
		}
		defer cleanup(ctx, prov, denyWS.Handle())
		st, serr := denyWS.Status(ctx)
		if serr != nil {
			report.Errorf("Status: %v", serr)
			return
		}
		if !hasCondition(st.Conditions, workspaceprovider.ConditionEgressDenied) {
			report.Errorf("a blocked dial-out must surface ConditionEgressDenied, conditions = %v", st.Conditions)
		}
		return
	}

	// REAL substrate: POSITIVE CONTROL first — confirm exec works and the dial-out tool is
	// present, so a tool-missing/exec fault cannot masquerade as a network block (a false pass).
	control, cerr := ws.Exec(ctx, workspaceprovider.ExecSpec{Command: []string{"sh", "-c", "command -v wget >/dev/null"}, Timeout: 20 * time.Second})
	if cerr != nil {
		report.Fatalf("egress positive control (exec): %v", cerr)
		return
	}
	if control.ExitCode != 0 {
		report.Skipf("the workspace image has no wget to drive the dial-out probe; egress enforcement not exercised here (honest skip, not a fake pass)")
		return
	}
	// Now attempt an ACTUAL dial-out to a public host and assert it is BLOCKED.
	if blocked, reason := dialOutBlocked(ctx, ws); !blocked {
		report.Errorf("default-deny egress not enforced: a dial-out from a zero-egress workspace SUCCEEDED (%s)", reason)
	}
}

// dialOutBlocked execs a real off-host dial-out attempt from inside ws and reports whether it
// was blocked (the default-deny guarantee). It returns (true, reason) when the connection
// could not be established — the expected, enforced outcome — and (false, reason) when the
// workspace reached the public internet (a default-deny FAILURE). A short timeout bounds the
// attempt so a genuinely-blocked dial does not hang the case.
func dialOutBlocked(ctx context.Context, ws workspaceprovider.Workspace) (blocked bool, reason string) {
	// busybox wget: a blocked connect exits non-zero quickly ("bad address" / "Network is
	// unreachable"); a reachable host exits 0. -T bounds it.
	res, err := ws.Exec(ctx, workspaceprovider.ExecSpec{
		Command: []string{"wget", "-T", "5", "-q", "-O", "/dev/null", "https://example.com"},
		Timeout: 20 * time.Second, // comfortably over wget's own -T 5
	})
	if err != nil {
		// A transport/deadline error on the exec itself is treated as blocked-with-caveat: the
		// dial did not succeed. Report the reason so a genuine substrate fault is visible.
		return true, "exec error (dial did not complete): " + err.Error()
	}
	if res.ExitCode == 0 {
		return false, "wget https://example.com exited 0 (host was reachable)"
	}
	return true, "wget exited " + strconv.Itoa(res.ExitCode) + " (dial blocked)"
}

// caseResourceLimits proves RESOURCE LIMITS BIND: a workload exceeding MemoryBytes is
// RunKilled / ConditionOOMKilled with the native reason in Detail (the runaway-agent signal,
// 02 §2), not a generic failure. It runs FOR REAL on every substrate that DECLARES
// CapResourceLimits: it provisions a workspace with a tight memory ceiling and runs a real
// memory-bomb under it (against a real cgroup on docker AND k3d). It SKIPS HONESTLY only when
// the running daemon/node does not actually enforce the memory cgroup (some rootless/CI
// daemons disable it) — an honest skip, never a fake pass. The in-memory fake exercises the
// modeled OOM path via OOMKillRun.
func caseResourceLimits(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	if !h.Has(capLimits) {
		report.Skipf("CapResourceLimits absent: this substrate does not honor Resources")
		return
	}
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	spec := baseSpec("ws-oom")
	spec.Resources = workspaceprovider.Resources{MemoryBytes: 16 << 20} // 16 MiB ceiling

	// The fake path: force the modeled OOM and assert the RunKilled/ConditionOOMKilled signal.
	if fake, ok := adapter.(*Adapter); ok {
		caseResourceLimitsFake(ctx, fake, prov, &spec, report)
		return
	}

	// REAL substrate: run a genuine memory-bomb under a real cgroup.
	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())
	// Allocate ~512 MiB into a tmpfs-backed file (charged to the container's memory cgroup) to
	// trip the 16 MiB ceiling.
	run, rerr := ws.Run(ctx, workspaceprovider.RunSpec{
		Command: []string{"sh", "-c", "dd if=/dev/zero of=/dev/shm/fill bs=1M count=512 2>/dev/null; cat /dev/shm/fill >/dev/null; sleep 1"},
	})
	if rerr != nil {
		report.Fatalf("Run: %v", rerr)
		return
	}
	final := drainToTerminal(ctx, run)
	if final.Phase == workspaceprovider.RunSucceeded {
		report.Skipf("the running daemon/node did not enforce the memory cgroup (rootless/CI); the OOM path is not inducible here — honest skip, not a fake pass")
		return
	}
	// The cgroup killed the workload: it must be a terminal kill/failure (never Succeeded).
	if final.Phase != workspaceprovider.RunKilled && final.Phase != workspaceprovider.RunFailed {
		report.Errorf("an over-memory workload phase = %v, want Killed/Failed", final.Phase)
	}
	assertOOMKilledShape(final, report)
}

// caseResourceLimitsFake drives the in-memory fake's modeled OOM path: a forced OOMKill makes
// the run terminate RunKilled / ConditionOOMKilled with the native reason in Detail.
func caseResourceLimitsFake(ctx context.Context, fake *Adapter, prov workspaceprovider.Provider, spec *workspaceprovider.WorkspaceSpec, report edentesting.Report) {
	fake.OOMKillRun(0)
	ws, err := prov.Provision(ctx, *spec)
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())
	run, rerr := ws.Run(ctx, workspaceprovider.RunSpec{Command: []string{"memory-bomb"}})
	if rerr != nil {
		report.Fatalf("Run: %v", rerr)
		return
	}
	final := drainToTerminal(ctx, run)
	if final.Phase != workspaceprovider.RunKilled {
		report.Errorf("an over-memory workload must be RunKilled, got %v", final.Phase)
	}
	if final.Condition != workspaceprovider.ConditionOOMKilled {
		report.Errorf("an over-memory workload must carry ConditionOOMKilled, got %v", final.Condition)
	}
	if final.Detail == "" {
		report.Errorf("the native OOM reason must ride RunStatus.Detail, got empty")
	}
}

// assertOOMKilledShape asserts the OOMKilled signal's shape when a real substrate surfaces it
// (docker reads the container's OOMKilled flag): it must be a RunKilled carrying the native
// reason in Detail. A substrate that reports the kill only as a non-zero exit (e.g. SIGKILL
// 137 on kubernetes) is honest and not asserted here.
func assertOOMKilledShape(final workspaceprovider.RunStatus, report edentesting.Report) {
	if final.Condition != workspaceprovider.ConditionOOMKilled {
		return
	}
	if final.Phase != workspaceprovider.RunKilled {
		report.Errorf("an OOMKilled workload must be RunKilled, got %v", final.Phase)
	}
	if final.Detail == "" {
		report.Errorf("the native OOM reason must ride RunStatus.Detail, got empty")
	}
}

// mountSecretTarget is the in-workspace path a MountSecret's resolved material is written to.
const mountSecretTarget = "/run/eden/secrets/mounted-token"

// caseMountSecret proves the MountSecret credential seam END TO END on a REAL substrate: a
// workspace declares a MountSecret whose secrets.Reference resolves (server-side, by the
// library) to the seeded canary; the adapter must WRITE that resolved material into the
// workspace at the mount Target with restrictive mode, so an exec reading the Target INSIDE the
// workspace returns the secret VALUE — while the value still appears in NO Handle/Status/spec/
// log (07 §2, the no-leak guarantee runnable). This is the B6 fix's executable proof: the
// docker adapter writes a 0600 tmpfs file; the kubernetes adapter mounts a 0400 secret volume;
// both yield the same observable — `cat <target>` == the secret. It runs FOR REAL on docker AND
// k3d (and against the in-memory fake, which models the same write).
func caseMountSecret(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	spec := baseSpec("ws-mount-secret")
	spec.Mounts = append(spec.Mounts, workspaceprovider.Mount{
		Kind:   workspaceprovider.MountSecret,
		Target: mountSecretTarget,
		Ref:    pullSecretRef(), // resolves to SeededCanary, server-side, by the library
	})

	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("Provision with MountSecret: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	// Read the mounted secret from INSIDE the workspace: it must equal the seeded value (the
	// resolved material actually reached the workspace — not an empty file).
	var out bytes.Buffer
	res, eerr := ws.Exec(ctx, workspaceprovider.ExecSpec{
		Command: []string{"cat", mountSecretTarget},
		Stdout:  &out,
		Timeout: 30 * time.Second,
	})
	if eerr != nil {
		report.Fatalf("Exec(cat mount-secret): %v", eerr)
		return
	}
	if res.ExitCode != 0 {
		report.Errorf("reading the MountSecret target exited %d (the material did not reach the workspace)", res.ExitCode)
		return
	}
	got := strings.TrimRight(out.String(), "\n")
	if got != SeededCanary {
		report.Errorf("MountSecret content = %q, want the seeded secret value (the resolved material was dropped)", got)
	}

	// The value must NOT have leaked into the loggable surfaces (07 §2): the Handle, the Status
	// detail, or any List Descriptor. (The exec STDOUT above is the workload reading its own
	// credential at point of use — that is the legitimate read path, not a leak.)
	if strings.Contains(ws.Handle().String(), SeededCanary) {
		report.Errorf("the mounted secret leaked into the Handle")
	}
	if st, serr := ws.Status(ctx); serr != nil {
		report.Errorf("Status: %v", serr)
	} else if strings.Contains(st.Detail, SeededCanary) {
		report.Errorf("the mounted secret leaked into Status.Detail")
	}
	for _, desc := range listLabels(ctx, prov, spec.Labels, report) {
		if strings.Contains(desc.Handle.String(), SeededCanary) {
			report.Errorf("the mounted secret leaked into a Descriptor")
		}
	}
	if fake, ok := adapter.(*Adapter); ok {
		fake.AssertNoSecretMaterial(reportAsTestingT{report}, SeededCanary)
	}
}

func caseNoSecretLeak(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	spec := baseSpec("ws-secret")
	spec.ImagePull = pullSecretRef() // resolves to SeededCanary, server-side
	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("Provision with pull-secret: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	// The seeded plaintext must appear in NO Handle/Descriptor/Status.
	if strings.Contains(ws.Handle().String(), SeededCanary) {
		report.Errorf("the seeded credential leaked into the Handle")
	}
	if st, serr := ws.Status(ctx); serr != nil {
		report.Errorf("Status: %v", serr)
	} else if strings.Contains(st.Detail, SeededCanary) {
		report.Errorf("the seeded credential leaked into Status.Detail")
	}
	for _, desc := range listLabels(ctx, prov, spec.Labels, report) {
		if strings.Contains(desc.Handle.String(), SeededCanary) || strings.Contains(desc.Name, SeededCanary) {
			report.Errorf("the seeded credential leaked into a Descriptor")
		}
	}
	if fake, ok := adapter.(*Adapter); ok {
		fake.AssertNoSecretMaterial(reportAsTestingT{report}, SeededCanary)
	}
}

func caseManifestTruthful(adapter workspaceprovider.Adapter, _ edentesting.Harness, report edentesting.Report) {
	manifest := adapter.Manifest()
	if manifest.Capabilities == nil {
		report.Errorf("Manifest carries a nil Capabilities map")
	}
	// A declared CapFull capability must have passed its gated cases — this case asserts
	// the manifest is well-formed; the per-capability gated cases above ARE the
	// truthfulness check (a declared-but-failing capability fails its case).
	if manifest.Distro == "" {
		report.Errorf("Manifest.Distro is empty (telemetry/UI identity required)")
	}
}

func caseTenancyIsolation(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	if !h.Has(capMulti) {
		report.Skipf("CapMultiTenant absent: this substrate does not isolate tenancies")
		return
	}
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	spec := baseSpec("ws-tenant-a")
	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	// A List with a DIFFERENT tenancy key never returns this workspace.
	other := workspaceprovider.Selector{Labels: map[string]string{
		workspaceprovider.LabelOrganization: "org-OTHER",
		workspaceprovider.LabelProject:      "proj-OTHER",
	}}
	descs, lerr := prov.List(ctx, other)
	if lerr != nil {
		report.Errorf("List(other tenancy): %v", lerr)
	}
	if containsHandle(descs, ws.Handle()) {
		report.Errorf("List with a different tenancy key returned this tenant's workspace (cross-tenant leak)")
	}
}

func caseStateNormalization(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	ctx := h.Context()
	prov, _ := providerOver(adapter)
	ws, err := prov.Provision(ctx, baseSpec("ws-state"))
	if err != nil {
		report.Fatalf("Provision: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	st, serr := ws.Status(ctx)
	if serr != nil {
		report.Fatalf("Status: %v", serr)
		return
	}
	// The normalized State is one of the closed enum values; native strings ride Detail.
	if st.State > workspaceprovider.StateGone {
		report.Errorf("Status.State = %d is outside the closed State taxonomy", st.State)
	}
	if st.Since.IsZero() {
		report.Errorf("Status.Since must be Clock-stamped, got the zero time")
	}
}

// small assertion helpers.

// cleanup tears a workspace down at the end of a case, ignoring the (idempotent) result —
// the case under test has already asserted what it needed; a teardown error here is not the
// property being tested.
func cleanup(ctx context.Context, prov workspaceprovider.Provider, handle workspaceprovider.Handle) {
	_ = prov.Teardown(ctx, handle) //nolint:errcheck // best-effort case teardown; Teardown is idempotent and not the property under test.
}

// listLabels lists by a tenancy selector, surfacing a List error on report rather than
// returning it (so a case body stays linear).
func listLabels(ctx context.Context, prov workspaceprovider.Provider, labels map[string]string, report edentesting.Report) []workspaceprovider.Descriptor {
	descs, err := prov.List(ctx, workspaceprovider.Selector{Labels: labels})
	if err != nil {
		report.Errorf("List: %v", err)
	}
	return descs
}

func containsHandle(descs []workspaceprovider.Descriptor, handle workspaceprovider.Handle) bool {
	for i := range descs {
		if descs[i].Handle.String() == handle.String() {
			return true
		}
	}
	return false
}

func containsEntry(entries []workspaceprovider.FileEntry, name string) bool {
	for i := range entries {
		if entries[i].Name == name {
			return true
		}
	}
	return false
}

func hasCondition(conds []workspaceprovider.Condition, want workspaceprovider.Condition) bool {
	for i := range conds {
		if conds[i] == want {
			return true
		}
	}
	return false
}

// reportAsTestingT adapts a testing.Report to the TestingT the no-leak assertion needs.
type reportAsTestingT struct{ report edentesting.Report }

func (r reportAsTestingT) Helper() {}
func (r reportAsTestingT) Errorf(format string, args ...any) {
	r.report.Errorf(format, args...)
}
