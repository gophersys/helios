// Package agentruntime is the Eden agent-pod PID-1 runtime sidecar (Milestone-B B3, ADR-0022 §4 +
// Consequences). It is the container's main process on docker AND kubernetes (the
// workspaceprovider Entrypoint/workload-pod capability): it resolves its agent, spawns the harness
// IN-PROCESS through the frozen agentsession Factory, pumps that session's normalized Event stream,
// and bridges it onto a NATS/JetStream reactive bus —
//
//   - PUBLISHES the sequenced event stream to agent.<id>.events (JetStream-durable, replay-by-Seq),
//   - SUBSCRIBES agent.<id>.control for the soft control signal (prompt/steer/abort/stop/kill) and
//     maps each verb onto the agentsession session (+ a kill path via the active-agent registry),
//   - PUBLISHES periodic agent.<id>.health heartbeats the thinned orchestrator Probes,
//
// every message carrying OTel trace context. Run IS the graceful-shutdown state machine
// (signal.NotifyContext → typed TerminationReason → cancel → drain the in-flight turn → close the
// session → flush OTel), and a small HTTP surface (/live, /health/{id}) serves the kubelet probes.
//
// Module: github.com/gophersys/libs/go/agentruntime  (go 1.26)
//
// It does NOT own (one concept, one home — it CONSUMES these frozen ports, never redefines them):
// the harness spawn / Event taxonomy / Seq ordering (agentsession, ADR-0008); pod provisioning /
// the hard docker-or-kubernetes lifecycle (workspaceprovider, ADR-0016/0022 — the API kills the
// container, the bus is only the SOFT signal); credential storage/minting (secrets + Vault, the
// agentsession credential seam carries an opaque Reference resolved server-side); desired-state
// reconciliation (orchestrator). The Bus is a consumer-defined port: the natsbus sub-package is the
// real adapter (the only place nats.go is imported), and a fake binds it in the fast lanes.
//
// Concurrency: New is PURE (no I/O, no clock read, no env read). A constructed *Runtime is used once
// via Run(ctx): Run owns the pump goroutine, the heartbeat ticker goroutine, and the control
// subscription, and reaps ALL of them before returning (goleak-clean). The active-agent registry is
// safe for concurrent use (a control-goroutine Kill vs the run loop).
package agentruntime

import (
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// Config is the immutable, fully-resolved input for ONE sidecar (the configuration pattern: parsed
// at the edge, frozen here). It holds NO live handles and NO secret VALUES — the agentsession Spec it
// carries holds only a loggable secrets.Reference. It is DATA. (The idiomatic Go exported type name
// is exempt from HNS-1's lowercase-slug ban, rule 11 — a package/dir named "config" is not.)
type Config struct {
	// AgentID scopes the three subjects (agent.<id>.*), keys the registry, and stamps every message.
	// Required: an empty id is a New-time ConfigError.
	AgentID AgentID

	// Spec is the fully-resolved agentsession.Spec the sidecar Opens the harness with (workspace,
	// routing, grants, the opaque Credential reference). The sidecar passes it through verbatim — it
	// is the agentsession contract, transported, never reinterpreted.
	Spec agentsession.Spec

	// HeartbeatInterval is the cadence of agent.<id>.health publishes. Zero == DefaultHeartbeat.
	HeartbeatInterval time.Duration

	// DrainTimeout bounds the graceful drain of the in-flight turn on shutdown (the Close ctx). Zero
	// == DefaultDrainTimeout. A kill (KILL verb) bypasses this.
	DrainTimeout time.Duration

	// InitialPrompt, when non-empty, is sent as the first turn the moment the session reaches Ready —
	// the batch/seed-prompt path (a one-agent-per-pod batch run). Empty == the interactive path: the
	// first turn arrives as a control PROMPT verb.
	InitialPrompt string
}

// Default sidecar tunables (the configuration pattern: a zero field selects the default, never an
// implicit surprise).
const (
	DefaultHeartbeat    = 5 * time.Second  // agent.<id>.health cadence when HeartbeatInterval is zero
	DefaultDrainTimeout = 30 * time.Second // the graceful-drain Close bound when DrainTimeout is zero
)

// Deps is the injected hexagon (the ports the sidecar drives). New constructs no port; every field
// is required (a nil port is a New-time ConfigError) — the composition root wires the real
// agentsession Factory, the natsbus Bus, a Clock, and the observability Provider. (The idiomatic Go
// exported type name Deps is exempt from the HNS-1 lowercase-slug ban, rule 11.)
type Deps struct {
	// Sessions is the frozen agentsession Factory the sidecar Opens the harness through, in-process.
	Sessions agentsession.Factory

	// Bus is the reactive-bus port (the natsbus adapter in production; a fake in the fast lanes).
	Bus Bus

	// Observer is the OTel/telemetry sink the sidecar emits spans/logs onto AND whose carrier rides
	// every bus message; Run Flushes it at shutdown (the OTel-flush step of the state machine).
	Observer Observer

	// Clock is the sidecar's only time source (heartbeat cadence + EmitTime stamps).
	Clock Clock
}

// Runtime is the constructed, not-yet-running sidecar (the concrete return of New — accept the
// ports, return the concrete type, 10 §9). Its zero value is unusable; build it via New and drive it
// once via Run. It is safe to read its HTTP handler concurrently with Run.
type Runtime struct {
	configuration Config
	sessions      agentsession.Factory
	bus           Bus
	observer      Observer
	clock         Clock

	registry *registry
}

// New constructs a Runtime from its Config and Deps. It is PURE: it validates the invariants (a
// present AgentID, every required port non-nil) and wires the registry — no I/O, no clock read, no
// env read, no harness spawn (that happens in Run). It returns a typed ConfigError (KindInvalid) on a
// violated invariant, so the composition root fails fast and loud.
//
//nolint:gocritic // contract: Config is the frozen, copyable sidecar input (the configuration pattern); the constructor spine takes it by value.
func New(configuration Config, dependencies Deps) (*Runtime, error) {
	if configuration.AgentID == "" {
		return nil, newConfigError("AgentID is required")
	}
	if dependencies.Sessions == nil {
		return nil, newConfigError("Deps.Sessions (agentsession.Factory) is required")
	}
	if dependencies.Bus == nil {
		return nil, newConfigError("Deps.Bus is required")
	}
	if dependencies.Observer == nil {
		return nil, newConfigError("Deps.Observer is required")
	}
	if dependencies.Clock == nil {
		return nil, newConfigError("Deps.Clock is required")
	}
	return &Runtime{
		configuration: configuration,
		sessions:      dependencies.Sessions,
		bus:           dependencies.Bus,
		observer:      dependencies.Observer,
		clock:         dependencies.Clock,
		registry:      newRegistry(),
	}, nil
}

// heartbeatInterval returns the configured cadence or the default.
func (r *Runtime) heartbeatInterval() time.Duration {
	if r.configuration.HeartbeatInterval > 0 {
		return r.configuration.HeartbeatInterval
	}
	return DefaultHeartbeat
}

// drainTimeout returns the configured drain bound or the default.
func (r *Runtime) drainTimeout() time.Duration {
	if r.configuration.DrainTimeout > 0 {
		return r.configuration.DrainTimeout
	}
	return DefaultDrainTimeout
}

// compile-time assertion: a *Runtime satisfies no exported interface of its own (it is the concrete
// return), but its dependencies must satisfy the consumer ports — asserted at the wiring sites.
var _ = errors.KindInvalid
