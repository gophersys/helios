package agentruntime

import (
	"fmt"
	"time"

	"github.com/gophersys/libs/go/agentsession"
)

// The three NATS subjects the sidecar speaks, rendered per agent id. They are the MINIMAL
// reactive protocol (ADR-0022 #4): the orchestrator publishes control to the agent and the
// sidecar publishes the event stream + heartbeats back, every message carrying OTel context.
//
//   - events  (agent.<id>.events)  — the sequenced agentsession Event stream, JetStream-durable
//     so a gateway replica replays by Seq (the B5 NATS→SSE bridge consumes this).
//   - control (agent.<id>.control) — the SOFT control signal: prompt/steer/abort/stop/kill, the
//     orchestrator→sidecar verb the in-pod PID-1 subscribes and acts on.
//   - health  (agent.<id>.health)  — periodic liveness heartbeats the orchestrator Probes.
const (
	subjectEventsFormat  = "agent.%s.events"
	subjectControlFormat = "agent.%s.control"
	subjectHealthFormat  = "agent.%s.health"
)

// EventsStreamName is the durable JetStream stream that captures every agent's event subject
// (agent.*.events) — one stream, subject-filtered per agent, so a gateway consumer binds a durable
// per-agent and replays by Seq. It is the ONE home for the stream-name wire contract: the natsbus
// producer and any consumer (the B5 NATS→SSE bridge) cite this constant, never re-spell the literal
// (one concept, one home). It sits beside EventsSubject/ControlSubject/HealthSubject because it is
// the same minimal reactive protocol the sidecar speaks (ADR-0022 #4).
const EventsStreamName = "EDEN_AGENT_EVENTS"

// EventsSubject renders the events subject for an agent (agent.<id>.events). It is the ONE home for
// the subject grammar — the natsbus adapter and any consumer cite these, never re-spell the format.
func EventsSubject(id AgentID) string { return fmt.Sprintf(subjectEventsFormat, id) }

// ControlSubject renders the control subject for an agent (agent.<id>.control).
func ControlSubject(id AgentID) string { return fmt.Sprintf(subjectControlFormat, id) }

// HealthSubject renders the health subject for an agent (agent.<id>.health).
func HealthSubject(id AgentID) string { return fmt.Sprintf(subjectHealthFormat, id) }

// AgentID is the stable per-agent identifier that scopes the three subjects (agent.<id>.*). It is
// the JetStream subject token and the activeAgent registry key — one agent, one id, one pod.
type AgentID string

// OTelContext is the W3C trace-context carrier that rides EVERY message on all three subjects so a
// publish→consume hop is one distributed-trace edge (ADR-0022: "OTel trace context rides every NATS
// message"). It is the propagation map an observability adapter injects on publish and extracts on
// consume; empty == an un-traced message (still valid, just unparented). It carries NO secret.
type OTelContext map[string]string

// EventEnvelope is the typed message on agent.<id>.events: one sequenced agentsession Event plus the
// trace carrier. Seq is the durable transcript offset (Seq == JetStream sequence intent), so a
// consumer replays gap-free by ascending Seq and de-dups by it. The Event is the FROZEN agentsession
// taxonomy (message/thinking/tool/permission/usage/terminal) — agentruntime transports it, never
// redefines it (one concept, one home).
type EventEnvelope struct {
	AgentID  AgentID            `json:"agentId"`
	Seq      uint64             `json:"seq"`   // the agentsession transcript offset; the JetStream replay key
	Event    agentsession.Event `json:"event"` // the frozen normalized agentsession Event (transported verbatim)
	OTel     OTelContext        `json:"otel,omitempty"`
	EmitTime time.Time          `json:"emitTime"` // when the sidecar published this envelope (sidecar Clock)
}

// ControlVerb is the soft-control axis the orchestrator publishes to agent.<id>.control. It maps
// onto the agentsession turn-taking surface (prompt/steer/abort) plus the two lifecycle verbs the
// sidecar owns (stop = graceful drain+close; kill = immediate cancel via the active-agent registry).
// Closed taxonomy, append-only (10 §9): never reordered or renamed.
type ControlVerb uint8

// The control verbs (ADR-0022 #4 decision vocabulary).
const (
	VerbPrompt ControlVerb = iota // start a turn  → agentsession CommandPrompt
	VerbSteer                     // interject     → agentsession CommandSteer (degrades per CapSteer)
	VerbAbort                     // cancel turn   → agentsession CommandAbort
	VerbStop                      // graceful stop → drain the in-flight turn, Close the session, exit
	VerbKill                      // hard stop     → cancel the agent context immediately (the kill path)
)

// controlVerbTokens holds the stable lower-kebab token for each ControlVerb, indexed by value.
var controlVerbTokens = [...]string{
	VerbPrompt: "prompt",
	VerbSteer:  "steer",
	VerbAbort:  "abort",
	VerbStop:   "stop",
	VerbKill:   "kill",
}

// String returns the stable lower-kebab token (e.g. "prompt"). Total: returns "prompt" for any
// out-of-range value.
func (v ControlVerb) String() string {
	if int(v) < len(controlVerbTokens) {
		return controlVerbTokens[v]
	}
	return controlVerbTokens[VerbPrompt]
}

// ControlMessage is the typed message on agent.<id>.control: the verb the orchestrator wants the
// in-pod sidecar to enact, the optional text (prompt/steer payload), and the trace carrier. It holds
// NO secret value — a credential reaches the harness via the agentsession/secrets seam, never here.
type ControlMessage struct {
	AgentID AgentID     `json:"agentId"`
	Verb    ControlVerb `json:"verb"`
	Text    string      `json:"text,omitempty"` // prompt/steer message; empty for abort/stop/kill
	By      string      `json:"by,omitempty"`   // audit identity (user id or "policy:<name>")
	OTel    OTelContext `json:"otel,omitempty"`
}

// HealthPhase is the coarse liveness phase a heartbeat reports — the lifecycle of the SIDECAR (the
// PID-1 state machine), distinct from the agentsession.State of the harness turn it carries
// alongside. Closed taxonomy, append-only (10 §9).
type HealthPhase uint8

// The sidecar health phases (the PID-1 run-loop state machine).
const (
	PhaseStarting HealthPhase = iota // constructed; harness spawn / bus attach in progress
	PhaseRunning                     // pumping events, subscribed to control — the steady state
	PhaseDraining                    // a termination signal arrived; draining the in-flight turn
	PhaseStopped                     // drained, session closed, OTel flushed — terminal
)

// healthPhaseTokens holds the stable lower-kebab token for each HealthPhase, indexed by value.
var healthPhaseTokens = [...]string{
	PhaseStarting: "starting",
	PhaseRunning:  "running",
	PhaseDraining: "draining",
	PhaseStopped:  "stopped",
}

// String returns the stable lower-kebab token (e.g. "running"). Total: returns "starting" for any
// out-of-range value.
func (p HealthPhase) String() string {
	if int(p) < len(healthPhaseTokens) {
		return healthPhaseTokens[p]
	}
	return healthPhaseTokens[PhaseStarting]
}

// Heartbeat is the typed message on agent.<id>.health: the sidecar's liveness tick. LastSeq is the
// highest event Seq the sidecar has published (so the orchestrator's Probe derives "is the stream
// advancing?"); SessionState is the harness turn state; Phase is the sidecar's own PID-1 phase. The
// orchestrator Probes THIS rather than raw heartbeats (ADR-0022 #4: the thinned orchestrator).
type Heartbeat struct {
	AgentID      AgentID            `json:"agentId"`
	Phase        HealthPhase        `json:"phase"`
	SessionState agentsession.State `json:"sessionState"`
	LastSeq      uint64             `json:"lastSeq"` // the highest event Seq published so far
	At           time.Time          `json:"at"`      // the sidecar Clock instant the heartbeat was stamped
	OTel         OTelContext        `json:"otel,omitempty"`
}
