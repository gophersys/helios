package ompadapter_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
)

// TestBuildArguments_HeadlessJSONFlagSet proves the spawn argument construction: the headless
// -p flag, the json mode (NOT rpc — the spike's load-bearing choice), the model from the
// Route, the thinking level, the tools CSV rendered from Spec.Grants, and the ephemeral
// --no-session — all WITHOUT spawning a process.
func TestBuildArguments_HeadlessJSONFlagSet(t *testing.T) {
	t.Parallel()
	spec := agentsession.Spec{
		Grants: []agentsession.ToolGrant{
			{ID: "g1", Tool: "read"},
			{ID: "g2", Tool: "bash", Scopes: []string{"go *", "ls *"}},
			{ID: "g3", Tool: "read"}, // duplicate tool name collapses
		},
	}
	route := agentsession.Route{Harness: "omp", Model: "openrouter/deepseek/deepseek-v4-flash"}
	args := ompadapter.BuildArgumentsForTest(spec, route)

	// -p + --mode json is MANDATORY: it puts omp in headless one-way-stream mode. rpc mode
	// emits an extension_ui_request that blocks the turn until the client answers the rpc — the
	// spike's reason json is chosen. Guard the regression here.
	mustContain(t, args, "-p")
	mustContain(t, args, "--mode", "json")
	mustContain(t, args, "--model", "openrouter/deepseek/deepseek-v4-flash")
	mustContain(t, args, "--thinking", "minimal")
	mustContain(t, args, "--tools", "read,bash") // dedup, order-preserved; scopes collapse to the bare name
	mustContain(t, args, "--no-session")

	// rpc mode must never be selected (the UI-ack trap).
	for i, a := range args {
		if a == "--mode" && i+1 < len(args) && args[i+1] == "rpc" {
			t.Errorf("must never select --mode rpc (the extension_ui_request blocking trap); args: %s", strings.Join(args, " "))
		}
	}
}

// TestBuildArguments_NoGrantsDisablesTools proves a session with no grants passes --no-tools
// so an AssistantSession cannot reach a tool it was never given.
func TestBuildArguments_NoGrantsDisablesTools(t *testing.T) {
	t.Parallel()
	args := ompadapter.BuildArgumentsForTest(agentsession.Spec{}, agentsession.Route{Model: "m"})
	mustContain(t, args, "--no-tools")
	if containsAll(args, "--tools") {
		t.Errorf("a no-grant session must use --no-tools, not --tools; args: %v", args)
	}
}

// TestBuildArguments_ResumeReattachesSession proves a non-empty ResumeFrom re-attaches a
// harness-native session (CapResume) via --resume and roots lookup at a session dir derived
// from the Workspace (instead of --no-session).
func TestBuildArguments_ResumeReattachesSession(t *testing.T) {
	t.Parallel()
	spec := agentsession.Spec{Workspace: "/work/ws", ResumeFrom: "sess-abc"}
	args := ompadapter.BuildArgumentsForTest(spec, agentsession.Route{Model: "m"})
	mustContain(t, args, "--resume", "sess-abc")
	mustContain(t, args, "--session-dir", "/work/ws/.omp-session")
	if containsAll(args, "--no-session") {
		t.Errorf("a resuming session must not be ephemeral (--no-session); args: %v", args)
	}
}

// TestBuildArguments_SystemHintsAppended proves the SystemHints ride as --append-system-prompt
// (the hermetic-context seam; never a secret).
func TestBuildArguments_SystemHintsAppended(t *testing.T) {
	t.Parallel()
	spec := agentsession.Spec{SystemHints: "be terse"}
	args := ompadapter.BuildArgumentsForTest(spec, agentsession.Route{Model: "m"})
	mustContain(t, args, "--append-system-prompt", "be terse")
}

// TestChildEnvironment_InjectsKeyAndScrubsCredentialKeys proves the credential seam at the env
// level: the resolved OpenRouter key lands on EXACTLY OPENROUTER_API_KEY, and the inherited
// credential keys (a stray OPENROUTER_API_KEY copy, the library default OMP_AUTH_TOKEN, and
// other-provider keys that would divert the route) are scrubbed first. Runnable WITHOUT a real
// Secret or process.
func TestChildEnvironment_InjectsKeyAndScrubsCredentialKeys(t *testing.T) {
	t.Parallel()
	const key = "sk-or-v1-INJECTED"
	base := []string{
		"PATH=/usr/bin",
		"HOME=/home/eden",
		"OPENROUTER_API_KEY=stray-copy-must-be-replaced",
		"OMP_AUTH_TOKEN=library-default-must-be-scrubbed",
		"ANTHROPIC_API_KEY=other-provider-must-be-scrubbed",
		"OPENAI_API_KEY=other-provider-must-be-scrubbed",
	}
	env := ompadapter.ChildEnvironmentForTest(base, "OPENROUTER_API_KEY", key)

	for _, scrubbed := range []string{"OMP_AUTH_TOKEN=", "ANTHROPIC_API_KEY=", "OPENAI_API_KEY="} {
		if hasPrefixEntry(env, scrubbed) {
			t.Errorf("child env must scrub %q; env: %v", scrubbed, env)
		}
	}
	if n := countPrefixEntries(env, "OPENROUTER_API_KEY="); n != 1 {
		t.Errorf("expected exactly one OPENROUTER_API_KEY entry, got %d", n)
	}
	if !hasEntry(env, "OPENROUTER_API_KEY="+key) {
		t.Errorf("injected key not present on the child env")
	}
	if hasEntry(env, "OPENROUTER_API_KEY=stray-copy-must-be-replaced") {
		t.Errorf("the inherited key copy must be replaced by the injected value")
	}
	if !hasEntry(env, "PATH=/usr/bin") || !hasEntry(env, "HOME=/home/eden") {
		t.Errorf("non-credential env must be preserved; env: %v", env)
	}
}

// TestManifest_DeclaresRealOmpCapabilities proves the manifest matches omp's measured
// capabilities: Steer/Resume/ThinkingEvents/PartialToolResults full, NativeBudget absent.
func TestManifest_DeclaresRealOmpCapabilities(t *testing.T) {
	t.Parallel()
	m := ompadapter.MustNewForTest(t, ompadapter.Config{}).Manifest()
	full := []agentsession.Capability{
		agentsession.CapSteer, agentsession.CapResume,
		agentsession.CapThinkingEvents, agentsession.CapPartialToolResults,
	}
	for _, c := range full {
		if m.Status(c) != agentsession.CapFull {
			t.Errorf("capability %s = %v, want CapFull", c, m.Status(c))
		}
	}
	if m.Status(agentsession.CapNativeBudget) != agentsession.CapAbsent {
		t.Errorf("omp has no headless cost cap: CapNativeBudget must be CapAbsent")
	}
}

// Order-independent arg/env helpers (black-box) follow.

func mustContain(t *testing.T, args []string, wanted ...string) {
	t.Helper()
	if !containsAll(args, wanted...) {
		t.Errorf("args missing %v; got: %s", wanted, strings.Join(args, " "))
	}
}

// containsAll reports whether args contains wanted as a contiguous subsequence.
func containsAll(args []string, wanted ...string) bool {
	if len(wanted) == 0 {
		return true
	}
	for i := 0; i+len(wanted) <= len(args); i++ {
		match := true
		for j := range wanted {
			if args[i+j] != wanted[j] {
				match = false
				break
			}
		}
		if match {
			return true
		}
	}
	return false
}

func hasEntry(env []string, entry string) bool {
	for _, e := range env {
		if e == entry {
			return true
		}
	}
	return false
}

func hasPrefixEntry(env []string, prefix string) bool {
	for _, e := range env {
		if strings.HasPrefix(e, prefix) {
			return true
		}
	}
	return false
}

func countPrefixEntries(env []string, prefix string) int {
	count := 0
	for _, e := range env {
		if strings.HasPrefix(e, prefix) {
			count++
		}
	}
	return count
}
