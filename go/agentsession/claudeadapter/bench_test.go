package claudeadapter_test

import (
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
)

// sink keeps the benchmarked work observable so the compiler cannot prove the result dead
// and elide it (ADR-0020 dimension (g)). `any` keeps it off any sentinel/comparison path.
//
//nolint:gochecknoglobals // a benchmark sink must be package-level so the compiler cannot elide the measured work.
var sink any

// benchAssistantLine is a representative assistant stream-json line (text + thinking + a
// tool_use + a per-message usage tick) — the heaviest per-line normalize path.
var benchAssistantLine = []byte(`{"type":"assistant","message":{"model":"claude-fable-5","role":"assistant",` +
	`"content":[{"type":"thinking","thinking":"considering the request"},` +
	`{"type":"text","text":"I'll create hello.go and run go vet."},` +
	`{"type":"tool_use","id":"toolu_01","name":"Write","input":{"file_path":"hello.go","content":"package main"}}],` +
	`"usage":{"input_tokens":1983,"output_tokens":42,"cache_read_input_tokens":15822,"cache_creation_input_tokens":3335}}}`)

// benchResultLine is the terminal result line carrying the four-token ledger + cost — the
// FinOps-load-bearing normalize path (cost conversion, bounds checks).
var benchResultLine = []byte(`{"type":"result","subtype":"success","is_error":false,"num_turns":3,` +
	`"duration_ms":16342,"total_cost_usd":0.229861,"result":"Done.","stop_reason":"end_turn",` +
	`"usage":{"input_tokens":3944,"output_tokens":394,"cache_read_input_tokens":56397,"cache_creation_input_tokens":5689}}`)

// BenchmarkNormalizeAssistant measures the hottest path: normalizing one assistant line
// (parse + per-block event allocation + the digest of the tool input). Each spawned session
// runs this once per stdout line, so it dominates the adapter's steady-state cost.
func BenchmarkNormalizeAssistant(b *testing.B) {
	var events []agentsession.Event
	b.ReportAllocs()
	for b.Loop() {
		events = claudeadapter.NormalizeLineForTest(benchAssistantLine)
	}
	sink = events
}

// BenchmarkNormalizeResult measures the terminal-line path: parse + ledger build + the
// usd->micros cost conversion with the bounds checks.
func BenchmarkNormalizeResult(b *testing.B) {
	var events []agentsession.Event
	b.ReportAllocs()
	for b.Loop() {
		events = claudeadapter.NormalizeLineForTest(benchResultLine)
	}
	sink = events
}

// BenchmarkBuildArguments measures the spawn arg-set construction (allowlist expansion,
// budget formatting, permission-mode selection) — run once per Spawn.
func BenchmarkBuildArguments(b *testing.B) {
	spec := agentsession.Spec{
		Grants: []agentsession.ToolGrant{
			{ID: "g1", Tool: "Write"},
			{ID: "g2", Tool: "Bash", Scopes: []string{"go *", "ls *"}},
			{ID: "g3", Tool: "Read", ReadOnly: true},
		},
		Budget:     agentsession.Budget{MaxCostMicros: 2_500_000, MaxTurns: 8},
		ResumeFrom: "sess-abc",
	}
	route := agentsession.Route{Harness: "claude-code", Model: "claude-fable-5"}
	var args []string
	b.ReportAllocs()
	for b.Loop() {
		args = claudeadapter.BuildArgumentsForTest(spec, route)
	}
	sink = args
}

// BenchmarkChildEnvironment measures the credential-seam env construction (scrub + inject)
// over a realistic inherited environment — run once per Spawn inside Secret.Use.
func BenchmarkChildEnvironment(b *testing.B) {
	base := []string{
		"PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/home/eden", "TERM=xterm",
		"LANG=en_US.UTF-8", "SHELL=/bin/bash", "ANTHROPIC_API_KEY=stray", "ANTHROPIC_AUTH_TOKEN=stray2",
	}
	var env []string
	b.ReportAllocs()
	for b.Loop() {
		env = claudeadapter.ChildEnvironmentForTest(base, "CLAUDE_CODE_OAUTH_TOKEN", "oauth-token-XYZ")
	}
	sink = env
}
