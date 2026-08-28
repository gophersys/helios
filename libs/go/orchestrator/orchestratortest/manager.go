package orchestratortest

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/secrets/secretstest"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// SeededCanary is the credential plaintext the harness seeds so the no-leak assertions
// have a concrete needle: it is resolved server-side at agentsession.Open, yet it must
// appear in NO Agent record, no ObservabilityEvent, no error string, and no store row.
const SeededCanary = "S3CR3T-orchestrator-token-do-not-leak"

// SeededCredentialRef is the loggable secrets.Reference the seeded canary resolves under
// (the VALUE never rides it). A consumer wiring its own SpawnRequest against the harness
// uses this so agentsession.Open can resolve the credential server-side.
const SeededCredentialRef = "vault://eden/anthropic#orchestrator-token" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value; the canary it resolves to lives server-side

// credentialRef is the internal alias for the seeded reference.
const credentialRef = SeededCredentialRef

// fakeHarnessKey is the harness key the scripted agentsessiontest adapter registers
// under, matched by the template's RouteKey.
const fakeHarnessKey = "fake"

// Manager is a deterministic in-process orchestrator.Manager: a real orchestrator.New
// over the in-memory fakes plus an agentsessiontest scripted Adapter wired into a real
// agentsession.Pool and a workspaceprovidertest Adapter wired into a real
// workspaceprovider.Provider — so it exercises the REAL reconcile logic, not a degenerate
// stub. WithScript sets the agentsession.Event sequence a launched session emits so a
// test drives ready/usage/terminal deterministically.
type Manager struct {
	pool         *orchestrator.Pool
	desiredStore *DesiredStore
	templates    *TemplateStore
	probe        *Probe
	telemetry    *Telemetry
	clock        *Clock
	workspaces   *workspaceprovidertest.Adapter
	provider     workspaceprovider.Provider // the scripted decorator the reconcile loop binds (wraps the real provider)
	inner        workspaceprovider.Provider // the undecorated real provider (used to provision orphans directly in a test)
	scripted     *scriptedProvider          // the arm point for driveResume recovery-branch faults
	sessions     agentsession.Factory
	secrets      *secretstest.Provider
}

// settings is the accumulated Option state (an unexported value bag — not the public
// orchestrator.Config; HNS-1 forbids "config" as a name).
type settings struct {
	templates         []orchestrator.AgentTemplate
	scripts           map[string][]agentsession.Event
	maxConcurrent     int
	workspaces        workspaceprovider.Provider
	wsAdapter         *workspaceprovidertest.Adapter
	provisionTimeout  time.Duration // 0 == the harness default (90s)
	retentionWindow   time.Duration // 0 == the harness default (24h)
	reconcileInterval time.Duration // 0 == the library default (Start's loop tick)
}

// Option configures New.
type Option func(*settings)

// WithTemplate seeds one resolvable AgentTemplate.
//
//nolint:gocritic // AgentTemplate is the contract's data record; the option carries it by value into the seed.
func WithTemplate(template orchestrator.AgentTemplate) Option {
	return func(s *settings) { s.templates = append(s.templates, template) }
}

// WithScript sets the agentsession.Event sequence the session for the template named
// templateName emits when reconcile Opens it (keyed by the template's RouteKey.Role, which
// the harness wires to the scripted adapter).
func WithScript(templateName string, script ...agentsession.Event) Option {
	return func(s *settings) {
		if s.scripts == nil {
			s.scripts = map[string][]agentsession.Event{}
		}
		s.scripts[templateName] = script
	}
}

// WithMaxConcurrent sets the per-(Tenant,Template) admission ceiling (to test LimitError).
func WithMaxConcurrent(n int) Option {
	return func(s *settings) { s.maxConcurrent = n }
}

// WithProvisionTimeout overrides Config.ProvisionTimeout (the bound on a Provision call), so a
// test proves a hung provision trips the deadline and marks the agent Failed.
func WithProvisionTimeout(d time.Duration) Option {
	return func(s *settings) { s.provisionTimeout = d }
}

// WithRetentionWindow overrides Config.RetentionWindow (how long terminal agents are kept
// before the Start loop reaps them), so a test proves the window is honored on the loop cadence.
func WithRetentionWindow(d time.Duration) Option {
	return func(s *settings) { s.retentionWindow = d }
}

// WithReconcileInterval overrides Config.ReconcileInterval (the Start loop's tick), so a test
// that exercises the loop cadence (retention) ticks fast and deterministically.
func WithReconcileInterval(d time.Duration) Option {
	return func(s *settings) { s.reconcileInterval = d }
}

// WithWorkspaces wires a specific workspaceprovider.Provider the reconcile loop provisions
// through (so a test inspects the lifecycle against the frozen S2 seam fake). When unset,
// the harness builds a real Provider over a fresh workspaceprovidertest.Adapter and
// exposes that Adapter via the Harness.
//
//nolint:ireturn // the option carries the frozen workspaceprovider.Provider port; that is the seam being injected.
func WithWorkspaces(provider workspaceprovider.Provider) Option {
	return func(s *settings) { s.workspaces = provider }
}

// New constructs a deterministic Manager over the fakes. It panics on a wiring error (the
// harness is statically valid; a panic is a programming error in a test, surfaced loudly).
func New(options ...Option) *Manager {
	configured := &settings{maxConcurrent: 0}
	for _, opt := range options {
		opt(configured)
	}

	clock := NewClock()
	desiredStore := NewDesiredStore()
	templates := NewTemplateStore(configured.templates...)
	probe := NewProbe()
	telemetry := &Telemetry{}
	secretsProvider := secretstest.New(map[string]string{credentialRef: SeededCanary})

	// Build the REAL agentsession.Factory over the scripted agentsessiontest adapter, so
	// reconcile Opens a genuine session whose script the test pinned.
	sessions := buildSessions(configured, secretsProvider)

	// Build (or accept) the workspace Provider over the frozen-seam fake.
	wsAdapter := configured.wsAdapter
	provider := configured.workspaces
	if provider == nil {
		wsAdapter = workspaceprovidertest.NewAdapter(workspaceProviderCaps()...)
		provider = buildWorkspaces(wsAdapter, secretsProvider)
	}

	// Wrap the real provider in the scripted decorator the reconcile loop binds, so a
	// conformance case can arm the driveResume recovery-branch faults (Open-miss, conflict)
	// against the SAME frozen seam. Unarmed, it passes straight through.
	scripted := newScriptedProvider(provider)

	provisionTimeout := configured.provisionTimeout
	if provisionTimeout == 0 {
		provisionTimeout = 90 * time.Second
	}
	retentionWindow := configured.retentionWindow
	if retentionWindow == 0 {
		retentionWindow = 24 * time.Hour
	}

	pool, err := orchestrator.New(
		orchestrator.Config{
			DefaultMaxConcurrent: configured.maxConcurrent,
			DefaultCluster:       orchestrator.ClusterRef{ID: "local-k3d"},
			ProvisionTimeout:     provisionTimeout,
			RetentionWindow:      retentionWindow,
			ReconcileInterval:    configured.reconcileInterval,
		},
		orchestrator.Deps{
			Desired:    desiredStore,
			Templates:  templates,
			Secrets:    secretsProvider,
			Telemetry:  telemetry,
			Clock:      clock,
			Workspaces: scripted,
			Sessions:   sessions,
			Probe:      probe,
		},
	)
	if err != nil {
		panic("orchestratortest.New: " + err.Error())
	}

	return &Manager{
		pool:         pool,
		desiredStore: desiredStore,
		templates:    templates,
		probe:        probe,
		telemetry:    telemetry,
		clock:        clock,
		workspaces:   wsAdapter,
		provider:     scripted,
		inner:        provider,
		scripted:     scripted,
		sessions:     sessions,
		secrets:      secretsProvider,
	}
}

// buildSessions wires the scripted agentsessiontest adapter into a real agentsession.Pool
// (the Factory reconcile Opens). One adapter serves every route; the script is the union
// the test pinned (one script per role key, defaulting to a clean ready→result run).
//
//nolint:ireturn // returns the agentsession.Factory port the reconcile loop binds (the frozen seam).
func buildSessions(configured *settings, secretsProvider *secretstest.Provider) agentsession.Factory {
	var script []agentsession.Event
	for _, s := range configured.scripts {
		script = s
		break
	}
	if script == nil {
		script = defaultScript()
	}
	adapter := agentsessiontest.New(script...)

	routing := map[agentsession.RouteKey]agentsession.Route{}
	for i := range configured.templates {
		routing[configured.templates[i].Routing] = agentsession.Route{Harness: fakeHarnessKey, Model: "fake-fable-5"}
	}
	if len(routing) == 0 {
		routing[agentsession.RouteKey{Role: "assistant"}] = agentsession.Route{Harness: fakeHarnessKey, Model: "fake-fable-5"}
	}

	pool, err := agentsession.New(
		agentsession.Config{Routing: routing},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{fakeHarnessKey: adapter},
			Secrets:    secretsProvider,
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      fixedSessionClock{},
		},
	)
	if err != nil {
		panic("orchestratortest.buildSessions: " + err.Error())
	}
	return pool
}

// buildWorkspaces wires a workspaceprovidertest.Adapter into a real workspaceprovider
// Provider over a docker default (the frozen S2 seam fake), reaping nothing of its own.
//
//nolint:ireturn // returns the frozen workspaceprovider.Provider port the reconcile loop binds.
func buildWorkspaces(adapter *workspaceprovidertest.Adapter, secretsProvider *secretstest.Provider) workspaceprovider.Provider {
	set, _, _, _ := dependenciestest.Fakes()
	provider, err := workspaceprovider.New(
		workspaceprovider.Config{Default: workspaceprovider.SubstrateDocker},
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{
				workspaceprovider.SubstrateDocker:     adapter,
				workspaceprovider.SubstrateKubernetes: adapter,
			},
			Secrets: secretsProvider,
			Clock:   set.Clock,
		},
	)
	if err != nil {
		panic("orchestratortest.buildWorkspaces: " + err.Error())
	}
	return provider
}

// workspaceProviderCaps is the full capability set the workspace fake declares so the
// provision/teardown lifecycle is exercised end to end.
func workspaceProviderCaps() []workspaceprovider.Capability {
	return []workspaceprovider.Capability{
		workspaceprovider.CapBindMount,
		workspaceprovider.CapEgressPolicy,
		workspaceprovider.CapResourceLimits,
		workspaceprovider.CapMultiTenant,
		workspaceprovider.CapReattach,
		workspaceprovider.CapLogStream,
	}
}

// defaultScript is the clean ready→usage→result run a session emits when a test pins no
// explicit script (the happy reconcile path).
func defaultScript() []agentsession.Event {
	return []agentsession.Event{
		agentsessiontest.TextDelta("working"),
		agentsessiontest.Usage(agentsession.UsageMeter{
			Model: "fake-fable-5", Harness: fakeHarnessKey,
			InputTokens: 100, OutputTokens: 40, CostMicros: 1500, Cumulative: true,
		}),
		agentsessiontest.Result(agentsession.TokenLedger{
			UsageMeter: agentsession.UsageMeter{
				Model: "fake-fable-5", Harness: fakeHarnessKey,
				InputTokens: 100, OutputTokens: 40, CostMicros: 1500, Cumulative: true,
			},
			Turns: 1,
		}, "done", "end_turn"),
	}
}

// fixedSessionClock is a deterministic agentsession.Clock for the harness's session Pool.
type fixedSessionClock struct{}

// Now returns a fixed instant.
func (fixedSessionClock) Now() time.Time {
	return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC)
}

// ── orchestrator.Manager + Watcher + Reconciler delegation ──────────────────────.

// Spawn delegates to the real Pool (the system under test); its already-wrapped, typed
// errors pass through unchanged so a test asserts on them.
//
//nolint:gocritic,wrapcheck // SpawnRequest is the frozen copyable input; the SUT's wrapped typed error passes through for assertion.
func (m *Manager) Spawn(ctx context.Context, request orchestrator.SpawnRequest) (orchestrator.Agent, error) {
	return m.pool.Spawn(ctx, request)
}

// Get delegates to the real Pool.
//
//nolint:wrapcheck // the SUT's wrapped typed error passes through for assertion.
func (m *Manager) Get(ctx context.Context, id orchestrator.AgentID) (orchestrator.Agent, error) {
	return m.pool.Get(ctx, id)
}

// List delegates to the real Pool.
//
//nolint:gocritic,wrapcheck // Filter is the frozen copyable query; the SUT's wrapped error passes through for assertion.
func (m *Manager) List(ctx context.Context, filter orchestrator.Filter) (orchestrator.Page, error) {
	return m.pool.List(ctx, filter)
}

// Stop delegates to the real Pool.
//
//nolint:wrapcheck // the SUT's wrapped typed error passes through for assertion.
func (m *Manager) Stop(ctx context.Context, id orchestrator.AgentID, by string) error {
	return m.pool.Stop(ctx, id, by)
}

// Resume delegates to the real Pool.
//
//nolint:wrapcheck // the SUT's wrapped typed error passes through for assertion.
func (m *Manager) Resume(ctx context.Context, id orchestrator.AgentID, by string) error {
	return m.pool.Resume(ctx, id, by)
}

// Watch delegates to the real Pool.
//
//nolint:gocritic,ireturn,wrapcheck // Filter is the frozen copyable query; Watch returns the AgentStream port and the SUT's wrapped error.
func (m *Manager) Watch(ctx context.Context, filter orchestrator.Filter) (orchestrator.AgentStream, error) {
	return m.pool.Watch(ctx, filter)
}

// Reconcile drives a single deterministic pass by hand (no goroutine), so a test asserts
// exact transitions. It binds the harness's scripted probe/workspaces/sessions.
//
//nolint:wrapcheck // the SUT's wrapped error passes through for assertion.
func (m *Manager) Reconcile(ctx context.Context) (orchestrator.ReconcileReport, error) {
	return m.pool.Reconcile(ctx, orchestrator.ReconcilePorts{
		Workspaces: m.provider,
		Sessions:   m.sessions,
		Probe:      m.probe,
	})
}

// Advance steps the manual Clock for retention/timeout assertions. Fluent.
func (m *Manager) Advance(d time.Duration) *Manager {
	m.clock.Advance(d)
	return m
}

// RecycleNode tears the agent's workspace down OUT-OF-BAND (the provider Teardown the
// orchestrator did NOT request) — a deterministic model of a real node-recycle / preemption
// that reclaims the pod under a live agent. It reads the handle off the desired record (the
// durable state that survives the recycle) and releases it through the bound provider, so the
// NEXT driveResume Open misses and re-provisions. Mirrors RealHarness.RecycleNode so the same
// conformance case drives both bindings. Returns false when the agent has no live workspace.
func (m *Manager) RecycleNode(ctx context.Context, id orchestrator.AgentID) (bool, error) {
	agent, err := m.desiredStore.Get(ctx, id)
	if err != nil || agent.Workspace.IsZero() {
		return false, nil //nolint:nilerr // no live workspace to recycle is not an error here.
	}
	if terr := m.provider.Teardown(ctx, agent.Workspace); terr != nil {
		return false, terr //nolint:wrapcheck // the provider's typed error passes through for the test to assert.
	}
	return true, nil
}

// Pool exposes the underlying *orchestrator.Pool for lifecycle (Start/Close) in tests.
func (m *Manager) Pool() *orchestrator.Pool { return m.pool }

// Probe exposes the scriptable probe so a test pins the observed actual.
func (m *Manager) Probe() *Probe { return m.probe }

// Telemetry exposes the recorder so a test asserts emitted events.
func (m *Manager) Telemetry() *Telemetry { return m.telemetry }

// Clock exposes the manual clock so a test steps retention/timeout.
func (m *Manager) Clock() *Clock { return m.clock }

// Workspaces exposes the frozen-seam fake Adapter so a test asserts provision/teardown.
func (m *Manager) Workspaces() *workspaceprovidertest.Adapter { return m.workspaces }

// Provider exposes the workspaceprovider.Provider the reconcile loop binds (the scripted
// decorator over the real provider), so a test can drive Reconcile with the Pool's DEFAULT
// in-process Probe (omitting Probe from ReconcilePorts) and still supply the workspace/session
// seams. Unarmed it is a pure pass-through to the real provider.
//
//nolint:ireturn // returns the frozen workspaceprovider.Provider port the reconcile loop binds.
func (m *Manager) Provider() workspaceprovider.Provider { return m.provider }

// Sessions exposes the real agentsession.Factory the reconcile loop binds, paired with
// Provider for the default-Probe drive path.
//
//nolint:ireturn // returns the frozen agentsession.Factory port the reconcile loop binds.
func (m *Manager) Sessions() agentsession.Factory { return m.sessions }

// FailNextResumeOpens arms the next n Open calls on the bound provider to transiently miss
// (the recorded handle's pod still settling), so driveResume falls through to re-provision.
func (m *Manager) FailNextResumeOpens(n int) { m.scripted.FailNextOpens(n, nil) }

// ConflictNextProvision arms the next Provision to surface a settling ConflictError so
// driveResume takes the conflict-readopt branch.
func (m *Manager) ConflictNextProvision() { m.scripted.ConflictNextProvision() }

// ReprovisionsObserved returns how many genuine re-provisions (Create) the scripted seam saw
// (excluding the armed-conflict short-circuit), so a case asserts exactly one re-adopt.
func (m *Manager) ReprovisionsObserved() int { return m.scripted.Provisions() }

// BlockProvision makes every Provision hang until its ctx is canceled (a hung provider), so a
// test proves Config.ProvisionTimeout bounds the call and marks the agent Failed. Fluent.
func (m *Manager) BlockProvision() *Manager {
	m.scripted.BlockProvision()
	return m
}

// DesiredStore exposes the in-memory desired-state store for record-shape assertions.
func (m *Manager) DesiredStore() *DesiredStore { return m.desiredStore }

// compile-time assertions: *Manager satisfies the orchestrator ports.
var (
	_ orchestrator.Manager = (*Manager)(nil)
	_ orchestrator.Watcher = (*Manager)(nil)
)

// AssertNoOrphans fails t if any provisioned workspace was not Released by the end of the
// test (the forced-CRUD / leak guarantee made runnable). It compares the frozen-seam
// fake's Provisioned vs Destroyed by Handle.
func (m *Manager) AssertNoOrphans(t TestingT) {
	t.Helper()
	if m.workspaces == nil {
		return
	}
	destroyed := map[string]bool{}
	for _, h := range m.workspaces.Destroyed {
		destroyed[h.String()] = true
	}
	// Every provisioned workspace with a corresponding terminal agent must be destroyed.
	live, err := m.desiredStore.List(context.Background(), orchestrator.Filter{Limit: 0})
	if err != nil {
		t.Errorf("orchestratortest: AssertNoOrphans list: %v", err)
		return
	}
	for i := range live.Agents {
		agent := live.Agents[i]
		if agent.Status.Terminal() && !agent.Workspace.IsZero() && !destroyed[agent.Workspace.String()] {
			t.Errorf("orchestratortest: orphaned workspace for terminal agent %s: %s not Released",
				agent.ID, agent.Workspace.String())
		}
	}
}

// AssertNoSecretInRecord fails t if canary appears in any Agent record's logged form, an
// ObservabilityEvent, the workspace fake's recorded specs, or an error string (the
// credential-seam guarantee, runnable — mirrors agentsessiontest.AssertNoSecretInStream).
func (m *Manager) AssertNoSecretInRecord(t TestingT, canary string) {
	t.Helper()
	if canary == "" {
		return
	}
	// Scan EVERY record version ever written (the full Put history), not just the final
	// List() — a leak into a transient field (Detail/By) that a later transition overwrites
	// would otherwise escape a guard that reads only the latest record per agent.
	versions := m.desiredStore.AllVersions()
	for i := range versions {
		if recordContainsCanary(&versions[i], canary) {
			t.Errorf("orchestratortest: secret leaked into an Agent record version %s: canary %q present",
				versions[i].ID, canary)
		}
	}
	if m.telemetry.containsCanary(canary) {
		t.Errorf("orchestratortest: secret leaked into an ObservabilityEvent: canary %q present", canary)
	}
	if m.workspaces != nil {
		m.workspaces.AssertNoSecretMaterial(t, canary)
	}
}

// TestingT is the minimal testing surface the assertions need (satisfied by *testing.T).
type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
}

// compile-time assertion: *testing.T satisfies TestingT.
var _ TestingT = (*testing.T)(nil)
