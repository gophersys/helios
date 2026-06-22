package clusterprobe_test

import (
	"context"
	stderrors "errors"
	"testing"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/clusterprobe"
	"github.com/gophersys/libs/go/workspaceprovider"
	"go.uber.org/goleak"
)

// TestMain installs the goleak resource-leak guard for this package (rule 21(b): a
// VerifyTestMain per package). The cluster Probe holds no goroutines — every Observe is a
// synchronous fold over two injected reads — so the package's own goroutine high-water is
// zero; the guard proves no test (or a future change) leaks one.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}

// ─────────────────────────────────────────────────────────────────────────────.
// Fakes — a fake WorkspaceLister + a fake HealthSource (no real cluster, no real NATS).
// ─────────────────────────────────────────────────────────────────────────────.

// fakeWorkspaces is a fake WorkspaceLister: it records the selector it was queried with (so a
// test asserts the project scoping) and returns a canned Descriptor set or a canned error.
type fakeWorkspaces struct {
	descriptors []workspaceprovider.Descriptor
	err         error
	gotSelector workspaceprovider.Selector
	calls       int
}

func (f *fakeWorkspaces) Reconcile(_ context.Context, selector workspaceprovider.Selector) ([]workspaceprovider.Descriptor, error) {
	f.calls++
	f.gotSelector = selector
	if f.err != nil {
		return nil, f.err
	}
	return f.descriptors, nil
}

// fakeHealth is a fake HealthSource: it records the ids it was queried with and returns a
// canned most-recent-beat map or a canned error.
type fakeHealth struct {
	beats  map[agentruntime.AgentID]agentruntime.Heartbeat
	err    error
	gotIDs []agentruntime.AgentID
	calls  int
}

func (f *fakeHealth) LatestHealth(_ context.Context, ids []agentruntime.AgentID) (map[agentruntime.AgentID]agentruntime.Heartbeat, error) {
	f.calls++
	f.gotIDs = ids
	if f.err != nil {
		return nil, f.err
	}
	return f.beats, nil
}

// ─────────────────────────────────────────────────────────────────────────────.
// Helpers.
// ─────────────────────────────────────────────────────────────────────────────.

const (
	testOrg     = "org-7"
	testProject = "proj-42"
)

func testTenant() orchestrator.Tenancy {
	return orchestrator.Tenancy{OrganizationID: testOrg, ProjectID: testProject}
}

// workspaceFor builds a Descriptor carrying the agent-id join label + the given live State,
// exactly as the orchestrator's fold stamps a provisioned workspace.
func workspaceFor(id orchestrator.AgentID, state workspaceprovider.State) workspaceprovider.Descriptor {
	return workspaceprovider.Descriptor{
		Name:      "ws-" + string(id),
		Substrate: workspaceprovider.SubstrateDocker,
		State:     state,
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: testOrg,
			workspaceprovider.LabelProject:      testProject,
			clusterprobe.DefaultAgentLabelKey:   string(id),
		},
	}
}

func beatFor(id orchestrator.AgentID, phase agentruntime.HealthPhase, state agentsession.State, seq uint64) agentruntime.Heartbeat {
	return agentruntime.Heartbeat{
		AgentID:      agentruntime.AgentID(id),
		Phase:        phase,
		SessionState: state,
		LastSeq:      seq,
	}
}

// newProbe builds a Probe over the two fakes scoped to the test tenant (the common spine
// every Observe test shares).
func newProbe(t *testing.T, workspaces *fakeWorkspaces, health *fakeHealth) *clusterprobe.Probe {
	t.Helper()
	probe, err := clusterprobe.New(
		clusterprobe.Config{Tenant: testTenant()},
		clusterprobe.Deps{Workspaces: workspaces, Health: health},
	)
	if err != nil {
		t.Fatalf("New: unexpected error: %v", err)
	}
	return probe
}

// ─────────────────────────────────────────────────────────────────────────────.
// New — the pure constructor spine validation.
// ─────────────────────────────────────────────────────────────────────────────.

func TestNew_RejectsZeroTenant(t *testing.T) {
	t.Parallel()
	_, err := clusterprobe.New(
		clusterprobe.Config{}, // zero Tenant
		clusterprobe.Deps{Workspaces: &fakeWorkspaces{}, Health: &fakeHealth{}},
	)
	assertKind(t, err, errors.KindInvalid)
	assertConfigError(t, err)
}

func TestNew_RejectsNilWorkspaces(t *testing.T) {
	t.Parallel()
	_, err := clusterprobe.New(
		clusterprobe.Config{Tenant: testTenant()},
		clusterprobe.Deps{Workspaces: nil, Health: &fakeHealth{}},
	)
	assertKind(t, err, errors.KindInvalid)
	assertConfigError(t, err)
}

func TestNew_RejectsNilHealth(t *testing.T) {
	t.Parallel()
	_, err := clusterprobe.New(
		clusterprobe.Config{Tenant: testTenant()},
		clusterprobe.Deps{Workspaces: &fakeWorkspaces{}, Health: nil},
	)
	assertKind(t, err, errors.KindInvalid)
	assertConfigError(t, err)
}

func TestNew_DefaultsAgentLabelKey(t *testing.T) {
	t.Parallel()
	id := orchestrator.AgentID("agent-default-label")
	// A workspace carrying the DEFAULT agent-id label key resolves with an EMPTY
	// Config.AgentLabelKey (the default is applied) — proves the default wiring.
	workspaces := &fakeWorkspaces{descriptors: []workspaceprovider.Descriptor{
		workspaceFor(id, workspaceprovider.StateReady),
	}}
	probe, err := clusterprobe.New(
		clusterprobe.Config{Tenant: testTenant()}, // AgentLabelKey empty → default
		clusterprobe.Deps{Workspaces: workspaces, Health: &fakeHealth{}},
	)
	if err != nil {
		t.Fatalf("New: unexpected error: %v", err)
	}
	actual, err := probe.Observe(context.Background(), []orchestrator.AgentID{id})
	if err != nil {
		t.Fatalf("Observe: unexpected error: %v", err)
	}
	if !actual[id].WorkspaceLive {
		t.Fatalf("default agent-label key did not resolve the workspace: %+v", actual[id])
	}
}

func TestNew_CustomAgentLabelKey(t *testing.T) {
	t.Parallel()
	const customKey = "eden.custom.agent"
	id := orchestrator.AgentID("agent-custom-label")
	descriptor := workspaceprovider.Descriptor{
		Name:  "ws-" + string(id),
		State: workspaceprovider.StateReady,
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: testOrg,
			workspaceprovider.LabelProject:      testProject,
			customKey:                           string(id),
		},
	}
	workspaces := &fakeWorkspaces{descriptors: []workspaceprovider.Descriptor{descriptor}}
	probe, err := clusterprobe.New(
		clusterprobe.Config{Tenant: testTenant(), AgentLabelKey: customKey},
		clusterprobe.Deps{Workspaces: workspaces, Health: &fakeHealth{}},
	)
	if err != nil {
		t.Fatalf("New: unexpected error: %v", err)
	}
	actual, err := probe.Observe(context.Background(), []orchestrator.AgentID{id})
	if err != nil {
		t.Fatalf("Observe: unexpected error: %v", err)
	}
	if !actual[id].WorkspaceLive {
		t.Fatalf("custom agent-label key did not resolve the workspace: %+v", actual[id])
	}
}

// ─────────────────────────────────────────────────────────────────────────────.
// Observe — the derivation matrix (workspace × heartbeat → Actual).
// ─────────────────────────────────────────────────────────────────────────────.

func TestObserve_EmptyIDs_NoQuery(t *testing.T) {
	t.Parallel()
	workspaces := &fakeWorkspaces{}
	health := &fakeHealth{}
	probe := newProbe(t, workspaces, health)

	actual, err := probe.Observe(context.Background(), nil)
	if err != nil {
		t.Fatalf("Observe(nil): unexpected error: %v", err)
	}
	if len(actual) != 0 {
		t.Fatalf("Observe(nil): want empty, got %+v", actual)
	}
	// An empty id set short-circuits before any source query (no wasted cluster/NATS read).
	if workspaces.calls != 0 || health.calls != 0 {
		t.Fatalf("Observe(nil) queried sources: workspaces=%d health=%d", workspaces.calls, health.calls)
	}
}

func TestObserve_FullyLive(t *testing.T) {
	t.Parallel()
	id := orchestrator.AgentID("agent-live")
	workspaces := &fakeWorkspaces{descriptors: []workspaceprovider.Descriptor{
		workspaceFor(id, workspaceprovider.StateRunning),
	}}
	health := &fakeHealth{beats: map[agentruntime.AgentID]agentruntime.Heartbeat{
		agentruntime.AgentID(id): beatFor(id, agentruntime.PhaseRunning, agentsession.StateRunning, 42),
	}}
	probe := newProbe(t, workspaces, health)

	actual := observeOne(t, probe, id)
	assertActual(t, &actual, true, true, agentsession.StateRunning)
}

func TestObserve_WorkspaceLiveNoHeartbeat(t *testing.T) {
	t.Parallel()
	// A provisioned workspace with no heartbeat yet (the just-provisioned, sidecar-not-yet-
	// beating window): WorkspaceLive true, SessionLive false, SessionState the unobserved zero.
	id := orchestrator.AgentID("agent-provisioning")
	workspaces := &fakeWorkspaces{descriptors: []workspaceprovider.Descriptor{
		workspaceFor(id, workspaceprovider.StateReady),
	}}
	health := &fakeHealth{beats: map[agentruntime.AgentID]agentruntime.Heartbeat{}}
	probe := newProbe(t, workspaces, health)

	actual := observeOne(t, probe, id)
	assertActual(t, &actual, true, false, agentsession.StateInitializing)
}

func TestObserve_HeartbeatNoWorkspace(t *testing.T) {
	t.Parallel()
	// A heartbeat with no live workspace in the list (the workspace was reclaimed/evicted but a
	// stale beat is still cached): SessionLive true off the beat, WorkspaceLive false — the
	// drift the reconcile loop drives to Failed. The id is still PRESENT (one source observed it).
	id := orchestrator.AgentID("agent-orphan-beat")
	workspaces := &fakeWorkspaces{descriptors: nil}
	health := &fakeHealth{beats: map[agentruntime.AgentID]agentruntime.Heartbeat{
		agentruntime.AgentID(id): beatFor(id, agentruntime.PhaseRunning, agentsession.StateAwaitingInput, 7),
	}}
	probe := newProbe(t, workspaces, health)

	actual := observeOne(t, probe, id)
	assertActual(t, &actual, false, true, agentsession.StateAwaitingInput)
}

func TestObserve_NoActual_AbsentFromResult(t *testing.T) {
	t.Parallel()
	// An id with NEITHER a live workspace NOR a heartbeat is absent from the result (the
	// not-yet-provisioned / fully-dropped path — orchestrator.Probe.Observe's "absent" contract).
	id := orchestrator.AgentID("agent-nothing")
	probe := newProbe(t, &fakeWorkspaces{}, &fakeHealth{})

	actual, err := probe.Observe(context.Background(), []orchestrator.AgentID{id})
	if err != nil {
		t.Fatalf("Observe: unexpected error: %v", err)
	}
	if _, present := actual[id]; present {
		t.Fatalf("id with no live actual should be absent, got %+v", actual[id])
	}
}

func TestObserve_GoneWorkspace_NotLive(t *testing.T) {
	t.Parallel()
	// A Gone Descriptor is a tombstone the substrate has not reaped — NOT a live workspace.
	// With no beat either, the id is absent (no live actual on either source).
	id := orchestrator.AgentID("agent-gone")
	workspaces := &fakeWorkspaces{descriptors: []workspaceprovider.Descriptor{
		workspaceFor(id, workspaceprovider.StateGone),
	}}
	probe := newProbe(t, workspaces, &fakeHealth{})

	actual, err := probe.Observe(context.Background(), []orchestrator.AgentID{id})
	if err != nil {
		t.Fatalf("Observe: unexpected error: %v", err)
	}
	if _, present := actual[id]; present {
		t.Fatalf("Gone workspace with no beat should be absent, got %+v", actual[id])
	}
}

func TestObserve_EvictedWorkspace_NotLive(t *testing.T) {
	t.Parallel()
	// An Evicted workspace (the substrate reclaimed it out-of-band — the drift signal) with a
	// still-live beat: WorkspaceLive false, SessionLive true. Present because a beat observed it.
	id := orchestrator.AgentID("agent-evicted")
	workspaces := &fakeWorkspaces{descriptors: []workspaceprovider.Descriptor{
		workspaceFor(id, workspaceprovider.StateEvicted),
	}}
	health := &fakeHealth{beats: map[agentruntime.AgentID]agentruntime.Heartbeat{
		agentruntime.AgentID(id): beatFor(id, agentruntime.PhaseDraining, agentsession.StateRunning, 9),
	}}
	probe := newProbe(t, workspaces, health)

	actual := observeOne(t, probe, id)
	if actual.WorkspaceLive {
		t.Fatalf("Evicted workspace should not be WorkspaceLive: %+v", actual)
	}
	if !actual.SessionLive {
		t.Fatalf("draining sidecar should be SessionLive: %+v", actual)
	}
}

func TestObserve_StoppedSidecar_NotSessionLive(t *testing.T) {
	t.Parallel()
	// A Stopped sidecar (drained, session closed, exited) is NOT a live session even with a
	// cached beat — its lifecycle is terminal. The workspace may still be Ready (mid-teardown).
	id := orchestrator.AgentID("agent-stopped-sidecar")
	workspaces := &fakeWorkspaces{descriptors: []workspaceprovider.Descriptor{
		workspaceFor(id, workspaceprovider.StateReady),
	}}
	health := &fakeHealth{beats: map[agentruntime.AgentID]agentruntime.Heartbeat{
		agentruntime.AgentID(id): beatFor(id, agentruntime.PhaseStopped, agentsession.StateCompleted, 100),
	}}
	probe := newProbe(t, workspaces, health)

	actual := observeOne(t, probe, id)
	if actual.SessionLive {
		t.Fatalf("Stopped sidecar should not be SessionLive: %+v", actual)
	}
	if !actual.WorkspaceLive {
		t.Fatalf("Ready workspace should be WorkspaceLive: %+v", actual)
	}
	// SessionState still reflects the observed terminal inner state (so reconcile's
	// unrecoverable-inner-state arm can act on a Failed/Completed inner state).
	if actual.SessionState != agentsession.StateCompleted {
		t.Fatalf("SessionState should carry the observed terminal state: %+v", actual)
	}
}

func TestObserve_UnrecoverableInnerState_Surfaced(t *testing.T) {
	t.Parallel()
	// The whole reason this Probe populates SessionState (which live.go could not): a sidecar
	// that is up (PhaseRunning) but whose INNER agent loop entered StateFailed must surface
	// that truthfully, so reconcile's driveRunning unrecoverable-inner-state arm fires.
	id := orchestrator.AgentID("agent-inner-failed")
	workspaces := &fakeWorkspaces{descriptors: []workspaceprovider.Descriptor{
		workspaceFor(id, workspaceprovider.StateRunning),
	}}
	health := &fakeHealth{beats: map[agentruntime.AgentID]agentruntime.Heartbeat{
		agentruntime.AgentID(id): beatFor(id, agentruntime.PhaseRunning, agentsession.StateFailed, 55),
	}}
	probe := newProbe(t, workspaces, health)

	actual := observeOne(t, probe, id)
	if actual.SessionState != agentsession.StateFailed {
		t.Fatalf("unrecoverable inner state not surfaced: %+v", actual)
	}
	if !actual.SessionLive || !actual.WorkspaceLive {
		t.Fatalf("sidecar+workspace still up while inner loop failed: %+v", actual)
	}
}

// ─────────────────────────────────────────────────────────────────────────────.
// Observe — project scoping, mis-attribution, fault propagation.
// ─────────────────────────────────────────────────────────────────────────────.

func TestObserve_ScopesSelectorToProject(t *testing.T) {
	t.Parallel()
	// The workspace list-by-label MUST carry the tenancy keys (the project scope) so a
	// per-tenant pass never reads another tenant's namespace (cross-tenant listing impossible).
	workspaces := &fakeWorkspaces{}
	probe := newProbe(t, workspaces, &fakeHealth{})

	if _, err := probe.Observe(context.Background(), []orchestrator.AgentID{"agent-x"}); err != nil {
		t.Fatalf("Observe: unexpected error: %v", err)
	}
	if got := workspaces.gotSelector.Labels[workspaceprovider.LabelOrganization]; got != testOrg {
		t.Fatalf("selector org = %q, want %q", got, testOrg)
	}
	if got := workspaces.gotSelector.Labels[workspaceprovider.LabelProject]; got != testProject {
		t.Fatalf("selector project = %q, want %q", got, testProject)
	}
}

func TestObserve_IgnoresUnrequestedAndUnlabeledWorkspaces(t *testing.T) {
	t.Parallel()
	requested := orchestrator.AgentID("agent-requested")
	other := orchestrator.AgentID("agent-other-live-but-unrequested")
	unlabeled := workspaceprovider.Descriptor{ // a workspace with no agent-id label — skipped, never mis-attributed
		Name:   "ws-unlabeled",
		State:  workspaceprovider.StateRunning,
		Labels: map[string]string{workspaceprovider.LabelOrganization: testOrg, workspaceprovider.LabelProject: testProject},
	}
	workspaces := &fakeWorkspaces{descriptors: []workspaceprovider.Descriptor{
		workspaceFor(requested, workspaceprovider.StateReady),
		workspaceFor(other, workspaceprovider.StateRunning),
		unlabeled,
	}}
	probe := newProbe(t, workspaces, &fakeHealth{})

	actual, err := probe.Observe(context.Background(), []orchestrator.AgentID{requested})
	if err != nil {
		t.Fatalf("Observe: unexpected error: %v", err)
	}
	// Only the requested id is in the result; the other live workspace + the unlabeled one
	// are not (Observe is scoped to the requested id set).
	if len(actual) != 1 {
		t.Fatalf("want exactly the requested id, got %d entries: %+v", len(actual), actual)
	}
	if !actual[requested].WorkspaceLive {
		t.Fatalf("requested workspace should be live: %+v", actual[requested])
	}
}

func TestObserve_WorkspaceQueryFault_Wrapped(t *testing.T) {
	t.Parallel()
	sentinel := stderrors.New("substrate unreachable")
	workspaces := &fakeWorkspaces{err: sentinel}
	probe := newProbe(t, workspaces, &fakeHealth{})

	_, err := probe.Observe(context.Background(), []orchestrator.AgentID{"agent-x"})
	if err == nil {
		t.Fatal("want a wrapped WorkspaceQueryError, got nil")
	}
	assertKind(t, err, errors.KindUnavailable)
	if !stderrors.Is(err, sentinel) {
		t.Fatalf("workspace fault did not preserve the cause chain: %v", err)
	}
	if !errors.IsType[*clusterprobe.WorkspaceQueryError](err) {
		t.Fatalf("want a *WorkspaceQueryError in the chain, got %v", err)
	}
}

func TestObserve_HealthQueryFault_Wrapped(t *testing.T) {
	t.Parallel()
	sentinel := stderrors.New("nats bucket read failed")
	// Workspaces succeed; the health read fails — the whole Observe fails (no half-known actual).
	workspaces := &fakeWorkspaces{descriptors: []workspaceprovider.Descriptor{
		workspaceFor("agent-x", workspaceprovider.StateReady),
	}}
	health := &fakeHealth{err: sentinel}
	probe := newProbe(t, workspaces, health)

	_, err := probe.Observe(context.Background(), []orchestrator.AgentID{"agent-x"})
	if err == nil {
		t.Fatal("want a wrapped HealthQueryError, got nil")
	}
	assertKind(t, err, errors.KindUnavailable)
	if !stderrors.Is(err, sentinel) {
		t.Fatalf("health fault did not preserve the cause chain: %v", err)
	}
	if !errors.IsType[*clusterprobe.HealthQueryError](err) {
		t.Fatalf("want a *HealthQueryError in the chain, got %v", err)
	}
}

func TestObserve_QueriesHealthForRequestedIDs(t *testing.T) {
	t.Parallel()
	ids := []orchestrator.AgentID{"a", "b", "c"}
	health := &fakeHealth{}
	probe := newProbe(t, &fakeWorkspaces{}, health)

	if _, err := probe.Observe(context.Background(), ids); err != nil {
		t.Fatalf("Observe: unexpected error: %v", err)
	}
	if len(health.gotIDs) != len(ids) {
		t.Fatalf("health queried %d ids, want %d", len(health.gotIDs), len(ids))
	}
	for i, id := range ids {
		if health.gotIDs[i] != agentruntime.AgentID(id) {
			t.Fatalf("health id[%d] = %q, want %q", i, health.gotIDs[i], id)
		}
	}
}

// ─────────────────────────────────────────────────────────────────────────────.
// Restart-determinism — the multi-node property: two independent Probes computing the same
// Actual from the same source snapshots (no in-memory table, so a replica restart is a no-op).
// ─────────────────────────────────────────────────────────────────────────────.

func TestObserve_RestartDeterminism(t *testing.T) {
	t.Parallel()
	id := orchestrator.AgentID("agent-replica")
	descriptors := []workspaceprovider.Descriptor{workspaceFor(id, workspaceprovider.StateRunning)}
	beats := map[agentruntime.AgentID]agentruntime.Heartbeat{
		agentruntime.AgentID(id): beatFor(id, agentruntime.PhaseRunning, agentsession.StateRunning, 12),
	}

	// Two SEPARATE Probe instances (two replicas) over the same source snapshots.
	replicaA := newProbe(t, &fakeWorkspaces{descriptors: descriptors}, &fakeHealth{beats: beats})
	replicaB := newProbe(t, &fakeWorkspaces{descriptors: descriptors}, &fakeHealth{beats: beats})

	a := observeOne(t, replicaA, id)
	b := observeOne(t, replicaB, id)
	if a.WorkspaceLive != b.WorkspaceLive || a.SessionLive != b.SessionLive || a.SessionState != b.SessionState {
		t.Fatalf("two replicas derived different Actual (no restart-determinism):\n A %+v\n B %+v", a, b)
	}
}

// ─────────────────────────────────────────────────────────────────────────────.
// Assertion helpers.
// ─────────────────────────────────────────────────────────────────────────────.

func observeOne(t *testing.T, probe *clusterprobe.Probe, id orchestrator.AgentID) orchestrator.Actual {
	t.Helper()
	actual, err := probe.Observe(context.Background(), []orchestrator.AgentID{id})
	if err != nil {
		t.Fatalf("Observe: unexpected error: %v", err)
	}
	got, present := actual[id]
	if !present {
		t.Fatalf("id %q absent from result %+v", id, actual)
	}
	return got
}

// assertActual compares the three observed scalar fields of an Actual (orchestrator.Actual
// embeds agentsession.TokenLedger, which holds a map and is not ==-comparable; this Probe
// leaves Ledger zero, so the scalar triple is the full observed surface to assert).
func assertActual(t *testing.T, got *orchestrator.Actual, workspaceLive, sessionLive bool, state agentsession.State) {
	t.Helper()
	if got.WorkspaceLive != workspaceLive || got.SessionLive != sessionLive || got.SessionState != state {
		t.Fatalf("Actual mismatch:\n got  {WorkspaceLive:%v SessionLive:%v SessionState:%v}\n want {WorkspaceLive:%v SessionLive:%v SessionState:%v}",
			got.WorkspaceLive, got.SessionLive, got.SessionState, workspaceLive, sessionLive, state)
	}
}

func assertKind(t *testing.T, err error, want errors.Kind) {
	t.Helper()
	if got := errors.KindOf(err); got != want {
		t.Fatalf("error Kind = %v, want %v (err: %v)", got, want, err)
	}
}

func assertConfigError(t *testing.T, err error) {
	t.Helper()
	if !errors.IsType[*clusterprobe.ConfigError](err) {
		t.Fatalf("want a *ConfigError in the chain, got %v", err)
	}
}
