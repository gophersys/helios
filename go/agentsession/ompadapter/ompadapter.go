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
// `omp -p --mode json` headless stream supports and spawns the subprocess at Spawn. Each
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

// Manifest declares the capabilities `omp` supports, as measured in the live spike.
//
//   - Steer is CapFull: omp's interactive/rpc session accepts mid-turn input on stdin (the
//     SteeringMode the §7 Q7 note names); the headless adapter writes the steer as the next
//     stdin user turn.
//   - Resume is CapFull: omp `--resume <id>` / `--session-dir` re-attach a saved session.
//   - ThinkingEvents is CapFull: the spike captured distinct thinking_start/thinking_delta/
//     thinking_end frames carrying reasoning text.
//   - PartialToolResults is CapFull: omp streams toolcall_delta + a top-level
//     tool_execution_start/tool_execution_end pair (the OMP partial-result streaming the
//     taxonomy's EventToolUpdate exists for).
//   - HostTools is CapPartial: omp supports host/extension tools and an extension_ui channel,
//     but the headless json stream surfaces them as data the adapter normalizes/declines
//     rather than a wired in-process callback round-trip — declared Partial, not Full.
//   - NativeBudget is CapAbsent: omp has no headless --max-budget-usd cost cap (the §02 budget
//     authority is the engine watching EventUsage); the adapter does not claim one.
//   - PermissionPrompt is CapPartial: omp gates tools via --approval-mode and emits approval
//     requests, but the json one-way stream does not block on an out-of-band Resolve the way
//     the full round-trip requires — declared Partial.
func (a *Adapter) Manifest() agentsession.CapabilityManifest {
	return agentsession.CapabilityManifest{Capabilities: map[agentsession.Capability]agentsession.CapStatus{
		agentsession.CapSteer:              agentsession.CapFull,
		agentsession.CapResume:             agentsession.CapFull,
		agentsession.CapThinkingEvents:     agentsession.CapFull,
		agentsession.CapHostTools:          agentsession.CapPartial,
		agentsession.CapNativeBudget:       agentsession.CapAbsent,
		agentsession.CapPermissionPrompt:   agentsession.CapPartial,
		agentsession.CapPartialToolResults: agentsession.CapFull,
	}}
}

// buildArguments assembles the headless flag set for one omp session (the spike's measured
// choices, ADR-0008). It is PURE (no env, no process) so it is unit-tested directly.
//
// Mode choice (the spike's load-bearing decision): `--mode json` over `--mode rpc`. In rpc
// mode omp emits {"type":"ready"} then a bidirectional `extension_ui_request` (a widget UI)
// that BLOCKS the turn until the client answers the rpc — the adapter would have to speak
// omp's rpc response protocol to make progress. `--mode json` yields a clean ONE-WAY frame
// stream (session -> agent_start -> turn_start -> message_*/message_update -> turn_end ->
// agent_end) carrying the full taxonomy with NO UI ack required.
//
//nolint:gocritic // contract §2: Spec is the frozen, copyable session input (the configuration pattern); the port takes it by value.
func buildArguments(spec agentsession.Spec, route agentsession.Route) []string {
	arguments := []string{
		// -p/--print is MANDATORY: it puts omp in non-interactive headless mode (process the
		// turn and exit) instead of starting a TUI. --mode json selects the clean one-way
		// event stream. --no-session keeps the run ephemeral unless a session dir is derived
		// from the Workspace (CapResume).
		"-p",
		"--mode", "json",
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
	arguments = append(arguments, sessionArguments(spec.Workspace, spec.ResumeFrom)...)
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

// sessionArguments renders the session-persistence flags. A non-empty resumeFrom re-attaches
// a harness-native session (CapResume) via --resume and roots lookup at a session dir derived
// from the workspace; otherwise the run is ephemeral (--no-session) so nothing is written into
// the provisioned workspace by default.
func sessionArguments(workspace, resumeFrom string) []string {
	if resumeFrom != "" {
		args := []string{"--resume", resumeFrom}
		if dir := sessionDir(workspace); dir != "" {
			args = append(args, "--session-dir", dir)
		}
		return args
	}
	return []string{"--no-session"}
}

// sessionDir derives the omp --session-dir from the provisioned Workspace (the session store
// lives under the workspace so resume is co-located with the run). Empty workspace yields no
// dir (omp falls back to its default lookup).
func sessionDir(workspace string) string {
	if workspace == "" {
		return ""
	}
	return strings.TrimRight(workspace, "/") + "/.omp-session"
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
