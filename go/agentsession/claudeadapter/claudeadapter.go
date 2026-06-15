package claudeadapter

import (
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/agentsession"
)

// credentialEnvName is the child-process env var the Claude Code CLI reads its OAuth /
// setup-token from. The library hands the adapter an InjectedCredential naming this var;
// the value crosses into the CHILD env ONLY, never Eden's env, never a log.
const credentialEnvName = "CLAUDE_CODE_OAUTH_TOKEN" // #nosec G101 -- the NAME of the env var the CLI reads, not a secret value

// claudeBinary is the CLI name, resolved from PATH at spawn.
const claudeBinary = "claude"

// scrubbedKeys are the higher-precedence credential env vars the adapter STRIPS from the
// child environment before injecting the setup-token: a stray ANTHROPIC_API_KEY /
// ANTHROPIC_AUTH_TOKEN inherited from Eden's env would silently WIN over the injected
// token (the precedence trap verified in the spike). They are scrubbed so the injected
// credential is the only one the child can use.
var scrubbedKeys = []string{
	"ANTHROPIC_API_KEY",
	"ANTHROPIC_AUTH_TOKEN",
	"CLAUDE_CODE_OAUTH_TOKEN", // any inherited copy is replaced by the injected value
}

// Config is the immutable configuration for the claude-code adapter. Binary names the
// CLI executable (defaulting to "claude" when empty), so an integration harness can point
// the SAME spawn/parse path at a trivial stub binary to exercise the real subprocess
// lifecycle without a live authenticated claude. It reads NO env and NO secret.
type Config struct {
	Binary string // the CLI executable name/path; "" == "claude"
}

// Adapter is the real claude-code agentsession.Adapter. It declares the capabilities the
// headless CLI supports and spawns the subprocess at Spawn. Each Spawn owns its own
// process; the Adapter holds only the immutable Config.
type Adapter struct {
	binary string
}

// New returns the claude-code adapter (the v1 entry per ADR-0008) on the canonical
// constructor spine New(configuration[, dependencies]) (*T, error). This adapter needs no
// dependencies (it injects no ports), so the spine collapses to the single configuration
// argument; the zero Config selects the default "claude" binary, so New(Config{}) is the
// default entry and New(Config{Binary: stub}) is the integration seam for a stub binary.
// It is PURE: no env, no process, no secret. The error return is part of the spine; New
// never fails today, so it returns nil, but the shape is uniform with every other New.
//
//nolint:gocritic,unparam // contract: Config is the frozen copyable configuration (taken by value); the (*Adapter, error) return is the canonical New spine shape even though this pure constructor cannot fail today.
func New(configuration Config) (*Adapter, error) {
	binary := configuration.Binary
	if binary == "" {
		binary = claudeBinary
	}
	return &Adapter{binary: binary}, nil
}

// Manifest declares the capabilities the headless `claude` CLI supports. Steer is
// CapPartial: headless Claude queues guidance for the next turn rather than true
// mid-turn interjection (the §7 Q7 distinction). Resume is full (--resume); thinking
// events, the permission prompt, and the native budget cap are full; partial tool
// results are absent (no OMP-style streaming).
func (a *Adapter) Manifest() agentsession.CapabilityManifest {
	return agentsession.CapabilityManifest{Capabilities: map[agentsession.Capability]agentsession.CapStatus{
		agentsession.CapSteer:              agentsession.CapPartial,
		agentsession.CapResume:             agentsession.CapFull,
		agentsession.CapThinkingEvents:     agentsession.CapFull,
		agentsession.CapHostTools:          agentsession.CapAbsent,
		agentsession.CapNativeBudget:       agentsession.CapFull,
		agentsession.CapPermissionPrompt:   agentsession.CapFull,
		agentsession.CapPartialToolResults: agentsession.CapAbsent,
	}}
}

// buildArguments assembles the headless flag set for one session (the spike's measured
// choices, ADR-0008): -p for headless, stream-json + --verbose for the event stream, the
// allowlist as data via --allowedTools, --permission-mode, an optional --max-budget-usd
// courtesy cap, and --resume for a harness-native re-attach. It is PURE (no env, no
// process) so it is unit-tested directly. The task text is supplied per turn (Send), so
// the spawn arguments carry only the session-wide flags.
//
//nolint:gocritic // contract §2: Spec is the frozen, copyable session input (the configuration pattern); the port takes it by value.
func buildArguments(spec agentsession.Spec, route agentsession.Route) []string {
	arguments := []string{
		// -p/--print is MANDATORY, not optional: `claude --help` states that
		// --input-format/--output-format stream-json "only work with --print". Without
		// -p, claude starts its DEFAULT interactive session — it waits on a TTY/trust
		// dialog and never emits the headless `system/init` event, so Open() blocks on the
		// Ready handshake forever (the real-claude hang the fakes hid). With -p +
		// stream-json, claude emits init on startup (→ StateReady) and stays open reading
		// stdin user turns until EOF — exactly the Send(stdin turn)/Abort(close stdin) model.
		"-p",
		"--output-format", "stream-json",
		"--verbose",
		"--input-format", "stream-json",
	}
	if route.Model != "" {
		arguments = append(arguments, "--model", route.Model)
	}
	if allowed := allowedTools(spec.Grants); len(allowed) > 0 {
		arguments = append(arguments, "--allowedTools")
		arguments = append(arguments, allowed...)
	}
	arguments = append(arguments, "--permission-mode", permissionMode(spec))
	if spec.Budget.MaxCostMicros > 0 {
		arguments = append(arguments, "--max-budget-usd", microsToUSDArg(spec.Budget.MaxCostMicros))
	}
	if spec.Budget.MaxTurns > 0 {
		arguments = append(arguments, "--max-turns", strconv.Itoa(int(spec.Budget.MaxTurns)))
	}
	if spec.ResumeFrom != "" {
		arguments = append(arguments, "--resume", spec.ResumeFrom)
	}
	if spec.SystemHints != "" {
		arguments = append(arguments, "--append-system-prompt", spec.SystemHints)
	}
	return arguments
}

// allowedTools renders the Spec.Grants allowlist into the --allowedTools patterns the
// CLI accepts ("Write", "Bash(go *)"). A grant with scopes yields one pattern per scope;
// an unscoped grant yields the bare tool name.
func allowedTools(grants []agentsession.ToolGrant) []string {
	var patterns []string
	for _, grant := range grants {
		if len(grant.Scopes) == 0 {
			patterns = append(patterns, grant.Tool)
			continue
		}
		for _, scope := range grant.Scopes {
			patterns = append(patterns, grant.Tool+"("+scope+")")
		}
	}
	return patterns
}

// permissionMode chooses the CLI --permission-mode. When the Spec drives the permission
// round-trip (OnPermission set OR standing grants present) the adapter uses "default" so
// out-of-grant tools raise a prompt the library round-trips; otherwise "acceptEdits" lets
// granted file edits proceed without a prompt. It NEVER uses
// --dangerously-skip-permissions (the gate is the contract).
//
//nolint:gocritic // contract §2/§3: Spec is the frozen copyable session input; the fake Adapter mirrors the port's by-value seam.
func permissionMode(spec agentsession.Spec) string {
	if spec.OnPermission != nil {
		return "default"
	}
	return "acceptEdits"
}

// microsToUSDArg renders an integer micro-unit budget as the --max-budget-usd decimal
// string with no float drift in the formatting.
func microsToUSDArg(micros int64) string {
	whole := micros / 1_000_000
	frac := micros % 1_000_000
	return strconv.FormatInt(whole, 10) + "." + padMicros(frac)
}

// padMicros renders the fractional micro-units as a zero-padded 6-digit string.
func padMicros(frac int64) string {
	s := strconv.FormatInt(frac, 10)
	return strings.Repeat("0", 6-len(s)) + s
}

// childEnvironment builds the child process environment from the inherited base, the
// resolved token, and the env var name. It STRIPS the higher-precedence credential keys
// first (the precedence trap), then sets exactly the injected var to the token. The token
// is supplied by the caller from inside Secret.Use, so the value never escapes the
// injection closure into a retained string. base is os.Environ() at the call site.
func childEnvironment(base []string, envName, token string) []string {
	out := make([]string, 0, len(base)+1)
	for _, entry := range base {
		if isScrubbed(entry) {
			continue
		}
		out = append(out, entry)
	}
	out = append(out, envName+"="+token)
	return out
}

// isScrubbed reports whether an env entry's key is a higher-precedence credential key to
// strip from the child environment.
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
