package workspaceprovider

import (
	"io"
	"time"

	"github.com/gophersys/libs/go/secrets"
)

// Substrate selects the adapter. Closed-by-convention but string-typed so a new managed
// adapter (EKS/GKE/AKS/DO ⊂ kubernetes) registers without a code change to this library
// (05 §2: cloud vendors are managed adapters of substrates).
type Substrate string

// The v1 substrates. A managed kubernetes (EKS/GKE/AKS/DO) is the SAME kubernetes
// adapter with a different client config, not a new Substrate value.
const (
	SubstrateDocker     Substrate = "docker"     // the daemon
	SubstrateKubernetes Substrate = "kubernetes" // ANY conformant distro (k3d default, kind 2nd target, EKS/GKE/AKS/DO later)
)

// WorkspaceSpec is the immutable, fully-resolved request for ONE isolated workspace
// (the configuration pattern). It is DATA: an adapter reads it, it carries no behavior.
// It holds NO live handles and NO secret VALUES — only loggable secrets.References. This
// is the substrate's whole provision vocabulary; the consumer writes ONE spec shape and
// the adapter realizes it on either substrate (distro transparency, 05 §6).
type WorkspaceSpec struct {
	Name             string            // stable, tenancy-scoped logical name; idempotency key for Provision
	Substrate        Substrate         // "" routes via Config.Default
	Image            string            // OCI image ref (the template/devcontainer/agent-runtime/code-server image, 02 §1 Archetype)
	ImagePull        secrets.Reference // OPTIONAL registry pull-secret; resolved server-side at Provision; zero == public image; never the value
	Mounts           []Mount           // file/dir/tmpfs mounts (worktree, read-only clean-room inputs, credential-vehicle tmpfs)
	Resources        Resources         // cpu/memory/storage/pids ceilings (07 §3 isolation; 07 §6 tenancy quota)
	Egress           []EgressRule      // the DECLARED dial-out set; default-deny otherwise (07 §3); no ingress field: dial-out-only is structural
	Labels           map[string]string // ownership-domain + tenancy tags (Organization/Project, 07 §6); queryable via Selector
	Env              []EnvVar          // NON-secret environment for the workspace; secret env goes via a MountSecret, never here
	ProvisionTimeout time.Duration     // bounds the Ready handshake; 0 == ctx bounds it

	// Entrypoint is the WORKLOAD-POD capability (ADR-0022 §4, OD-15 option-a): when non-empty,
	// the container's MAIN process IS the workload (PID-1) on docker AND kubernetes, rather than
	// the long-lived "sleep infinity" hold container the library otherwise execs Run/Exec into.
	// PID-1 means native liveness/restart/OOM, and on kubernetes the kubelet's OOMKilled
	// container-status REASON attaches to the readable workspace container — so the
	// ConditionOOMKilled discriminator now surfaces natively on the kubernetes Run path (closing
	// the OD-15 / §7 Q14 gap). Empty (the default) keeps the exec-into-hold model verbatim, so
	// every existing consumer is unaffected: the Entrypoint path is ADDITIVE and spec-selected. A
	// workspace whose Entrypoint exits Provisions Ready only while it is Running (it is the
	// workload, so its lifecycle IS the workspace's); a Run into an Entrypoint workspace targets
	// the SAME primary workload (the contract's one-primary-workload rule holds either way). The
	// argv is data; a credential the entrypoint needs rides RunSpec on the Run that adopts it, or
	// a MountSecret, never here.
	Entrypoint []string

	// Editor is the READ-ONLY EDITOR-SIDECAR capability (ADR-0027, CapEditorSidecar): when
	// non-nil, the adapter co-locates a read-only code-server alongside the workspace that mounts
	// the SAME workdir READ-ONLY (the `readOnly: true` volumeMount on kubernetes / the
	// `--volumes-from …:ro` sibling on docker), so a user opens the agent's live worktree in a
	// view-only VS Code without a second writer racing the supervisor. Read-only is STRUCTURAL,
	// not advisory: the mount mode means the editor process CANNOT write the worktree. nil (the
	// default) ⇒ BYTE-IDENTICAL pods/containers — every existing consumer is unaffected; the
	// editor path is ADDITIVE and spec-selected, exactly as Entrypoint is. It carries NO secret:
	// EditorSpec is a viewer image + port (+ optional caps), never a credential — the canary
	// redaction property holds. On kubernetes the sidecar is exposed per agent via a Service + an
	// Ingress (host-per-agent, `<agent-id>.editor.<domain>`); the gateway derives EditorURLBase
	// from that host (ADR-0027 §3). The sidecar inherits the namespace's default-deny egress (it
	// serves files, it does not dial out).
	Editor *EditorSpec
}

// EditorSpec is the read-only editor sidecar's configuration (ADR-0027). It is DATA: the adapter
// reads it to co-locate a read-only code-server that mounts the workspace's workdir read-only. It
// holds NO secret VALUE and NO live handle — a viewer image + the port it serves + optional
// resource ceilings — so it is loggable and redaction-safe by construction (the canary property).
// A zero EditorSpec (reached only via a non-nil pointer to the zero value) lets the adapter
// substitute its default editor image/port; the FIELD on WorkspaceSpec being nil is the
// not-requested signal.
type EditorSpec struct {
	Image     string    // the read-only code-server OCI image ref (e.g. "codercom/code-server"); "" == the adapter default
	Port      int       // the container port the editor serves (e.g. 8080); 0 == the adapter default
	Resources Resources // OPTIONAL cpu/memory/storage ceilings for the editor sidecar (07 §3); zero == the adapter/tenancy default
}

// Mount is one mount, as data. Source semantics depend on Kind; the adapter maps it to
// a bind mount / volume / configMap / tmpfs.
type Mount struct {
	Kind     MountKind         // Bind | Volume | Tmpfs | Inputs | Secret
	Target   string            // absolute path in the workspace (the default Bind/Inputs target becomes WorkDir)
	Source   string            // host path (Bind), volume name (Volume), "" (Tmpfs/Inputs)
	Ref      secrets.Reference // Kind==Secret: the opaque ref resolved server-side and written to a tmpfs Target (07 §2)
	ReadOnly bool              // the clean-room declared-inputs mount is read-only (07 §4)
}

// MountKind selects how a Mount is realized on the substrate.
type MountKind uint8

// The mount kinds. Closed taxonomy, additive-only.
const (
	MountBind   MountKind = iota // host path -> workspace (local-as-a-cluster dev; the source worktree)
	MountVolume                  // a named persistent volume (CapPersistentVolume)
	MountTmpfs                   // in-memory scratch (credential vehicles land here, never an image layer — 07 §2)
	MountInputs                  // a read-only inputs volume seeded via Files.Put before Run (07 §4 clean room)
	MountSecret                  // a secrets.Reference resolved server-side and written to a tmpfs Target
)

// EgressRule is one declared dial-out destination. The workspace DECLARES what it needs
// (model-provider endpoint, a granted tool's endpoint — derivable by the orchestrator
// from agentsession ToolGrants, 05 §2); the adapter ENFORCES default-deny + these allows
// (07 §3). This is the data F1's NetworkPolicy / the broker consume; this port opens no
// socket and runs no tunnel.
type EgressRule struct {
	Host  string            // FQDN or CIDR the workspace may connect OUT to, e.g. "api.anthropic.com"
	Ports []int             // empty == 443 only
	Note  string            // provenance, e.g. "anthropic api", "grant:Bash(go *) module proxy"
	Ref   secrets.Reference // OPTIONAL mTLS client-material ref for this destination; resolved server-side; never the value
}

// Resources bounds the workspace (07 §3 isolation; 07 §6 quota). Integer milli-units and
// bytes — no float drift across millions of pods (aligned with the CostMicros discipline
// in observability/agentsession). Zero in a field == the adapter/tenancy default (NOT
// unbounded — the multi-tenant adapter substitutes the quota policy's ceiling; unbounded
// only where the manifest declares CapResourceLimits absent).
type Resources struct {
	CPUMilli     int64 // 1000 == one core; the docker-compose cpus / k8s cpu request+limit
	MemoryBytes  int64 // the memory limit; an OOMKill surfaces as ConditionOOMKilled
	StorageBytes int64 // ephemeral-storage limit
	PIDs         int64 // fork-bomb ceiling
}

// EnvVar is one NON-secret environment entry. Secrets go via MountSecret /
// RunSpec.Credential, never here.
type EnvVar struct{ Name, Value string }

// RunSpec is the request to run ONE primary workload in a provisioned workspace. The
// agentsession adapter builds this from the harness argv + the credential vehicle; a CI
// executor builds it from the step command; the chat backend from the code-server argv.
type RunSpec struct {
	Command    []string          // argv; empty == the image's default entrypoint
	Env        []EnvVar          // NON-secret workload env; credential env is placed by the adapter via Credential, not here
	WorkDir    string            // "" == the workspace's default mount target
	Credential secrets.Reference // OPAQUE; resolved server-side and injected by the adapter at the injection site; never the value
	Vehicle    CredentialVehicle // how the workload reads it (env on the child / a mounted tmpfs file)
	TTY        bool              // allocate a PTY (interactive sessions)
}

// ExecSpec is the synchronous one-shot exec verb (docker exec / kubectl exec):
// readiness probes, git invocations, a one-shot test command, open-in-shell.
type ExecSpec struct {
	Command []string
	Stdin   io.Reader // optional; nil == none
	Stdout  io.Writer // optional; nil == discarded (or buffered into ExecResult, bounded)
	Stderr  io.Writer // optional; nil == discarded (or buffered into ExecResult, bounded)
	WorkDir string
	TTY     bool          // PTY for open-in-shell; CapExecPTY-gated
	Timeout time.Duration // 0 == ctx bounds it; exceed == DeadlineError
}

// ExecResult is the synchronous result of an Exec.
type ExecResult struct {
	ExitCode int
	Stdout   []byte // bounded, redaction-eligible; large output streams via a Run instead
	Stderr   []byte // bounded, redaction-eligible
	Detail   string // adapter-native exec diagnostics, verbatim
}

// CredentialVehicle mirrors agentsession's seam so the substrate and the harness agree
// on how a credential reaches a child process (07 §2, agentsession §2).
type CredentialVehicle uint8

// The credential-delivery vehicles.
const (
	VehicleEnv  CredentialVehicle = iota // env var on the CHILD process ONLY, scrubbed of higher-precedence keys
	VehicleFile                          // a short-lived token written to a tmpfs file the workload reads
)

// Descriptor is workspace METADATA (no live handle) — what List returns and the
// reconcile loop / drift detector diff (05 §5, 10 §7.1).
type Descriptor struct {
	Handle    Handle
	Name      string
	Substrate Substrate
	State     State
	Labels    map[string]string // the ownership-domain + tenancy tags
	CreatedAt time.Time         // Clock-stamped
}

// Selector filters List by tenancy + labels (cross-tenant impossible: the tenancy keys
// are a required label match enforced by the adapter, 07 §6).
type Selector struct {
	Labels map[string]string // exact-match label set (MUST include the tenancy keys on the multi-tenant cluster)
}

// State is the workspace lifecycle. Closed taxonomy, additive-only (10 §9). Legal transitions are
// enforced by the library (not the adapter) per the authoritative legalTransitions adjacency table
// in statemachine.go — see there for the exact edge set, never re-spelled here. In shape:
// Provisioning enters; Ready and Running interconvert and accept work; Degraded is recoverable;
// Evicted is the substrate-reclaim DRIFT signal (05 §5) that may be re-provisioned or reaped; Gone
// is terminal. The adapter-native phase rides Status.Detail verbatim.
type State uint8

// The lifecycle states.
const (
	StateProvisioning State = iota // image pulling / namespace+pod creating; Ready handshake not yet confirmed
	StateReady                     // provisioned; mounts attached; egress installed; limits bound — accepts Run/Exec
	StateRunning                   // a primary workload is Running (Run started and live)
	StateDegraded                  // running but a Condition fired (probe failing, memory pressure) — recoverable
	StateEvicted                   // the substrate reclaimed it out-of-band (node pressure, preemption) — the DRIFT signal (05 §5)
	StateGone                      // terminal: torn down / GC'd / never existed; Open -> NotFoundError
)

// String renders the State for logs/diagnostics (loggable; never a secret).
func (s State) String() string {
	switch s {
	case StateProvisioning:
		return "provisioning"
	case StateReady:
		return "ready"
	case StateRunning:
		return "running"
	case StateDegraded:
		return "degraded"
	case StateEvicted:
		return "evicted"
	case StateGone:
		return "gone"
	default:
		return "unknown"
	}
}

// Status is the live observed state + a typed Condition snapshot + a resource snapshot
// (the meter's input, S9; the reconcile-loop + dashboard read).
type Status struct {
	State      State
	Conditions []Condition   // typed, branchable substrate conditions
	Usage      ResourceUsage // observed cpu/memory/storage — folded into UsageRecord by the F1 meter
	Detail     string        // adapter-native phase VERBATIM (CrashLoopBackOff, OOMKilled) for diagnostics; NOT a normalized field
	Since      time.Time     // when State was entered (Clock-stamped)
}

// Condition is one typed, branchable substrate condition (NOT a free-form string — the
// engine/orchestrator branch on it). Closed, additive-only (10 §9).
type Condition uint8

// The branchable substrate conditions.
const (
	ConditionReady Condition = iota
	ConditionImagePulling
	ConditionOOMKilled     // a workload exceeded MemoryBytes — the runaway-agent signal (02 §2)
	ConditionEvicted       // node pressure / preemption (the drift surface, 05 §5)
	ConditionUnschedulable // no node satisfies the resource request (a capacity/quota signal)
	ConditionEgressDenied  // a dial-out to a non-allowlisted host was blocked (07 §3 evidence)
)

// Event is ONE platform-neutral supervision event — the normalized form of a docker action
// (start/die/stop/destroy/oom) or a kubernetes pod-phase transition (Pending→Running→
// Succeeded/Failed, Deleted), as produced by the supervising provider's global label-filtered
// watch (ADR-0022 §4). It reuses the EXISTING State/Condition vocabulary (never a parallel one):
// the normalized lifecycle State the substrate transitioned INTO, the typed Conditions that
// fired (ConditionOOMKilled on a memory-bomb, ConditionEvicted on node pressure), the native
// reason verbatim in Detail, and the workspace Handle the event is FOR. The orchestrator Probes
// the supervised Status (docker/k8s API = the hard lifecycle) and consumes this stream to react
// without polling each workspace. An Event NEVER carries a secret (Handle is loggable-by-contract;
// Detail is a native phase string, redaction-eligible).
type Event struct {
	Handle    Handle    // the supervised workspace this event is for (loggable; never a secret)
	Kind      EventKind // the coarse normalized transition (started/stopped/failed/removed)
	State     State     // the normalized lifecycle State the substrate transitioned INTO
	Condition Condition // the typed branchable condition that fired (ConditionOOMKilled etc.), or ConditionReady
	Detail    string    // adapter-native phase/reason VERBATIM (die exit 137, OOMKilled, Evicted) — diagnostics, never normalized
	At        time.Time // when the event was observed (Clock-stamped by the library)
}

// EventKind is the coarse normalized supervision transition — the platform-neutral collapse of
// docker actions and kubernetes pod phases into ONE closed set (mirrors IOTEA's runtime.Event,
// adapted to Eden's State/Condition vocabulary). Closed, additive-only (10 §9). The fine-grained
// lifecycle detail rides Event.State / Event.Condition / Event.Detail; EventKind is the branchable
// "what happened" the supervision loop and the orchestrator switch on.
type EventKind uint8

// The normalized supervision event kinds.
const (
	EventStarted  EventKind = iota // the workload/pod entered Running (docker start / k8s PodRunning) — healthy
	EventStopping                  // graceful stop in progress (docker stop, SIGTERM)
	EventStopped                   // terminated cleanly (docker die exit 0 / k8s PodSucceeded)
	EventFailed                    // crashed / exited non-zero / OOM-killed (docker die!=0 or oom / k8s PodFailed) — Condition carries the discriminator
	EventRemoved                   // the native object was deleted from the substrate (docker destroy / k8s pod Deleted) — the workspace is Gone
)

// String renders the EventKind for logs/diagnostics (loggable; never a secret).
func (k EventKind) String() string {
	switch k {
	case EventStarted:
		return "started"
	case EventStopping:
		return "stopping"
	case EventStopped:
		return "stopped"
	case EventFailed:
		return "failed"
	case EventRemoved:
		return "removed"
	default:
		return "unknown"
	}
}

// RunStatus is one workload's status (Run.Status transitions).
type RunStatus struct {
	Phase     RunPhase
	ExitCode  int       // valid at terminal
	Condition Condition // ConditionOOMKilled etc. at a Failed/Killed terminal
	Detail    string    // adapter-native exit reason, verbatim
}

// RunPhase is one workload's coarse phase.
type RunPhase uint8

// The run phases. Succeeded/Failed/Killed are terminal.
const (
	RunPending RunPhase = iota
	RunRunning
	RunSucceeded // terminal
	RunFailed    // terminal
	RunKilled    // terminal: aborted via ctx / Teardown / OOM
)

// IsTerminal reports whether the phase is a terminal one (Run.Status stops transitioning).
func (p RunPhase) IsTerminal() bool {
	return p == RunSucceeded || p == RunFailed || p == RunKilled
}

// ResourceUsage is the observed resource snapshot the F1 meter folds into UsageRecord.
type ResourceUsage struct {
	CPUMilli     int64
	MemoryBytes  int64
	StorageBytes int64
}

// FileMode is the unix file mode for a Files.Put / FileEntry.
type FileMode uint32

// FileEntry is one shallow directory entry from Files.List.
type FileEntry struct {
	Name  string
	IsDir bool
	Size  int64
	Mode  FileMode
}

// LogCursor is the follow-from position into a workload's log buffer (Run.Logs).
type LogCursor uint64

// Resolved is the server-side-resolved secret material handed to an Adapter at Create:
// the library called Deps.Secrets.Resolve for every secrets.Reference in the spec and
// hands the adapter un-printable *secrets.Secret values keyed by where they go. The
// adapter calls Secret.Use at the injection site ONLY; the value never re-enters the
// spec, a Handle, a Status, a log, or an image layer (07 §2). Empty fields == no
// credential for that slot.
type Resolved struct {
	PullSecret *secrets.Secret            // nil if Spec.ImagePull was zero
	Mounts     map[string]*secrets.Secret // MountSecret Target -> resolved material
	Egress     map[string]*secrets.Secret // EgressRule Host    -> resolved mTLS material
	Workload   *secrets.Secret            // RunSpec.Credential -> resolved workload token (nil if zero)
}

// CapabilityManifest is the adapter's truthful declaration (DATA, not code) of which
// optional capabilities the substrate implements. The engine/UI degrade gracefully (a
// feature needing CapPersistentVolume is disabled on a substrate lacking it, not
// broken — a workspace without enforced egress is FLAGGED, not broken, per C18's
// permanently-visible guarantee badge); the conformance suite verifies truthfulness
// (05 §6). This is the ONE place k3d/kind/docker/EKS divergence is recorded — distro
// transparency is the claim, the manifest is its honest escape hatch.
type CapabilityManifest struct {
	Capabilities map[Capability]CapStatus
	Distro       string // free-form distro identity, e.g. "k3d v5.x / k3s", "kind v0.32", "docker 29.4" — telemetry/UI only
}

// Status reports the declared CapStatus for capability (CapAbsent if undeclared).
func (m CapabilityManifest) Status(capability Capability) CapStatus {
	return m.Capabilities[capability]
}

// Supports reports whether capability is declared CapPartial or CapFull (usable at all).
func (m CapabilityManifest) Supports(capability Capability) bool {
	return m.Capabilities[capability] != CapAbsent
}

// Capability is one optional substrate feature whose presence is distro-divergent.
type Capability uint8

// The optional capabilities. Additive-only.
const (
	CapExecPTY          Capability = iota // interactive PTY exec/run (open-in-shell)
	CapPersistentVolume                   // named persistent volumes (MountVolume) survive restart
	CapBindMount                          // host bind mounts (local-as-a-cluster dev; docker:full, k3d:via hostPath, EKS:absent)
	CapEgressPolicy                       // enforces declared egress / default-deny — DISTRO-DIVERGENT (k8s NetworkPolicy CRDs; docker firewall)
	CapResourceLimits                     // honors Resources (cgroups / k8s requests+limits)
	CapLogStream                          // Run.Logs follow-from-cursor (vs one-shot)
	CapMultiTenant                        // namespace-per-project isolation + quotas (the central cluster, 07 §6)
	CapReattach                           // Provider.Open re-dial survives a control-plane restart
	CapHibernate                          // pause/resume without teardown (policy idle/hibernate, 10 §12) — deferred verb, Q4
	CapSupervise                          // a global label-filtered watch (docker events / k8s pod-watch) → the normalized Event stream (ADR-0022 §4, §7 Q15)
	CapWorkloadPod                        // the Entrypoint capability: the container's MAIN process IS the workload (PID-1); on k8s this surfaces the native OOM-discriminator (ADR-0022 §4, §7 Q16, OD-15-a)
	CapEditorSidecar                      // the Editor capability: a read-only code-server co-located with the workspace, mounting the workdir read-only (ADR-0027); k8s = sidecar+Service+Ingress, docker = `--volumes-from …:ro` sibling
)

// CapStatus is the declared support level for a Capability.
type CapStatus uint8

// The capability support levels.
const (
	CapAbsent  CapStatus = iota // feature gated off in the UI, not broken (05 §3)
	CapPartial                  // e.g. egress allow-by-host but not by-CIDR; buffered-only Exec where streaming is full
	CapFull
)
