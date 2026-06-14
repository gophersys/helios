//go:build integration || load

package orchestratortest

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	natsserver "github.com/nats-io/nats-server/v2/server"
	natsservertest "github.com/nats-io/nats-server/v2/test"
	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/secrets/secretstest"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// RealHarness is the THIN-ORCHESTRATOR-over-REAL-pods harness (B4): a real orchestrator.Pool
// bound to (a) the REAL workspaceprovider.Provider/Supervisor over a real substrate adapter
// (docker EphemeralContainer or k3d cluster), (b) a REAL Postgres DesiredStore (desired-state
// survives node recycle), (c) the REAL SupervisedProbe (Actual derived from the provider's
// supervised Status — the HARD lifecycle), and (d) a real agentsession.Factory (the scripted
// stub harness the other lanes use). Soft Stop/Kill publishes to agent.<id>.control over a
// REAL NATS connection AFTER recording the desired-intent. Everything is reaped on t.Cleanup.
//
// This is the proof that the orchestrator's reconcile loop — spawn → running → stop → resume
// → kill — runs end-to-end over REAL pods, a REAL Postgres, and a REAL NATS, with the
// orchestrator THINNED (it owns desired-state and Probes the supervised Status, never raw
// heartbeats). No mock of any of those substrates.
type RealHarness struct {
	pool     *orchestrator.Pool
	store    *PostgresStore
	provider *workspaceprovider.Provisioner
	sessions agentsession.Factory
	probe    *SupervisedProbe
	control  *nats.Conn
	clock    *Clock
}

// RealConfig is the resolved input for a RealHarness (the entrypoint command the workload
// pods run, the substrate-default cluster, the admission ceiling).
type RealConfig struct {
	// Entrypoint is the workload-pod PID-1 command the orchestrator Provisions (the
	// agent-runtime sidecar in production; a representative real workload for the gate — a
	// long-lived sleep that keeps the supervised workspace Running so the reconcile loop
	// Probes a live Status). The point under test is the orchestrator↔provider↔NATS↔Postgres
	// reconcile, NOT building the agent-runtime container image (that is the B8 hand-off).
	Entrypoint []string
	Image      string
	Substrate  orchestrator.Substrate
	Cluster    orchestrator.ClusterRef
	MaxAgents  int
}

// NewRealHarness boots the real substrates and wires the thinned orchestrator over them. It
// SKIPS (via the substrate harnesses / container boots) when docker/k3d/postgres is
// unavailable locally, and is REQUIRED in the devcontainer where all are live.
func NewRealHarness(t *testing.T, adapter workspaceprovider.Adapter, substrate orchestrator.Substrate, configuration RealConfig) *RealHarness {
	t.Helper()
	ctx := t.Context()

	secretsProvider := newRealSecrets()
	provider := newRealProvider(t, adapter, substrate, secretsProvider)

	dsn := startPostgres(t)
	store, err := NewPostgresStore(ctx, dsn)
	if err != nil {
		t.Fatalf("connect real postgres DesiredStore: %v", err)
	}
	t.Cleanup(store.Close)

	natsURL := startEmbeddedNATS(t)
	control, err := nats.Connect(natsURL, nats.Timeout(5*time.Second))
	if err != nil {
		t.Fatalf("dial real NATS for soft control: %v", err)
	}
	t.Cleanup(control.Close)

	probe := NewSupervisedProbe(provider, &storeResolver{store: store})
	sessions := buildRealSessions(secretsProvider)
	clock := NewClock()

	pool, err := orchestrator.New(
		orchestrator.Config{
			DefaultMaxConcurrent: configuration.MaxAgents,
			DefaultCluster:       configuration.Cluster,
			ProvisionTimeout:     120 * time.Second,
			RetentionWindow:      24 * time.Hour,
		},
		orchestrator.Deps{
			Desired:    store,
			Templates:  NewTemplateStore(realTemplate(&configuration)),
			Secrets:    secretsProvider,
			Telemetry:  &Telemetry{},
			Clock:      clock,
			Workspaces: provider,
			Sessions:   sessions,
			Probe:      probe,
		},
	)
	if err != nil {
		t.Fatalf("construct thinned orchestrator over real pods: %v", err)
	}

	return &RealHarness{
		pool:     pool,
		store:    store,
		provider: provider,
		sessions: sessions,
		probe:    probe,
		control:  control,
		clock:    clock,
	}
}

// Pool exposes the real orchestrator.Pool (the system under test).
func (h *RealHarness) Pool() *orchestrator.Pool { return h.pool }

// Supervisor exposes the real workspaceprovider.Supervisor the probe reads (so a test asserts
// the supervised Status directly — the HARD lifecycle truth).
//
//nolint:ireturn // returns the frozen workspaceprovider.Supervisor port the probe reads.
func (h *RealHarness) Supervisor() workspaceprovider.Supervisor { return h.provider }

// Store exposes the real Postgres DesiredStore (so a test asserts the persisted record shape /
// the no-leak history).
func (h *RealHarness) Store() *PostgresStore { return h.store }

// Reconcile drives ONE deterministic reconcile pass over the REAL ports (no goroutine), so a
// test asserts exact transitions against the live substrate.
//
//nolint:wrapcheck // the SUT's wrapped error passes through for assertion.
func (h *RealHarness) Reconcile(ctx context.Context) (orchestrator.ReconcileReport, error) {
	return h.pool.Reconcile(ctx, orchestrator.ReconcilePorts{
		Workspaces: h.provider,
		Sessions:   h.sessions,
		Probe:      h.probe,
	})
}

// SoftControl publishes a control verb to agent.<id>.control over the REAL NATS connection —
// the SOFT control signal (ADR-0022 §4: NATS = the soft signal; the docker/k8s API = the
// hard lifecycle). The orchestrator records the desired-intent FIRST (via Stop, below); this
// is the low-latency nudge to the in-pod PID-1 that the hard reconcile then enforces.
func (h *RealHarness) SoftControl(id orchestrator.AgentID, verb, by string) error {
	message := controlMessage{
		AgentID: string(id),
		Verb:    verb,
		By:      by,
		OTel:    map[string]string{"traceparent": traceParent},
	}
	payload, err := json.Marshal(message)
	if err != nil {
		return errors.Wrap(errors.KindInternal, "orchestratortest: marshal control message", err)
	}
	if pubErr := h.control.Publish(controlSubject(id), payload); pubErr != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestratortest: publish soft control", pubErr)
	}
	if ferr := h.control.Flush(); ferr != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestratortest: flush soft control", ferr)
	}
	return nil
}

// SoftStopThenKill records the DESIRED terminal intent FIRST (the durable Stop the
// orchestrator owns), THEN publishes the low-latency stop/kill nudge to agent.<id>.control —
// the contract order (record desired-intent first, soft-signal second). The hard kill (the
// provider tearing down the pod) is enacted by the reconcile loop's driveStopping →
// Teardown, observed via the supervised Probe going Gone.
func (h *RealHarness) SoftStopThenKill(ctx context.Context, id orchestrator.AgentID, kill bool, by string) error {
	if err := h.pool.Stop(ctx, id, by); err != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestratortest: record stop intent before soft signal", err)
	}
	verb := "stop"
	if kill {
		verb = "kill"
	}
	return h.SoftControl(id, verb, by)
}

// ControlSubscription subscribes to agent.<id>.control over the real NATS connection so a test
// can assert the SOFT signal actually reached the bus (the round-trip the in-pod sidecar would
// consume). Reaped on cleanup.
func (h *RealHarness) ControlSubscription(t *testing.T, id orchestrator.AgentID) *nats.Subscription {
	t.Helper()
	sub, err := h.control.SubscribeSync(controlSubject(id))
	if err != nil {
		t.Fatalf("subscribe control %s: %v", id, err)
	}
	t.Cleanup(func() { _ = sub.Unsubscribe() }) //nolint:errcheck // best-effort reap.
	_ = h.control.Flush()                       //nolint:errcheck // propagate the interest before a publish.
	return sub
}

// Advance steps the manual Clock for retention/timeout assertions.
func (h *RealHarness) Advance(d time.Duration) { h.clock.Advance(d) }

// RecycleNode tears the agent's pod down OUT-OF-BAND (the provider Teardown the orchestrator
// did NOT request) — a real node-recycle / preemption. The next reconcile pass Probes a Gone
// supervised Status (the dropped actual) and moves the agent Running → Suspended; a subsequent
// Resume re-provisions and re-attaches. It reads the handle off the REAL Postgres record (the
// durable state that survives the recycle). Returns false when the agent has no live workspace.
func (h *RealHarness) RecycleNode(ctx context.Context, id orchestrator.AgentID) (bool, error) {
	agent, err := h.store.Get(ctx, id)
	if err != nil || agent.Workspace.IsZero() {
		return false, nil //nolint:nilerr // no live workspace to recycle is not an error here.
	}
	if terr := h.provider.Teardown(ctx, agent.Workspace); terr != nil {
		return false, errors.Wrap(errors.KindUnavailable, "orchestratortest: out-of-band recycle teardown", terr)
	}
	return true, nil
}

// Spawn/Get/List/Stop/Resume delegate to the real Pool (the Manager surface under test).

// Spawn records the desired intent on the real Pool.
//
//nolint:gocritic,wrapcheck // SpawnRequest is the frozen copyable input; the SUT's wrapped error passes through.
func (h *RealHarness) Spawn(ctx context.Context, request orchestrator.SpawnRequest) (orchestrator.Agent, error) {
	return h.pool.Spawn(ctx, request)
}

// Get reads one record from the real Pool (backed by Postgres).
//
//nolint:wrapcheck // the SUT's wrapped error passes through for assertion.
func (h *RealHarness) Get(ctx context.Context, id orchestrator.AgentID) (orchestrator.Agent, error) {
	return h.pool.Get(ctx, id)
}

// List reads matching records from the real Pool (backed by Postgres).
//
//nolint:gocritic,wrapcheck // Filter is the frozen copyable query; the SUT's wrapped error passes through.
func (h *RealHarness) List(ctx context.Context, filter orchestrator.Filter) (orchestrator.Page, error) {
	return h.pool.List(ctx, filter)
}

// Stop records the terminal intent on the real Pool.
//
//nolint:wrapcheck // the SUT's wrapped error passes through for assertion.
func (h *RealHarness) Stop(ctx context.Context, id orchestrator.AgentID, by string) error {
	return h.pool.Stop(ctx, id, by)
}

// Resume records the re-attach intent on the real Pool.
//
//nolint:wrapcheck // the SUT's wrapped error passes through for assertion.
func (h *RealHarness) Resume(ctx context.Context, id orchestrator.AgentID, by string) error {
	return h.pool.Resume(ctx, id, by)
}

// storeResolver resolves an AgentID to its persisted workspace Handle + ledger by reading the
// real Postgres DesiredStore — the SupervisedProbe's HandleResolver. It reads the SAME durable
// record the orchestrator wrote, so the probe's supervised read is keyed off persisted state
// (the multi-node, stateless-restart property).
type storeResolver struct{ store *PostgresStore }

// HandleFor reads the agent's record and returns its workspace Handle + ledger; ok=false when
// the record is absent or has no workspace yet (Pending).
func (r *storeResolver) HandleFor(ctx context.Context, id orchestrator.AgentID) (workspaceprovider.Handle, agentsession.TokenLedger, bool) {
	agent, err := r.store.Get(ctx, id)
	if err != nil || agent.Workspace.IsZero() {
		return workspaceprovider.Handle{}, agentsession.TokenLedger{}, false
	}
	return agent.Workspace, agent.Ledger, true
}

// realTemplate builds the AgentTemplate the real harness spawns from: a real Entrypoint
// workload-pod (the agent-runtime sidecar in production; a representative real workload here)
// on the configured substrate, with a small resource envelope.
func realTemplate(configuration *RealConfig) orchestrator.AgentTemplate {
	return orchestrator.AgentTemplate{
		Ref:     orchestrator.TemplateRef{Name: "real-runtime", Version: "1.0.0"},
		Routing: agentsession.RouteKey{Role: "assistant"},
		Sandbox: orchestrator.SandboxSpec{
			Substrate:  configuration.Substrate,
			Image:      configuration.Image,
			Resources:  orchestrator.ResourceEnvelope{CPUMillis: 250, MemoryMiB: 64, EphemeralMiB: 64},
			Entrypoint: configuration.Entrypoint, // the workload-pod PID-1 (OD-15-a)
		},
		Limits: orchestrator.Limits{Budget: agentsession.Budget{MaxTurns: 4}},
	}
}

// ── soft-control wire shapes (the agent.<id>.control protocol; mirrors agentruntime) ───────.

// traceParent is the OTel carrier the soft-control messages stamp (every NATS message carries
// trace context, ADR-0022 §4).
const traceParent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

// controlMessage is the typed soft-control message published to agent.<id>.control. It mirrors
// agentruntime.ControlMessage's wire shape (the in-pod PID-1 consumes exactly this) WITHOUT a
// cross-module import: the orchestrator does not depend on agentruntime (the bus subjects are a
// data contract, not a code dependency). It carries NO secret value.
type controlMessage struct {
	AgentID string            `json:"agentId"`
	Verb    string            `json:"verb"`
	Text    string            `json:"text,omitempty"`
	By      string            `json:"by,omitempty"`
	OTel    map[string]string `json:"otel,omitempty"`
}

// controlSubject renders agent.<id>.control (the soft-control subject; the SAME format
// agentruntime.ControlSubject renders — a data contract).
func controlSubject(id orchestrator.AgentID) string {
	return "agent." + string(id) + ".control"
}

// ── real-substrate container boots (docker-out-of-docker; the vaultadapter posture) ────────.

// startPostgres boots a REAL postgres:16-alpine container docker-out-of-docker, reaped on
// t.Cleanup under a unique name, and returns a DSN reachable over the container's docker-bridge
// IP (the devcontainer shares the docker network — the vaultadapter posture). SKIPS when docker
// is unavailable; REQUIRED in the devcontainer.
func startPostgres(t *testing.T) string {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker CLI not on PATH: the real-postgres DesiredStore arm is skipped")
	}
	name := "eden-orchestrator-pg-" + strconv.FormatInt(time.Now().UnixNano(), 36)
	// #nosec G204 -- fixed `docker run` of the official postgres image; name is time-derived, not user input.
	run := exec.Command("docker", "run", "-d", "--rm", "--name", name,
		"-e", "POSTGRES_PASSWORD=eden", "-e", "POSTGRES_USER=eden", "-e", "POSTGRES_DB=eden",
		"postgres:16-alpine", "-c", "fsync=off") // fsync=off: ephemeral test DB, faster boot
	if out, err := run.CombinedOutput(); err != nil {
		t.Skipf("could not start postgres container (image unavailable?): %v\n%s", err, out)
	}
	t.Cleanup(func() {
		// #nosec G204 -- fixed `docker rm -f` of the just-created container by its time-derived name.
		_ = exec.Command("docker", "rm", "-f", name).Run() //nolint:errcheck // best-effort reap.
	})
	ip := dockerBridgeIP(t, name)
	dsn := fmt.Sprintf("postgres://eden:eden@%s:5432/eden?sslmode=disable", ip)
	waitForPostgres(t, dsn)
	return dsn
}

// dockerBridgeIP reads the container's docker-bridge IP (directly reachable from the
// devcontainer on the shared docker network).
func dockerBridgeIP(t *testing.T, name string) string {
	t.Helper()
	// #nosec G204 -- fixed `docker inspect` of the just-created container by its time-derived name.
	out, err := exec.Command("docker", "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name).CombinedOutput()
	if err != nil {
		t.Fatalf("docker inspect: %v\n%s", err, out)
	}
	ip := strings.TrimSpace(string(out))
	if ip == "" {
		t.Fatalf("docker inspect returned an empty bridge IP for %s", name)
	}
	return ip
}

// waitForPostgres polls until the container accepts a real connection AND a trivial query
// succeeds (the boot grace).
func waitForPostgres(t *testing.T, dsn string) {
	t.Helper()
	deadline := time.After(45 * time.Second)
	for {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		ok := pingPostgres(ctx, dsn)
		cancel()
		if ok {
			return
		}
		select {
		case <-deadline:
			t.Fatalf("postgres at %s never became ready", dsn)
		case <-time.After(300 * time.Millisecond):
		}
	}
}

// pingPostgres opens a single connection and runs SELECT 1, returning whether the server is
// ready to serve queries.
func pingPostgres(ctx context.Context, dsn string) bool {
	conn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		return false
	}
	defer func() { _ = conn.Close(ctx) }() //nolint:errcheck // best-effort close of the probe conn.
	var one int
	if qerr := conn.QueryRow(ctx, "SELECT 1").Scan(&one); qerr != nil {
		return false
	}
	return one == 1
}

// startEmbeddedNATS boots an in-process REAL nats-server (JetStream enabled, the B3 pattern)
// on a random port, reaped on cleanup, and returns its client URL — the REAL bus the soft
// control signal rides. (Embedded is a real nats-server, not a mock; the cross-process
// container arm is the agentruntime lane's job — here NATS is the soft-control wire.)
func startEmbeddedNATS(t *testing.T) string {
	t.Helper()
	options := &natsserver.Options{
		Host:      "127.0.0.1",
		Port:      -1, // random free port
		JetStream: true,
		StoreDir:  t.TempDir(),
		NoLog:     true,
		NoSigs:    true,
	}
	server := natsservertest.RunServer(options)
	t.Cleanup(server.Shutdown)
	if !server.ReadyForConnections(10 * time.Second) {
		t.Fatal("embedded nats-server not ready within 10s")
	}
	return server.ClientURL()
}

// ── real port wiring (provider, sessions, secrets) ─────────────────────────────────────────.

// newRealSecrets builds the secrets.Provider seeded with the canary credential, so the
// no-leak assertions have a concrete needle resolved server-side at agentsession.Open.
func newRealSecrets() *secretstest.Provider {
	return secretstest.New(map[string]string{credentialRef: SeededCanary})
}

// newRealProvider wires the REAL substrate adapter (docker EphemeralContainer or k3d cluster)
// into a real workspaceprovider.Provisioner — the concrete that implements BOTH Provider and
// Supervisor. The orchestrator Provisions through Provider and Probes through Supervisor; both
// are this ONE real provider over the REAL substrate (no mock).
func newRealProvider(t *testing.T, adapter workspaceprovider.Adapter, substrate orchestrator.Substrate, secretsProvider *secretstest.Provider) *workspaceprovider.Provisioner {
	t.Helper()
	set, _, _, _ := dependenciestest.Fakes()
	provider, err := workspaceprovider.New(
		workspaceprovider.Config{Default: toProviderSubstrate(substrate)},
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{
				toProviderSubstrate(substrate): adapter,
			},
			Secrets: secretsProvider,
			Clock:   set.Clock,
		},
	)
	if err != nil {
		t.Fatalf("construct real workspaceprovider over the real substrate: %v", err)
	}
	return provider
}

// buildRealSessions wires the scripted agentsessiontest adapter into a REAL agentsession.Pool —
// the Factory the reconcile loop Opens. The session inside is a real subprocess in production
// (the deterministic stub harness the other lanes use); a token-gated real-claude/omp arm SKIPS
// without a key (out of scope for this gate — the point is the orchestrator↔provider↔NATS↔
// Postgres reconcile is REAL).
//
//nolint:ireturn // returns the agentsession.Factory port the reconcile loop binds (the frozen seam).
func buildRealSessions(secretsProvider *secretstest.Provider) agentsession.Factory {
	adapter := agentsessiontest.New(defaultScript()...)
	pool, err := agentsession.New(
		agentsession.Config{
			Routing: map[agentsession.RouteKey]agentsession.Route{
				{Role: "assistant"}: {Harness: fakeHarnessKey, Model: "fake-fable-5"},
			},
		},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{fakeHarnessKey: adapter},
			Secrets:    secretsProvider,
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      fixedSessionClock{},
		},
	)
	if err != nil {
		panic("orchestratortest.buildRealSessions: " + err.Error())
	}
	return pool
}

// toProviderSubstrate maps the orchestrator's Substrate enum onto the workspaceprovider's
// substrate string (the compile step the orchestrator already performs in fold.go; mirrored
// here so the harness Provisions on the right adapter).
func toProviderSubstrate(substrate orchestrator.Substrate) workspaceprovider.Substrate {
	if substrate == orchestrator.SubstrateDocker {
		return workspaceprovider.SubstrateDocker
	}
	return workspaceprovider.SubstrateKubernetes
}
