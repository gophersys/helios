package ompadapter

import (
	"strings"

	"github.com/gophersys/libs/go/agentsession"
)

// openRouterEnvName is the child-process env var the Oh My Pi (omp) CLI reads its provider
// key from for the OpenRouter route (ADR-0008's omp lane runs DeepSeek-v4-flash via
// OpenRouter). It is the NAME of an env var, never a secret value. The library hands the
// adapter an InjectedCredential; the adapter OWNS the final placement — it ignores the
// library's default OMP_AUTH_TOKEN and lands the value on exactly this var, which crosses
// into the CHILD env ONLY, never Eden's env, never a log.
const openRouterEnvName = "OPENROUTER_API_KEY"

// ompBinary is the CLI name, resolved from PATH at spawn.
const ompBinary = "omp"

// approvalMode is the tool-approval policy the child is PINNED to. omp accepts
// always-ask|write|yolo; always-ask gates every tool call, and `yolo` (and its --auto-approve
// alias, main.ts:1310) would skip the prompt entirely — leaving nothing for the permission
// plane to gate. The dialog it produces is answered from the session's standing grant.
const approvalMode = "always-ask"

// sessionStoreEnvName is omp's session-storage directory var (`omp --help`: "Session storage
// directory (default: ~/.omp/agent)"), and the supported way to place that store — the probe
// harness that captured testdata/rpc-17.3.7-*.jsonl set exactly this var. Inherited, every
// eden session would write its transcripts into the operator's own store.
const sessionStoreEnvName = "PI_CODING_AGENT_DIR"

// sessionStoreDir is the store ROOT the adapter names inside the provisioned workspace. Only
// the root: the layout below it is omp's (see sessionArguments).
const sessionStoreDir = ".omp"

// scrubbedKeys are the credential env vars the adapter STRIPS from the child environment
// before injecting the OpenRouter key. omp's auth-resolution order (verified in the spike
// against the bundled models.md) places stored/env provider keys ahead of a models.yml
// literal; a stray OPENROUTER_API_KEY (or the library's OMP_AUTH_TOKEN, or another
// provider's key that would let omp silently route elsewhere) inherited from Eden's env
// would shadow or divert the injected key. They are scrubbed so the injected credential is
// the only provider key the child sees and the route is deterministic.
var scrubbedKeys = []string{
	"OPENROUTER_API_KEY", // any inherited copy is replaced by the injected value
	"OMP_AUTH_TOKEN",     // the library default vehicle var omp would read for its broker; never the OpenRouter key
	"ANTHROPIC_API_KEY",
	"ANTHROPIC_OAUTH_TOKEN",
	"OPENAI_API_KEY",
	"GEMINI_API_KEY",
}

// Config is the immutable configuration for the omp adapter. Binary names the CLI
// executable (defaulting to "omp" when empty), so an integration harness can point the SAME
// spawn/parse path at a trivial stub binary to exercise the real subprocess lifecycle
// without a live OpenRouter call. It reads NO env and NO secret.
type Config struct {
	Binary string // the CLI executable name/path; "" == "omp"
}

// Adapter is the real Oh My Pi (omp) agentsession.Adapter. It declares the capabilities the
// `omp --mode rpc` session supports and spawns ONE long-lived subprocess per Spawn. Each
// Spawn owns its own process; the Adapter holds only the immutable Config.
type Adapter struct {
	binary string
}

// New returns the omp adapter (the ADR-0008 omp lane) on the canonical constructor spine
// New(configuration[, dependencies]) (*T, error). This adapter needs no dependencies (it
// injects no ports), so the spine collapses to the single configuration argument; the zero
// Config selects the default "omp" binary, so New(Config{}) is the default entry and
// New(Config{Binary: stub}) is the integration seam for a stub binary. It is PURE: no env,
// no process, no secret. The error return is part of the spine; New never fails today, so
// it returns nil, but the shape is uniform with every other New.
//
//nolint:gocritic,unparam // contract: Config is the frozen copyable configuration (taken by value); the (*Adapter, error) return is the canonical New spine shape even though this pure constructor cannot fail today.
func New(configuration Config) (*Adapter, error) {
	binary := configuration.Binary
	if binary == "" {
		binary = ompBinary
	}
	return &Adapter{binary: binary}, nil
}

// Manifest declares the capabilities `omp --mode rpc` supports, as measured on the live
// harness (the 17.3.7 probe captures replayed in testdata/rpc-17.3.7-*.jsonl).
//
//   - Steer is CapFull: the live rpc session takes a mid-turn `steer` frame on stdin.
//   - Resume is CapFull: omp `--resume <id>` re-attaches a saved session.
//   - ThinkingEvents is CapFull: the stream carries distinct thinking_start/thinking_delta/
//     thinking_end frames carrying reasoning text.
//   - PartialToolResults is CapFull: omp streams toolcall_delta + a top-level
//     tool_execution_start/tool_execution_end pair (the OMP partial-result streaming the
//     taxonomy's EventToolUpdate exists for).
//   - HostTools is CapFull: the Spec's HostTools are registered on the live session with
//     set_host_tools, and a host_tool_call is routed into the in-process Handler and answered
//     with host_tool_result — a real callback round trip, not data the adapter declines.
//   - NativeBudget is CapAbsent: omp has no headless --max-budget-usd cost cap (the §02 budget
//     authority is the engine watching EventUsage); the adapter does not claim one.
//   - PermissionPrompt is CapFull: the approval dialog SURFACES as an EventPermissionRequest
//     the library's resolution chain acts on, and IS answered on the wire. The answer is the
//     session's own standing grant applied at arrival: omp arms no timer on a `select`
//     (rpc-mode.ts:640), so a dialog held open for an out-of-band decision stalls the turn
//     forever (q3-probe5 measured 45s and no agent_end).
//   - PeerMessaging is CapFull: omp has no cross-session plane of its own, so Eden owns BOTH
//     ends — the library's eden_peer_send / eden_peer_list host tools ride the same rpc bridge
//     the line above declares full, and an arrival is unwrapped onto the model-facing envelope
//     here. Nothing about this capability depends on a vendor feature.
func (a *Adapter) Manifest() agentsession.CapabilityManifest {
	return agentsession.CapabilityManifest{Capabilities: map[agentsession.Capability]agentsession.CapStatus{
		agentsession.CapSteer:              agentsession.CapFull,
		agentsession.CapResume:             agentsession.CapFull,
		agentsession.CapThinkingEvents:     agentsession.CapFull,
		agentsession.CapHostTools:          agentsession.CapFull,
		agentsession.CapNativeBudget:       agentsession.CapAbsent,
		agentsession.CapPermissionPrompt:   agentsession.CapFull,
		agentsession.CapPartialToolResults: agentsession.CapFull,
		agentsession.CapPeerMessaging:      agentsession.CapFull,
	}}
}

// buildArguments assembles the flag set for ONE long-lived omp session. It is PURE (no env,
// no process) so it is unit-tested directly.
//
//nolint:gocritic // contract §2: Spec is the frozen, copyable session input (the configuration pattern); the port takes it by value.
func buildArguments(spec agentsession.Spec, route agentsession.Route) []string {
	arguments := []string{
		// --mode rpc is the ONE long-lived session plane: NDJSON commands on stdin, frames on
		// stdout, one process across every turn. Never rpc-ui — that mode installs the tool UI
		// context and sets hasUI (main.ts:1570,1765), which is what lets a tool open a blocking
		// dialog. Never -p/--mode json either: print mode processes one prompt and exits.
		"--mode", "rpc",
		// The approval mode is pinned EXPLICITLY: `tools.approvalMode` is not in the rpc
		// host-default reset list (applyRpcDefaultSettingOverrides, main.ts:1316), so with no
		// flag the child inherits the operator's own setting — q3-probe4 watched a `bash` call
		// run ungated under exactly that inheritance. always-ask keeps every tool gated; the
		// dialog is answered from the session's standing grant (rpc.go).
		"--approval-mode", approvalMode,
	}
	if route.Model != "" {
		arguments = append(arguments, "--model", route.Model)
	}
	if thinking := thinkingLevel(spec); thinking != "" {
		arguments = append(arguments, "--thinking", thinking)
	}
	// NOTE: Budget.MaxTurns / MaxCostMicros emit NO omp flag — omp has no headless turn-cap or
	// cost-cap (NativeBudget is Absent in the Manifest); the §02 budget authority is the engine
	// watching EventUsage and aborting.
	arguments = append(arguments, toolArguments(spec.Grants)...)
	arguments = append(arguments, sessionArguments(spec.ResumeFrom)...)
	if spec.SystemHints != "" {
		arguments = append(arguments, "--append-system-prompt", spec.SystemHints)
	}
	return arguments
}

// toolArguments renders the Spec.Grants allowlist into omp's tool flags: the granted tool
// names as a --tools CSV, or --no-tools when the session grants none (so a no-grant
// AssistantSession cannot reach a tool it was never given). omp's --tools takes bare tool
// names; the per-scope sub-patterns Eden tracks for audit are not part of omp's tool
// vocabulary, so a scoped grant contributes its bare tool name once.
func toolArguments(grants []agentsession.ToolGrant) []string {
	names := toolNames(grants)
	if len(names) == 0 {
		return []string{"--no-tools"}
	}
	return []string{"--tools", strings.Join(names, ",")}
}

// toolNames collects the distinct, order-preserved tool names from the grant set.
func toolNames(grants []agentsession.ToolGrant) []string {
	var names []string
	seen := make(map[string]struct{}, len(grants))
	for i := range grants {
		name := grants[i].Tool
		if name == "" {
			continue
		}
		if _, dup := seen[name]; dup {
			continue
		}
		seen[name] = struct{}{}
		names = append(names, name)
	}
	return names
}

// sessionArguments renders the session-persistence flags. A non-empty resumeFrom re-attaches a
// harness-native session (CapResume) via --resume; otherwise the run is ephemeral
// (--no-session) so nothing is written into the provisioned workspace by default.
//
// The adapter deliberately spells NO path below the store root: omp owns its on-disk layout
// and has changed it twice (17.2.5-17.2.8 wrote hashed <scope>-<project>-<sha256(cwd)>
// buckets, 17.2.9 reverted to the legacy project-scoped naming, 17.2.10 added a one-way
// migration so `omp -r` could still find a session written under the other scheme). The store
// ROOT is named once, on the child env (sessionEnvironment); everything under it is omp's.
func sessionArguments(resumeFrom string) []string {
	if resumeFrom != "" {
		return []string{"--resume", resumeFrom}
	}
	return []string{"--no-session"}
}

// thinkingLevel maps the Spec onto an omp --thinking level. The Budget.MaxTurns and cost
// ceilings do not select a thinking level; the adapter requests the lightweight "minimal"
// level by default (the spike used it to keep one-shot reasoning bounded), which omp accepts
// for DeepSeek-v4-flash. An empty return omits the flag (omp's configured default).
//
//nolint:gocritic // contract §2: Spec is the frozen copyable session input; taken by value to match the port seam.
func thinkingLevel(spec agentsession.Spec) string {
	_ = spec
	return "minimal"
}

// childEnvironment builds the child process environment from the inherited base, the
// resolved key, and the env var name. It STRIPS the higher-precedence / route-diverting
// credential keys first, then sets exactly the injected var to the key. The key is supplied
// by the caller from inside Secret.Use, so the value never escapes the injection closure
// into a retained string. base is os.Environ() at the call site.
func childEnvironment(base []string, envName, key string) []string {
	out := make([]string, 0, len(base)+1)
	for _, entry := range base {
		if isScrubbed(entry) {
			continue
		}
		out = append(out, entry)
	}
	out = append(out, envName+"="+key)
	return out
}

// isScrubbed reports whether an env entry's key is a credential key to strip from the child
// environment.
func isScrubbed(entry string) bool {
	key, _, _ := strings.Cut(entry, "=")
	for _, scrubbed := range scrubbedKeys {
		if key == scrubbed {
			return true
		}
	}
	return false
}

// compile-time assertion: *Adapter is an agentsession.Adapter.
var _ agentsession.Adapter = (*Adapter)(nil)
