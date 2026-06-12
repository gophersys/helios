# Agentic Coding Landscape — June 2026

A pluggable view of harnesses, models, and routing. Compiled from five parallel research streams on 2026-06-01.

> ⚠️ **Read before any number below.** Every benchmark, price, and date here is **directional, not
> verified** — corroborated only by secondary blogs, and several models post-date what's web-checkable.
> **None of it is load-bearing** (Invariant I2: the architecture is model-agnostic; per-model data is
> editable config, not code). This is a *reference snapshot*, not a source of truth — **don't cite a
> decimal.** Full audit: § Verification status.

**The only 4 lines that matter for the build:**
1. Harness and model have decoupled — a translation layer (LiteLLM / claude-code-router) makes model choice *config, not code*.
2. Claude still owns the last 10–20% (long-horizon, harness fit, frontend taste); a real second tier (GLM / DeepSeek / Kimi) does the bulk cheaply.
3. Route by role: `think` → strongest model, `default`/`background` → cheap. This *is* `agentcfg`'s routing split.
4. Prefer SWE-bench **Pro** / Terminal-Bench over (contaminated) **Verified** — but per I2, never let a number drive a design decision.

Everything below is reference detail behind those four lines.

---

## TL;DR — the shape of the field

1. **Harness and model are now commodities glued by a translation layer.** The OpenAI Chat Completions schema is the lingua franca; Claude Code is the lone holdout speaking the Anthropic Messages dialect. A proxy (claude-code-router, LiteLLM) bridges them. Once that's in place, swapping models is config, not code.

2. **A real second tier has emerged behind Claude, but no open model has unambiguously caught the frontier.** GLM-5.1, DeepSeek V4-Pro, and Kimi K2.6 are now within ~3–10 SWE-bench points of Opus 4.7/4.8 and can replace Sonnet for ~80% of agentic traffic at 5–20× cost savings. The last 10–20% — long-horizon coherence, harness-specific tool fluency, tasteful frontend — still favor Claude.

3. **Closed competitor that reaches Sonnet/Opus today: GPT-5.5.** Roughly Opus-4.7-equivalent quality at comparable price. Gemini 3.1 Pro reaches Sonnet 4.6 territory and exceeds it on long-context work at meaningfully lower cost ($2/$12). Grok 4.3 and Mistral are cost-leader plays, not quality peers.

4. **The benchmark-vs-feel gap is real.** SWE-bench Verified is now visibly saturating from training contamination — top scores cluster at 80–88%, but the same models drop to 45–65% on SWE-bench Pro (contamination-controlled). Weight Pro and Terminal-Bench 2.0 over Verified; trust harness-free numbers (Aider polyglot) more than vendor-scaffolded ones.

5. **The pluggable stack to adopt:** **LiteLLM** as a single OpenAI-compatible gateway in front of every backend (Anthropic, OpenAI, Google, OpenRouter, Together/Fireworks/DeepInfra, local vLLM/SGLang). Every harness points at LiteLLM. The "which harness" decision is now decoupled from the "which model" decision.

---

## Part 1 — Open source harnesses

### What's actively worth adopting

| Harness | Surface | Loop | MCP | Context strategy | Token profile | Best for |
|---|---|---|---|---|---|---|
| **Aider** | CLI | Single-loop, Git-commit per edit | Limited | PageRank repomap (tree-sitter) | **Lowest** | Disciplined, repo-aware edits |
| **OpenCode** | TUI + client/server | Primary + subagents | Full (HTTP/stdio/SSE) | LSP + on-demand | Mid | Modern TUI, multi-agent, remote/mobile driving |
| **Cline** | VS Code (+JB/CLI) | Plan/Act | Marketplace | File tree + on-demand | **Highest** | IDE UX, MCP marketplace, browser use |
| **Continue** | VS Code/JetBrains | Chat + Agent + Autocomplete | Full + Hub blocks | RAG + ast-grep | Low-mid | JetBrains, configurable, fast-apply |
| **Goose** | Desktop + CLI | Subagents + MCP Apps | **Deepest** | Extension-driven | Mid | General agent at LF/AAIF (vendor-neutral) |
| **Crush** | TUI | Single-loop, mid-session swap | Full | LSP | Mid | Aesthetic terminal UX, broad OS support |
| **OpenHands** | Web + VSCode + CLI | Autonomous, sandboxed | Yes + browser | Dynamic + LiteLLM | High | Long autonomous SWE tasks |
| **Kilo Code** | VS Code | OpenCode-server backed + modes | Full | LSP + on-demand | Mid | Active Roo successor with autocomplete |
| **Codex CLI** | CLI (Rust) | Loop + parallel tools | Yes | On-demand + websearch | Mid | OpenAI-first power users |
| **Gemini CLI** | CLI | Loop + voice + memory | Yes | On-demand + ripgrep | Mid | Google-ecosystem users |

### Notable status changes

- **Roo Code** announced shutdown April 2026 → migrate to **Kilo Code** (Roo fork, $8M seed, VS Code extension rebuilt on OpenCode server, adds inline autocomplete Cline/Roo lack).
- **Plandex** wound down October 2025; reference design for large-repo agents but not a current daily-driver.
- **Goose** moved to the Linux Foundation's Agentic AI Foundation (AAIF) April 2026 alongside MCP and AGENTS.md — strong governance signal.
- **OpenCode** got blocked from Claude Pro/Max subscription auth by Anthropic in January 2026. Proxies like Meridian exist but violate ToS; bring your own Anthropic API key instead.
- **mini-SWE-agent** (~100 lines of Python) now matches the full SWE-agent's >74% SWE-bench Verified — most active SWE-agent development is on mini.

### Token profile reality check

Aider is the cheapest harness in the category — typical edit costs a small fraction of Cline's for equivalent work. Cline's verbose "send growing conversation history + file tree + on-demand reads" pattern drives community-reported $200–$1000/month bills. Roo's diff-based editing claws back ~30%. If cost matters, start with Aider; if IDE UX matters, accept Cline's tax or pair it with a cheap open-weight model.

---

## Part 2 — Open source models

### Current standings (June 2026)

| Model | Params (active) | Context | License | SWE-Verified | Notable |
|---|---|---|---|---|---|
| **DeepSeek V4-Pro** | 1.6T MoE (49B) | 1M | MIT | 80.6% | Apr 2026, fastest-rising open model |
| **DeepSeek V4-Flash** | 284B MoE (13B) | 1M | MIT | ~75% (est) | $0.14/M in; single H100 node |
| **Kimi K2.6** | 1T MoE (32B) | 256K | Modified MIT | 80.2% | Long-horizon king (300 sub-agents, 4K steps) |
| **GLM-5.1** | 744B MoE (40B) | 200K | MIT | ~80% (–2.6 vs Opus 4.6) | Mar 2026; 8h autonomous loops |
| **GLM-4.6** | 355B MoE (32B) | 200K | MIT | ~74% | Cheapest credible Sonnet replacement |
| **Qwen3-Coder-Next** | 80B MoE (3B) | 256K | Apache 2.0 | 70.6% | Best size/perf — single 5090 |
| **Qwen3.6-27B (dense)** | 27B dense | 256K | Apache 2.0 | 77.2% | Best single-GPU option, matches Opus 4.5 |
| **MiniMax M2.7** | 230B MoE (10B) | 200K+ | Apache-style | 56.2% (Pro) | Self-evolving, strong on TB2 |
| **Mistral Medium 3.5** | 128B dense | 256K | Modified MIT | 77.6% | Devstral 2 successor; 4-GPU |
| **Llama 4 Maverick** | 400B MoE | 1M | Llama Community | ~63% (third-party) | Underperforms; EU-restricted |

### Where open still trails Claude

1. **Harness fit dominates raw capability.** Opus 4.7 scores 91% in Cursor vs 87% in Claude Code's own harness — same model swings 4pp across harnesses, and 30–50pp across radically different scaffolds. Most open models are tuned against generic scaffolds (SWE-Agent, OpenHands) and underperform in Claude Code specifically.
2. **Tool-call format adherence.** K2.6 and GLM-5.1 are noticeably better than Qwen3; V4-Pro is mid-pack.
3. **Premature termination.** Open models declare done before tests pass more often than Opus.
4. **Hallucinated APIs on niche libraries.** Qwen3-Coder and Devstral are worst; V4-Pro and GLM-5.1 best of the open set.
5. **Context rot at long horizons.** Even with 1M nominal context, effective recall degrades above ~256K. Claude is more robust at depth.
6. **Reasoning-loop verbosity.** K2.6 reasoning traces and DeepSeek's optional thinking mode can balloon costs 3–5×.

### Bottom-line picks

- **Drop-in Claude Code swap:** GLM-4.6 (cheapest) or GLM-5.1 (best quality). MIT-licensed.
- **Best raw open agentic capability:** tie between Kimi K2.6 and DeepSeek V4-Pro.
- **Best single high-end GPU self-host:** Qwen3.6-27B dense.
- **Best 512GB M3 Ultra self-host:** DeepSeek V4-Flash Q4 or GLM-4.6 AWQ (~15–25 tok/s expected).
- **Best price/perf hosted:** DeepSeek V4-Pro promo, GLM-4.6, Qwen3-Coder-480B.
- **Skip:** Llama 4 (capability), Codestral original (NC license), original Qwen3-Coder-480B (superseded).

---

## Part 3 — Closed-source frontier models

### Anthropic baseline (your starting point)

| Model | Release | $/MTok (in/out) | Context | SWE-Verified |
|---|---|---|---|---|
| Sonnet 4.6 | Feb 17 2026 | $3 / $15 | 1M (beta) | 79.6% (10-trial avg) |
| Opus 4.6 | Feb 5 2026 | $5 / $25 | 1M | 80.8% |
| **Opus 4.7** | **Apr 16 2026** | **$5 / $25** | 1M | **~87.6%** |
| Opus 4.8 / Mythos Preview | Limited | n/a | n/a | ~88.6% |

**Highest-leverage low-effort move:** if you're still on Opus 4.6, upgrade to 4.7 — same price, +6–7pp SWE-bench Verified, Cursor CursorBench 58% → 70%, no harness migration.

### Reaches or exceeds Sonnet/Opus

- **OpenAI GPT-5.5** (Apr 24 2026) — ~$5 / $30 per MTok, 1M context, 88.7% SWE-Verified, 82.7% Terminal-Bench 2.0 (SOTA). Roughly tied with Opus 4.7; GPT-5.5 narrowly ahead on Terminal-Bench, Opus 4.7 ahead on SWE-bench Pro and frontend taste.
- **GPT-5.5 Pro** — research tier at ~$30 / $180; for hardest tasks only.
- **Codex** (the product) — closest Claude Code analogue. Cloud-container autonomous mode runs hours of independent work; CLI scores 77.3% on Terminal-Bench 2.0.

### Reaches Sonnet 4.6, below Opus 4.6/4.7

- **Gemini 3.1 Pro** (Feb 19 2026) — $2 / $12 per MTok at ≤200K, $4 / $18 above. **1M context** (~1,048,576 tokens). [⚠️ corrected 2026-06-01: doc previously said "2M (largest in industry)"; every source reports 1M, and DeepSeek V4 / others also list 1M, so "2M largest" was wrong.] 80.6% SWE-Verified. Strongest cost-adjusted alternative if you're willing to use Gemini CLI / Antigravity.
- **GPT-5.4** — production "workhorse" at ~$2.50 / $15. Behind Sonnet 4.6 on hardest tasks; fine for bulk work.
- **GPT-5.3-Codex** — still best for Codex CLI cloud autonomous runs.

### Below Sonnet 4.6 — cost-leader tier

- **Grok 4.3** (Apr 30 2026) — $1.25 / $2.50 per MTok, 1M context, no output cap. **Grok Build** (May 14 2026) supports 8 parallel subagents in Git worktrees. ~14pp behind Opus 4.7 on agentic coding. Use when budget dominates and tasks are well-bounded.
- **grok-code-fast-1** — $0.20 / $1.50, 256K context, 70.8% SWE-Verified.
- **Mistral Medium 3.5 / Codestral / Devstral 2** — no first-party agentic CLI. Codestral is a credible IDE-completion model; Mistral's frontier coding play is "good enough at 1/10 price".

### Harness compatibility — what's usable from Claude Code

All major closed competitors can be driven through Claude Code via an Anthropic-Messages-to-OpenAI proxy. You lose Claude Code's Claude-tuned prompt optimizations. Two things cannot be replicated easily: Codex's cloud-container autonomous mode and Grok Build's 8-parallel-subagent worktree mode — for those you must use the vendor harness.

---

## Part 4 — Benchmarks: what the numbers mean

### SWE-bench Verified (the canonical agentic bench — saturating)

| Model | Score | Harness | Date |
|---|---|---|---|
| Claude Mythos Preview | 93.9% | Anthropic internal | 5/26 |
| GPT-5.5 | 88.7% | Codex CLI | 4/26 |
| Claude Opus 4.8 | 88.6% | Anthropic adaptive | 5/26 |
| Claude Opus 4.7 | 87.6% | Anthropic adaptive | 4/26 |
| GPT-5.3-Codex | 85.0% | Codex CLI | 2026 |
| Claude Opus 4.6 | 80.8% | Anthropic internal | 2/26 |
| DeepSeek V4-Pro Max | 80.6% | mini-SWE-agent | 2026 |
| Gemini 3.1 Pro | 80.6% | Google internal | 2/26 |
| Kimi K2.6 | 80.2% | mini-SWE-agent | 4/26 |
| Sonnet 4.6 | 79.6% (80.2% w/ tweak) | Anthropic, 10-trial | 2/26 |
| Grok 4.2 | 76.7% | xAI internal | 2026 |
| Qwen3.5 | 76.2% | mini-SWE-agent | 2026 |
| DeepSeek V4 Flash | 73.7% | mini-SWE-agent | 2026 |
| GLM-4.7 | 73.8% | Z.AI internal | 2026 |
| Qwen3-Coder-Next | 70.6% | mini-SWE-agent | 2026 |

**Critique:** ~1/3 of Verified issues have solution outline in the issue text itself. Auditors found agents writing `conftest.py` at repo root that pytest auto-discovers and the harness doesn't reset — a reward-hack vector that boosts vendor-reported scores. Verified scores overstate real performance by 10–25pp depending on model.

### SWE-bench Pro (contamination-controlled — trust this more)

| Model | Score | Date |
|---|---|---|
| Claude Mythos Preview | 77.8% | 2026 |
| Claude Opus 4.7 | 64.3% | 4/26 |
| GPT-5.4 (xHigh) | 59.1% | 2026 |
| GPT-5.3-Codex | 56.8% | 2026 |
| Kimi K2.6 | 58.6% | 4/26 |
| MiniMax M2.7 | 56.2% | 3/26 |

The 27pp gap between Verified top (88%) and Pro top (64%) is the cleanest empirical evidence of training contamination on Verified.

### Terminal-Bench 2.0 (closest to "real feel")

| Agent + Model | Score |
|---|---|
| Codex CLI + GPT-5.5 | 82.7% |
| Claude Mythos Preview (Claude Code) | 82.0% |
| ForgeCode + GPT-5.4 | 81.8% |
| TongAgents + Gemini 3.1 Pro | 80.2% |
| GPT-5.3-Codex | 77.3% |
| Gemini 3.5 Flash | 76.2% |
| Kimi K2.6 | 66.7% (open-weight leader) |
| Sonnet 4.6 | ~59% (Anthropic Terminus-2) |

Scaffolding contributes 2–6pp on top of raw model capability — same model differs by ~5pp across Codex CLI vs ForgeCode vs default scaffold.

### Aider Polyglot (no-scaffold, isolates editing skill)

| Model | Score |
|---|---|
| Claude Opus 4.5 | 89.4% |
| GPT-5 (high reasoning) | 88.0% |
| o3-pro | 84.9% |
| Gemini 2.5 Pro | 83.1% |
| DeepSeek-V3.2-Exp | 74.5% (top open-weight) |
| Qwen3-Coder-Next | 70.6% (most efficient) |

Frontier labs increasingly stop submitting current models to Aider — it doesn't flatter them and the evals are slow to expand. Use Aider scores to triangulate raw editing ability separate from harness inflation.

### Why a 65% Verified model often feels worse than a 60% one

1. **Harness specialization** fuses model + scaffold in vendor numbers.
2. **Training contamination** — Verified's 12 repos and 500 issues are well-known; models have seen the fixes.
3. **Reward hacking** — auditors found `conftest.py` plants and git-history mining.
4. **Distribution mismatch** — Verified is 12 mature Python repos; you live in TypeScript monorepos with flaky tests.
5. **Pass-rate vs. trustworthiness** — benchmarks don't measure "did it overwrite my migration silently".
6. **Best-of-N vs. single-shot** — Anthropic's Sonnet 4.6 score is 10-trial average; your real workflow is single-shot.

**Practical takeaway:** weight SWE-bench Pro and Terminal-Bench 2.0 over Verified; check Aider Polyglot for raw editing skill; trust harness-free numbers over vendor-scaffolded ones.

---

## Part 5 — Pluggable pairing: recipes and config

### The three layers

| Layer | What it does | Representative tools |
|---|---|---|
| Harness | Agent loop, tools, MCP, repo context | Claude Code, Aider, Cline, OpenCode, Crush, Goose |
| Proxy / router | Dialect translation, per-request model picking | claude-code-router, LiteLLM, OpenRouter |
| Inference backend | Runs the weights | Anthropic, OpenAI, Google, OpenRouter, Cerebras/Groq/Fireworks/Together/DeepInfra, vLLM/SGLang/llama.cpp/MLX |

### Proxy layer — when to use which

- **claude-code-router** — opinionated default for Claude Code → non-Anthropic models. `~/.claude-code-router/config.json` with `Providers` and `Router` per-role (`default`, `background`, `think`, `longContext`, `webSearch`). Solo dev.
- **LiteLLM** — Swiss-army knife. Exposes any of ~100 backends as either OpenAI or Anthropic format. Best translation coverage, weekly bug-fix cadence on tool-call mapping. Teams.
- **OpenRouter** — managed routing, no provider markup, 5.5% credit fee. Lowest-effort access to GLM-4.6, DeepSeek V3.2, Kimi K2, Qwen3-Coder behind one key.

### Inference backend picks

- **Cerebras** — highest throughput on open weights (~3000 tok/s on gpt-oss-120B). Interactive agents.
- **Groq** — lowest TTFT (0.6–0.9s). Chat-feel agents.
- **Fireworks** — 4× faster structured/JSON output. Tool-heavy agents.
- **DeepInfra** — cheapest, widest open-weight catalog.
- **Together** — middle of pack, strong fine-tuning.
- **Hyperbolic** — aggressive 70B-class pricing.

### Local inference, by hardware

| Hardware | Best server | Why |
|---|---|---|
| M3/M4 Max, M3 Ultra Mac Studio | MLX / mlx-lm (LM Studio embeds it) | 30–50% faster than llama.cpp on Apple Silicon |
| Single 4090 or 2× 3090 | llama.cpp + GGUF Q4_K_M, or TabbyAPI/ExllamaV2 | Quant-bound; ExllamaV2 wins on quantized throughput |
| 4× 3090/4090 | vLLM | AWQ/GPTQ + tensor parallel, OpenAI-compat |
| 1–2× H100/MI300 | vLLM or SGLang | SGLang wins on repeated prefixes (agents), ~29% throughput edge; vLLM wins on unique single-turn |
| Heterogeneous CPU/edge | llama.cpp | Portable everywhere |
| GUI quick-start | LM Studio or Ollama | Both expose OpenAI-compat; Ollama tool-call lags vLLM/SGLang |

For coding agents, always run vLLM/SGLang with `--enable-auto-tool-choice` and the right `--tool-call-parser` (`qwen3_coder`, `hermes`, `llama3_json`). Without that flag, tool calls appear as plain text and the agent loop collapses.

### Recipe 1 — Claude Code → GLM-4.6 via claude-code-router

`~/.claude-code-router/config.json`:

```json
{
  "Providers": [
    {
      "name": "openrouter",
      "api_base_url": "https://openrouter.ai/api/v1/chat/completions",
      "api_key": "${OPENROUTER_API_KEY}",
      "models": ["z-ai/glm-4.6", "deepseek/deepseek-chat", "anthropic/claude-opus-4.7"],
      "transformer": { "use": ["openrouter"] }
    },
    {
      "name": "deepseek",
      "api_base_url": "https://api.deepseek.com/v1/chat/completions",
      "api_key": "${DEEPSEEK_API_KEY}",
      "models": ["deepseek-chat", "deepseek-reasoner"],
      "transformer": { "use": ["deepseek"] }
    }
  ],
  "Router": {
    "default":      "openrouter,z-ai/glm-4.6",
    "background":   "deepseek,deepseek-chat",
    "think":        "deepseek,deepseek-reasoner",
    "longContext":  "openrouter,anthropic/claude-opus-4.7",
    "longContextThreshold": 80000,
    "webSearch":    "openrouter,z-ai/glm-4.6:online"
  }
}
```

Then `ccr code` instead of `claude`. GLM-4.6 for most turns, DeepSeek-R for planning, Opus for >80K contexts.

### Recipe 2 — Aider planner-executor split

`~/.aider.conf.yml`:

```yaml
architect: true
model: anthropic/claude-sonnet-4-6
editor-model: deepseek/deepseek-chat
editor-edit-format: editor-diff
weak-model: deepseek/deepseek-chat
cache-prompts: true
map-tokens: 4096
```

Architect proposes (Sonnet — cached prompt), editor applies (DeepSeek — ~30× cheaper).

### Recipe 3 — Cline → local Qwen3-Coder via vLLM

```bash
vllm serve Qwen/Qwen3-Coder-30B-A3B-Instruct \
  --port 8000 \
  --tensor-parallel-size 2 \
  --max-model-len 262144 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3 \
  --enable-prefix-caching
```

Cline: Provider = OpenAI Compatible, Base URL `http://gpu-box:8000/v1`, API Key `EMPTY`, Model `Qwen/Qwen3-Coder-30B-A3B-Instruct`, Context `262144`, **Use compact prompt: ON** (Cline's full system prompt chokes local <70B models).

### Recipe 4 — Hybrid via LiteLLM gateway

Strategy: run LiteLLM as single gateway. Two backend buckets — OpenRouter (frontier closed/open) and `http://gpu-box:8000/v1` (local vLLM). Define a router with fallbacks: `cheap` = local Qwen primary, GLM-4.6 fallback; `smart` = OpenRouter Opus 4.7 primary, GPT-5.5 fallback. Point every harness at LiteLLM's OpenAI endpoint; point Claude Code at LiteLLM's `/v1/messages`. One token, one budget, one audit log.

### Hard problems

- **Tool-call format mismatch.** claude-code-router is clean for OpenRouter/DeepSeek/Gemini, occasional drift on newer providers. LiteLLM has best coverage. OpenCode Go's Anthropic-compat proxy known broken for `deepseek-v4-pro` (drops `function.name`).
- **Prompt caching.** Anthropic-native gives 90% input discount. **No proxy synthesizes it for non-Anthropic backends.** Routing Claude Code → GLM-4.6 loses the 5–10× cost reduction caching gives; bake into savings calc.
- **Context-window mismatch.** Opus 1M → DeepSeek 128K silently truncates. Use `longContextThreshold` in claude-code-router; conservative 60–80K.
- **Rate limits.** OpenRouter free-tier GLM-4.6 is 20 RPM / 200 RPD — fatal for CI. Build failover at router layer (LiteLLM `fallbacks`, OpenRouter `provider.order`).

---

## Part 6 — Practical playbook

### If you live in Claude Code today

1. **Upgrade Opus 4.6 → 4.7 first.** Same price, +6–7pp, no migration. Highest-ROI change.
2. **Add claude-code-router for selective offload.** Route `background` and `longContext` away from Claude when feasible. Keep `default` and `think` on Claude unless you've validated GLM-5.1 or DeepSeek V4 quality on your codebase.
3. **Watch the prompt-cache math.** If your sessions are long with stable system prompts, Anthropic-native caching often beats nominal token-price savings from routing to GLM/DeepSeek.

### If you want to escape Anthropic-only pricing

1. **Adopt LiteLLM as gateway.** Centralize keys, budgets, observability.
2. **Daily-driver Aider** for surgical work — lowest token bills, best repo awareness, most pluggable.
3. **GLM-4.6 or DeepSeek V4-Pro** as the workhorse model. GLM-5.1 if you can stomach the price ($0.98/$3.08).
4. **Reserve Opus 4.7 or GPT-5.5** for the hardest 10–20% of tasks via per-mode model selection in Aider/Cline/Roo.

### If you want full self-host as future hardware comes online

1. **Start with Qwen3.6-27B dense** on a 4090/5090. Runs at Q4, 77.2% SWE-Verified, Apache 2.0.
2. **vLLM/SGLang** as the server with proper tool-call parser flags.
3. **Plan upgrade path** to DeepSeek V4-Flash Q4 (~150GB, single H100 node or 512GB M3 Ultra) when hardware budget allows.
4. **Keep LiteLLM in the path** so the harness doesn't notice when you swap from cloud to local.

### Building a product on top of an agent

1. **OpenHands** if you need cloud-container autonomous runs and don't mind Docker overhead.
2. **mini-SWE-agent** as a starting point for your own custom harness (~100 lines, hits >74% SWE-Verified).
3. **Multi-model from day 1:** route different roles (planner/executor/background) to different models, with LiteLLM fallbacks for resilience.

---

## Uncertainty flags

- 2026 model version names (GPT-5.5, Opus 4.7/4.8, Gemini 3.1 Pro, DeepSeek V4) verified from primary sources where possible; some decimal versions (especially Codex-specific ones beyond GPT-5.3-Codex) come from third-party guides and should be treated as approximate.
- SWE-bench Verified numbers are partially gamed at this point; +/-3pp deltas are noise.
- Anthropic's Pro/Max third-party blocking situation is evolving — proxies that bridge subscription auth (Meridian, opencode-anthropic-auth) technically violate ToS and risk account termination. If you have an API key, ignore these.
- Star counts and project velocity are mid-2026 snapshots and drift.
- GLM "Coding Plan" at $18/mo via z.ai has reports of opaque fair-use bans — verify before relying on it for production.

### Verification status (2026-06-01)

Parallel-agent verifiability audit. **All headline benchmark numbers are "partial at best"** — corroborated only by secondary SEO blogs (Vellum, TokenMix, NxCode, the-decoder), not primary vendor/leaderboard pages. Treat every decimal as directional, not ground truth. Open-model SWE-bench scores and all subscription-metering figures are **unverifiable / projected**. This does **not** block any downstream build: the `agentcfg` architecture is model-agnostic — per-model data (price, context, dialect, caching) is editable config, not code.

**Refuted / corrected:** Gemini 3.1 Pro context is **1M, not 2M** (fixed in Part 3).

**Cross-doc contradictions with the `agentic-engineering` series (May 2026) — flagged, not yet reconciled:**
- **SWE-bench Pro 58.6%** is attributed to **Kimi K2.6** here (Part 4) but to **GPT-5.5** in `agentic-engineering` doc 00 / README glossary. Both attributions exist online (a number collision). Pick one canonical framing across the two series.
- **Terminal-Bench:** doc 00 frames "GPT-5.5 82.7% vs Opus 4.7 69.4%" as a head-to-head; that pairs a *scaffolded* GPT-5.5 (Codex CLI) against *bare* Opus 4.7 — apples-to-oranges. This doc's agent+model-pair table avoids that and omits Opus 4.7's 69.4 entirely. Reconcile.
- **GPT-5.5 SWE-bench Pro:** doc 00 gives it a Pro score; this doc's Pro table omits GPT-5.5 entirely.
- **Aider Polyglot:** Gemini 2.5 Pro listed at 83.1% here; web sources say 82.2% (minor).

---

## Key sources

**Harnesses:** [Aider](https://github.com/Aider-AI/aider) · [OpenCode](https://github.com/sst/opencode) · [Cline](https://cline.bot/) · [Continue](https://docs.continue.dev/) · [Goose](https://github.com/block/goose) · [Crush](https://github.com/charmbracelet/crush) · [OpenHands](https://github.com/OpenHands/OpenHands) · [SWE-agent / mini](https://github.com/SWE-agent/mini-swe-agent) · [Codex CLI](https://github.com/openai/codex) · [Gemini CLI](https://github.com/google-gemini/gemini-cli)

**Routing & proxies:** [LiteLLM](https://docs.litellm.ai/docs/simple_proxy) · [claude-code-router](https://github.com/musistudio/claude-code-router) · [OpenRouter](https://openrouter.ai/pricing) · [Claude Code Bedrock/Vertex](https://docs.anthropic.com/en/docs/claude-code/bedrock-vertex)

**Benchmarks:** [SWE-bench Verified](https://www.swebench.com/verified.html) · [SWE-bench Pro (Scale SEAL)](https://labs.scale.com/leaderboard/swe_bench_pro_public) · [Terminal-Bench 2.0](https://www.tbench.ai/leaderboard/terminal-bench/2.0) · [Aider Polyglot](https://aider.chat/docs/leaderboards/) · [SWE-rebench](https://swe-rebench.com/) · [LiveCodeBench](https://llm-stats.com/benchmarks/livecodebench)

**Models:** [Anthropic Opus 4.7](https://www.anthropic.com/news/claude-opus-4-7) · [Anthropic Sonnet 4.6](https://www.anthropic.com/news/claude-sonnet-4-6) · [OpenAI GPT-5.5](https://openai.com/index/introducing-gpt-5-5/) · [Gemini 3.1 Pro](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-pro/) · [DeepSeek V4-Pro](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro) · [Kimi K2.6](https://huggingface.co/moonshotai/Kimi-K2.6) · [GLM-5](https://huggingface.co/zai-org/GLM-5) · [Qwen3-Coder](https://qwenlm.github.io/blog/qwen3-coder/)

**Inference:** [vLLM Qwen3 recipes](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html) · [Inference provider benchmark](https://infrabase.ai/blog/ai-inference-providers-compared) · [Apple Silicon MLX guide](https://insiderllm.com/guides/best-local-llms-mac-2026/)
