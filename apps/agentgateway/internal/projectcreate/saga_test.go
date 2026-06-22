package projectcreate_test

import (
	"context"
	"sync"
	"testing"
	"time"

	edenerrors "github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/secrets"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/eden/apps/agentgateway/internal/projectcreate"
)

// This file unit-tests the saga step machine end to end over FAKE ports (forge/seeder/orchestrator) and
// in-memory stores that mirror the real Postgres/dev fakes' semantics (idempotent Record, terminal
// Advance, status-patch read-modify-write). It proves: the happy path walks all four steps and lands at
// WIZARD with every saga-scratch field recorded; a step fault parks the project at FAILED with the
// reason + step; a resume picks up at the first not-done step and never re-runs a done step; an
// idempotent replay of a completed saga is a no-op.

// ── fakes ────────────────────────────────────────────────────────────────────────────────────────.

type fakeProjectStore struct {
	mutex    sync.Mutex
	projects map[string]gateway.Project
	clock    projectcreate.Clock
}

func newFakeProjectStore(clock projectcreate.Clock) *fakeProjectStore {
	return &fakeProjectStore{projects: map[string]gateway.Project{}, clock: clock}
}

//nolint:gocritic // matches gateway.ProjectStore (Create takes the Project by value).
func (s *fakeProjectStore) Create(_ context.Context, project gateway.Project) (gateway.Project, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	s.projects[project.ID] = project
	return project, nil
}

func (s *fakeProjectStore) Get(_ context.Context, id string) (gateway.Project, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	project, ok := s.projects[id]
	if !ok {
		return gateway.Project{}, edenerrors.New(edenerrors.KindNotFound, "fake: no project "+id)
	}
	return project, nil
}

func (s *fakeProjectStore) List(_ context.Context, _ gateway.ProjectFilter) (gateway.ProjectPage, error) {
	return gateway.ProjectPage{}, nil
}

//nolint:gocritic // matches gateway.ProjectStore (UpdateStatus takes the patch by value).
func (s *fakeProjectStore) UpdateStatus(_ context.Context, id string, patch gateway.ProjectStatusPatch) (gateway.Project, error) {
	if patch.Status != nil && !gateway.ValidProjectStatus(*patch.Status) {
		return gateway.Project{}, edenerrors.New(edenerrors.KindInvalid, "fake: off-contract status")
	}
	s.mutex.Lock()
	defer s.mutex.Unlock()
	project, ok := s.projects[id]
	if !ok {
		return gateway.Project{}, edenerrors.New(edenerrors.KindNotFound, "fake: no project "+id)
	}
	patch.ApplyTo(&project)
	project.UpdatedAt = s.clock.Now()
	s.projects[id] = project
	return project, nil
}

type fakeStepStore struct {
	mutex sync.Mutex
	steps []gateway.CreateStep
	clock projectcreate.Clock
}

func newFakeStepStore(clock projectcreate.Clock) *fakeStepStore {
	return &fakeStepStore{clock: clock}
}

//nolint:gocritic // matches gateway.CreateStepStore (Record takes the step by value).
func (s *fakeStepStore) Record(_ context.Context, step gateway.CreateStep) (gateway.CreateStep, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.steps {
		if s.steps[i].ProjectID == step.ProjectID && s.steps[i].Step == step.Step {
			return s.steps[i], nil // idempotent on (projectID, step)
		}
	}
	step.Status = gateway.CreateStepStatusPending
	step.StartedAt = s.clock.Now()
	s.steps = append(s.steps, step)
	return step, nil
}

func (s *fakeStepStore) Advance(_ context.Context, projectID, step, status string, output gateway.RawJSON) (gateway.CreateStep, error) {
	if !gateway.ValidCreateStepStatus(status) || status == gateway.CreateStepStatusPending {
		return gateway.CreateStep{}, edenerrors.New(edenerrors.KindInvalid, "fake: non-terminal advance")
	}
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.steps {
		if s.steps[i].ProjectID == projectID && s.steps[i].Step == step {
			s.steps[i].Status = status
			s.steps[i].Output = output
			s.steps[i].FinishedAt = s.clock.Now()
			return s.steps[i], nil
		}
	}
	return gateway.CreateStep{}, edenerrors.New(edenerrors.KindNotFound, "fake: no step "+step)
}

func (s *fakeStepStore) Get(_ context.Context, projectID, step string) (gateway.CreateStep, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.steps {
		if s.steps[i].ProjectID == projectID && s.steps[i].Step == step {
			return s.steps[i], nil
		}
	}
	return gateway.CreateStep{}, edenerrors.New(edenerrors.KindNotFound, "fake: no step "+step)
}

func (s *fakeStepStore) List(_ context.Context, projectID string) ([]gateway.CreateStep, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	out := make([]gateway.CreateStep, 0)
	for i := range s.steps {
		if s.steps[i].ProjectID == projectID {
			out = append(out, s.steps[i])
		}
	}
	return out, nil
}

// markDone is a test seam: pre-record a step as DONE so a resume test starts past it.
func (s *fakeStepStore) markDone(projectID, step string) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	s.steps = append(s.steps, gateway.CreateStep{
		ProjectID: projectID, Step: step, Status: gateway.CreateStepStatusDone,
		IdempotencyKey: projectID + ":" + step, StartedAt: s.clock.Now(), FinishedAt: s.clock.Now(),
	})
}

type fakeForge struct {
	mutex sync.Mutex
	calls int
	err   error
}

func (f *fakeForge) CreateRepository(_ context.Context, input projectcreate.CreateRepositoryInput) (projectcreate.RepositoryCoordinates, error) {
	f.mutex.Lock()
	defer f.mutex.Unlock()
	f.calls++
	if f.err != nil {
		return projectcreate.RepositoryCoordinates{}, f.err
	}
	return projectcreate.RepositoryCoordinates{
		Owner: input.Owner, Name: input.Name,
		CloneURL: "https://github.com/" + input.Owner + "/" + input.Name + ".git", DefaultBranch: "main",
	}, nil
}

type fakeSeeder struct {
	mutex sync.Mutex
	calls int
	err   error
}

func (f *fakeSeeder) SeedRepository(_ context.Context, _ projectcreate.SeedInput) (projectcreate.SeedResult, error) {
	f.mutex.Lock()
	defer f.mutex.Unlock()
	f.calls++
	if f.err != nil {
		return projectcreate.SeedResult{}, f.err
	}
	return projectcreate.SeedResult{DefaultBranch: "main", CommitID: "abc123seedcommit"}, nil
}

// fakeManager is a minimal orchestrator.Manager: Spawn admits an agent, Get returns it (its status is
// scripted so the readiness step can drive ready/failed). It implements the 5-method surface but only
// Spawn/Get are exercised by the saga.
type fakeManager struct {
	mutex      sync.Mutex
	spawnCalls int
	getCalls   int
	spawnErr   error
	agent      orchestrator.Agent
	// readyAfter is the number of Get calls before the agent reports StatusRunning (0 == ready on the
	// first Get); failAt, when >0, returns StatusFailed on that Get call instead.
	readyAfter int
	failAt     int
}

//nolint:gocritic // mirrors orchestrator.Manager.Spawn — SpawnRequest is the frozen, copyable port input taken by value.
func (m *fakeManager) Spawn(_ context.Context, request orchestrator.SpawnRequest) (orchestrator.Agent, error) {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	m.spawnCalls++
	if m.spawnErr != nil {
		return orchestrator.Agent{}, m.spawnErr
	}
	m.agent = orchestrator.Agent{
		ID:      orchestrator.AgentID("agent-" + request.Tenant.ProjectID),
		Tenant:  request.Tenant,
		Status:  orchestrator.StatusPending,
		Session: orchestrator.SessionRef("session-" + request.Tenant.ProjectID),
	}
	return m.agent, nil
}

func (m *fakeManager) Get(_ context.Context, id orchestrator.AgentID) (orchestrator.Agent, error) {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	m.getCalls++
	agent := m.agent
	agent.ID = id
	switch {
	case m.failAt > 0 && m.getCalls >= m.failAt:
		agent.Status = orchestrator.StatusFailed
		agent.Detail = "scripted supervisor failure"
	case m.getCalls > m.readyAfter:
		agent.Status = orchestrator.StatusRunning
	default:
		agent.Status = orchestrator.StatusProvisioning
	}
	return agent, nil
}

//nolint:gocritic // mirrors orchestrator.Manager.List — Filter is the frozen, copyable port input taken by value.
func (m *fakeManager) List(_ context.Context, _ orchestrator.Filter) (orchestrator.Page, error) {
	return orchestrator.Page{}, nil
}

func (m *fakeManager) Stop(_ context.Context, _ orchestrator.AgentID, _ string) error { return nil }

func (m *fakeManager) Resume(_ context.Context, _ orchestrator.AgentID, _ string) error { return nil }

type fixedClock struct{}

func (fixedClock) Now() time.Time { return time.Date(2026, time.June, 22, 12, 0, 0, 0, time.UTC) }

// ── harness ──────────────────────────────────────────────────────────────────────────────────────.

type sagaHarness struct {
	saga     *projectcreate.Saga
	projects *fakeProjectStore
	steps    *fakeStepStore
	forge    *fakeForge
	seeder   *fakeSeeder
	manager  *fakeManager
}

func newSagaHarness(t *testing.T, configure func(*fakeForge, *fakeSeeder, *fakeManager)) *sagaHarness {
	t.Helper()
	clock := fixedClock{}
	projects := newFakeProjectStore(clock)
	steps := newFakeStepStore(clock)
	forge := &fakeForge{}
	seeder := &fakeSeeder{}
	manager := &fakeManager{}
	if configure != nil {
		configure(forge, seeder, manager)
	}
	saga, err := projectcreate.New(
		projectcreate.Config{
			RepositoryOwner:        "MateoSegura",
			PrivateRepository:      true,
			ForgeCredential:        secrets.Ref("gh://token"),
			SupervisorCredential:   secrets.Ref("claude://supervisor"),
			TemplateRepositoryURL:  "https://github.com/gophersys/template.git",
			TemplateReference:      "gophersys/template@main",
			SupervisorTemplate:     orchestrator.TemplateRef{Name: "supervisor", Version: "0.1.0"},
			OrganizationID:         "eden",
			SupervisorPollInterval: time.Millisecond,
		},
		projectcreate.Deps{
			Projects: projects, Steps: steps, Forge: forge, Seeder: seeder, Supervisor: manager, Clock: clock,
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return &sagaHarness{saga: saga, projects: projects, steps: steps, forge: forge, seeder: seeder, manager: manager}
}

// seedDraft writes the DB-first DRAFT row (status=creating) the handler would write before kicking.
func (h *sagaHarness) seedDraft(t *testing.T, id, name string) {
	t.Helper()
	if _, err := h.projects.Create(context.Background(), gateway.Project{
		ID: id, Name: name, Status: gateway.ProjectStatusCreating,
	}); err != nil {
		t.Fatalf("seed draft: %v", err)
	}
}

// project reads one project (erroring the test on a store fault) — the checked accessor the assertions use.
func (h *sagaHarness) project(t *testing.T, id string) gateway.Project {
	t.Helper()
	project, err := h.projects.Get(context.Background(), id)
	if err != nil {
		t.Fatalf("get project %q: %v", id, err)
	}
	return project
}

// step reads one ledger step (erroring on absence) — the checked accessor the assertions use.
func (h *sagaHarness) step(t *testing.T, id, step string) gateway.CreateStep {
	t.Helper()
	got, err := h.steps.Get(context.Background(), id, step)
	if err != nil {
		t.Fatalf("get step %q/%q: %v", id, step, err)
	}
	return got
}

// ledger reads all of a project's steps (erroring on a store fault).
func (h *sagaHarness) ledger(t *testing.T, id string) []gateway.CreateStep {
	t.Helper()
	steps, err := h.steps.List(context.Background(), id)
	if err != nil {
		t.Fatalf("list steps %q: %v", id, err)
	}
	return steps
}

// ── tests ────────────────────────────────────────────────────────────────────────────────────────.

func TestSaga_HappyPath_RecordsEverySagaScratchField(t *testing.T) {
	t.Parallel()
	h := newSagaHarness(t, nil)
	const id = "project-aabbccddeeff001122"
	h.seedDraft(t, id, "pay backend")

	if err := h.saga.Run(context.Background(), id); err != nil {
		t.Fatalf("Run: %v", err)
	}

	project := h.project(t, id)
	if project.Status != gateway.ProjectStatusWizard {
		t.Fatalf("terminal status = %q, want wizard", project.Status)
	}
	if project.LastError != "" {
		t.Errorf("LastError set on success: %q", project.LastError)
	}
	// Every saga-scratch field the steps record must be present.
	assertRecorded(t, "repo owner", project.GitHubOwner == "MateoSegura")
	assertRecorded(t, "repo name", project.GitHubRepo != "")
	assertRecorded(t, "repo url", project.RepoURL != "")
	assertRecorded(t, "default branch", project.DefaultBranch == "main")
	assertRecorded(t, "template ref", project.TemplateRef == "gophersys/template@main")
	assertRecorded(t, "supervisor agent", project.SupervisorAgentID != "")
	assertRecorded(t, "session ref", project.SessionRef != "")
	// The repo slug carries the project name AND the unique id suffix (collision-free).
	assertRecorded(t, "slug carries name prefix", contains(project.GitHubRepo, "pay-backend"))
}

func TestSaga_HappyPath_AllLedgerStepsDoneAndEffectsRunOnce(t *testing.T) {
	t.Parallel()
	h := newSagaHarness(t, nil)
	const id = "project-bbccddeeff0011223344"
	h.seedDraft(t, id, "pay backend")

	if err := h.saga.Run(context.Background(), id); err != nil {
		t.Fatalf("Run: %v", err)
	}

	steps := h.ledger(t, id)
	if len(steps) != 4 {
		t.Fatalf("ledger has %d steps, want 4", len(steps))
	}
	for _, step := range steps {
		if step.Status != gateway.CreateStepStatusDone {
			t.Errorf("step %q status = %q, want done", step.Step, step.Status)
		}
	}
	// Each effect ran exactly once.
	if h.forge.calls != 1 || h.seeder.calls != 1 || h.manager.spawnCalls != 1 {
		t.Errorf("effect call counts: forge=%d seeder=%d spawn=%d, want 1/1/1", h.forge.calls, h.seeder.calls, h.manager.spawnCalls)
	}
}

func assertRecorded(t *testing.T, what string, ok bool) {
	t.Helper()
	if !ok {
		t.Errorf("%s not recorded", what)
	}
}

func TestSaga_StepFailure_ParksAtFailedWithReasonAndStep(t *testing.T) {
	t.Parallel()
	seedFault := edenerrors.New(edenerrors.KindUnavailable, "template clone refused")
	h := newSagaHarness(t, func(_ *fakeForge, seeder *fakeSeeder, _ *fakeManager) {
		seeder.err = seedFault
	})
	const id = "project-failurecase0011223344"
	h.seedDraft(t, id, "billing")

	err := h.saga.Run(context.Background(), id)
	if err == nil {
		t.Fatal("Run returned nil on a seed fault, want the wrapped error")
	}
	if edenerrors.KindOf(err) != edenerrors.KindUnavailable {
		t.Errorf("error kind = %v, want unavailable", edenerrors.KindOf(err))
	}

	project := h.project(t, id)
	if project.Status != gateway.ProjectStatusFailed {
		t.Fatalf("status = %q, want failed", project.Status)
	}
	if project.SagaStep != projectcreate.StepSeedTemplate {
		t.Errorf("SagaStep = %q, want %q (the parked step)", project.SagaStep, projectcreate.StepSeedTemplate)
	}
	if project.LastError == "" || !contains(project.LastError, "template clone refused") {
		t.Errorf("LastError = %q, want the human reason", project.LastError)
	}
	// Step 1 is done; step 2 is failed; steps 3+4 never recorded.
	first := h.step(t, id, projectcreate.StepProvisionRepository)
	if first.Status != gateway.CreateStepStatusDone {
		t.Errorf("step 1 status = %q, want done", first.Status)
	}
	second := h.step(t, id, projectcreate.StepSeedTemplate)
	if second.Status != gateway.CreateStepStatusFailed {
		t.Errorf("step 2 status = %q, want failed", second.Status)
	}
}

func TestSaga_Resume_StartsAtFirstNotDoneStep(t *testing.T) {
	t.Parallel()
	h := newSagaHarness(t, nil)
	const id = "project-resumecase00aabbccdd"
	// A prior run completed steps 1 and 2 (repo + seed). Reflect that in BOTH the ledger (the resume
	// truth) and the project scratch (what those steps recorded), as a real crash-then-reload would.
	h.seedDraft(t, id, "analytics")
	if _, err := h.projects.UpdateStatus(context.Background(), id, gateway.ProjectStatusPatch{
		Status:        ptr(gateway.ProjectStatusSeedingTemplate),
		GitHubOwner:   ptr("MateoSegura"),
		GitHubRepo:    ptr("analytics-00aabbccdd"),
		RepoURL:       ptr("https://github.com/MateoSegura/analytics-00aabbccdd.git"),
		DefaultBranch: ptr("main"),
	}); err != nil {
		t.Fatalf("seed prior scratch: %v", err)
	}
	h.steps.markDone(id, projectcreate.StepProvisionRepository)
	h.steps.markDone(id, projectcreate.StepSeedTemplate)

	if err := h.saga.Run(context.Background(), id); err != nil {
		t.Fatalf("Run (resume): %v", err)
	}

	// The two already-done effects must NOT have re-run; only the supervisor steps execute.
	if h.forge.calls != 0 {
		t.Errorf("forge re-ran on resume (%d calls), want 0", h.forge.calls)
	}
	if h.seeder.calls != 0 {
		t.Errorf("seeder re-ran on resume (%d calls), want 0", h.seeder.calls)
	}
	if h.manager.spawnCalls != 1 {
		t.Errorf("supervisor spawn calls = %d, want 1", h.manager.spawnCalls)
	}
	project := h.project(t, id)
	if project.Status != gateway.ProjectStatusWizard {
		t.Fatalf("status after resume = %q, want wizard", project.Status)
	}
}

func TestSaga_CompletedReplay_IsNoOp(t *testing.T) {
	t.Parallel()
	h := newSagaHarness(t, nil)
	const id = "project-completed00aabb1122cc"
	h.seedDraft(t, id, "done project")
	// Run once to completion.
	if err := h.saga.Run(context.Background(), id); err != nil {
		t.Fatalf("first Run: %v", err)
	}
	forgeAfterFirst := h.forge.calls
	spawnAfterFirst := h.manager.spawnCalls

	// Replay: every step is done, so no effect should re-run and the status stays wizard.
	if err := h.saga.Run(context.Background(), id); err != nil {
		t.Fatalf("replay Run: %v", err)
	}
	if h.forge.calls != forgeAfterFirst || h.manager.spawnCalls != spawnAfterFirst {
		t.Errorf("replay re-ran effects: forge %d->%d spawn %d->%d", forgeAfterFirst, h.forge.calls, spawnAfterFirst, h.manager.spawnCalls)
	}
	project := h.project(t, id)
	if project.Status != gateway.ProjectStatusWizard {
		t.Errorf("status after replay = %q, want wizard", project.Status)
	}
}

func TestSaga_SupervisorReady_WaitsThenFlips(t *testing.T) {
	t.Parallel()
	h := newSagaHarness(t, func(_ *fakeForge, _ *fakeSeeder, manager *fakeManager) {
		manager.readyAfter = 2 // the agent reports running only on the 3rd Get
	})
	const id = "project-readiness00aa11bb22cc"
	h.seedDraft(t, id, "slow boot")

	if err := h.saga.Run(context.Background(), id); err != nil {
		t.Fatalf("Run: %v", err)
	}
	if h.manager.getCalls < 3 {
		t.Errorf("readiness polled %d times, want >= 3 (waited for ready)", h.manager.getCalls)
	}
	project := h.project(t, id)
	if project.Status != gateway.ProjectStatusWizard {
		t.Fatalf("status = %q, want wizard", project.Status)
	}
}

func TestSaga_SupervisorFailed_ParksAtFailed(t *testing.T) {
	t.Parallel()
	h := newSagaHarness(t, func(_ *fakeForge, _ *fakeSeeder, manager *fakeManager) {
		manager.failAt = 1 // the first readiness Get reports terminal failed
	})
	const id = "project-supfail00aa11bb22cc33"
	h.seedDraft(t, id, "doomed")

	err := h.saga.Run(context.Background(), id)
	if err == nil {
		t.Fatal("Run returned nil on a supervisor failure, want an error")
	}
	project := h.project(t, id)
	if project.Status != gateway.ProjectStatusFailed {
		t.Fatalf("status = %q, want failed", project.Status)
	}
	if project.SagaStep != projectcreate.StepSupervisorReady {
		t.Errorf("SagaStep = %q, want %q", project.SagaStep, projectcreate.StepSupervisorReady)
	}
}

func TestNew_RejectsMissingSeams(t *testing.T) {
	t.Parallel()
	valid := projectcreate.Config{
		RepositoryOwner: "MateoSegura", ForgeCredential: secrets.Ref("gh://token"),
		SupervisorCredential:  secrets.Ref("claude://supervisor"),
		TemplateRepositoryURL: "https://github.com/gophersys/template.git",
		SupervisorTemplate:    orchestrator.TemplateRef{Name: "supervisor", Version: "0.1.0"},
		OrganizationID:        "eden",
	}
	dependencies := projectcreate.Deps{
		Projects: newFakeProjectStore(fixedClock{}), Steps: newFakeStepStore(fixedClock{}),
		Forge: &fakeForge{}, Seeder: &fakeSeeder{}, Supervisor: &fakeManager{}, Clock: fixedClock{},
	}
	if _, err := projectcreate.New(valid, dependencies); err != nil {
		t.Fatalf("valid config rejected: %v", err)
	}

	// Each missing required seam is a KindInvalid at New.
	bad := dependencies
	bad.Forge = nil
	if _, err := projectcreate.New(valid, bad); edenerrors.KindOf(err) != edenerrors.KindInvalid {
		t.Errorf("missing Forge: kind = %v, want invalid", edenerrors.KindOf(err))
	}
	badConfig := valid
	badConfig.RepositoryOwner = ""
	if _, err := projectcreate.New(badConfig, dependencies); edenerrors.KindOf(err) != edenerrors.KindInvalid {
		t.Errorf("empty owner: kind = %v, want invalid", edenerrors.KindOf(err))
	}
	// The supervisor harness credential is a SEPARATE required reference from the gh-token.
	noSupervisorCred := valid
	noSupervisorCred.SupervisorCredential = secrets.Reference{}
	if _, err := projectcreate.New(noSupervisorCred, dependencies); edenerrors.KindOf(err) != edenerrors.KindInvalid {
		t.Errorf("missing SupervisorCredential: kind = %v, want invalid", edenerrors.KindOf(err))
	}
}

func ptr(s string) *string { return &s }

func contains(haystack, needle string) bool {
	return len(haystack) >= len(needle) && (haystack == needle || indexOf(haystack, needle) >= 0)
}

func indexOf(haystack, needle string) int {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return i
		}
	}
	return -1
}
