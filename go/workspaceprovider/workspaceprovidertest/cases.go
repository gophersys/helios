package workspaceprovidertest

import (
	"bytes"
	"context"
	"strings"

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

func caseProvisionAllOrNothing(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	fake, ok := adapter.(*Adapter)
	if !ok {
		report.Skipf("all-or-nothing rollback is forced via the fake's FailProvisionWith; real substrates assert no-orphan via the harness Cleanup re-scan")
		return
	}
	ctx := h.Context()
	fake.FailProvisionWith(&workspaceprovider.IsolationError{Detail: "forced: egress policy rejected"})
	prov, _ := providerOver(adapter)

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
	// No orphan: the fake's state is empty after the failed create.
	if descs := listLabels(ctx, prov, nil, report); len(descs) != 0 {
		report.Errorf("a failed Provision left %d orphaned workspace(s)", len(descs))
	}
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
	second, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("re-Provision (idempotent): unexpected error: %v", err)
		return
	}
	if first.Handle().String() != second.Handle().String() {
		report.Errorf("idempotent re-Provision returned a different handle: %q vs %q", first.Handle(), second.Handle())
	}
	cleanup(ctx, prov, first.Handle())
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

func caseEgress(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	if !h.Has(capEgress) {
		report.Skipf("CapEgressPolicy absent: this substrate does not enforce declared egress")
		return
	}
	ctx := h.Context()
	fake, isFake := adapter.(*Adapter)
	if isFake {
		fake.DenyEgressTo("evil.example.com")
	}
	prov, _ := providerOver(adapter)
	spec := baseSpec("ws-egress")
	spec.Egress = []workspaceprovider.EgressRule{
		{Host: "evil.example.com", Note: "undeclared dial-out attempt"},
	}
	ws, err := prov.Provision(ctx, spec)
	if err != nil {
		report.Fatalf("Provision with egress: %v", err)
		return
	}
	defer cleanup(ctx, prov, ws.Handle())

	st, serr := ws.Status(ctx)
	if serr != nil {
		report.Errorf("Status: %v", serr)
		return
	}
	if isFake && !hasCondition(st.Conditions, workspaceprovider.ConditionEgressDenied) {
		report.Errorf("a blocked dial-out must surface ConditionEgressDenied, conditions = %v", st.Conditions)
	}
}

func caseResourceLimits(adapter workspaceprovider.Adapter, h edentesting.Harness, report edentesting.Report) {
	if !h.Has(capLimits) {
		report.Skipf("CapResourceLimits absent: this substrate does not honor Resources")
		return
	}
	fake, isFake := adapter.(*Adapter)
	if !isFake {
		report.Skipf("the OOM-kill path is forced via the fake; a real substrate exercises it with a memory-bomb workload under MemoryBytes")
		return
	}
	ctx := h.Context()
	fake.OOMKillRun(0)
	prov, _ := providerOver(adapter)
	spec := baseSpec("ws-oom")
	spec.Resources = workspaceprovider.Resources{MemoryBytes: 16 << 20}
	ws, err := prov.Provision(ctx, spec)
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
