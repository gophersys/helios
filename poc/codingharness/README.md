# codingharness — WS2 spike

> Status: Spike (donor material) · 2026-06-12 · Home of the 09 §7 item-4 spike: a Go program
> that drives **one** headless Claude Code session end-to-end and captures the full transcript
> plus a token/cost ledger. De-risks the kernel's F4 agent adapter (ADR-0008) before
> `libs/go/codingharness` is contract-drafted. Not a library; not on the `main` path (poc rules,
> ADR-0009 D).

## What it does

1. Creates a fresh temp workspace and seeds a minimal `go.mod` (so the task's `go vet` step has a
   module context).
2. Spawns `claude` in headless print mode with a minimal tool allowlist, streaming stdout.
3. Writes **every** stream event verbatim, line-by-line, to `transcript.jsonl`.
4. Folds the events into a token/cost ledger (input/output/cache-read/cache-creation tokens, cost,
   turns, tool uses, wall time, final result text).
5. Writes `ledger.json`, prints the ledger as one JSON line to stdout, and **exits non-zero if the
   session failed** (no `result` event, `is_error`, or a non-`success` subtype) so a parent
   orchestrator can branch on the exit code alone.

The transcript parser is **forward-compatible**: unknown event types are counted (`unknown_event_types`)
and skipped, never fatal. The real stream already carries a type beyond the documented set
(`rate_limit_event`), so this is load-bearing, not theoretical.

## How to run

```sh
# canonical trivial task, fresh temp workspace + temp output dir:
go run ./cmd/spike

# pin the output dir (where transcript.jsonl + ledger.json land):
go run ./cmd/spike -output ./sample-run

# keep the temp workspace for inspection; override the task:
go run ./cmd/spike -keep -task "Create foo.txt containing bar"
```

`go vet ./...` and `go build ./...` pass. Stdlib only; module is poc-local
(`github.com/gophersys/eden/poc/codingharness`).

### Flags used to drive Claude Code, and why

The session is spawned as:

```
claude -p "<task>" \
  --output-format stream-json \
  --verbose \
  --allowedTools Write Read "Bash(go *)" \
  --permission-mode acceptEdits
```

| Flag | Why |
|---|---|
| `-p` / `--print` | Headless: print and exit, no interactive session. Also skips the workspace-trust dialog. |
| `--output-format stream-json` | Emit one JSON event per line as the loop runs — the transcript stream. (Alternatives: `text`, single-shot `json`.) |
| `--verbose` | **Required** with `stream-json` in print mode; without it the CLI errors out. |
| `--allowedTools Write Read "Bash(go *)"` | The **minimum** the task needs: `Write` to create the file, `Read` to re-read it, and `Bash` scoped to `go *` only. Space-separated list; tool names support argument patterns like `Bash(go *)`. Anything outside this set is denied. |
| `--permission-mode acceptEdits` | Lets file edits proceed without an interactive prompt **while still denying anything outside the allowlist** — narrower than `bypassPermissions`. We deliberately did **not** use `--dangerously-skip-permissions`. |

**Permission/sandbox note (what worked).** `acceptEdits` + a tight `--allowedTools` was sufficient
for fully unattended execution of write+`go vet`: no prompt blocked the run, and the agent could not
reach a tool outside the allowlist. `--dangerously-skip-permissions` was **not** needed and was not
used. If a future task needs to run arbitrary commands, the narrowest working escalation is to widen
the `Bash(...)` pattern, not to drop to bypass mode. The harness also inherits the ambient
environment for auth (it does not inject credentials) — the real adapter must change this.

There is no explicit "restrict file writes to the workspace" flag; the workspace is enforced only by
`command.Dir` (the child's cwd) plus the tool allowlist. A real sandbox boundary is an open question
(below).

## Observed event schema (from the real run)

Output format `stream-json`. **One JSON object per line.** Every object carries `type`, `uuid`, and
`session_id`. The exact line sequence captured in `sample-run/transcript.jsonl` (11 lines):

| Line | `type` | `subtype` | Notes |
|---|---|---|---|
| 0 | `system` | `init` | Session config: `session_id`, `model`, `tools`, `permissionMode`, `cwd`, `mcp_servers`, `slash_commands`, … |
| 1 | `rate_limit_event` | — | **Undocumented extra type.** Carries `rate_limit_info`. Counted as unknown, ignored. |
| 2 | `assistant` | — | `message.content = [thinking]` |
| 3 | `assistant` | — | `message.content = [text]` |
| 4 | `assistant` | — | `message.content = [tool_use]` (Write) |
| 5 | `user` | — | tool result fed back: `tool_use_result` |
| 6 | `assistant` | — | `message.content = [tool_use]` (Bash) |
| 7 | `user` | — | tool result fed back |
| 8 | `assistant` | — | `message.content = [thinking]` |
| 9 | `assistant` | — | `message.content = [text]` |
| 10 | `result` | `success` | **The authoritative ledger.** |

### Where token usage and cost live

- **Per-message usage:** on `assistant` events at `message.usage` —
  `{input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens,
  cache_creation:{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}, service_tier}`.
  The model is at `message.model`.
- **Tool uses:** `assistant` events with a `message.content[]` block of `type: "tool_use"`
  (`name`, `id`). Tool **results** come back on the next `user` event as `tool_use_result`.
- **Aggregate ledger (authoritative):** the single `result` event. It carries:
  - `total_cost_usd` — total session cost (USD).
  - `usage` — rolled-up `{input_tokens, output_tokens, cache_read_input_tokens,
    cache_creation_input_tokens, server_tool_use:{web_search_requests, web_fetch_requests},
    iterations[]}`.
  - `modelUsage` — **per-model** breakdown `{ "<model-id>": {inputTokens, outputTokens,
    cacheReadInputTokens, cacheCreationInputTokens, costUSD, contextWindow, maxOutputTokens} }`.
    Useful because the run touched **two** models (a small one for a sub-task plus the main model) —
    a cost-routing signal the kernel will care about.
  - `num_turns`, `duration_ms` (session wall time as the CLI measured it), `duration_api_ms`,
    `is_error`, `stop_reason` (`end_turn`), `permission_denials` (empty here), and `result` (the
    final assistant text).

This spike reads the aggregate `usage` and `total_cost_usd` from the `result` event for the headline
ledger, and derives `tool_uses` / `tool_use_by_name` by walking `assistant` events. `modelUsage` and
per-message usage are present in the captured transcript for anyone who wants finer granularity.

### Real-run ledger (the numbers)

```json
{"succeeded":true,"stop_reason":"end_turn","turns":3,"tool_uses":2,"event_count":11,
 "unknown_event_types":1,"input_tokens":3944,"output_tokens":394,"cache_read_tokens":56397,
 "cache_creation_tokens":5689,"total_cost_usd":0.229861,"wall_ms":16733,"session_reported_ms":16342,
 "tool_use_by_name":{"Bash":1,"Write":1}}
```

Full artifacts: [`sample-run/transcript.jsonl`](sample-run/transcript.jsonl) and
[`sample-run/ledger.json`](sample-run/ledger.json). Verified out-of-band: `hello.go` appeared in the
workspace and printed the expected string; an independent `go vet .` in the workspace passed.

### Gotchas

- **`--verbose` is mandatory** with `stream-json` in print mode — omit it and the CLI refuses.
- **`rate_limit_event` is not in the obvious documented set.** Any parser that hard-switches on a
  fixed type enum will choke. Decode loosely; count unknowns; never fail on them.
- **Two cache token axes.** Cache *creation* (write) and cache *read* are separate and both large
  relative to raw input/output — at 56k cache-read vs 3.9k input here, **cache economics dominate**.
  A cost model that ignores cache tokens is wrong.
- **Multiple models per session.** `modelUsage` shows the run silently used a cheaper model for a
  sub-step. Per-model accounting matters for the routing economics (04 §6).
- **Cost is non-trivial even for a trivial task** ($0.23) — almost entirely system-prompt/CLAUDE.md
  context priming, not the task. The CLI loads ambient context (CLAUDE.md, skills) unless told not
  to; for clean-room runs consider `--bare` / `--safe-mode` (untested here).
- **`num_turns` (3) ≠ tool uses (2) ≠ assistant messages (6).** A "turn" is the CLI's own count;
  don't conflate the three.
- **Lines can be large** (a `tool_use_result` may carry a whole file). The scanner buffer is raised
  to 16 MiB; the default 64 KiB would truncate on real workloads.
- Exit code is `0` only when a `result` event with `subtype: success` and `is_error:false` is seen
  **and** the CLI process itself exited `0`; otherwise the spike exits non-zero.

## Layout

```
codingharness/
├── go.mod                       # module github.com/gophersys/eden/poc/codingharness (go 1.26)
├── cmd/spike/main.go            # entrypoint: workspace + invocation + exit policy
├── internal/session/session.go  # spawn claude, stream stdout → transcript, fold ledger
├── internal/ledger/ledger.go    # forward-compatible event model + the fold
├── README.md
└── sample-run/                  # the real run's transcript.jsonl + ledger.json
```

## Open questions for the real codingharness

- **Permission / sandbox model.** `acceptEdits` + `--allowedTools` was enough for unattended runs,
  but nothing confined writes to the workspace beyond cwd. The real adapter needs a true filesystem
  + network boundary (workspace pod, seccomp/landlock, or `--add-dir` scoping) so a misbehaving
  agent cannot touch the host — and a policy for when, if ever, `bypassPermissions` is acceptable.
- **Tool allowlisting as contract.** The F4 contract's `tools` grant must compile to
  `--allowedTools`/`--disallowedTools` patterns (`Bash(go *)`-style) deterministically. Who owns the
  mapping from a phase's declared capabilities to the concrete allowlist, and how is a denied tool
  surfaced (it lands in `permission_denials`, not an error)?
- **Session resume / multi-turn.** This spike is single-shot. The real loop needs steering across
  turns: `--resume <session-id>` / `--continue`, `--input-format stream-json` for realtime input,
  and a decision on `--no-session-persistence` vs. keeping resumable state (and where it lives).
- **Structured output enforcement.** `--json-schema` + `--output-format json` can force the final
  result into a schema (e.g. a `SourceChange` artifact). Does the kernel rely on this, or parse
  free-form `result` text? Schema-forcing is cleaner but constrains the prompt.
- **Cost ceilings / budgets.** `--max-budget-usd` exists and maps cleanly onto `TokenBudget`
  (02 §2). The spike wires the flag but did not exercise it — need to confirm the abort behavior,
  the partial-ledger emitted on a budget kill, and how it reconciles with the run-level budget
  escalation policy (promote-to-stronger-model).
- **Multi-model cost attribution.** `modelUsage` proves a single session spans models. The ledger
  must carry per-model token/cost lines (not just the aggregate) for the routing-economics
  comparison ADR-0008 promises "measured, not argued."
- **Cache-token cost modeling.** Cache read/write dominate token volume. The ledger and any cost
  ceiling must price all four token axes (input/output/cache-read/cache-creation) per the provider's
  cache pricing, or budgets will be wildly wrong.
- **Clean-room context.** The CLI auto-loaded ambient CLAUDE.md/skills, inflating cost and polluting
  the run. The real harness should run hermetically (`--bare`/`--safe-mode`, explicit
  `--system-prompt`, pinned `--model`) so runs are reproducible and the agent only sees the Spec's
  context — relevant to the evidence information-barrier (02 §2).
- **Failure taxonomy.** `result.subtype` carries failure classes (`error_max_turns`,
  `error_during_execution`, …) that this spike collapses to a boolean. The adapter must map these to
  the `errors` pattern's typed `Kind`s so gates and retries can branch.
- **Schema drift / version pinning.** The event schema is a moving target (`rate_limit_event` is
  evidence). The adapter needs a pinned-and-tested CLI version, a conformance suite over the event
  stream (05 §6), and a forward-compatible decoder (this spike's loose-decode approach) as the
  baseline.
- **Auth & credential injection.** The spike inherited ambient auth from the environment. The real
  adapter must inject short-lived scoped tokens via the `secrets` port (05 §4) and never let
  credentials reach agent context or the transcript.
- **Transcript redaction & storage.** Transcripts are first-class objects (02 §1) but may capture
  secrets in tool results. The adapter owes redaction-on-capture and the observability plane-(b)
  storage path before this stream is persisted.
