package ompadapter_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
)

// TestBuildArguments_RPCModeFlagSet proves the spawn argument construction for the ONE
// long-lived `omp --mode rpc` process per session: the rpc mode (never rpc-ui, never the
// one-shot json print mode), the model from the Route, the thinking level, the tools CSV
// rendered from Spec.Grants, and the ephemeral --no-session — all WITHOUT spawning a process.
//
// Provenance: the credential-free probe harness that captured every frame in
// testdata/rpc-17.3.7-*.jsonl spawned exactly `omp --mode rpc --model <id>` with
// PI_CODING_AGENT_DIR on the child env and the workspace as cwd (driver3.js:3,6-7 of
// omp-rpc-probe-harness.tar.gz). No `-p`: print mode processes ONE prompt and exits, which is
// the per-turn-process model this rewrite deletes — under rpc the turn text rides a stdin
// `prompt` frame, never argv.
//
// The mode inversion is deliberate. The pre-rewrite argument set chose `--mode json` because a
// blocking `extension_ui_request` was believed to be unanswerable; q3 proved the opposite —
// the frame is answerable (`extension_ui_response`), the setWidget variant is fire-and-forget,
// and only rpc keeps ONE process alive across turns, which multi-turn, set_host_tools and turn
// injection all require.
func TestBuildArguments_RPCModeFlagSet(t *testing.T) {
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

	mustContain(t, args, "--mode", "rpc")
	mustContain(t, args, "--model", "openrouter/deepseek/deepseek-v4-flash")
	mustContain(t, args, "--thinking", "minimal")
	mustContain(t, args, "--tools", "read,bash") // dedup, order-preserved; scopes collapse to the bare name
	mustContain(t, args, "--no-session")

	// The one-shot print mode and its json stream are GONE: a session that exits after one turn
	// cannot serve a second Prompt, cannot hold set_host_tools, and cannot take an injected turn.
	if containsAll(args, "-p") {
		t.Errorf("--mode rpc is a long-lived session, not print mode: -p must be gone; args: %s", strings.Join(args, " "))
	}
	if containsAll(args, "--mode", "json") {
		t.Errorf("--mode json is the one-process-per-turn stream this rewrite deletes; args: %s", strings.Join(args, " "))
	}
	// rpc-ui is the mode that CAN block on a tool-originated dialog: it installs the tool UI
	// context and sets hasUI=true (main.ts:1570,1765). Plain rpc never opens one. Never select it.
	if containsAll(args, "--mode", "rpc-ui") {
		t.Errorf("--mode rpc-ui wires the tool UI context and is the blocking plane; args: %s", strings.Join(args, " "))
	}
	assertExplicitApprovalMode(t, args)
}

// assertExplicitApprovalMode proves the SECURITY half of the rewrite: `tools.approvalMode` is
// NOT in omp's rpc host-default reset list (q3 §"Why --mode rpc is the non-blocking plane"), so
// with no flag the child INHERITS the operator's own approval setting — q3-probe4 §A watched a
// `bash` tool call run ungated under exactly that inheritance. The adapter must therefore pin
// the mode explicitly, and to a value that ASKS (omp accepts always-ask|write|yolo): `yolo` and
// its `--auto-approve` alias skip the approval prompt entirely, which would make the
// CapPermissionPrompt promotion an over-claim — there would be nothing left to prompt.
func assertExplicitApprovalMode(t *testing.T, args []string) {
	t.Helper()
	asking := map[string]bool{"always-ask": true, "write": true}
	seen := 0
	for i, a := range args {
		if a != "--approval-mode" {
			continue
		}
		seen++
		if i+1 >= len(args) {
			t.Fatalf("--approval-mode carries no value; args: %s", strings.Join(args, " "))
		}
		if !asking[args[i+1]] {
			t.Errorf("--approval-mode %s does not ask: an out-of-grant tool runs ungated and CapPermissionPrompt has nothing to prompt; want one of always-ask|write",
				args[i+1])
		}
	}
	if seen != 1 {
		t.Errorf("the child must be pinned to EXACTLY one explicit --approval-mode (found %d): with no flag omp inherits the operator's tools.approvalMode and q3-probe4 watched bash run ungated; args: %s",
			seen, strings.Join(args, " "))
	}
	if containsAll(args, "--auto-approve") {
		t.Errorf("--auto-approve maps to tools.approvalMode=yolo (main.ts:1310) and skips every approval prompt; args: %s", strings.Join(args, " "))
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

// TestBuildArguments_ResumeNeverDerivesTheSessionLayout proves a non-empty ResumeFrom
// re-attaches a harness-native session (CapResume) via --resume — and that the adapter does
// NOT hand omp a derived --session-dir. omp OWNS the on-disk layout: 17.2.5-17.2.8 wrote
// hashed `<scope>-<project>-<sha256(cwd)>` buckets, 17.2.9 reverted to the legacy
// project-scoped naming and removed the migration (omp.json harnessSurfaceChanges[9], issue
// #7646/PR #7397), and 17.2.10 had to add a one-way migration back so `omp -r` could still find
// a session created under the other scheme. A wrapper that spells a bucket path is a wrapper
// that breaks on the next revert. The session STORE root is the child-env
// PI_CODING_AGENT_DIR instead (its own pin lives in the child-env test).
func TestBuildArguments_ResumeNeverDerivesTheSessionLayout(t *testing.T) {
	t.Parallel()
	spec := agentsession.Spec{Workspace: "/work/ws", ResumeFrom: "sess-abc"}
	args := ompadapter.BuildArgumentsForTest(spec, agentsession.Route{Model: "m"})
	mustContain(t, args, "--resume", "sess-abc")
	if containsAll(args, "--session-dir") {
		t.Errorf("the adapter must not derive omp's session directory layout (the 17.2.9 bucket revert); args: %v", args)
	}
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
	const key = "sk-or-v1-INJECTED" //gitleaks:allow // deliberate FAKE OpenRouter key (the literal word INJECTED) — a test fixture, never a real secret.
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
