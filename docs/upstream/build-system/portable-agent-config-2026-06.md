# Portable Agent Configuration Across Coding Harnesses — June 2026

A migratable agent-config design that composes three orthogonal layers — **routing, modes, subagents** — and emits native configs for Claude Code, Aider, Cline, Roo Code, Kilo Code, OpenCode, Crush, Continue, Goose, and Codex CLI.

Compiled 2026-06-01 from primary docs and adversarial verification.

---

## 1. Mental model: three layers, one config

Every harness handles model assignment with some combination of three primitives. The portable schema treats them as orthogonal:

| Layer | What it does | Triggered by | Lifetime |
|---|---|---|---|
| **Routing** | Pick a model based on *request shape* | Token count, prompt content, request type | Per-call |
| **Modes** | Pick a model + system prompt + tool allow-list based on *task phase* | User toggles mode (Plan/Act/Architect/Code/Debug/Ask) | Per-turn until mode change |
| **Subagents** | Spawn an isolated sub-process with its own model, context, and tools | Primary agent calls Task/`new_task`/Agent tool | Per-subtask, then merge-back |

Real workflows compose all three. A primary `architect` mode (Opus) drafts a plan; routing sends `longContext` calls to Gemini and `background` reads to a cheap local model; the architect spawns a `test-writer` subagent (DeepSeek) which itself routes a few `longContext` calls and returns one summary.

The schema below maps each of these to a single `agents.yaml`. The "compiler" section shows where each schema field lives in each harness's native config.

---

## 2. Canonical schema — `agents.yaml`

```yaml
# agents.yaml — portable agent configuration
version: 1
metadata:
  project: helios
  description: Portable agent config; compiled to each harness's native format

# --- 1. Provider catalog ---------------------------------------------------
# Provider definitions. Every model reference below uses these IDs.
# Keys are NEVER inline; only env-var references.
providers:
  anthropic:
    type: anthropic                       # anthropic | openai | openai-compat | bedrock | vertex | gemini | ollama
    api_key_env: ANTHROPIC_API_KEY
  openai:
    type: openai
    api_key_env: OPENAI_API_KEY
  zai:
    type: openai-compat
    base_url: https://api.z.ai/api/coding/paas/v4
    api_key_env: ZAI_API_KEY
  deepseek:
    type: openai-compat
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
  openrouter:
    type: openai-compat
    base_url: https://openrouter.ai/api/v1
    api_key_env: OPENROUTER_API_KEY
  gemini:
    type: gemini
    api_key_env: GEMINI_API_KEY
  local-vllm:
    type: openai-compat
    base_url: http://gpu-box:8000/v1
    api_key_env: LOCAL_API_KEY            # set to "EMPTY" for unauthenticated vLLM

# --- 2. Model aliases (semantic role -> provider+model) ---------------------
# Decouple "what we call this" from "which model serves it today".
# When models get cheaper/better, edit one line here, not every harness.
models:
  thinker:    { provider: anthropic,  id: claude-opus-4-7,         capabilities: [reasoning, tool_use] }
  architect:  { provider: anthropic,  id: claude-sonnet-4-6,       capabilities: [tool_use, cache] }
  coder:      { provider: zai,        id: glm-4.6,                 capabilities: [tool_use] }
  workhorse:  { provider: deepseek,   id: deepseek-chat,           capabilities: [tool_use] }
  longctx:    { provider: gemini,     id: gemini-2.5-pro,          capabilities: [tool_use, longctx_2m] }
  web:        { provider: openrouter, id: z-ai/glm-4.6:online,     capabilities: [web_search] }
  background: { provider: deepseek,   id: deepseek-chat,           capabilities: [] }
  fast:       { provider: anthropic,  id: claude-haiku-4-5,        capabilities: [] }
  local:      { provider: local-vllm, id: Qwen/Qwen3-Coder-30B-A3B-Instruct }

# --- 3. Routing (layer 1) ---------------------------------------------------
# Maps request types to a model alias. Honored natively by claude-code-router.
# Other harnesses emulate via the small/large/auxiliary slots they expose.
routing:
  default:               coder
  background:            background          # auto-compaction, title gen, summaries
  think:                 thinker             # Plan-mode / extended-thinking calls
  longContext:           longctx             # auto-route above threshold
  longContextThreshold:  60000               # tokens
  webSearch:             web

# --- 4. Modes (layer 2) -----------------------------------------------------
# Each mode = persona + model + tool allow-list + per-mode rules.
# Roo/Kilo/Continue/Aider-architect implement these natively.
modes:
  architect:
    model: thinker
    description: System design, multi-file refactor planning
    tools: [read, web, mcp:context7]
    rules_dir: rules/architect/
  code:
    model: coder
    description: Default implementation
    tools: [read, edit, command, mcp:github]
    rules_dir: rules/code/
  debug:
    model: workhorse
    description: Bug triage and fix
    tools: [read, edit, command]
    edit_path_glob:                          # path-scoped edit allow
      - "**/*.test.{ts,js,py}"
      - "**/*.spec.{ts,js,py}"
  ask:
    model: fast
    description: Q&A, no edits
    tools: [read, web]

# --- 5. Subagents (layer 3) -------------------------------------------------
# Each subagent has isolated context, optional own model, scoped tools/MCP.
# Honored by Claude Code (with model-inherit bug — see §workarounds),
# OpenCode, Goose (as sub-recipes), Roo (via Boomerang/new_task).
subagents:
  test-writer:
    description: Generate Jest/Pytest suites for a target file
    model: workhorse                         # cheap; instruction-following task
    isolation: true                          # do not pollute parent context
    tools: [read, edit, command]
    mcp_servers: []                          # none — minimal attack surface
    prompt_file: prompts/test-writer.md
    permissions:
      edit_path_glob: ["**/*.test.{ts,js,py}", "**/__tests__/**"]
      bash_allow:    ["npm test*", "pytest*"]
  code-reviewer:
    description: Review changes for security, style, regressions
    model: thinker                           # quality matters more than speed
    isolation: true
    tools: [read, grep, glob]
    mcp_servers: [github]
    prompt_file: prompts/code-reviewer.md
    permissions:
      edit: deny
  explore:
    description: Read-only repo exploration / context gathering
    model: workhorse
    isolation: true
    tools: [read, grep, glob, web]
    permissions:
      edit: deny
      bash: deny

# --- 6. MCP servers (referenced from modes/subagents) -----------------------
mcp_servers:
  github:
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env: { GITHUB_PERSONAL_ACCESS_TOKEN: "${GH_PAT}" }
  context7:
    transport: http
    url: https://mcp.context7.com/mcp
    headers: { Authorization: "Bearer ${CONTEXT7_TOKEN}" }
  playwright:
    transport: stdio
    command: npx
    args: ["-y", "@playwright/mcp@latest"]

# --- 7. Rules (cross-harness AGENTS.md compatibility) -----------------------
rules:
  global: AGENTS.md                          # always-on project rules
  per_mode_root: rules/                      # rules/{mode}/*.md
```

The 7-section schema separates concerns cleanly. The provider catalog and model aliases mean **changing "what serves the `coder` role" is a one-line edit** — every harness's compiled config gets regenerated to point at the new model.

---

## 3. Native config per harness (same 6 roles, side-by-side)

Each section below implements the same logical config — `thinker=Opus`, `architect=Sonnet`, `coder=GLM-4.6`, `workhorse=DeepSeek`, `longctx=Gemini`, `background=DeepSeek` — in the harness's native syntax. File paths cited.

### 3.1 Claude Code (native + claude-code-router)

**Native settings** — `.claude/settings.json` (project) or `~/.claude/settings.json` (user):

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "model": "claude-sonnet-4-6",
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456",
    "ANTHROPIC_AUTH_TOKEN": "sk-ccr-local",
    "CLAUDE_CODE_SUBAGENT_MODEL": "claude-sonnet-4-6"
  },
  "permissions": {
    "allow": ["Bash(npm test *)", "Bash(pytest *)"],
    "deny":  ["Bash(curl *)", "Read(./.env)", "Read(./secrets/**)"],
    "ask":   ["Bash(git push *)"]
  },
  "enabledMcpjsonServers": ["github", "context7"]
}
```

**Subagents** — one file per subagent in `.claude/agents/`:

`.claude/agents/test-writer.md`:
```markdown
---
name: test-writer
description: Generate Jest/Pytest suites. Use proactively after new code changes.
tools: Read, Edit, Bash(npm test *), Bash(pytest *)
model: sonnet                              # ⚠️ ignored due to bug #44385; use CCR injection
permissionMode: acceptEdits
maxTurns: 20
mcpServers: []
---
You are a test specialist. Read the target file, generate a complete test suite
covering happy path, edge cases, and error branches. Run the tests and iterate
until they pass.
```

`.claude/agents/code-reviewer.md`:
```markdown
---
name: code-reviewer
description: Expert code review specialist. Use proactively after code changes.
tools: Read, Grep, Glob
disallowedTools: Write, Edit, Bash
model: opus                                # ⚠️ same bug
mcpServers:
  - github
---
You are a senior code reviewer. Focus on correctness, security, and style.
```

**Routing via claude-code-router** — `~/.claude-code-router/config.json`:

```json
{
  "APIKEY": "sk-ccr-local",
  "HOST": "127.0.0.1",
  "Providers": [
    {
      "name": "anthropic",
      "api_base_url": "https://api.anthropic.com/v1/messages",
      "api_key": "$ANTHROPIC_API_KEY",
      "models": ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"],
      "transformer": { "use": ["Anthropic"] }
    },
    {
      "name": "zai",
      "api_base_url": "https://api.z.ai/api/coding/paas/v4/chat/completions",
      "api_key": "$ZAI_API_KEY",
      "models": ["glm-4.6"]
    },
    {
      "name": "deepseek",
      "api_base_url": "https://api.deepseek.com/v1/chat/completions",
      "api_key": "$DEEPSEEK_API_KEY",
      "models": ["deepseek-chat"],
      "transformer": { "use": ["deepseek"] }
    },
    {
      "name": "openrouter",
      "api_base_url": "https://openrouter.ai/api/v1/chat/completions",
      "api_key": "$OPENROUTER_API_KEY",
      "models": ["google/gemini-2.5-pro-preview"],
      "transformer": { "use": ["openrouter"] }
    }
  ],
  "Router": {
    "default":              "zai,glm-4.6",
    "background":           "deepseek,deepseek-chat",
    "think":                "anthropic,claude-opus-4-7",
    "longContext":          "openrouter,google/gemini-2.5-pro-preview",
    "longContextThreshold": 60000,
    "webSearch":            "openrouter,google/gemini-2.5-pro-preview:online"
  }
}
```

**Workaround for the subagent-model bug:** prepend `<CCR-SUBAGENT-MODEL>provider,model</CCR-SUBAGENT-MODEL>` to the subagent's prompt body. CCR strips the tag and reroutes:

```markdown
---
name: test-writer
...
---
<CCR-SUBAGENT-MODEL>deepseek,deepseek-chat</CCR-SUBAGENT-MODEL>
You are a test specialist...
```

### 3.2 Aider

`~/.aider.conf.yml`:
```yaml
# Architect mode = planner-executor split
architect: true
model: anthropic/claude-opus-4-7            # thinker
editor-model: openrouter/zai/glm-4.6        # coder
editor-edit-format: editor-diff
weak-model: deepseek/deepseek-chat          # background (commits + summaries)
auto-accept-architect: true
cache-prompts: true
cache-keepalive-pings: 6
map-tokens: 4096
map-refresh: auto
alias:
  - "thinker:anthropic/claude-opus-4-7"
  - "coder:openrouter/zai/glm-4.6"
  - "longctx:openrouter/google/gemini-2.5-pro-preview"
```

`.env` (chmod 600, gitignored):
```
ANTHROPIC_API_KEY=sk-ant-...
ZAI_API_KEY=...
DEEPSEEK_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
```

Aider has no modes beyond `code/architect/ask/help`, no subagents, no MCP. The `--alias` mechanism is the closest analog to portable model names.

### 3.3 Cline

**No file config for model bindings** — Cline stores per-mode model selection in the extension's global state via UI toggle. The only file-based config is `.clinerules/`:

`.clinerules/01-core.md`:
```markdown
# Project rules — apply to Plan and Act modes
- Always run `npm test` after edits
- Never commit to main directly
- Use functional components with hooks
```

`.clinerules/02-typescript.md`:
```markdown
---
paths:
  - "src/**/*.ts"
  - "src/**/*.tsx"
---
# TypeScript-specific rules
- Prefer interface over type for object shapes
- Use `as const` for literal unions
```

**MCP** — `cline_mcp_settings.json`:
```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "${GH_PAT}" },
      "disabled": false,
      "autoApprove": ["search_repositories", "get_file_contents"]
    }
  }
}
```

For per-mode models, set in the Settings UI: Plan = Opus 4.7, Act = GLM-4.6. There is no way to express this declaratively in a checked-in file — known gap.

### 3.4 Roo Code

`.roomodes` (workspace) or `custom_modes.yaml` (global):

```yaml
customModes:
  - slug: architect
    name: Architect
    roleDefinition: You are Roo, a software architect focused on system design.
    whenToUse: Use when planning multi-file changes or new features.
    groups: [read, browser]
    apiConfiguration: opus-profile             # → API profile in settings
    customInstructions: |
      Decompose every change into atomic steps. Always validate against existing patterns.

  - slug: code
    name: Code
    roleDefinition: You are Roo, an implementation specialist.
    groups:
      - read
      - edit
      - command
      - - mcp
        - servers: [github]                    # only github MCP visible in Code mode
    apiConfiguration: glm-profile

  - slug: debug
    name: Debug
    roleDefinition: You are Roo, a debugging specialist.
    groups:
      - read
      - - edit
        - fileRegex: \.(test|spec)\.(ts|js|py)$
          description: Test files only
      - command
    apiConfiguration: deepseek-profile

  - slug: ask
    name: Ask
    roleDefinition: You are Roo, an explainer.
    groups: [read, mcp]
    apiConfiguration: haiku-profile
```

Per-mode rules: `.roo/rules-architect/`, `.roo/rules-code/`, etc.

API profiles are configured in the UI (provider + key + model + temperature) and named for cross-reference. Subagent equivalent = Boomerang: orchestrator calls `new_task` with `mode: "code"` and a `message`; subtask inherits parent's profile, but the mode-linked profile takes precedence at spawn.

### 3.5 Kilo Code

`kilo.jsonc` at project root (or `~/.config/kilo/kilo.jsonc`):

```jsonc
{
  "agent": {
    "plan": {
      "model": "anthropic/claude-opus-4-7",
      "temperature": 0.4,
      "permission": {
        "read": "allow",
        "edit": "deny",
        "bash": "deny",
        "webfetch": "allow",
        "github_*": "allow"                    // MCP tool allow per agent
      }
    },
    "code": {
      "model": "zhipu/glm-4.6",
      "temperature": 0.2,
      "permission": {
        "read": "allow",
        "edit": "allow",
        "bash": "ask",
        "github_create_pull_request": "ask",
        "github_*": "allow"
      }
    },
    "debug": {
      "model": "deepseek/deepseek-r1",
      "temperature": 0.1,
      "permission": {
        "read": "allow",
        "edit": {
          "**/*.test.{ts,js,py}": "allow",
          "**/*": "ask"
        },
        "bash": "allow"
      }
    },
    "ask": {
      "model": "anthropic/claude-haiku-4-5",
      "permission": {
        "read": "allow",
        "edit": "deny",
        "bash": "deny",
        "websearch": "allow"
      }
    }
  }
}
```

Subagents as `.kilo/agents/test-writer.md` (same format as OpenCode):

```markdown
---
description: Generate test suites for a target file
mode: subagent
model: deepseek/deepseek-chat
temperature: 0.2
permission:
  read: allow
  edit:
    "**/*.test.{ts,js,py}": allow
    "**/*": deny
  bash:
    "npm test*": allow
    "*": deny
---
You are a test specialist...
```

Kilo's MCP per-agent scoping uses the `{server}_{tool}` permission key — verified per its docs.

### 3.6 OpenCode

`opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "zhipu/glm-4.6",
  "small_model": "deepseek/deepseek-chat",
  "provider": {
    "anthropic": { "options": { "apiKey": "{env:ANTHROPIC_API_KEY}" } },
    "zhipu":     { "options": { "apiKey": "{env:ZAI_API_KEY}" } },
    "deepseek":  { "options": { "apiKey": "{env:DEEPSEEK_API_KEY}" } },
    "google":    { "options": { "apiKey": "{env:GEMINI_API_KEY}" } }
  },
  "agent": {
    "plan": {
      "mode": "primary",
      "model": "anthropic/claude-opus-4-7",
      "permission": { "edit": "deny", "bash": "deny", "webfetch": "allow" }
    },
    "build": {
      "mode": "primary",
      "model": "zhipu/glm-4.6",
      "permission": { "edit": "allow", "bash": { "*": "ask", "npm test*": "allow" } }
    },
    "test-writer": {
      "description": "Generate Jest/Pytest test suites",
      "mode": "subagent",
      "model": "deepseek/deepseek-chat",
      "prompt": "{file:./prompts/test-writer.md}",
      "permission": {
        "edit": { "**/*.test.{ts,js,py}": "allow", "**/*": "deny" },
        "bash": { "npm test*": "allow", "pytest*": "allow", "*": "deny" }
      }
    },
    "code-reviewer": {
      "description": "Security/style review",
      "mode": "subagent",
      "model": "anthropic/claude-opus-4-7",
      "prompt": "{file:./prompts/code-reviewer.md}",
      "permission": { "edit": "deny", "bash": "deny", "github_*": "allow" }
    }
  },
  "mcp": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "{env:GH_PAT}" },
      "enabled": true
    }
  }
}
```

OpenCode has the cleanest match to the canonical schema. Caveats: built-in subagents (`general`, `explore`) ignore agent.model override (#21952); user-defined subagents work as documented.

### 3.7 Crush

`crush.json`:

```json
{
  "$schema": "https://charm.land/crush.json",
  "models": {
    "large": { "model": "glm-4.6", "provider": "zai" },
    "small": { "model": "deepseek-chat", "provider": "deepseek" }
  },
  "providers": {
    "zai": {
      "type": "openai-compat",
      "base_url": "https://api.z.ai/api/coding/paas/v4",
      "api_key": "$ZAI_API_KEY",
      "models": [{ "id": "glm-4.6", "name": "GLM 4.6", "context_window": 200000, "default_max_tokens": 32000 }]
    },
    "deepseek": {
      "type": "openai-compat",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "$DEEPSEEK_API_KEY",
      "models": [{ "id": "deepseek-chat", "context_window": 64000, "default_max_tokens": 5000 }]
    },
    "anthropic": {
      "type": "anthropic",
      "api_key": "$ANTHROPIC_API_KEY",
      "models": [{ "id": "claude-opus-4-7", "context_window": 1000000, "default_max_tokens": 50000, "can_reason": true }]
    }
  },
  "mcp": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": { "Authorization": "Bearer $GH_PAT" }
    }
  }
}
```

**Crush is the most-limited target.** Two model slots only: `large` (used by coder/task) and `small` (titles/summaries). No user-defined subagents (issues #431, #1807 — both verified open 2026-06-01). No per-mode bindings. The compiler emits warnings: `thinker`, `architect`, `debug`, `longctx`, `web` cannot be expressed; mid-session `/model` switch is the only escape. ⚠️ **Note:** the hosted `$schema: https://charm.land/crush.json` lags the in-repo `schema.json` (issue #1252) — validate against the repo schema, not the hosted URL, or valid configs may be rejected.

### 3.8 Continue.dev

`~/.continue/config.yaml`:

```yaml
name: helios-config
version: 1.0.0
schema: v1
models:
  - name: Planner (Opus 4.7)
    provider: anthropic
    model: claude-opus-4-7
    apiKey: ${{ secrets.ANTHROPIC_API_KEY }}
    roles: [chat, edit, apply]
    capabilities: [tool_use]
    chatOptions:
      basePlanSystemMessage: "You are the planner. Decompose every change."
      baseAgentSystemMessage: "You are the autonomous executor."
  - name: Coder (GLM-4.6)
    provider: openai
    apiBase: https://api.z.ai/api/coding/paas/v4
    model: glm-4.6
    apiKey: ${{ secrets.ZAI_API_KEY }}
    roles: [chat, edit, apply]
    capabilities: [tool_use]
  - name: Autocomplete (DeepSeek)
    provider: deepseek
    model: deepseek-coder
    apiKey: ${{ secrets.DEEPSEEK_API_KEY }}
    roles: [autocomplete, summarize]
rules:
  - uses: myorg/typescript-rules
  - Always prefer functional patterns
prompts:
  - name: test-writer
    description: Write Jest unit tests for the selected function
    prompt: |
      Write a complete Jest test suite for the selected function.
      Cover happy path, edge cases, and error branches.
mcpServers:
  - name: github
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: ${{ secrets.GH_PAT }}
```

Continue uses role-based modeling (`chat`/`edit`/`apply`/`autocomplete`/`embed`/`rerank`), not modes-as-personas. Plan/Agent mode reuses the `chat` model with different system prompts via `chatOptions.*SystemMessage`. Subagent equivalent = slash-command `prompts` (no isolated context, same model).

### 3.9 Goose

`~/.config/goose/config.yaml`:

```yaml
GOOSE_PROVIDER: "zai"
GOOSE_MODEL: "glm-4.6"
GOOSE_PLANNER_PROVIDER: "anthropic"
GOOSE_PLANNER_MODEL: "claude-opus-4-7"
GOOSE_MODE: "smart_approve"
GOOSE_AUTO_COMPACT_THRESHOLD: 0.8
slash_commands:
  - command: "test-writer"
    recipe_path: "/Users/me/.local/share/goose/recipes/test-writer.yaml"
extensions:
  developer:
    bundled: true
    enabled: true
    name: developer
    timeout: 300
    type: builtin
  github:
    type: stdio
    enabled: true
    cmd: github-mcp-server
    args: []
    env_keys: [GITHUB_PERSONAL_ACCESS_TOKEN]
    timeout: 60
```

Subagent equivalent = sub-recipe (`recipes/test-writer.yaml`) with its own `settings.goose_provider` + `settings.goose_model`:

```yaml
version: "1.0.0"
title: "Test Writer"
description: "Generate Jest tests for a target file"
parameters:
  - key: target_file
    input_type: string
    requirement: required
instructions: |
  You are a unit-test generator. Read {{ target_file }} and emit a Jest suite.
prompt: "Write tests for {{ target_file }}"
settings:
  goose_provider: "deepseek"
  goose_model: "deepseek-chat"
  temperature: 0.2
extensions:
  - type: builtin
    name: developer
    timeout: 300
    bundled: true
retry:
  max_retries: 2
  checks:
    - type: shell
      command: "npm test"
```

Goose subagents (natural-language spawned) inherit parent's model — only sub-recipes get per-task model override.

### 3.10 Codex CLI

`~/.codex/config.toml`:

```toml
model = "gpt-5.5"
model_provider = "openai"
approval_policy = "on-request"
sandbox_mode    = "workspace-write"

[sandbox_workspace_write]
writable_roots = ["/tmp/codex"]

# Route Codex at non-OpenAI models via LiteLLM
[model_providers.litellm]
name     = "LiteLLM gateway"
base_url = "http://localhost:4000/v1"
env_key  = "LITELLM_CODEX_KEY"
wire_api = "responses"   # ⚠️ corrected 2026-06-01: current Codex requires the Responses API,
                         # not "chat". Emitting "chat" produces a non-working Codex→proxy config.
                         # Re-verify against developers.openai.com/codex/config-advanced.

# Profiles = the closest analog to modes
[profiles.architect]
model          = "claude-opus-4-7"
model_provider = "litellm"
approval_policy = "untrusted"
sandbox_mode    = "read-only"

[profiles.code]
model          = "glm-4.6"
model_provider = "litellm"

[profiles.debug]
model          = "deepseek-chat"
model_provider = "litellm"

[mcp_servers.github]
command = "github-mcp-server"
env     = { GITHUB_PERSONAL_ACCESS_TOKEN = "${GH_PAT}" }
```

Invoke a "mode" via `codex --profile architect`. No native subagents; mode switching requires `codex --profile X` per session. MCP servers are global per-session, scoped only via plugin sandboxes.

---

## 4. Compiler / migration mapping

The matrix below shows how each `agents.yaml` field translates per harness. ✅ = native support, ⚠️ = workaround needed, ❌ = unsupported.

### 4.1 Schema field → native location

| `agents.yaml` field | Claude Code | Aider | Cline | Roo | Kilo | OpenCode | Crush | Continue | Goose | Codex |
|---|---|---|---|---|---|---|---|---|---|---|
| `providers.*` | env vars + `settings.env` | `.env` + `api-key:` | UI + extension state | UI API Profiles | provider blocks in `kilo.jsonc` | `provider.*.options` | `providers.*` | `models[].apiKey` | env vars + `~/.config/goose/secrets.yaml` | `[model_providers.*]` |
| `models.thinker` | `model:` field + `/model` | `model:` (architect) | UI Plan-model | Profile linked to Architect mode | `agent.plan.model` | `agent.plan.model` | mid-session `/model` switch ⚠️ | `models[]` w/ `chatOptions.basePlanSystemMessage` | `GOOSE_PLANNER_MODEL` | `[profiles.architect]` |
| `models.coder` | `settings.model` | `editor-model:` | UI Act-model | Profile linked to Code mode | `agent.code.model` | top-level `model` | `models.large` | `models[]` w/ `roles: [chat,edit,apply]` | `GOOSE_MODEL` | `[profiles.code]` |
| `models.workhorse` | CCR `Router.background` | `weak-model:` | ❌ | Profile on Debug/Ask | `agent.debug.model` | `small_model` | `models.small` | `models[]` w/ `roles: [autocomplete]` | sub-recipe `settings.goose_model` | `[profiles.debug]` |
| `routing.default` | CCR `Router.default` | `--model` ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `routing.think` | CCR `Router.think` | `--model` + `--architect` ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | `GOOSE_PLANNER_MODEL` ⚠️ | profile switch ⚠️ |
| `routing.background` | CCR `Router.background` + `ANTHROPIC_SMALL_FAST_MODEL` | `weak-model:` | ❌ | ❌ | ❌ | `small_model` | `models.small` | per-role `summarize` | sub-recipe | ❌ |
| `routing.longContext` | CCR `Router.longContext` + threshold | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `routing.webSearch` | CCR `Router.webSearch` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `modes.architect` | subagent `.md` + `agent:` setting | `--architect` (only one mode) | Plan mode ⚠️ | Architect mode | `agent.plan` | `agent.plan` (primary) | ❌ | `chatOptions.basePlanSystemMessage` | `GOOSE_PLANNER_*` | `[profiles.architect]` |
| `modes.code` | default + subagent | default | Act mode | Code mode | `agent.code` | `agent.build` | hard-coded `coder` agent | role-based | default | `[profiles.code]` |
| `modes.debug` | subagent `.md` | ❌ | ❌ | Debug mode | `agent.debug` | custom primary agent | ❌ | custom prompt | ❌ | `[profiles.debug]` |
| `modes.ask` | subagent `.md` | `/ask` (built-in) | ❌ | Ask mode | `agent.ask` | custom primary | ❌ | `chatOptions.baseSystemMessage` | ❌ | profile |
| `subagents.test-writer` (own model) | `.claude/agents/*.md` ⚠️ (#44385) | ❌ | Subagents feature ⚠️ | Boomerang `new_task` (mode-linked profile) | `.kilo/agents/*.md` ✅ | `agent.test-writer` ⚠️ (#21952 for built-ins; works for user-defined) | ❌ (#431, #1807) | `prompts[]` (no isolation) | sub-recipe ✅ | ❌ |
| `subagents.*.isolation` | `.claude/agents/` natively isolates | ❌ | per-subagent | Boomerang isolates | per-agent | per-agent | ❌ | ❌ | sub-recipe isolates | ❌ |
| `subagents.*.mcp_servers` | frontmatter `mcpServers` (additive only — #24054) | ❌ | global only | mode `groups: [mcp]` | `permission.{server}_*` | `permission` glob | ❌ | global only | per-recipe `extensions[]` | plugin sandboxes |
| `mcp_servers.*` | `.mcp.json` + `claude mcp add` | ❌ (community wrappers) | `cline_mcp_settings.json` | global config | global config | `mcp` top-level | `mcp` top-level | `mcpServers[]` | `extensions.*` | `[mcp_servers.*]` |
| `rules.global` (AGENTS.md) | ❌ not auto — needs `@AGENTS.md` import in CLAUDE.md or symlink ⚠️ | ❌ | reads | reads | reads | reads | reads | `rules[]` | `.goosehints` | reads |

### 4.2 What's unsupported per harness — at a glance

| Harness | What's missing | Severity |
|---|---|---|
| **Claude Code** | Per-subagent model override (bug #44385); per-subagent MCP isolation (additive only, #24054) | High — workaround via CCR injection |
| **Aider** | Modes, subagents, MCP, hooks, content routing | Medium — Aider is intentionally single-loop |
| **Cline** | File-based per-mode model binding, per-mode MCP scoping | Medium — UI-driven; not migratable |
| **Roo Code** | Project is sunsetting | High — migrate to Kilo |
| **Kilo Code** | Inline autocomplete model in file config; per-MCP server (vs tool) scoping documented | Low |
| **OpenCode** | Built-in subagent model override (#21952); content routing | Medium |
| **Crush** | Subagents, third model role, modes-as-personas | High — limited target |
| **Continue** | True spawned subagents with own model + isolation; content routing | Medium |
| **Goose** | Subagent model override (use sub-recipes); deep nesting; content routing | Low (sub-recipes cover it) |
| **Codex CLI** | Spawned subagents; native non-OpenAI models without proxy; content routing | Medium |

### 4.3 Cross-harness capability heatmap

| Capability | Best target | Notes |
|---|---|---|
| Multi-tier routing (default/think/background/longctx) | **Claude Code + CCR** | Only stack with first-class content routing |
| Per-mode model + tools + rules | **Roo / Kilo / OpenCode** | All three express this cleanly in checked-in files |
| Spawned subagent w/ own model + isolation | **Kilo + Goose (sub-recipes)** | OpenCode close behind for user-defined agents |
| Per-subagent MCP allow-list | **Kilo + OpenCode** | Tool-level glob filtering |
| Cost-conscious workhorse split | **Aider (`weak-model`)** | Most token-efficient harness; predictable splits |
| Cross-harness rules portability | **AGENTS.md** | Wide adoption (Codex, Cursor, Copilot, Aider, Gemini CLI). ⚠️ **Correction (2026-06-01):** Claude Code does **not** auto-read AGENTS.md at session time — it reads `CLAUDE.md`. To honor AGENTS.md, the compiler must emit a `CLAUDE.md` containing `@AGENTS.md` (or symlink), not rely on an absence-fallback. |

---

## 5. Key hygiene — one file, all harnesses

The portable schema references env vars; the env vars live in one place. Recommended layout:

`~/.config/llm-keys.env` (chmod 600, sourced from shell):

```bash
# OpenAI (Codex CLI, OpenAI SDK, LiteLLM upstream)
export OPENAI_API_KEY="sk-proj-..."

# Anthropic (Claude Code direct, LiteLLM upstream)
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Google
export GEMINI_API_KEY="..."
export GOOGLE_API_KEY="$GEMINI_API_KEY"

# Z.AI, DeepSeek, OpenRouter, Groq
export ZAI_API_KEY="..."
export DEEPSEEK_API_KEY="sk-..."
export OPENROUTER_API_KEY="sk-or-..."
export GROQ_API_KEY="gsk_..."

# Local vLLM/llama.cpp (often unauthenticated)
export LOCAL_API_KEY="EMPTY"

# LiteLLM master + virtual keys (per-tool budget control)
export LITELLM_MASTER_KEY="sk-litellm-master-..."        # admin only
export LITELLM_CODEX_KEY="sk-litellm-codex-..."          # Codex CLI
export LITELLM_CLAUDE_KEY="sk-litellm-claude-..."        # Claude Code
export LITELLM_CONTINUE_KEY="sk-litellm-continue-..."    # Continue
export LITELLM_BASE_URL="http://localhost:4000/v1"

# MCP server tokens
export GH_PAT="ghp_..."
export CONTEXT7_TOKEN="..."
```

Then in `~/.zshrc`:

```bash
[ -f ~/.config/llm-keys.env ] && { set -a; . ~/.config/llm-keys.env; set +a; }
```

For zero-on-disk secrets, swap to 1Password CLI:

```bash
# ~/.config/llm-keys.env.tmpl  (commit this; no secrets)
OPENAI_API_KEY=op://Personal/OpenAI/credential
ANTHROPIC_API_KEY=op://Personal/Anthropic/credential
ZAI_API_KEY=op://Personal/Z.AI/credential
DEEPSEEK_API_KEY=op://Personal/DeepSeek/credential
GEMINI_API_KEY=op://Personal/Google AI Studio/credential

# Launch a session with resolved env:
op signin
op run --env-file=$HOME/.config/llm-keys.env.tmpl -- zsh -l
```

For team-scale: distribute virtual keys via LiteLLM (each tool gets a budget-capped, model-allowlisted key; real provider keys live only in LiteLLM config):

```bash
curl -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "models": ["glm-4.6", "deepseek-chat", "claude-opus-4-7"],
        "max_budget": 50,
        "duration": "30d",
        "metadata": {"tool": "claude-code", "user": "mateo"}
      }'
```

Interpolation support varies — verified working:

| Harness | Pattern | Notes |
|---|---|---|
| OpenCode | `{env:VAR}` | In string positions inside config.json |
| Continue | `${{ secrets.VAR }}` | Hub-style |
| Codex CLI | `env_key = "VAR"` / `bearer_token_env_var = "VAR"` | Pointer, not interpolation |
| Claude Code | `${VAR}` in `.mcp.json` headers and env | Also reads from process env |
| CCR | `$VAR` in `api_key` field | Verified |
| Aider | Plain `.env` file or shell env | `api-key: provider=$VAR` not interpolated — use shell env |
| Gemini CLI | No interpolation in `settings.json` | Set via shell env |

**Rule of thumb:** Keep keys in shell env. The portable schema references env-var *names*, never values. Every harness can read shell env; not every harness interpolates inside its config file.

---

## 6. Recommended adoption path

Pick your level of investment:

### Level 1 — same harness, swap models pluggably (1 hour)

1. Install `claude-code-router` (`npm i -g @musistudio/claude-code-router`).
2. Drop in the CCR config from §3.1.
3. `eval "$(ccr activate)"` so plain `claude` routes through CCR.
4. **You now have Opus for thinking + GLM-4.6 workhorse + DeepSeek background in Claude Code.** No harness change.

### Level 2 — portable schema + LiteLLM gateway (half day)

1. Author `agents.yaml` from §2.
2. Stand up LiteLLM with virtual keys (`docker run litellm/litellm -p 4000:4000 -v config.yaml`).
3. Compile to native configs for the 2–3 harnesses you actually use (Claude Code, Aider, and one IDE).
4. Point every harness at LiteLLM via the env-var hygiene from §5.
5. **Single source of truth for "which model serves which role"; one budget; one audit log.**

### Level 3 — full subagent isolation across harnesses (1–2 days)

1. Designate Kilo Code (IDE) and OpenCode (CLI/TUI) as your subagent-capable targets — they're the cleanest fits today.
2. Author the `.kilo/agents/*.md` and `opencode.json` subagent definitions for `test-writer`, `code-reviewer`, `explore`.
3. Wire them to use cheap workhorses (DeepSeek) for instruction-following subagents and Opus for quality-critical ones (code-reviewer, architect).
4. Use Goose sub-recipes for any **long-running automated** workflow (CI, scheduled jobs) — they're the most production-shaped option.
5. **You now have role-based model assignment, isolation, and budget control across CLI + IDE + CI.**

---

## 7. Critical caveats to internalize

1. **Subagent model override is broken in Claude Code (#44385) and OpenCode built-ins (#21952).** Workaround: CCR `<CCR-SUBAGENT-MODEL>` tag injection, `CLAUDE_CODE_SUBAGENT_MODEL` env, or explicit Agent-tool model arg. Kilo and Goose sub-recipes are the only harnesses where per-subagent model selection works as documented. ⚠️ **Verified 2026-06-01:** both issues exist and concern what's claimed, but **both are now CLOSED** (#44385 closed-as-duplicate, #21952 closed) — the underlying bugs may be fixed in versions newer than this doc's snapshot. The `CLAUDE_CODE_SUBAGENT_MODEL` env (resolution priority #1 in current docs) is the stable path; re-check current frontmatter-`model:` behavior rather than hard-coding the workaround as permanently necessary.

2. **Crush is a limited target.** Two model slots, no user-defined subagents (issues #431, #1807 still open as of v0.47.0). Don't pick Crush if your design needs subagent isolation.

3. **Roo Code is sunsetting.** Migrate to Kilo Code (auto-migrates `.roomodes` on first launch). Both share the OpenCode-server backend, so Kilo configs can also use `.opencode/agents/*.md`.

4. **AGENTS.md is the only cross-harness rules portability win.** Adopt it as your global rules file. ⚠️ **Corrected 2026-06-01:** Claude Code does **not** auto-read AGENTS.md when CLAUDE.md is absent (verified against code.claude.com/docs/en/memory — "Claude Code reads `CLAUDE.md`, not `AGENTS.md`"). To honor it you must `@AGENTS.md`-import it from CLAUDE.md or symlink. `/init` reads AGENTS.md once to *seed* CLAUDE.md, but that is setup-time, not a session read.

5. **Prompt caching is non-portable.** Anthropic-native caching (`cache_control`) is what makes Claude Code economic. Routing Claude Code → GLM-4.6 loses the 5–10× cost reduction. Bake into savings calc.

6. **Content-based routing is Claude-Code-via-CCR-only today.** No other harness picks model per-request based on content shape. If you need it elsewhere, build it at the LiteLLM router layer.

7. **The "harness was leaked" angle:** Anthropic accidentally shipped a Claude Code sourcemap on npm in March 2026 exposing the agent loop and 44 feature flags. Community reimplementations exist; running an independent reimplementation pointed at a third-party model is the safer posture vs. redistributing the leaked bundle. Verify ToS posture before commercial use.

---

## 8. Working "Opus for thinking + GLM-4.6 workhorse + DeepSeek background" — every harness

For quick reference, the same model assignment in each harness's invocation:

| Harness | Command |
|---|---|
| Claude Code + CCR | `ccr start && ccr code` with §3.1 router config |
| Aider | `aider --architect --model anthropic/claude-opus-4-7 --editor-model openrouter/zai/glm-4.6 --weak-model deepseek/deepseek-chat` |
| Cline | UI: Plan = Opus 4.7, Act = GLM-4.6; `.clinerules/` for global rules |
| Roo Code | Create three API Profiles; link Architect→Opus, Code→GLM, Debug→DeepSeek |
| Kilo Code | `kilo.jsonc` per §3.5 (declarative, checked-in) |
| OpenCode | `opencode.json` per §3.6 with `model: zhipu/glm-4.6`, `small_model: deepseek/deepseek-chat`, `agent.plan.model: anthropic/claude-opus-4-7` |
| Crush | `crush.json` per §3.7: `large: glm-4.6`, `small: deepseek-chat`; mid-session `/model` to swap Opus for thinking |
| Continue | `config.yaml` per §3.8 — Opus for chat/edit, GLM for second `chat/edit`, DeepSeek for `autocomplete/summarize` |
| Goose | `GOOSE_PROVIDER=zai GOOSE_MODEL=glm-4.6 GOOSE_PLANNER_PROVIDER=anthropic GOOSE_PLANNER_MODEL=claude-opus-4-7`; sub-recipes for DeepSeek workhorse tasks |
| Codex CLI | `[profiles.architect] model="claude-opus-4-7"`; invoke with `codex --profile architect`; runs against LiteLLM at `localhost:4000` |

---

## Verification status (2026-06-01)

Parallel-agent verification against official docs and GitHub. Config formats are largely accurate; corrections applied inline.

**Confirmed.** Claude Code `settings.json` keys + subagent frontmatter (`name`/`description`/`tools`/`model`/`disallowedTools`) + `CLAUDE_CODE_SUBAGENT_MODEL` env · Aider `architect`/`model`/`editor-model`/`weak-model`/aliases · OpenCode `agent` blocks (`mode: primary|subagent`), `small_model` · Crush `large`/`small` slots · Continue role-based models · Goose recipes + AAIF move · Codex profiles + `model_providers` · Roo→Kilo migration · AGENTS.md as a real cross-vendor convention. **All five cited GitHub issues (#44385, #24054, #21952, #431, #1807) exist and concern what's claimed.**

**Corrected (applied inline).**
- **AGENTS.md / Claude Code** — refuted the "reads when CLAUDE.md absent" claim in §4.1, §4.3, §7.4. Claude Code reads `CLAUDE.md`; honor AGENTS.md via `@AGENTS.md` import or symlink.
- **Codex `wire_api`** — `"chat"` → `"responses"` (§3.10); current Codex needs the Responses API.
- **#44385 and #21952 are CLOSED** — the bugs may be fixed; treat the model-override workaround as provisional, not permanent (§7.1).
- **Crush hosted `$schema`** lags the repo schema (#1252) — validate against repo (§3.7).

**Drift-prone (re-verify before the compiler emits them).** Codex (`wire_api`, top-level-only `model_providers`/`mcp_servers`) · Crush (fast-moving `schema.json`) · OpenCode/Kilo (rapid OpenCode-server iteration; `.roomodes`/`.opencode/agents` file-naming in flux) · Claude Code subagent model resolution (bug closed; behavior may have changed).

---

## Sources

**Claude Code:** [settings reference](https://docs.anthropic.com/en/docs/claude-code/settings) · [subagents docs](https://code.claude.com/docs/en/sub-agents) · [hooks reference](https://code.claude.com/docs/en/hooks) · [env vars](https://code.claude.com/docs/en/env-vars) · [MCP docs](https://code.claude.com/docs/en/mcp) · [subagent model bug #44385](https://github.com/anthropics/claude-code/issues/44385) · [subagent MCP isolation #24054](https://github.com/anthropics/claude-code/issues/24054)

**claude-code-router:** [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router) · [docs site](https://musistudio.github.io/claude-code-router/)

**Aider:** [config overview](https://aider.chat/docs/config.html) · [YAML config](https://aider.chat/docs/config/aider_conf.html) · [model aliases](https://aider.chat/docs/config/model-aliases.html) · [chat modes](https://aider.chat/docs/usage/modes.html) · [advanced model settings](https://aider.chat/docs/config/adv-model-settings.html) · [MCP request #4506](https://github.com/aider-ai/aider/issues/4506)

**Cline:** [Plan & Act](https://docs.cline.bot/core-workflows/plan-and-act) · [rules](https://docs.cline.bot/features/cline-rules) · [MCP marketplace](https://docs.cline.bot/mcp/mcp-marketplace) · [subagents](https://docs.cline.bot/features/subagents)

**Roo Code:** [custom modes](https://docs.roocode.com/features/custom-modes) · [API profiles](https://docs.roocode.com/features/api-configuration-profiles) · [boomerang tasks](https://docs.roocode.com/features/boomerang-tasks) · [custom instructions](https://docs.roocode.com/features/custom-instructions)

**Kilo Code:** [custom modes / agents](https://kilo.ai/docs/agent-behavior/custom-modes) · [MCP in Kilo](https://kilo.ai/docs/automate/mcp/using-in-kilo-code) · [auto-approving actions](https://kilo.ai/docs/getting-started/settings/auto-approving-actions) · [agent manager](https://kilo.ai/docs/automate/agent-manager)

**OpenCode:** [agents](https://opencode.ai/docs/agents/) · [config](https://opencode.ai/docs/config/) · [permissions](https://opencode.ai/docs/permissions/) · [MCP servers](https://opencode.ai/docs/mcp-servers/) · [built-in subagent override #21952](https://github.com/anomalyco/opencode/issues/21952)

**Crush:** [README](https://github.com/charmbracelet/crush) · [config.go (canonical)](https://github.com/charmbracelet/crush/blob/main/internal/config/config.go) · [DeepWiki configuration](https://deepwiki.com/charmbracelet/crush/2.2-configuration) · [subagents request #1807](https://github.com/charmbracelet/crush/issues/1807)

**Continue:** [config.yaml reference](https://docs.continue.dev/reference) · [configuring models](https://docs.continue.dev/guides/configuring-models-rules-tools) · [model capabilities](https://docs.continue.dev/customize/deep-dives/model-capabilities) · [model roles intro](https://docs.continue.dev/customize/model-roles/intro)

**Goose:** [config files](https://goose-docs.ai/docs/guides/config-files/) · [recipe reference](https://block.github.io/goose/docs/guides/recipes/recipe-reference/) · [subagents vs subrecipes](https://block.github.io/goose/blog/2025/09/26/subagents-vs-subrecipes/) · [multi-model config](https://goose-docs.ai/docs/guides/multi-model/) · [moved to AAIF](https://goose-docs.ai/blog/2026/04/07/goose-moves-to-aaif)

**Codex CLI:** [config index](https://github.com/openai/codex/blob/main/docs/config.md) · [config reference](https://developers.openai.com/codex/config-reference) · [advanced config](https://developers.openai.com/codex/config-advanced) · [sandbox](https://developers.openai.com/codex/concepts/sandboxing) · [auth](https://developers.openai.com/codex/auth)

**Cross-cutting:** [AGENTS.md spec](https://agents.md/) · [LiteLLM /v1/messages](https://docs.litellm.ai/docs/anthropic_unified/) · [LiteLLM virtual keys](https://docs.litellm.ai/docs/proxy/virtual_keys) · [LiteLLM Codex tutorial](https://docs.litellm.ai/docs/tutorials/openai_codex) · [1Password op run](https://developer.1password.com/docs/cli/secrets-environment-variables/)

**The leak:** [VentureBeat coverage](https://venturebeat.com/technology/claude-codes-source-code-appears-to-have-leaked-heres-what-we-know) · [zep-us/claude-system-prompt](https://github.com/zep-us/claude-system-prompt)
