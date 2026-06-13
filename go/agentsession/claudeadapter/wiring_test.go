package claudeadapter_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
)

// TestBuildArguments_HeadlessFlagSet proves the spawn argument construction: the
// stream-json output/input format, the model, the allowlist rendered from Spec.Grants
// (including scoped patterns like "Bash(go *)"), the permission mode, the budget cap, max
// turns, and a harness-native resume — all WITHOUT spawning a process.
func TestBuildArguments_HeadlessFlagSet(t *testing.T) {
	t.Parallel()
	spec := agentsession.Spec{
		Grants: []agentsession.ToolGrant{
			{ID: "g1", Tool: "Write"},
			{ID: "g2", Tool: "Bash", Scopes: []string{"go *", "ls *"}},
		},
		Budget:     agentsession.Budget{MaxCostMicros: 2_500_000, MaxTurns: 8},
		ResumeFrom: "sess-abc",
	}
	route := agentsession.Route{Harness: "claude-code", Model: "claude-fable-5"}
	args := claudeadapter.BuildArgumentsForTest(spec, route)

	// -p/--print is MANDATORY: --input-format/--output-format stream-json only work under
	// --print; without it claude starts an interactive session and never emits the headless
	// init, hanging Open() on the Ready handshake. Guard the regression here.
	mustContain(t, args, "-p")
	mustContain(t, args, "--output-format", "stream-json")
	mustContain(t, args, "--input-format", "stream-json")
	mustContain(t, args, "--verbose")
	mustContain(t, args, "--model", "claude-fable-5")
	mustContain(t, args, "--allowedTools", "Write", "Bash(go *)", "Bash(ls *)")
	mustContain(t, args, "--permission-mode", "acceptEdits") // OnPermission nil -> acceptEdits
	mustContain(t, args, "--max-budget-usd", "2.500000")
	mustContain(t, args, "--max-turns", "8")
	mustContain(t, args, "--resume", "sess-abc")

	// The contract bans --dangerously-skip-permissions.
	for _, a := range args {
		if strings.Contains(a, "dangerously-skip-permissions") {
			t.Errorf("must never pass --dangerously-skip-permissions; args: %s", strings.Join(args, " "))
		}
	}
}

// TestBuildArguments_PolicyDeciderUsesDefaultPermissionMode proves that when the engine
// supplies an OnPermission policy, the adapter uses --permission-mode default so
// out-of-grant tools raise a prompt the library round-trips.
func TestBuildArguments_PolicyDeciderUsesDefaultPermissionMode(t *testing.T) {
	t.Parallel()
	spec := agentsession.Spec{
		OnPermission: func(agentsession.PermissionRequest) agentsession.Decision {
			return agentsession.Decision{Allow: false, By: "policy:test"}
		},
	}
	args := claudeadapter.BuildArgumentsForTest(spec, agentsession.Route{Model: "m"})
	mustContain(t, args, "--permission-mode", "default")
}

// TestChildEnvironment_InjectsTokenAndScrubsPrecedenceKeys proves the credential seam at
// the env level: the resolved token lands on EXACTLY the injected var, and the
// higher-precedence credential keys inherited from Eden's env are scrubbed first (the
// precedence trap) so a stray ANTHROPIC_API_KEY cannot silently win. Runnable WITHOUT a
// real Secret or process.
func TestChildEnvironment_InjectsTokenAndScrubsPrecedenceKeys(t *testing.T) {
	t.Parallel()
	const token = "oauth-token-XYZ"
	base := []string{
		"PATH=/usr/bin",
		"HOME=/home/eden",
		"ANTHROPIC_API_KEY=stray-key-must-be-scrubbed",
		"ANTHROPIC_AUTH_TOKEN=stray-token-must-be-scrubbed",
		"CLAUDE_CODE_OAUTH_TOKEN=inherited-copy-must-be-replaced",
	}
	env := claudeadapter.ChildEnvironmentForTest(base, "CLAUDE_CODE_OAUTH_TOKEN", token)

	// The higher-precedence keys are gone.
	for _, scrubbed := range []string{"ANTHROPIC_API_KEY=", "ANTHROPIC_AUTH_TOKEN="} {
		if hasPrefixEntry(env, scrubbed) {
			t.Errorf("child env must scrub %q (the precedence trap); env: %v", scrubbed, env)
		}
	}
	// Exactly one CLAUDE_CODE_OAUTH_TOKEN entry, carrying the injected token (the inherited
	// copy was replaced).
	tokenEntries := countPrefixEntries(env, "CLAUDE_CODE_OAUTH_TOKEN=")
	if tokenEntries != 1 {
		t.Errorf("expected exactly one CLAUDE_CODE_OAUTH_TOKEN entry, got %d", tokenEntries)
	}
	if !hasEntry(env, "CLAUDE_CODE_OAUTH_TOKEN="+token) {
		t.Errorf("injected token not present on the child env")
	}
	// The inherited stray copy's value did NOT survive.
	if hasEntry(env, "CLAUDE_CODE_OAUTH_TOKEN=inherited-copy-must-be-replaced") {
		t.Errorf("the inherited token copy must be replaced by the injected value")
	}
	// Non-credential env is preserved.
	if !hasEntry(env, "PATH=/usr/bin") || !hasEntry(env, "HOME=/home/eden") {
		t.Errorf("non-credential env must be preserved; env: %v", env)
	}
}

// mustContain fails unless args contains every wanted token (order-independent).
func mustContain(t *testing.T, args []string, wanted ...string) {
	t.Helper()
	if !containsAll(args, wanted...) {
		t.Errorf("args missing %v; got: %s", wanted, joinArgs(args))
	}
}

// hasEntry reports whether env contains an exact entry.
func hasEntry(env []string, entry string) bool {
	for _, e := range env {
		if e == entry {
			return true
		}
	}
	return false
}

// hasPrefixEntry reports whether any env entry starts with prefix.
func hasPrefixEntry(env []string, prefix string) bool {
	for _, e := range env {
		if strings.HasPrefix(e, prefix) {
			return true
		}
	}
	return false
}

// countPrefixEntries counts env entries starting with prefix.
func countPrefixEntries(env []string, prefix string) int {
	count := 0
	for _, e := range env {
		if strings.HasPrefix(e, prefix) {
			count++
		}
	}
	return count
}
