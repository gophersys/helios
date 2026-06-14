package ompadapter_test

import (
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
)

// sink is the package-level any sink so the compiler cannot prove the benchmarked work dead and
// elide it (ADR-0020 dimension (g)). Kept off any sentinel path; written on every iteration.
//
//nolint:gochecknoglobals // a benchmark sink MUST be package-level so the compiler cannot elide the measured work.
var sink any

// benchAgentEndLine is the terminal frame — the hottest single fold (it builds the authoritative
// four-token ledger + USD->micros conversion on every turn).
var benchAgentEndLine = []byte(`{"type":"agent_end","messages":[{"role":"user","content":[{"type":"text","text":"prompt"}]},{"role":"assistant","content":[{"type":"thinking","thinking":"reasoning here"},{"type":"text","text":"ok"}],"api":"openai-completions","provider":"openrouter","model":"deepseek/deepseek-v4-flash","stopReason":"stop","duration":1500,"usage":{"input":3494,"output":19,"cacheRead":0,"cacheWrite":0,"totalTokens":3513,"reasoningTokens":16,"cost":{"input":0.000342412,"output":0.0000037,"cacheRead":0,"cacheWrite":0,"total":0.000346136}}}]}`)

// benchStreamLines is a representative single-turn omp json stream (the hottest per-turn path:
// the conn folds one of these per Prompt/Steer).
var benchStreamLines = func() [][]byte {
	raw := []string{
		`{"type":"session","version":3,"id":"s1"}`,
		`{"type":"agent_start"}`,
		`{"type":"turn_start"}`,
		`{"type":"message_start","message":{"role":"assistant","content":[],"model":"deepseek/deepseek-v4-flash"}}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"thinking_delta","delta":"The user asked"}}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"ok"}}`,
		`{"type":"tool_execution_start","toolCallId":"c1","toolName":"read","args":{"path":"sample.txt"}}`,
		`{"type":"tool_execution_end","toolCallId":"c1","toolName":"read","isError":false,"result":{"content":[{"type":"text","text":"hello"}]}}`,
		`{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"ok"}],"usage":{"input":120,"output":18,"cacheRead":900,"cacheWrite":40,"cost":{"total":0.0123}}}}`,
		`{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"ok"}],"usage":{"input":120,"output":18,"cost":{"total":0.0123}}}}`,
		`{"type":"agent_end","messages":[{"role":"assistant","content":[{"type":"text","text":"ok"}],"model":"deepseek/deepseek-v4-flash","stopReason":"stop","usage":{"input":120,"output":18,"cacheRead":900,"cacheWrite":40,"cost":{"total":0.0123}}}]}`,
	}
	lines := make([][]byte, len(raw))
	for i, l := range raw {
		lines[i] = []byte(l)
	}
	return lines
}()

// BenchmarkNormalizeTerminal measures the single hottest fold: the agent_end terminal that
// builds the four-token ledger and the USD->micros conversion (the FinOps-load-bearing path).
func BenchmarkNormalizeTerminal(b *testing.B) {
	var events []agentsession.Event
	b.ReportAllocs()
	for b.Loop() {
		events = ompadapter.NormalizeLineForTest(benchAgentEndLine)
	}
	sink = events
}

// BenchmarkNormalizeStream measures the per-turn fold spine: one fresh stream normalizer folding
// a whole representative turn (the path the conn drives on every Prompt/Steer), threading model
// attribution and the terminal aggregate across lines.
func BenchmarkNormalizeStream(b *testing.B) {
	var events []agentsession.Event
	b.ReportAllocs()
	for b.Loop() {
		normalize := ompadapter.StreamNormalizerForTest()
		events = events[:0]
		for _, line := range benchStreamLines {
			events = append(events, normalize(line)...)
		}
	}
	sink = events
}

// BenchmarkBuildArguments measures the pure spawn-arg construction (run once per turn before the
// process launch).
func BenchmarkBuildArguments(b *testing.B) {
	spec := agentsession.Spec{
		Workspace:   "/work/ws",
		SystemHints: "be terse",
		Grants: []agentsession.ToolGrant{
			{ID: "g1", Tool: "read"}, {ID: "g2", Tool: "bash"}, {ID: "g3", Tool: "write"},
		},
	}
	route := agentsession.Route{Harness: "omp", Model: "openrouter/deepseek/deepseek-v4-flash"}
	var args []string
	b.ReportAllocs()
	for b.Loop() {
		args = ompadapter.BuildArgumentsForTest(spec, route)
	}
	sink = args
}
