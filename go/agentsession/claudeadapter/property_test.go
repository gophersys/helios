package claudeadapter_test

import (
	"bytes"
	"encoding/json"
	"math"
	"strconv"
	"strings"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
)

// The `property` ctl.sh verb runs `go test -race` with RAPID_CHECKS set in the process
// environment (default 1000 iterations/property, ADR-0020 dimension (a)); rapid reads it
// directly. Every property below drives the REAL normalizer / arg-builder / env-builder
// over generated-but-well-formed inputs and asserts an invariant that must hold for ALL
// of them — the deterministic behavior the live conn relies on.

// TestProperty_NormalizeIsDeterministic asserts the normalizer is a pure function of its
// input line: two FRESH normalizers fed the identical bytes emit the identical Event
// sequence (kinds + the load-bearing payload fields). Determinism is the contract the
// transcript replay and multi-client fan-out depend on — a non-deterministic parser would
// make Seq replay diverge between tailers.
func TestProperty_NormalizeIsDeterministic(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		line := drawStreamLine(rt)
		a := claudeadapter.NormalizeLineForTest(line)
		b := claudeadapter.NormalizeLineForTest(line)
		if len(a) != len(b) {
			rt.Fatalf("non-deterministic event count: %d vs %d for line %s", len(a), len(b), line)
		}
		for i := range a {
			if a[i].Kind != b[i].Kind {
				rt.Fatalf("non-deterministic kind at %d: %v vs %v", i, a[i].Kind, b[i].Kind)
			}
			if !sameEventValue(&a[i], &b[i]) {
				rt.Fatalf("non-deterministic payload at %d for line %s", i, line)
			}
		}
	})
}

// TestProperty_ResultLedgerFaithfulAndBounded asserts the ledger the normalizer builds from a
// result line is a faithful, bounded projection of the wire usage: every token kind equals the
// reported count (never negative, never invented), the cost is EXACTLY round(usd*1e6) with no
// float drift, and the subtype determines the BOUNDARY the line draws. This is the
// FinOps-load-bearing invariant — the ledger is the authoritative spend record.
//
// Re-pinned for contract revision R1: a SUCCESS result is a TURN boundary over the whole
// generated space (non-terminal, rendering the "turn-end" token, still carrying the full
// ledger), while an ERROR result stays a SESSION terminal (EventFailed). Asserting it as a
// property rather than on one fixture is what stops the fix from being special-cased to the
// committed sample: EVERY well-formed success result must be a turn boundary.
func TestProperty_ResultLedgerFaithfulAndBounded(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		in := rapid.IntRange(0, 1_000_000).Draw(rt, "input_tokens")
		out := rapid.IntRange(0, 1_000_000).Draw(rt, "output_tokens")
		cacheRead := rapid.IntRange(0, 1_000_000).Draw(rt, "cache_read")
		cacheCreate := rapid.IntRange(0, 1_000_000).Draw(rt, "cache_create")
		// A non-negative cost with at most micro-cent precision so the round-trip is exact.
		costMicros := rapid.Int64Range(0, 1_000_000_000).Draw(rt, "cost_micros")
		usd := float64(costMicros) / 1_000_000
		success := rapid.Bool().Draw(rt, "success")
		turns := rapid.IntRange(0, 100_000).Draw(rt, "num_turns")

		subtype := "success"
		if !success {
			subtype = rapid.SampledFrom([]string{
				"error_max_turns", "error_during_execution", "error_rate_limit", "error_max_budget",
			}).Draw(rt, "fail_subtype")
		}
		line := mustJSON(rt, map[string]any{
			"type": "result", "subtype": subtype, "is_error": !success,
			"num_turns": turns, "total_cost_usd": usd, "result": "ok", "stop_reason": "end_turn",
			"usage": map[string]any{
				"input_tokens": in, "output_tokens": out,
				"cache_read_input_tokens": cacheRead, "cache_creation_input_tokens": cacheCreate,
			},
		})

		events := claudeadapter.NormalizeLineForTest(line)
		if len(events) != 1 {
			rt.Fatalf("result line must yield exactly one terminal event, got %d", len(events))
		}
		ev := events[0]
		if ev.Terminal == nil {
			rt.Fatalf("result line must carry a TerminalPayload, got kind %v", ev.Kind)
		}
		assertResultBoundary(rt, &ev, success, subtype)
		l := ev.Terminal.Ledger
		assertNonNegativeTokens(rt, &l)
		if l.InputTokens != int64(in) || l.OutputTokens != int64(out) ||
			l.CacheReadTokens != int64(cacheRead) || l.CacheCreationTokens != int64(cacheCreate) {
			rt.Fatalf("ledger tokens drifted from wire: got %+v, want in=%d out=%d cr=%d cc=%d",
				l, in, out, cacheRead, cacheCreate)
		}
		wantMicros := int64(math.Round(usd * 1_000_000))
		if l.CostMicros != wantMicros {
			rt.Fatalf("cost drift: usd=%v -> %d micros, want %d", usd, l.CostMicros, wantMicros)
		}
		if int(l.Turns) != turns {
			rt.Fatalf("turns drifted: got %d, want %d", l.Turns, turns)
		}
		if l.Harness != "claude-code" {
			rt.Fatalf("ledger harness = %q, want claude-code", l.Harness)
		}
	})
}

// assertResultBoundary asserts which BOUNDARY a result line draws (contract revision R1): a
// success result ends the TURN and leaves the session alive; an error result ends the SESSION.
// The turn-end kind is identified by its stable token rather than by its constant, so this file
// compiles against the pre-R1 tree and the failure is behavioral.
func assertResultBoundary(rt *rapid.T, ev *agentsession.Event, success bool, subtype string) {
	if !success {
		if !ev.IsTerminal() {
			rt.Fatalf("subtype %q: an error result must stay a SESSION terminal, got non-terminal kind %v", subtype, ev.Kind)
		}
		if ev.Kind != agentsession.EventFailed {
			rt.Fatalf("subtype %q -> kind %v, want %v", subtype, ev.Kind, agentsession.EventFailed)
		}
		return
	}
	if ev.IsTerminal() {
		rt.Fatalf("subtype %q: a success result is a TURN boundary, not a session terminal (kind %v); one claude process emits one result PER TURN",
			subtype, ev.Kind)
	}
	if got := ev.Kind.String(); got != "turn-end" {
		rt.Fatalf("subtype %q: a success result must render the turn-end token, got %q", subtype, got)
	}
}

// TestProperty_UnknownTypeIsVerbatimExtension asserts that ANY line whose top-level type
// is not one Eden models survives as EXACTLY one EventExtension carrying the raw bytes
// verbatim — never dropped, never fatal (the rate_limit_event forward-compat lesson, over
// the whole space of unknown type tokens).
func TestProperty_UnknownTypeIsVerbatimExtension(t *testing.T) {
	t.Parallel()
	modeled := map[string]bool{"system": true, "assistant": true, "user": true, "result": true}
	rapid.Check(t, func(rt *rapid.T) {
		typ := rapid.StringMatching(`[a-z][a-z_]{0,30}`).Draw(rt, "type")
		if modeled[typ] {
			return // modeled types have their own structured mapping; this property is the escape hatch
		}
		line := mustJSON(rt, map[string]any{"type": typ, "payload": map[string]any{"n": 1}})
		events := claudeadapter.NormalizeLineForTest(line)
		if len(events) != 1 || events[0].Kind != agentsession.EventExtension {
			rt.Fatalf("unknown type %q must yield one Extension, got %+v", typ, events)
		}
		if !bytes.Equal(events[0].Extension, line) {
			rt.Fatalf("Extension must carry verbatim bytes: got %q want %q", events[0].Extension, line)
		}
	})
}

// TestProperty_AssistantNeverEmitsReady asserts the Initializing->Ready handshake invariant
// from the parser side: the normalizer NEVER synthesizes a Ready transition (readiness is
// conn-emitted on spawn, spawn.go: scan). An assistant line maps to a MessageStart .. blocks
// .. MessageEnd envelope and nothing more — so a regression that started inferring Ready from
// a frame (the real-claude hang the fakes hid) is caught.
func TestProperty_AssistantNeverEmitsReady(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		text := rapid.StringMatching(`[a-zA-Z0-9 .]{1,40}`).Draw(rt, "text")
		line := mustJSON(rt, map[string]any{
			"type": "assistant",
			"message": map[string]any{
				"model": "claude-fable-5", "role": "assistant",
				"content": []any{map[string]any{"type": "text", "text": text}},
			},
		})
		events := claudeadapter.NormalizeLineForTest(line)
		if len(events) == 0 {
			rt.Fatalf("assistant line produced no events")
		}
		if events[0].Kind != agentsession.EventMessageStart {
			rt.Fatalf("assistant must open with MessageStart, got %v", events[0].Kind)
		}
		if events[len(events)-1].Kind != agentsession.EventMessageEnd {
			rt.Fatalf("assistant must close with MessageEnd, got %v", events[len(events)-1].Kind)
		}
		assertNoReadyAndTextRoundTrips(rt, events, text)
	})
}

// assertNoReadyAndTextRoundTrips asserts no event is a session-state transition (Ready is
// conn-emitted, never parser-inferred) and the text block round-trips verbatim as a delta.
func assertNoReadyAndTextRoundTrips(rt *rapid.T, events []agentsession.Event, text string) {
	sawText := false
	for i := range events {
		if events[i].Kind == agentsession.EventSessionState {
			rt.Fatalf("normalizer must NOT emit a session-state transition from a frame (Ready is conn-emitted)")
		}
		if events[i].Kind != agentsession.EventTextDelta {
			continue
		}
		sawText = true
		if events[i].Message == nil || events[i].Message.Delta != text {
			rt.Fatalf("text delta must round-trip verbatim: got %+v want %q", events[i].Message, text)
		}
	}
	if !sawText {
		rt.Fatalf("a non-empty text block must yield a TextDelta")
	}
}

// TestProperty_BuildArgumentsInvariants asserts the spawn arg-set invariants hold for ANY
// Spec/Route: -p + stream-json (in+out) are ALWAYS present (the headless requirement that,
// if dropped, hangs Open on the Ready handshake), --dangerously-skip-permissions is NEVER
// present (the gate is the contract), the allowedTools pattern count equals the expanded
// grant set, and the permission mode is exactly the closed {default, acceptEdits} set.
func TestProperty_BuildArgumentsInvariants(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		spec, wantPatterns := drawSpec(rt)
		route := agentsession.Route{Model: rapid.StringMatching(`[a-z0-9-]{0,20}`).Draw(rt, "model")}
		args := claudeadapter.BuildArgumentsForTest(spec, route)

		mustHaveFlag(rt, args, "-p")
		mustHavePair(rt, args, "--output-format", "stream-json")
		mustHavePair(rt, args, "--input-format", "stream-json")
		mustHaveFlag(rt, args, "--verbose")
		for _, a := range args {
			if strings.Contains(a, "dangerously-skip-permissions") {
				rt.Fatalf("--dangerously-skip-permissions must NEVER appear; args: %v", args)
			}
		}
		mode := pairValue(args, "--permission-mode")
		if mode != "default" && mode != "acceptEdits" {
			rt.Fatalf("permission-mode must be default|acceptEdits, got %q", mode)
		}
		// The control-channel sentinel is paired EXACTLY with default mode: present iff the
		// session drives the round-trip (default), absent under acceptEdits — never the reverse
		// (a stdio flag without default, or a default without stdio, both bypass the gate).
		hasStdio := pairValue(args, "--permission-prompt-tool") == "stdio"
		if (mode == "default") != hasStdio {
			rt.Fatalf("--permission-prompt-tool stdio must be present iff mode==default; mode=%q stdio=%v args=%v", mode, hasStdio, args)
		}
		if got := countAfterFlag(args, "--allowedTools"); got != wantPatterns {
			rt.Fatalf("allowedTools pattern count = %d, want %d (args %v)", got, wantPatterns, args)
		}
	})
}

// TestProperty_ChildEnvironmentScrubsAndInjects asserts the credential-seam invariant over
// arbitrary base environments: after building the child env, the injected var carries
// EXACTLY the token (one entry), every higher-precedence credential key is gone, and every
// non-credential base entry survives. This is the precedence-trap defense as a property.
func TestProperty_ChildEnvironmentScrubsAndInjects(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		base, safeKeys := drawBaseEnv(rt)
		token := rapid.StringMatching(`[A-Za-z0-9_-]{1,40}`).Draw(rt, "token")
		env := claudeadapter.ChildEnvironmentForTest(base, "CLAUDE_CODE_OAUTH_TOKEN", token)
		assertScrubbedAndInjected(rt, env, safeKeys, token)
	})
}

// drawBaseEnv generates a base environment with some safe entries and optionally some of the
// higher-precedence credential keys that MUST be scrubbed, returning the base and the safe
// keys that must survive the scrub.
func drawBaseEnv(rt *rapid.T) (base, safeKeys []string) {
	nSafe := rapid.IntRange(0, 6).Draw(rt, "n_safe")
	for i := range nSafe {
		k := "SAFE_" + strconv.Itoa(i) + "_" + rapid.StringMatching(`[A-Z]{1,5}`).Draw(rt, "k")
		base = append(base, k+"=v"+strconv.Itoa(i))
		safeKeys = append(safeKeys, k)
	}
	for _, sk := range []string{"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"} {
		if rapid.Bool().Draw(rt, "seed_"+sk) {
			base = append(base, sk+"=stray-"+sk)
		}
	}
	return base, safeKeys
}

// assertScrubbedAndInjected asserts the child env carries exactly the injected token, no
// surviving higher-precedence key, and every safe base entry.
func assertScrubbedAndInjected(rt *rapid.T, env, safeKeys []string, token string) {
	if c := countPrefix(env, "CLAUDE_CODE_OAUTH_TOKEN="); c != 1 {
		rt.Fatalf("want exactly one CLAUDE_CODE_OAUTH_TOKEN entry, got %d (env %v)", c, env)
	}
	if !hasExact(env, "CLAUDE_CODE_OAUTH_TOKEN="+token) {
		rt.Fatalf("injected token entry missing")
	}
	for _, sk := range []string{"ANTHROPIC_API_KEY=", "ANTHROPIC_AUTH_TOKEN="} {
		if hasPrefix(env, sk) {
			rt.Fatalf("scrubbed key %q survived: %v", sk, env)
		}
	}
	for i, k := range safeKeys {
		if !hasExact(env, k+"=v"+strconv.Itoa(i)) {
			rt.Fatalf("non-credential entry %q was dropped: %v", k, env)
		}
	}
}

// ── rapid generators + helpers ────────────────────────────────────────────────────────.

// drawStreamLine generates one well-formed stream-json line spanning the modeled frame
// kinds plus the unknown escape hatch, so the determinism property covers every branch.
func drawStreamLine(rt *rapid.T) []byte {
	kind := rapid.SampledFrom([]string{"assistant_text", "assistant_tool", "user_result", "result", "system", "unknown"}).
		Draw(rt, "frame")
	switch kind {
	case "assistant_text":
		return mustJSON(rt, map[string]any{"type": "assistant", "message": map[string]any{
			"model": "m", "role": "assistant",
			"content": []any{map[string]any{"type": "text", "text": rapid.StringMatching(`[a-z ]{1,20}`).Draw(rt, "t")}},
		}})
	case "assistant_tool":
		return mustJSON(rt, map[string]any{"type": "assistant", "message": map[string]any{
			"model": "m", "role": "assistant",
			"content": []any{map[string]any{"type": "tool_use", "id": "toolu_1", "name": "Write", "input": map[string]any{"x": 1}}},
		}})
	case "user_result":
		return mustJSON(rt, map[string]any{"type": "user", "message": map[string]any{
			"role":    "user",
			"content": []any{map[string]any{"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}},
		}})
	case "result":
		return mustJSON(rt, map[string]any{
			"type": "result", "subtype": "success", "is_error": false,
			"num_turns": 1, "total_cost_usd": 0.01, "result": "done", "stop_reason": "end_turn",
			"usage": map[string]any{"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 1, "cache_creation_input_tokens": 1},
		})
	case "system":
		return mustJSON(rt, map[string]any{"type": "system", "subtype": "init", "session_id": "s1", "model": "m"})
	default:
		return mustJSON(rt, map[string]any{"type": "rate_limit_event", "retry_after": rapid.IntRange(0, 99).Draw(rt, "ra")})
	}
}

// drawSpec generates a Spec with a random grant allowlist and an optional permission
// policy, returning the number of --allowedTools patterns those grants must expand to.
func drawSpec(rt *rapid.T) (spec agentsession.Spec, wantPatterns int) {
	nGrants := rapid.IntRange(0, 4).Draw(rt, "n_grants")
	var grants []agentsession.ToolGrant
	for i := range nGrants {
		nScopes := rapid.IntRange(0, 3).Draw(rt, "n_scopes")
		var scopes []string
		for range nScopes {
			scopes = append(scopes, rapid.StringMatching(`[a-z ]{1,6}\*?`).Draw(rt, "scope"))
		}
		grants = append(grants, agentsession.ToolGrant{
			ID: "g" + strconv.Itoa(i), Tool: rapid.SampledFrom([]string{"Write", "Bash", "Read"}).Draw(rt, "tool"),
			Scopes: scopes,
		})
		if nScopes == 0 {
			wantPatterns++
		} else {
			wantPatterns += nScopes
		}
	}
	spec = agentsession.Spec{Grants: grants}
	if rapid.Bool().Draw(rt, "policy") {
		spec.OnPermission = func(agentsession.PermissionRequest) agentsession.Decision {
			return agentsession.Decision{Allow: false, By: "policy:test"}
		}
	}
	return spec, wantPatterns
}

// mustJSON marshals v to a compact stream-json line, failing the rapid case on error.
func mustJSON(rt *rapid.T, v map[string]any) []byte {
	b, err := json.Marshal(v)
	if err != nil {
		rt.Fatalf("marshal generated frame: %v", err)
	}
	return b
}

// assertNonNegativeTokens asserts every ledger token kind is non-negative (the bounded
// invariant — the normalizer never invents a negative count).
func assertNonNegativeTokens(rt *rapid.T, l *agentsession.TokenLedger) {
	if l.InputTokens < 0 || l.OutputTokens < 0 || l.CacheReadTokens < 0 || l.CacheCreationTokens < 0 {
		rt.Fatalf("ledger produced a negative token count: %+v", l)
	}
	if l.Turns < 0 {
		rt.Fatalf("ledger produced a negative turn count: %d", l.Turns)
	}
}

// sameEventValue compares the load-bearing payload fields of two events of the same kind,
// delegating each payload variant to a focused helper so no single function carries the
// whole tagged-union comparison.
func sameEventValue(a, b *agentsession.Event) bool {
	return bytes.Equal(a.Extension, b.Extension) &&
		sameMessage(a.Message, b.Message) &&
		sameTool(a.Tool, b.Tool) &&
		sameTerminal(a.Terminal, b.Terminal) &&
		sameUsage(a.Usage, b.Usage)
}

// sameMessage compares two MessagePayload pointers (nil-equal, then field-equal).
func sameMessage(a, b *agentsession.MessagePayload) bool {
	if (a == nil) != (b == nil) {
		return false
	}
	return a == nil || (a.Role == b.Role && a.Delta == b.Delta)
}

// sameTool compares two ToolPayload pointers on the fields the normalizer populates.
func sameTool(a, b *agentsession.ToolPayload) bool {
	if (a == nil) != (b == nil) {
		return false
	}
	return a == nil || (a.CallID == b.CallID && a.Name == b.Name &&
		a.ArgsSummary == b.ArgsSummary && a.ResultDigest == b.ResultDigest)
}

// sameTerminal compares two TerminalPayload pointers. TokenLedger embeds a map
// (ToolUsesByName), so it is not == comparable; the scalar accounting the normalizer writes
// is compared instead (it never populates the map).
func sameTerminal(a, b *agentsession.TerminalPayload) bool {
	if (a == nil) != (b == nil) {
		return false
	}
	if a == nil {
		return true
	}
	la, lb := a.Ledger, b.Ledger
	return la.UsageMeter == lb.UsageMeter && la.Turns == lb.Turns &&
		la.ToolUses == lb.ToolUses && la.WallTime == lb.WallTime &&
		a.Reason == b.Reason && a.ResultText == b.ResultText
}

// sameUsage compares two UsageMeter pointers (nil-equal, then value-equal).
func sameUsage(a, b *agentsession.UsageMeter) bool {
	if (a == nil) != (b == nil) {
		return false
	}
	return a == nil || *a == *b
}

// mustHaveFlag fails the case unless flag appears as a bare token in args.
func mustHaveFlag(rt *rapid.T, args []string, flag string) {
	for _, a := range args {
		if a == flag {
			return
		}
	}
	rt.Fatalf("required flag %q missing from args %v", flag, args)
}

// mustHavePair fails the case unless flag is immediately followed by value in args.
func mustHavePair(rt *rapid.T, args []string, flag, value string) {
	for i := 0; i+1 < len(args); i++ {
		if args[i] == flag && args[i+1] == value {
			return
		}
	}
	rt.Fatalf("required pair %q %q missing from args %v", flag, value, args)
}

// pairValue returns the token immediately following flag, or "" if absent.
func pairValue(args []string, flag string) string {
	for i := 0; i+1 < len(args); i++ {
		if args[i] == flag {
			return args[i+1]
		}
	}
	return ""
}

// countAfterFlag returns the number of consecutive non-flag tokens that follow flag (the
// variadic allowlist patterns), 0 if the flag is absent.
func countAfterFlag(args []string, flag string) int {
	for i := range args {
		if args[i] != flag {
			continue
		}
		n := 0
		for j := i + 1; j < len(args); j++ {
			if strings.HasPrefix(args[j], "--") {
				break
			}
			n++
		}
		return n
	}
	return 0
}

// countPrefix counts env entries starting with prefix.
func countPrefix(env []string, prefix string) int {
	n := 0
	for _, e := range env {
		if strings.HasPrefix(e, prefix) {
			n++
		}
	}
	return n
}

// hasPrefix reports whether any env entry starts with prefix.
func hasPrefix(env []string, prefix string) bool { return countPrefix(env, prefix) > 0 }

// hasExact reports whether env contains an exact entry.
func hasExact(env []string, entry string) bool {
	for _, e := range env {
		if e == entry {
			return true
		}
	}
	return false
}
