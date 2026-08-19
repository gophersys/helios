package agentsession

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/secrets"
)

// Session is the controllable, instrumented agent session — the single port a
// consumer holds, obtained from Factory.Open. Exactly 4 methods (the 10 §9
// ceiling, well under it). Both the chat (live render) and the engine (fold to
// evidence) drive exactly these. Its zero value is unusable.
type Session interface {
	// Events returns the normalized event stream from the given cursor. FromSeq(0)
	// replays the whole session from the durable transcript, then attaches to the
	// live tail with no gap and no dup. A reconnecting consumer passes its last-seen
	// Seq+1. MULTIPLE concurrent calls are MULTIPLE viewers of one session (fan-out:
	// the chat tab, a second browser, the dashboard observer) — all see identical
	// Seq-ordered events. Closing ctx drops THIS subscriber only; it neither stalls
	// other viewers nor the agent (backpressure: contract "Resumability & fan-out").
	Events(ctx context.Context, from Cursor) Stream

	// Control issues a turn-taking command. Prompt is valid only when
	// Ready/AwaitingInput; Steer interjects guidance into a Running turn without
	// aborting it (degrades per CapSteer); Abort cancels the in-flight turn and is
	// valid until terminal. It returns the Seq the control was ADMITTED at (so a UI
	// correlates the resulting events) — NOT the agent's reply, which streams back on
	// Events. Returns a wrapped StateError (errors.AsType) if out of phase, or
	// UnsupportedError if the adapter declares the verb's Capability absent.
	Control(ctx context.Context, command Command) (Ack, error)

	// Resolve answers a pending PermissionRequest (the agent asked to use a capability
	// outside its standing Grants). The DECIDER is the caller: a human click or a
	// policy function. Idempotent on RequestID; first decision wins under multi-client
	// races (UnknownPermissionError if already resolved/expired). Returns the Seq of
	// the resulting PermissionResolved event. When Spec.OnPermission is set, the
	// library calls it and the consumer never calls Resolve directly; when it is nil,
	// requests surface as events for an out-of-band Resolve.
	Resolve(ctx context.Context, requestID string, decision Decision) (Ack, error)

	// Close releases the session handle: stop accepting input, signal the harness to
	// stop, drain the in-flight turn (bounded by ctx), emit the terminal Event, then
	// reap the process. It does NOT tear down the pod (that is workspaceprovider's
	// job, 02 §1). Idempotent. After Close, every live Events tail drains and closes.
	Close(ctx context.Context) error
}

// Stream is a one-shot, ordered, gap-free, dup-free event view for ONE consumer.
// The engine ranges over it; the SSE route awaits each event (Next) — both are
// ergonomic faces of the same pull-based stream.
type Stream interface {
	// Next blocks for the next event; ok=false at end-of-stream (terminal reached,
	// ctx canceled, or fault). Events arrive strictly Seq-ordered with no holes from
	// `from`. Pull-based: the consumer's read rate IS the backpressure (a slow chat
	// tab slows its own read; it does not stall other viewers or the agent).
	Next(ctx context.Context) (Event, bool)

	// Err reports a fault that ended the stream early (pod death mid-run, decode
	// fault). nil at a clean terminal end. The engine treats non-nil as a failed
	// phase; the chat shows a banner and may reconnect from its last Seq.
	Err() error
}

// Factory opens sessions. It is the port the engine/chat-backend holds; New returns
// the concrete *Pool. Open binds a harness Adapter (selected by Spec.Routing) to a
// workspace and returns a live Session. The Factory does NOT provision the workspace
// (that arrived via S2); it spawns the harness process inside it.
type Factory interface {
	// Open binds the credential (resolves the opaque Reference server-side, mints a
	// scoped token), invokes the harness in the already-provisioned pod, and returns a
	// live Session at Seq 0 once the handshake is confirmed (StateReady) — or an error.
	// ResumeFrom, when non-empty, re-attaches an existing harness session instead of
	// spawning fresh. Errors: AuthError (no usable credential — the silent-bad-token
	// trap is converted to this, not trusted as success); SpawnError (binary missing /
	// pod not ready); wrapped %w cause otherwise.
	Open(ctx context.Context, spec Spec) (Session, error)
}

// PermissionRequest is the policy decider's input (a non-pointer projection of
// PermissionPayload's request side, so OnPermission has no stream dependency).
type PermissionRequest struct {
	RequestID string
	Tool      string
	Input     []byte // the args the harness wants to run with (redaction is the adapter's job before this)
	Reason    string
}

// Spec is the immutable, fully-resolved input for ONE session (the configuration
// pattern: parsed at the edge, frozen). It holds NO live handles and NO secret
// values — only a loggable secrets.Reference.
type Spec struct {
	Workspace   string            // the already-provisioned workspace dir (S2 owns its lifecycle); the harness CWD (02 §1)
	Routing     RouteKey          // selects harness+model via agentconfiguration; routable per phase
	Grants      []ToolGrant       // the allowlist AS DATA — standing capability the session launches with (07 §3)
	HostTools   []HostTool        // Eden-provided callback tools (read-scoped project-data tools for AssistantSession)
	Credential  secrets.Reference // OPAQUE; resolved server-side at Open, injected per the credential-flow diagram — never the value
	Budget      Budget            // soft ceilings surfaced to the harness + hard ceilings the engine enforces by Abort
	ResumeFrom  string            // harness-native session id to re-attach (empty == fresh)
	SystemHints string            // optional system-prompt augmentation (hermetic-context seam; never a secret)

	// OnPermission is the policy decider for out-of-grant requests (the engine's
	// clean-room auto-resolver). When non-nil it is called synchronously and the
	// consumer never calls Session.Resolve. When NIL (the chat), requests surface as
	// EventPermissionRequest events for an out-of-band human Resolve. nil with no
	// Resolve ever arriving leaves the request pending until ctx/Close — so a batch
	// session MUST set it. Default-deny is the safe policy. It REMAINS the degrade path:
	// when no PermissionAdvisor is injected the resolution chain falls back to this.
	OnPermission func(PermissionRequest) Decision

	// PermissionResolution selects the per-session out-of-grant chain (the ratified
	// model). The zero value (ResolveChatHumanThenAdvisor) is the safe human-first chain.
	// ResolveAutonomousAdvisor consults the injected advisor directly (no human wait) for
	// an unattended session. Either way the terminal fallback is default-deny, and with no
	// advisor injected the chain degrades to OnPermission/default-deny (no regression).
	PermissionResolution PermissionResolution

	// PermissionTimeout bounds the human-Resolve wait in the chat chain before the
	// resolution falls back to the advisor (then default-deny). Zero == the safe default
	// (defaultPermissionTimeout). It is meaningful only for ResolveChatHumanThenAdvisor;
	// the autonomous chain consults the advisor immediately.
	PermissionTimeout time.Duration

	// Name is this session's stable peer address AND the harness-native session name. It is
	// assigned by the CALLER (the orchestrator), never minted by the library, because a peer
	// must be addressable BEFORE it is opened. It MUST match ^[a-z][a-z0-9-]{1,61}[a-z0-9]$
	// so it is safe as a CLI argument, a unix-socket filename, and a roster entry.
	//
	//	Deps.Peer != nil && Name == ""  ==> ConfigError at Open (a session that believes it is
	//	                                    reachable and is not is the silent failure this
	//	                                    design exists to remove).
	//	Deps.Peer == nil && Name == ""  ==> opens cleanly; no peer event is ever emitted.
	//	invalid non-empty               ==> ConfigError, never a mangled argv.
	Name string

	// Parent is the opener's Name ("" == a root session, whose parent is the orchestrator).
	// It is the TREE edge, reported as Peer.Parent. The tree is the registry, parentage,
	// authorization and audit structure — NEVER a reachability restriction.
	Parent string
}

// RouteKey is the opaque key agentconfiguration resolves to a concrete (harness,
// model) pair per phase/role (02 §5 agents.yaml). The session port does NOT decide
// which harness/model — it is told. This is C22's "right agent for the right phase"
// selector, kept out of this contract's policy.
type RouteKey struct {
	Phase string // "product-design", "implement", "review", ... | "" for interactive
	Role  string // "assistant" | "implementer" | "reviewer" | ...
}

// ToolGrant is one allowlist entry AS DATA (not code): a capability the session may
// exercise without a permission prompt. Pattern mirrors Claude --allowedTools
// ("Write", "Bash(go *)") and OMP SyncTools. The engine derives the egress endpoints
// a granted tool needs from the grant set.
type ToolGrant struct {
	ID       string   // stable id for audit linkage (ToolPayload.GrantID)
	Tool     string   // tool name, e.g. "Write", "Read", "Bash"
	Scopes   []string // sub-scoping, e.g. ["go *", "ls *"] for Bash; nil == whole tool
	ReadOnly bool     // marks a read-scoped grant (AssistantSession: project-data tools, NO write paths — 07 §3)
}

// HostTool is an Eden-provided tool the agent calls BACK into (the OMP host-tool
// channel: host_tool_call -> handler -> host_tool_result, with partial-result
// streaming surfaced as EventToolUpdate). For AssistantSession these are the
// read-scoped project-data tools with NO write paths and NO credential access
// (07 §3). The handler runs in-process, server-side.
type HostTool struct {
	Name        string
	Description string
	Schema      []byte // JSON-schema of parameters (opaque to this lib; passed to the harness)
	Handler     func(ctx context.Context, args []byte) (result []byte, err error)
}

// Budget carries the soft ceilings surfaced to the harness AND the hard ceilings the
// engine enforces by aborting. The harness-native cap is best-effort; the
// AUTHORITATIVE enforcement is the engine watching EventUsage against TokenBudget
// (02 §2) and calling Abort/Close — there is exactly ONE budget authority.
type Budget struct {
	MaxCostMicros int64         // 0 == unbounded here (engine still enforces TokenBudget)
	MaxTurns      int32         // 0 == harness default
	MaxWall       time.Duration // 0 == ctx bounds it
}

// Config is the immutable spine input for the Factory. It holds the routing table;
// it reads NO env, NO clock, NO secret (10 §4).
type Config struct {
	// Routing is the resolved agentconfiguration projection: RouteKey -> Route. Built
	// at the edge by the agentconfiguration library (02 §5); frozen here.
	Routing map[RouteKey]Route
}

// Route is a resolved (harness, model) binding for a RouteKey.
type Route struct {
	Harness string // adapter key: "claude-code" | "omp" | "codex"
	Model   string // model id passed to the harness
}

// Deps is the injected hexagon. New constructs no ports.
type Deps struct {
	// Adapters maps a harness key to its Adapter (the lower Harness seam). At least
	// one is required.
	Adapters map[string]Adapter

	// Secrets resolves the opaque Credential reference to a short-lived Secret at OPEN
	// time, server-side, so the value reaches the harness process per the
	// credential-flow diagram and NEVER enters this library's logs, the Spec, or any
	// Event (07 §2).
	Secrets secrets.Provider

	// Transcript is the durable replay log Seq is assigned against (Seq == transcript
	// offset) and from which FromSeq(n) replays. The library APPENDS to it and reads
	// it for replay; retention/redaction policy lives behind this seam (07 §2).
	Transcript Transcript

	// Clock stamps Event.Time when an adapter supplies none; keeps New pure and the
	// fake deterministic.
	Clock Clock

	// Advisor is the OPTIONAL reasoning port for the ratified permission model: the
	// out-of-grant resolution chain consults it (on a chat timeout, or directly when
	// autonomous) before the default-deny terminal. It is injected, never constructed
	// here — agentsession CALLS it and stays pure (it does NOT spawn agents; the impl in
	// the runtime does). When nil the chain degrades to OnPermission/default-deny with no
	// regression. The advisor's verdict is CLAMPED by the risk class in agentsession, so
	// it can never auto-allow a high-risk tool regardless of the advisor impl.
	Advisor PermissionAdvisor

	// Peer is the OPTIONAL inter-session message plane. agentsession opens NO socket — it
	// CALLS this port. peerplane.Orchestrator (the tree root) and peerplane.Client (a member
	// process) both implement it, so a session cannot tell whether its plane is in-process or
	// across the socket. nil == no peer plane: Spec.Name must be empty, CapPeerMessaging
	// degrades to CapAbsent, no peer event is ever emitted, and every existing consumer
	// compiles and behaves identically (no regression).
	Peer PeerPlane
}

// Transcript is the durable, append-only replay log seam (the 02 §2 / P9 object,
// behind a port so persistence/retention is the consumer's concern). The library
// assigns Seq at Append and replays via ReadFrom.
type Transcript interface {
	// Append durably stores one Event and returns the Seq it was assigned (the
	// transcript offset). Called once per Event before fan-out, so every viewer sees
	// identical Seq numbers.
	Append(ctx context.Context, event Event) (seq uint64, err error)

	// ReadFrom returns the stored events [from+1 .. head] for replay — available AFTER
	// a session terminates too (reload an old Run's chat), so replay reads the stored
	// transcript, not a live ring buffer.
	ReadFrom(ctx context.Context, sessionID string, from Cursor) (Stream, error)
}

// Clock is the minimal injected time port (mirrors observability.Clock). It is the
// only time source; New never reads the wall clock.
type Clock interface{ Now() time.Time }

// Adapter is the per-harness implementation seam — the only place a vendor harness
// is spawned or its wire format parsed (05 §1). It is THIN: the library owns the
// lifecycle state machine, Seq ordering, grant->audit linkage, budget watching,
// fan-out, and credential-injection shape; the adapter owns ONLY (a) spawning the
// process and (b) translating its native frames <-> the normalized Event/Control
// vocabulary.
type Adapter interface {
	// Spawn launches the harness process in spec.Workspace with the resolved Route,
	// the credential already injected (the library called Secrets.Resolve and hands
	// the adapter an InjectedCredential — the adapter places it where its harness
	// reads it). It returns a HarnessConn — the bidirectional, normalized stream +
	// control sink.
	Spawn(ctx context.Context, spec Spec, route Route, cred InjectedCredential) (HarnessConn, error)

	// Manifest declares which optional capabilities this adapter implements. The
	// library degrades gracefully (05 §3) and the conformance suite verifies the
	// manifest is truthful (a declared capability that fails its suite blocks release).
	Manifest() CapabilityManifest
}

// HarnessConn is the adapter's normalized connection: it EMITS normalized Events
// (already mapping native -> Event) and ACCEPTS normalized Control. The library
// wraps it as the Session, adding the state machine, Seq, transcript append,
// fan-out, grant linkage, and budget watching. Exactly 3 methods.
type HarnessConn interface {
	Events() <-chan Event                      // already-normalized; pre-Seq, pre-fan-out (the library stamps Seq)
	Send(ctx context.Context, c Command) error // Prompt/Steer/Abort as a normalized control frame
	Close(ctx context.Context) error           // the graceful abort->stdin-close->wait->kill ladder
}

// InjectedCredential is the resolved-but-still-protected credential handed to the
// adapter at Spawn. The Secret is resolved server-side from the opaque Reference and
// is un-printable (secrets.Secret); the adapter is told HOW its harness wants it
// (EnvName, or a HelperScript path) and uses Secret.Use to place it — the value
// never enters the Spec, an Event, a log, or an image layer.
type InjectedCredential struct {
	Secret  *secrets.Secret // un-printable; the adapter calls .Use(fn) at the injection site only
	Vehicle CredentialVehicle
	EnvName string // for VehicleEnv: e.g. "CLAUDE_CODE_OAUTH_TOKEN"
}

// CredentialVehicle is how a harness wants its credential placed. Append-only.
type CredentialVehicle uint8

// The credential injection vehicles.
const (
	VehicleEnv    CredentialVehicle = iota // env var on the CHILD process ONLY (not Eden's env), scrubbed of higher-precedence keys
	VehicleHelper                          // apiKeyHelper script that fetches a short-lived token on demand (the 07 §2 ideal)
)

// CapabilityManifest is the adapter's declaration (05 §3). DATA, not code.
type CapabilityManifest struct {
	Capabilities map[Capability]CapStatus
}

// Status reports the declared status of capability (CapAbsent when unlisted).
func (m CapabilityManifest) Status(capability Capability) CapStatus {
	if m.Capabilities == nil {
		return CapAbsent
	}
	return m.Capabilities[capability]
}

// Capability is one optional adapter feature the manifest declares. Append-only.
type Capability uint8

// The optional adapter capabilities.
const (
	CapSteer              Capability = iota // mid-turn steering (Claude streaming-input vs OMP SteeringMode vs codex none)
	CapResume                               // re-attach by harness-native session id (Claude --resume; omp session dir)
	CapThinkingEvents                       // emits separate thinking deltas
	CapHostTools                            // supports the host-tool callback channel
	CapNativeBudget                         // honors a harness-native budget cap (Claude --max-budget-usd)
	CapPermissionPrompt                     // supports the out-of-grant permission round-trip
	CapPartialToolResults                   // streams EventToolUpdate (OMP partial results)
	CapPeerMessaging                        // session<->session messaging ACROSS processes (claude: CapPartial, host roster not containable; omp: CapFull, library-owned)
	CapSubagentMessaging                    // parent<->child messaging INSIDE one harness process — a DISTINCT function from peer messaging
)

// capabilityTokens holds the stable lower-kebab token for each Capability.
var capabilityTokens = [...]string{
	CapSteer:              "steer",
	CapResume:             "resume",
	CapThinkingEvents:     "thinking-events",
	CapHostTools:          "host-tools",
	CapNativeBudget:       "native-budget",
	CapPermissionPrompt:   "permission-prompt",
	CapPartialToolResults: "partial-tool-results",
	CapPeerMessaging:      "peer-messaging",
	CapSubagentMessaging:  "subagent-messaging",
}

// String returns the stable lower-kebab token (e.g. "steer"). Total: returns
// "steer" for any out-of-range value.
func (c Capability) String() string {
	if int(c) < len(capabilityTokens) {
		return capabilityTokens[c]
	}
	return capabilityTokens[CapSteer]
}

// CapStatus is the declared support level for a Capability. Append-only.
type CapStatus uint8

// The capability support levels.
const (
	CapAbsent  CapStatus = iota // feature gated off in the UI, not broken (05 §3)
	CapPartial                  // e.g. Steer "queue for next turn" rather than true mid-turn
	CapFull                     // the capability works fully
)
