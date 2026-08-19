package ompadapter_test

import (
	"bytes"
	"encoding/json"
	"math"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS set in the process environment
// (default 1000 iterations/property, ADR-0020 dimension (a) threshold); rapid reads it directly.
// These properties assert the load-bearing invariants of the omp adapter's PURE core — the
// normalizer/converter folding omp json frames into the Event taxonomy, the token/cost ledger
// accounting, and the credential-scrub env builder — without spawning a process. Each is
// deterministic: identical input always folds to identical Events (no clock, no map iteration
// in the output, no randomness).

// drawCost draws a finite, non-negative USD cost in omp's realistic range (sub-cent to a few
// dollars), with enough fractional resolution to exercise the micro-unit rounding boundary.
func drawCost(rt *rapid.T) float64 {
	return rapid.Float64Range(0, 5).Draw(rt, "costUSD")
}

// TestProperty_NormalizeIsDeterministic asserts the cardinal converter invariant: a given omp
// json line, normalized through TWO independent fresh normalizers, folds to byte-identical
// Events. A normalizer that read a clock, a global, or ranged a map into its output would
// falsify this. The line space covers the modeled frame kinds plus an unknown kind (Extension).
func TestProperty_NormalizeIsDeterministic(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		line := drawFrameLine(rt)
		a := ompadapter.NormalizeLineForTest(line)
		b := ompadapter.NormalizeLineForTest(line)
		if len(a) != len(b) {
			rt.Fatalf("normalize not deterministic: %d vs %d events for %q", len(a), len(b), line)
		}
		for i := range a {
			ja, _ := json.Marshal(a[i]) //nolint:errcheck // marshaling a value Event for comparison never fails.
			jb, _ := json.Marshal(b[i]) //nolint:errcheck // marshaling a value Event for comparison never fails.
			if !bytes.Equal(ja, jb) {
				rt.Fatalf("normalize not deterministic at event %d: %s vs %s (line %q)", i, ja, jb, line)
			}
		}
	})
}

// TestProperty_UnknownFrameSurvivesVerbatim asserts the forward-compat invariant over the WHOLE
// space of unmodeled top-level frame types: any JSON object whose `type` Eden does not model
// folds to EXACTLY one EventExtension carrying the raw line verbatim — never dropped, never
// fatal, never reclassified (the rate_limit_event lesson, generalised).
func TestProperty_UnknownFrameSurvivesVerbatim(t *testing.T) {
	t.Parallel()
	modeled := map[string]struct{}{
		"session": {}, "agent_start": {}, "turn_start": {},
		"message_start": {}, "message_update": {}, "message_end": {},
		"tool_execution_start": {}, "tool_execution_end": {},
		"turn_end": {}, "agent_end": {},
	}
	rapid.Check(t, func(rt *rapid.T) {
		typ := rapid.StringMatching(`[a-z][a-z_]{0,20}`).Draw(rt, "type")
		if _, isModeled := modeled[typ]; isModeled {
			rt.Skip("drew a modeled type")
		}
		retry := rapid.Int64Range(0, 1000).Draw(rt, "retryAfter")
		raw, err := json.Marshal(map[string]any{"type": typ, "retryAfter": retry})
		if err != nil {
			rt.Fatalf("marshal frame: %v", err)
		}
		events := ompadapter.NormalizeLineForTest(raw)
		if len(events) != 1 {
			rt.Fatalf("unknown frame %q produced %d events, want 1", typ, len(events))
		}
		if events[0].Kind != agentsession.EventExtension {
			rt.Fatalf("unknown frame %q folded to %s, want extension", typ, events[0].Kind)
		}
		if !bytes.Equal(events[0].Extension, raw) {
			rt.Fatalf("Extension not verbatim: got %q want %q", events[0].Extension, raw)
		}
	})
}

// TestProperty_TerminalLedgerAccountsTokensAndCost asserts the ledger accounting invariant over
// the four-token + USD-cost space: an agent_end whose final assistant message carries a usage
// block folds to a boundary event whose TokenLedger reproduces the four token kinds EXACTLY and
// converts the USD cost to micro-units with the documented round-to-nearest rule and NO float
// drift across the whole cost range. This is the FinOps-load-bearing path (ADR-0008 routing
// economics are MEASURED here).
//
// Re-pinned for contract revision R1: a CLEAN agent_end is a TURN boundary over the whole
// generated space — non-terminal, rendering the "turn-end" token, still carrying the full
// authoritative ledger. Asserting it as a property rather than on one fixture is what stops the
// fix from being special-cased to the committed sample.
func TestProperty_TerminalLedgerAccountsTokensAndCost(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		in := rapid.Int64Range(0, 1_000_000).Draw(rt, "input")
		out := rapid.Int64Range(0, 1_000_000).Draw(rt, "output")
		cacheRead := rapid.Int64Range(0, 1_000_000).Draw(rt, "cacheRead")
		cacheWrite := rapid.Int64Range(0, 1_000_000).Draw(rt, "cacheWrite")
		cost := drawCost(rt)
		model := rapid.StringMatching(`[a-z0-9/.-]{1,30}`).Draw(rt, "model")

		line := agentEndLine(rt, model, in, out, cacheRead, cacheWrite, cost)
		// A FRESH stream normalizer, exactly as the live conn drives one per turn.
		normalize := ompadapter.StreamNormalizerForTest()
		events := normalize(line)
		if len(events) != 1 {
			rt.Fatalf("agent_end produced %d events, want 1 terminal: %q", len(events), line)
		}
		ev := events[0]
		if ev.Terminal == nil {
			rt.Fatalf("agent_end must carry a TerminalPayload, got kind %s (line %q)", ev.Kind, line)
		}
		// R1: a clean agent_end ends the TURN, not the session. The kind is identified by its
		// stable token rather than by its constant, so this file compiles against the pre-R1
		// tree and the failure is behavioral.
		if ev.IsTerminal() {
			rt.Fatalf("a clean agent_end is a TURN boundary, not a session terminal (kind %s); one omp process serves many turns (line %q)", ev.Kind, line)
		}
		if got := ev.Kind.String(); got != "turn-end" {
			rt.Fatalf("a clean agent_end must render the turn-end token, got %q (line %q)", got, line)
		}
		ledger := ev.Terminal.Ledger
		if ledger.InputTokens != in || ledger.OutputTokens != out ||
			ledger.CacheReadTokens != cacheRead || ledger.CacheCreationTokens != cacheWrite {
			rt.Fatalf("token kinds drifted: got in=%d out=%d cr=%d cw=%d want %d/%d/%d/%d",
				ledger.InputTokens, ledger.OutputTokens, ledger.CacheReadTokens, ledger.CacheCreationTokens,
				in, out, cacheRead, cacheWrite)
		}
		if ledger.Harness != "omp" {
			rt.Fatalf("ledger harness = %q, want omp", ledger.Harness)
		}
		if ledger.Model != model {
			rt.Fatalf("ledger model = %q, want %q", ledger.Model, model)
		}
		// The micro-unit conversion is round-to-nearest with no float drift: recompute the
		// reference independently and require an EXACT match.
		want := int64(math.Round(cost * 1_000_000))
		if ledger.CostMicros != want {
			rt.Fatalf("CostMicros = %d, want %d (%.9f USD)", ledger.CostMicros, want, cost)
		}
		if ledger.CostMicros < 0 {
			rt.Fatalf("a finite non-negative cost must never map to the -1 unreported sentinel")
		}
	})
}

// TestProperty_ChildEnvironmentScrubInvariant asserts the credential-scrub invariant over an
// arbitrary inherited base: childEnvironment ALWAYS (1) lands exactly ONE OPENROUTER_API_KEY
// entry carrying the injected key, (2) strips every route-diverting credential key the adapter
// scrubs, and (3) preserves every non-credential entry. A regression that forgot to scrub a key,
// or appended a second key entry, falsifies this — the precedence-trap defense (omp reads the
// first provider key it sees).
func TestProperty_ChildEnvironmentScrubInvariant(t *testing.T) {
	t.Parallel()
	scrubbed := []string{
		"OPENROUTER_API_KEY", "OMP_AUTH_TOKEN", "ANTHROPIC_API_KEY",
		"ANTHROPIC_OAUTH_TOKEN", "OPENAI_API_KEY", "GEMINI_API_KEY",
	}
	rapid.Check(t, func(rt *rapid.T) {
		// A non-credential carrier name the test asserts survives.
		const carrier = "PATH"
		carrierValue := rapid.StringMatching(`[A-Za-z0-9/:_.-]{1,40}`).Draw(rt, "carrierValue")
		key := rapid.StringMatching(`sk-or-v1-[A-Za-z0-9]{4,40}`).Draw(rt, "injectedKey")

		base := []string{carrier + "=" + carrierValue}
		// Randomly seed some inherited credential keys (the stray-copy / route-diverter traps).
		for _, name := range scrubbed {
			if rapid.Bool().Draw(rt, "seed_"+name) {
				base = append(base, name+"=inherited-must-be-scrubbed-or-replaced")
			}
		}

		env := ompadapter.ChildEnvironmentForTest(base, "OPENROUTER_API_KEY", key)

		// (1) exactly one OPENROUTER_API_KEY entry, carrying the injected key.
		if got := countEnv(env, "OPENROUTER_API_KEY="+key); got != 1 {
			rt.Fatalf("want exactly one injected OPENROUTER_API_KEY entry, got %d; env=%v", got, env)
		}
		// (2) no OTHER credential key survives, and no stray OPENROUTER copy survives.
		if leaked := firstUnscrubbedKey(env, scrubbed, key); leaked != "" {
			rt.Fatalf("credential key not scrubbed/replaced: %s", leaked)
		}
		// (3) the non-credential carrier is preserved verbatim.
		if !containsEnv(env, carrier+"="+carrierValue) {
			rt.Fatalf("non-credential entry %q=%q was not preserved; env=%v", carrier, carrierValue, env)
		}
	})
}

// firstUnscrubbedKey returns a non-empty diagnostic for the first env entry that violates the
// scrub invariant — a non-OpenRouter credential key that survived, or a stray OpenRouter copy
// that is not the injected value — or "" when the env is clean. Factored out so the property
// stays within the cognitive-complexity ceiling.
func firstUnscrubbedKey(env, scrubbed []string, injectedKey string) string {
	for _, e := range env {
		for _, name := range scrubbed {
			if name == "OPENROUTER_API_KEY" {
				if e != "OPENROUTER_API_KEY="+injectedKey && hasEnvPrefix(e, "OPENROUTER_API_KEY=") {
					return "a stray OPENROUTER_API_KEY copy survived: " + e
				}
				continue
			}
			if hasEnvPrefix(e, name+"=") {
				return name + " was not scrubbed: " + e
			}
		}
	}
	return ""
}

// countEnv counts how many env entries exactly equal entry.
func countEnv(env []string, entry string) int {
	n := 0
	for _, e := range env {
		if e == entry {
			n++
		}
	}
	return n
}

// TestProperty_BuildArgumentsAlwaysSelectsRPC asserts the spawn-arg invariant over arbitrary
// specs/routes: the ONE long-lived session's `--mode rpc` is ALWAYS selected, the approval mode
// is ALWAYS pinned explicitly (never inherited from the operator's settings), and neither the
// one-shot print stream (`-p` / `--mode json`) nor the blocking UI plane (`--mode rpc-ui`) is
// ever selected — regardless of grants/model/resume/system-hints.
//
// This is the inverse of the pre-rewrite property, which asserted rpc was NEVER selected. That
// invariant was a measurement of `--mode json`'s one-way stream, and it made the adapter
// single-turn by construction; q3 measured the rpc plane end to end (ready -> negotiate ->
// prompt -> host tool -> agent_end, BLOCKING_UI_REQUESTS 0) and the choice reverses.
func TestProperty_BuildArgumentsAlwaysSelectsRPC(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		spec := agentsession.Spec{
			Workspace:   rapid.StringMatching(`(/[a-z]{1,8}){0,3}`).Draw(rt, "workspace"),
			ResumeFrom:  rapid.StringMatching(`[a-z0-9-]{0,12}`).Draw(rt, "resume"),
			SystemHints: rapid.StringMatching(`[a-z ]{0,20}`).Draw(rt, "hints"),
		}
		nGrants := rapid.IntRange(0, 4).Draw(rt, "nGrants")
		for i := 0; i < nGrants; i++ {
			tool := rapid.StringMatching(`[a-z]{1,8}`).Draw(rt, "tool")
			spec.Grants = append(spec.Grants, agentsession.ToolGrant{ID: "g", Tool: tool})
		}
		route := agentsession.Route{
			Harness: "omp",
			Model:   rapid.StringMatching(`[a-z0-9/.-]{0,20}`).Draw(rt, "model"),
		}
		args := ompadapter.BuildArgumentsForTest(spec, route)

		sawRPC, approvalModes := false, 0
		for i, a := range args {
			switch a {
			case "-p":
				rt.Fatalf("print mode exits after one turn; the rpc session must outlive its turn; args=%v", args)
			case "--auto-approve":
				rt.Fatalf("--auto-approve pins tools.approvalMode=yolo and skips every approval prompt; args=%v", args)
			case "--approval-mode":
				approvalModes++
				if i+1 >= len(args) || args[i+1] == "yolo" {
					rt.Fatalf("--approval-mode must carry an ASKING value (always-ask|write); args=%v", args)
				}
			case "--mode":
				if i+1 >= len(args) {
					rt.Fatalf("--mode carries no value; args=%v", args)
				}
				switch args[i+1] {
				case "rpc":
					sawRPC = true
				case "json":
					rt.Fatalf("--mode json is the one-process-per-turn stream this rewrite deletes; args=%v", args)
				case "rpc-ui":
					rt.Fatalf("--mode rpc-ui installs the tool UI context (main.ts:1570) and CAN block; args=%v", args)
				}
			}
		}
		if !sawRPC {
			rt.Fatalf("--mode rpc missing; args=%v", args)
		}
		if approvalModes != 1 {
			rt.Fatalf("want exactly one explicit --approval-mode (found %d); with none omp inherits the operator's setting and q3-probe4 watched bash run ungated; args=%v",
				approvalModes, args)
		}
	})
}

// ── frame builders (valid-by-construction omp json lines) ────────────────────────────────.

// drawFrameLine draws one valid omp json line spanning the modeled + unknown frame space, so
// the determinism property exercises every fold branch.
func drawFrameLine(rt *rapid.T) []byte {
	kind := rapid.SampledFrom([]string{
		"session", "agent_start", "turn_start", "unknown_kind",
		"assistant_start", "thinking_delta", "text_delta", "tool_start", "tool_end",
		"message_end", "agent_end",
	}).Draw(rt, "frameKind")
	delta := rapid.StringMatching(`[a-z .]{0,30}`).Draw(rt, "delta")
	switch kind {
	case "session":
		return mustJSON(rt, map[string]any{"type": "session", "id": "s1", "version": 3})
	case "agent_start":
		return mustJSON(rt, map[string]any{"type": "agent_start"})
	case "turn_start":
		return mustJSON(rt, map[string]any{"type": "turn_start"})
	case "unknown_kind":
		return mustJSON(rt, map[string]any{"type": "rate_limit_event", "retryAfter": 7})
	case "assistant_start":
		return mustJSON(rt, map[string]any{"type": "message_start", "message": map[string]any{
			"role": "assistant", "model": "deepseek/deepseek-v4-flash", "content": []any{},
		}})
	case "thinking_delta":
		return mustJSON(rt, map[string]any{
			"type":                  "message_update",
			"assistantMessageEvent": map[string]any{"type": "thinking_delta", "delta": delta},
		})
	case "text_delta":
		return mustJSON(rt, map[string]any{
			"type":                  "message_update",
			"assistantMessageEvent": map[string]any{"type": "text_delta", "delta": delta},
		})
	case "tool_start":
		return mustJSON(rt, map[string]any{
			"type":       "tool_execution_start",
			"toolCallId": "call_1", "toolName": "read", "args": map[string]any{"path": "x"},
		})
	case "tool_end":
		return mustJSON(rt, map[string]any{
			"type":       "tool_execution_end",
			"toolCallId": "call_1", "toolName": "read", "isError": false,
			"result": map[string]any{"content": []any{}},
		})
	case "message_end":
		return mustJSON(rt, map[string]any{"type": "message_end", "message": map[string]any{
			"role": "assistant", "content": []any{map[string]any{"type": "text", "text": delta}},
			"usage": map[string]any{"input": 1, "output": 2, "cost": map[string]any{"total": 0.001}},
		}})
	default: // agent_end
		return agentEndLine(rt, "deepseek/deepseek-v4-flash", 10, 20, 0, 0, 0.001)
	}
}

// agentEndLine builds a valid agent_end terminal line whose final assistant message carries the
// given four-token usage and USD cost.
func agentEndLine(rt *rapid.T, model string, in, out, cacheRead, cacheWrite int64, cost float64) []byte {
	return mustJSON(rt, map[string]any{
		"type": "agent_end",
		"messages": []any{
			map[string]any{"role": "user", "content": []any{
				map[string]any{"type": "text", "text": "prompt"},
			}},
			map[string]any{
				"role":       "assistant",
				"model":      model,
				"stopReason": "stop",
				"content":    []any{map[string]any{"type": "text", "text": "ok"}},
				"usage": map[string]any{
					"input": in, "output": out, "cacheRead": cacheRead, "cacheWrite": cacheWrite,
					"cost": map[string]any{"total": cost},
				},
			},
		},
	})
}

// mustJSON marshals v to a line, failing the property on the (impossible for these shapes)
// marshal error.
func mustJSON(rt *rapid.T, v any) []byte {
	raw, err := json.Marshal(v)
	if err != nil {
		rt.Fatalf("marshal frame: %v", err)
	}
	return raw
}

// hasEnvPrefix reports whether env entry e begins with prefix.
func hasEnvPrefix(e, prefix string) bool {
	return len(e) >= len(prefix) && e[:len(prefix)] == prefix
}

// containsEnv reports whether env contains the exact entry.
func containsEnv(env []string, entry string) bool {
	for _, e := range env {
		if e == entry {
			return true
		}
	}
	return false
}
