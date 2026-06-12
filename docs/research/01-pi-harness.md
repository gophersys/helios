# Pi Harness — Integration Architecture

> Research date: June 5, 2026

## Overview

Pi (pi-mono) is a minimal, aggressively extensible terminal coding harness. DeepSeek officially documents it as a first-class integration target.

## How Pi Works

### Extension System

Pi is extended via TypeScript modules. The core primitives:
- **Extensions** — TypeScript modules that register tools, commands, event handlers, UI components
- **Skills** — Markdown-based agent skills following the [Agent Skills standard](https://agentskills.io)
- **Prompt Templates** — Reusable Markdown prompts with variable expansion
- **Themes** — Hot-reloaded terminal themes

### Key Extension API

| Capability | API |
|------------|-----|
| Custom tools | `pi.registerTool({ name, parameters, execute })` |
| Commands | `pi.registerCommand("name", { handler })` |
| Event interception | `pi.on("tool_call", handler)` — can block/modify |
| User interaction | `ctx.ui.confirm(), ctx.ui.select(), ctx.ui.notify()` |
| Session persistence | `pi.appendEntry(customType, data)` |
| Custom UI | `ctx.ui.custom()` for full TUI components |
| Inject messages | `pi.sendMessage(), pi.sendUserMessage()` |
| Provider registration | `pi.registerProvider()` |

### Event Lifecycle

```
session_start → resources_discover → [user prompt] →
  before_agent_start → agent_start →
    turn_start → context → tool_call → tool_result → turn_end
  → agent_end
```

Key intercept points:
- `tool_call` — block or mutate tool arguments before execution
- `tool_result` — modify tool output before LLM sees it
- `before_agent_start` — inject messages or modify system prompt
- `context` — reshape message history before each LLM call

### Extension Locations

| Location | Scope |
|----------|-------|
| `~/.pi/agent/extensions/*.ts` | Global |
| `~/.pi/agent/extensions/*/index.ts` | Global (subdirectory) |
| `.pi/extensions/*.ts` | Project-local |
| `.pi/extensions/*/index.ts` | Project-local |

Packages with `package.json` and `node_modules` supported for npm dependencies (e.g., cheerio).

## DeepSeek + Pi Integration

### Provider Configuration

Add to `~/.pi/agent/models.json`:

```json
{
  "providers": {
    "deepseek": {
      "baseUrl": "https://api.deepseek.com",
      "api": "openai-completions",
      "apiKey": "$DEEPSEEK_API_KEY",
      "models": [
        {
          "id": "deepseek-v4-pro",
          "name": "DeepSeek V4 Pro",
          "contextWindow": 1000000,
          "maxTokens": 384000,
          "input": ["text"],
          "reasoning": true,
          "cost": { "input": 0.435, "output": 0.87, "cacheRead": 0.003625, "cacheWrite": 0 },
          "compat": {
            "requiresReasoningContentOnAssistantMessages": true,
            "thinkingFormat": "deepseek",
            "reasoningEffortMap": {
              "minimal": "high", "low": "high", "medium": "high",
              "high": "high", "xhigh": "max"
            }
          }
        },
        {
          "id": "deepseek-v4-flash",
          "name": "DeepSeek V4 Flash",
          "contextWindow": 1000000,
          "maxTokens": 384000,
          "input": ["text"],
          "reasoning": true,
          "cost": { "input": 0.14, "output": 0.28, "cacheRead": 0.028, "cacheWrite": 0 },
          "compat": {
            "requiresReasoningContentOnAssistantMessages": true,
            "thinkingFormat": "deepseek",
            "reasoningEffortMap": {
              "minimal": "high", "low": "high", "medium": "high",
              "high": "high", "xhigh": "max"
            }
          }
        }
      ]
    }
  }
}
```

### DeepSeek-Specific Compat

DeepSeek has 16 documented behaviors not handled by stock OpenAI clients:
- **Mandatory `reasoning_content` round-trip** in multi-turn loops (HTTP 400 if omitted)
- **Default-enabled thinking mode** that burns 30–300 reasoning tokens on trivial prompts
- **Interleaved streaming** of thinking + tool_calls
- pi handles this via `requiresReasoningContentOnAssistantMessages: true` and `thinkingFormat: "deepseek"`

### Official Ecosystem Status

DeepSeek's **awesome-deepseek-agent** repo lists pi alongside Claude Code, Cline, Codex, OpenCode, and ~20 others. pi is a Tier 1 integration target.

Oh My Pi is a pi fork with additional DeepSeek-specific tooling (model roles, MCP, plugins, agent workflows).

## DeepSeek Harness (Internal Effort)

DeepSeek is building their own coding agent ("Harness") — not pi, but architecturally similar:

- **Status**: Hiring stage, 6–12 months from product launch
- **Interface**: Desktop agent (GUI + TUI) planned
- **Philosophy**: "Model + Harness = Agent" — model and infrastructure co-evolve
- **Scope**: Broader than coding — generalist agent harness
- **Memory**: Long-term vector memory + session replay planned
- **Stack**: Rust + Python backend, TypeScript + Tauri frontend, LanceDB for vectors

### deepseek-tui (Open-Source Blueprint)

A Rust terminal agent (2.3k+ stars, MIT) that implements the Harness vision:
- Agent loop with streaming + tool orchestration
- MCP client (full stdio transport, dynamic tool discovery)
- RLM subagent fan-out: V4-Pro orchestrator → 1–16 parallel V4-Flash children
- SQLite event timeline, replayable sessions
- LSP integration (post-edit diagnostics injected into context)
- 3 modes: Plan (read-only), Agent (approval), YOLO (auto)

## Subagent Architecture (RLM — Recursive Language Model)

From the deepseek-tui pattern, six subagent types:

| Role | Tools | Purpose |
|------|-------|---------|
| Planner | Read-only + grep + ls | Task decomposition, contract definition |
| Explorer | grep, file_search, ls, read | Codebase mapping, dependency tracing |
| Implementer | write, edit, bash | Code writing against spec contracts |
| Reviewer | read, diff | Quality grading, convention checking |
| Verifier | bash (test runner), read | Test suite execution, gate keeping |
| General | Full access | Multi-step autonomous tasks |

Key mechanisms:
- **File leases**: Implementers hold exclusive locks, released on completion
- **Whale nicknames**: Friendly identities for parallel agents in TUI
- **Mailbox system**: Monotonic sequence numbers for consistent event streams
- **Cancellation tokens**: Parent can cancel entire child trees
- **MAX_SUBAGENTS limit**: Configurable concurrency cap

## Agentic SDLC Framework (ASDLC)

Three-layer operating model:
1. **Spec Layer** — Human defines intent + constraints (the "Objective Packet")
2. **Harness Layer** — Orchestration, routing, context delivery
3. **Loop Layer** — Agents execute in continuous feedback loops

Factory stations:
- Planning → Spec-Definition → Implementation → Review → Verification

Key principles:
- **Contracts over vibes** — Typed interfaces between stations
- **Schema-first** — Agents fulfill contracts, don't guess
- **L3 Conditional Autonomy** — Agent is pilot, human is instructor-in-cockpit
- **Provenance is value** — Audit trail of who steered what and how it was verified

## Sources

- [DeepSeek API Docs: Pi Integration](https://api-docs.deepseek.com/quick_start/agent_integrations/pi_mono)
- [GitHub: awesome-deepseek-agent](https://github.com/deepseek-ai/awesome-deepseek-agent)
- [DeepSeek Harness Analysis](https://dlcmh.github.io/deepseek-harness)
- [DeepSeek Code Guide](https://deepseek-code.com/)
- [AI Market Watch: DeepSeek Harness Team](https://www.ai-market-watch.com/news/deepseekharnessai-p8g8s6)
- [DeepSeek-TUI Subagents & RLM](https://deepwiki.com/Hmbown/DeepSeek-TUI/5.4-sub-agents-and-rlm-(recursive-language-model))
- [ASDLC Framework](https://asdlc.io/concepts/agentic-sdlc/)
- [Pi Docs: Extensions](https://pi.dev/docs/extensions) (via pi package docs)
