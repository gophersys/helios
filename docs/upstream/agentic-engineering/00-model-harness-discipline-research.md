# 00 — Coding Tokens, Model+Harness Combinations, and the Discipline Layer

**Series:** Agentic Engineering Research (May 2026) — [README](README.md)  
**Doc:** 00 — Foundation research and recommended stack  
**Status:** Complete · **Last updated:** 2026-05-25 · **Reads in:** ~15 min  
**Depends on:** _none — start here_  
**Read next:** [01 — Software Ecology Problems at the 10x Tipping Point](01-software-ecology-problems.md)

## Summary

The model gap has closed. Claude Opus 4.7 scores 87.6% on SWE-Bench Verified; GPT-5.5 scores 88.7%. They split the harder benchmarks — Opus 4.7 leads SWE-Bench Pro 64.3% to 58.6%; GPT-5.5 leads Terminal-Bench 82.7% to 69.4%. Within ~1pp on the headline, a statistical tie.

Differentiation has moved up the stack. Hooks, skills, specs, and verification — the harness-encoded process around the model — are what stay portable as models churn ~10-20pp/year on benchmarks. The model is the least durable layer to invest in.

Recommended stack for a single developer:

- Claude Code on Max 5x ($100/mo), with Sonnet 4.6 as the workhorse and Opus 4.7 reserved for plan/review
- GitHub Spec-Kit for L2 spec-driven workflow on non-trivial features
- AGENTS.md (≤300 lines) of counter-pathology rules
- A hook stack that runs format, typecheck, secret scan, and a test-gate on each edit
- Skills files for domain capability that load on demand

A counter-intuitive 2026 finding: 200K context beats 1M for coding in most real sessions. The NoLiMa benchmark shows 11 of 12 tested models drop below 50% performance at just 32K tokens — long before the advertised 1M ceiling. Cap context aggressively. Use grep and glob for just-in-time retrieval.

Build the stack in order, not in parallel. Install the harness first. Then a minimal AGENTS.md. Then the three-hook stack. Adopt Spec-Kit when the next non-trivial feature comes up. Extract Skills as patterns repeat. The full stack is for month 3, not day 1.

---

**Context:** research into the right agentic software development setup for disciplined (non-vibe) engineering at single-developer scale.  
**Method:** four parallel research streams (Claude/Claude Code, OpenAI Codex/GPT-5, alternative harnesses, engineering-discipline patterns) synthesized into one architectural blueprint.

---

## Part 1 — Hard numbers

### Models (May 2026)

| Model | Context | Input $/M | Output $/M | Cached in | SWE-Verified | SWE-Pro | Terminal-Bench 2.0 |
|---|---|---|---|---|---|---|---|
| Claude Opus 4.7 | 1M | $5 | $25 | $0.50 | 87.6% | **64.3%** | 69.4% |
| Claude Sonnet 4.6 | 1M | $3 | $15 | $0.30 | 79.6% | — | — |
| Claude Haiku 4.5 | 200K | $1 | $5 | $0.10 | — | — | — |
| GPT-5.5 | 1.05M* | $5 | $30 | $0.50 | **88.7%** | 58.6% | **82.7%** |
| GPT-5.4 | 1M | $2.50 | $15 | — | — | — | 75.1% |
| GPT-5.3-Codex | 400K | $1.75 | $14 | $0.175 | 85.0% | 56.8% | 77.3% |
| GPT-5-Codex | 400K | $1.25 | $10 | $0.125 | — | — | — |

\* GPT-5.5 still has a >272K tier that 2× input / 1.5× output. Claude 4.6/4.7 eliminated the equivalent surcharge — flat pricing across the full 1M context.

**Notes:**
- Opus 4.7's new tokenizer eats ~1.35× more tokens for the same text → real bill goes up ~0-35% at "the same" rates
- Anthropic prompt caching: 5-min write $6.25/MTok, 1-hour write $10/MTok, cache hit $0.50/MTok (Opus)
- OpenAI batch API: 50% off; Flex tier: 50% off; Priority: 2.5×

### Subscription "coding tokens" — the real comparison

There is no single "coding tokens" metric. Both vendors meter opaquely and plan-specifically.

**Claude Code (post-May 13, 2026 50% bump, "anti-Codex" framed):**
| Plan | Monthly | 5h window | Weekly Opus (est.) | Weekly Sonnet (est.) |
|---|---|---|---|---|
| Pro | $20 | ~45 msgs | ~12h | ~60h |
| Max 5x | $100 | ~225 msgs | ~75h | ~unlimited normal use |
| Max 20x | $200 | ~900 msgs | ~300h | 240–480h |

**ChatGPT (Codex CLI access):**
| Plan | Monthly | GPT-5.3-Codex local / 5h | Cloud / 5h | Review / 5h |
|---|---|---|---|---|
| Plus | $20 | 30–150 msgs | 10–60 | 20–50 |
| Pro $100 (new Apr 2026) | $100 | ~5× Plus | ~5× | ~5× |
| Pro $200 | $200 | 600–3000 | 200–1200 | 400–1000 |

**Verdict:** At the $200 tier both are wildly cost-effective for a single dev. Claude Max 20x ≈ ~$15-25k/mo of API equivalent. ChatGPT Pro $200 ≈ similar magnitude in raw message count. The limits exist to stop arbitrage (24/7 autonomous loops), not normal use. Stop optimizing per-token cost; optimize for which harness you'll actually drive well.

---

## Part 2 — Benchmark reality check

Headline numbers (SWE-Verified within 1pp) are noise. What actually matters:

| Benchmark | Measures | Winner | Margin | Practical meaning |
|---|---|---|---|---|
| SWE-Bench Verified | Real issues, often single-file | GPT-5.5 (88.7) | +1.1pp | Statistical tie |
| **SWE-Bench Pro** | Long-horizon, multi-file, harder | **Opus 4.7 (64.3)** | +5.7pp | Opus wins on complex |
| **Terminal-Bench 2.0** | CLI agent, terminal commands | **GPT-5.5 (82.7)** | +13.3pp | Codex is more "agentic" |
| OSWorld-Verified | Desktop computer-use | Opus 4.7 (78.0) | small | Tie |
| Aider Polyglot | Cross-language refactors | Opus 4.5 (89.4) | — | Anthropic-leaning bench |

**Interpretation that fits the data:** OpenAI trained GPT-5.5 and the Codex line specifically for terminal/agentic patterns. Anthropic optimized Opus 4.7 for harder, more cognitively-demanding refactors and reasoning under multi-file context. For a disciplined setup that uses plan-then-execute, spec-driven workflows, the heavier reasoning model is more valuable than the higher-throughput terminal agent — the plan/spec phase is where senior thinking lives. Opus 4.7 edges for this purpose. (For "fire-and-forget unattended cloud agent" purposes, Codex CLI on GPT-5.5 edges.)

---

## Part 3 — Harness comparison (matters more than the model)

| Primitive | Claude Code | Codex CLI | Why it matters for discipline |
|---|---|---|---|
| Hooks | **29 events**, 4 handler types | 11 events, plugin-bundlable | Deterministic process enforcement |
| Subagents | Mature; worktree isolation; agent teams | TOML-defined; max 6 threads; sandbox-inherited | Architect/reviewer/security split |
| Skills | Progressive disclosure (3 levels); ~141k★ | Multi-tier discovery (project/user/system/built-in) | Domain capability without prompt bloat |
| MCP | Mature; stdio + streamable HTTP | v0.119+: resources, elicitations, file uploads | Tool extensibility |
| Plugins/marketplace | Spring 2026; ~101 in official directory | Marketplace launched Mar 26, 2026 (web); `codex marketplace add` shipped in v0.121.0 (Apr 11–13, 2026) | Sharing process across projects |
| Sandboxing | Worktree-based | **Seatbelt/Landlock/Windows Sandbox built-in** | Safe auto-edit |
| Scheduled/async | Routines (Apr 2026); cloud runs | **Codex Web/Cloud more polished**; Automations | Long-horizon work |
| Memory | Flat MD files indexed by MEMORY.md; CLAUDE.md tiers | `codex resume`; goals (May 2026) | Cross-session learning |
| Plan mode | First-class; Shift+Tab | "Read-only" + suggest modes | Forces explore-before-edit |

**Where they differ in spirit:**
- **Claude Code** = more mature on process primitives (more hook events, deeper Skills ecosystem, more plugins). Where a disciplined setup lives.
- **Codex CLI** = more mature on sandboxing and async (Seatbelt/Landlock built-in; Codex Web/Cloud is a more polished async story).

**Alternative harnesses worth knowing:**
- **Cursor (Composer 2.5, May 2026):** best single-IDE compromise; rules/hooks/skills/background agents; Composer 2.5 on Cursor's own Kimi-based model at ~1/10 Opus cost; three rule scopes.
- **Aider:** most disciplined OSS CLI. Architect/Editor split = plan-then-implement built in. CONVENTIONS.md is a versioned process file.
- **Roo Code** (OSS fork of Cline): Custom Modes with **scoped tool permissions** — define Architect (read-only) / Coder / Reviewer / Security as personas with hard tool restrictions. Closest thing to "discipline-enforced" OSS harness.
- **Kiro** (AWS): spec-first IDE; recent "mathematical spec-check" verifies requirements are contradiction-free *before* code. Limited model choice (Bedrock-only).
- **Plandex:** 2M-token effective context, cumulative-diff sandbox, branchable plans. Self-hosted only.
- **Devin:** async-first; Playbooks = process-as-code at the platform layer; opaque/expensive for personal use.
- **CodeRabbit / Greptile:** PR-review specialists. Greptile deeper (graph + multi-hop investigation).

---

## Part 4 — Engineering around LLM limitations

### LLM-code pathologies (from production-use research)

1. **Excessive defensive coding.** Try/catch around everything. Training rewards "runs without error"; no penalty for verbose defenses.
2. **Happy-path bias.** Beautiful golden path; error handling tacked on. Optimizes for the demo.
3. **Solving the literal problem.** "Add a button that does X" → adds a button. Senior asks "but *why*? does this conflict with pattern at line 42?"
4. **Premature DRY.** Two similar lines → instant abstraction with three parameters and a callback. Seniors wait for rule-of-three.
5. **Convention drift in long sessions.** Reinventing the same helper in three places.
6. **Reviewer over-correction.** When asked to review, LLMs flag correct code as wrong; verbose explanations *worsen* this.
7. **Unreadability lock-in.** Code becomes dense, abstract, only-LLM-readable.
8. **No forward model.** Seniors maintain "where is this code going next quarter." LLMs operate single-snapshot now.

### Encoding strategies — each maps to a harness primitive

**a) Counter-pathology rules in AGENTS.md (≤300 lines)**

Short, declarative, addressed to specific pathologies:
- "Don't add try/except unless explicitly asked or at a system boundary"
- "DRY only after three copies, not two"
- "Match existing patterns before inventing new ones — grep first"
- "Don't suppress errors — address root cause"
- "Don't add features or abstractions beyond what the task requires"

Litmus test: *would removing this rule cause a mistake?* If no, delete. Bloated CLAUDE.md/AGENTS.md causes the agent to ignore your actual instructions.

**b) Skills for domain capability (progressive disclosure)**

A skill named `<domain>-patterns` (for example `payment-flow` or `state-machine-conventions`) with metadata "use when working on the matching topic" loads only when relevant. Full SKILL.md (patterns, gotchas, examples) is in working context only during that work, not always. This is the *opposite* of stuffing CLAUDE.md with everything.

**c) Hooks as the deterministic spine**

Highest-leverage layer because hooks don't depend on prompt phrasing:
- **PostToolUse on Edit|Write:** format (Ruff/Prettier/swift-format), type-check (tsc/mypy/swiftc), secret scan (gitleaks). Output flows back so agent sees and fixes its own breakage.
- **PreToolUse on Bash:** block `rm -rf`, `git push --force` to main, dangerous codesign/notarization commands.
- **Stop hook:** enforce "tests were run" gate. Critical: check `stop_hook_active` to avoid infinite loops.
- **Block at submit, not at write** (Shankar's pattern): mid-edit blocking confuses the agent; gate at commit boundaries with non-blocking "hint hooks" in between.

**d) Spec-Driven Development at Level 2 (Spec-Kit)**

For non-trivial features:
1. `requirements.md` (EARS notation: "When X, the system shall Y")
2. `design.md` (architecture, components, interfaces)
3. `tasks.md` (work units with acceptance criteria)
4. Human approval gate
5. Implementation
6. Update spec if reality diverges (L2: bidirectional)

GitHub Spec-Kit (~106k★, agent-agnostic) is the battle-tested implementation. Early-adopter data: 3–10× first-pass success on non-trivial tasks.

**e) Writer/Reviewer separation via fresh sessions**

Session A writes failing tests for the spec; Session B (fresh context) implements code to pass them. Fresh context is essential — counter-acts pathology #6 (reviewer over-correction on own code).

**f) Verifier loops are non-negotiable**

"If you can't verify it, don't ship it." Every task ships with tests, screenshots, or scripted oracles. Anthropic's stated #1 leverage: include verification in the task so the agent can check itself.

**g) Cap context at 200K, compact at 70%**

Biggest counter-intuitive 2026 finding: **200K beats 1M for coding** in most real sessions. NoLiMa benchmark: 11/12 models drop below 50% performance at just 32K tokens. Settings:
- `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`
- `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70`

Use grep/glob for just-in-time retrieval, not file dumps.

**h) Multi-agent: use sparingly, separate roles strictly**

Cognition's "Don't Build Multi-Agents" (June 2025) critique stands for most coding work. Anthropic's own multi-agent research system needed 15× more tokens than chat.

Use sub-agents only for:
- Breadth-first exploration (preserves main context)
- Independent verification (bias-free review)
- Genuinely parallel tasks

For long-running work, adopt the **two-agent generator/evaluator** pattern (Anthropic's 2026 harness papers): one writes, one judges, context resets between sessions, state persisted to disk via `progress.txt` + `feature_list.json` + meaningful git commits.

---

## Part 5 — The architectural blueprint

```
LAYER 6: REVIEW / PR LOOP        ← CodeRabbit / Greptile / cross-tool reviewer
LAYER 5: VERIFICATION SPINE      ← tests, type-check, format, secret scan
LAYER 4: PROCESS / SPECS         ← Spec-Kit, AGENTS.md, plan mode
LAYER 3: DOMAIN CAPABILITY       ← Skills (one per domain the agent works in)
LAYER 2: DETERMINISTIC HOOKS     ← PostToolUse format/typecheck; Stop test-gate
LAYER 1: HARNESS                 ← Claude Code (preferred) / Codex CLI
LAYER 0: MODEL                   ← Opus 4.7 for plan/review; Sonnet 4.6 for grunt
```

**The model (L0) is the least differentiating layer right now. Discipline (L2-L5) is where the leverage is.**

### Why this layering matters for "tomorrow's software"

Models will improve ~10-20pp/year on benchmarks. Harnesses will commoditize (Claude Code and Codex CLI are already feature-converging). The durable investment is **L2-L5: hooks, skills, specs, verification.** That stack is mostly portable — Spec-Kit works across agents; AGENTS.md is standardizing across OpenAI/Google/Anthropic/Sourcegraph/Cursor/Factory; hooks are conceptually similar across tools.

### Near-term future (next 6-12 months)

**Likely to shift:**
- Cross-tool standardization continues. AGENTS.md, MCP, skills converging into a portable layer
- Specs become source. Tessl/L3 (spec is canonical, code generated) is the next frontier; Spec-Kit at L2 today, L3 in 12-18 months
- Verification gets richer. Playwright-based UI evaluation, audio/video oracles, perf-regression gating
- Sonnet-tier becomes the default. 1.2pp from Opus 4.6 on SWE-Verified at 1/5 cost
- Context windows stop being the bragging point. 200K-beats-1M is now widely known
- Async/cloud agents default for non-interactive work; local CLI stays for interactive design/debug

**Not going to change:**
- LLM pathologies (defensive coding, happy-path bias, premature DRY) — training-distribution artifacts. Bigger models don't fix them.
- Verification stays expensive
- Human judgment on architecture remains the bottleneck

---

## Part 6 — Recommendation

At single-developer scale:

### Primary stack
1. **Claude Code on Max 5x ($100/mo)** as primary CLI
2. **GitHub Spec-Kit** for L2 spec-driven workflow on non-trivial features
3. **AGENTS.md (≤300 lines)** with counter-pathology rules + project-specific gotchas
4. **Skills**: one per domain the agent works in; extract as patterns repeat (don't pre-create)
5. **Hook stack**: PostToolUse format/typecheck/secret-scan; PreToolUse dangerous-bash block; Stop test-gate (with `stop_hook_active` guard)
6. **Verification spine**: language-appropriate test frameworks (unit + integration); visual / output / golden-file fixtures for code that's hard to unit-test

### Secondary (optional, high-leverage)
7. **Codex CLI on Plus ($20/mo)** as second-opinion layer (cross-model bias-free review beats same-model)
8. **CodeRabbit (free public / $15 private)** for PR-review discipline even when solo

### Setup order (don't build everything day 1)
1. Install Claude Code, subscribe Max 5x
2. Write a minimal AGENTS.md (grow from observation, not anticipation)
3. Add the 3-hook stack (format/typecheck, dangerous-bash block, stop-test-gate)
4. Adopt Spec-Kit for next non-trivial feature
5. Extract domain knowledge into Skills as patterns repeat
6. Add Codex CLI Plus for second opinions after the above is solid

**Litmus for every addition:** *does this make my code more maintainable in 6 months, or is it ceremony?*

### Why not the alternatives?
- **Codex CLI as primary:** tempting (better Terminal-Bench, more aggressive usage at $200), but hook + skill + plugin ecosystem is 6-12 months ahead on Claude Code. Discipline layer matters more than raw model.
- **Cursor:** best for IDE-pair flow; harder to enforce strict process via hooks (improving). Better for real-time pair coding over agentic delegation.
- **Aider:** best OSS choice; consider if you want zero subscription lock-in and BYOK. Less feature-complete on subagents/skills.
- **Devin:** too async-heavy and opaque for personal dev; better for teams with platform-enforced governance.
- **Kiro:** excellent spec-first but Bedrock-only. Pilot in 6-12 months if Spec-Kit feels limiting.

### Future-proofing — invest in
- Discipline stack (hooks, skills, specs, verification) — portable across model/harness churn
- AGENTS.md over CLAUDE.md (cross-vendor standard)
- MCP over harness-specific integrations
- Spec-Kit L2 → likely upgrades smoothly to L3 (spec-as-source) when tooling matures

### Don't over-invest in
- Vendor-specific plugin marketplaces (they'll fragment)
- 1M context strategies (smaller working sets is the trend)
- Multi-agent orchestration beyond two-agent generator/evaluator

---

## Sources

**Models & pricing:**
- [Anthropic pricing docs](https://platform.claude.com/docs/en/about-claude/pricing)
- [Opus 4.7 release notes](https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7)
- [CloudZero API pricing 2026](https://www.cloudzero.com/blog/claude-api-pricing/)
- [OpenAI Codex pricing](https://developers.openai.com/codex/pricing)
- [GPT-5.5 model card](https://developers.openai.com/api/docs/models/gpt-5.5)
- [GPT-5-Codex model card](https://developers.openai.com/api/docs/models/gpt-5-codex)

**Subscription limits:**
- [Anthropic Max plan](https://support.claude.com/en/articles/11049741-what-is-the-max-plan)
- [Pillitteri May 2026 limits update](https://pasqualepillitteri.it/en/news/2494/claude-code-weekly-limits-50-percent-anti-codex-anthropic-2026)
- [Truefoundry limits guide](https://www.truefoundry.com/blog/claude-code-limits-explained)
- [ChatGPT pricing](https://chatgpt.com/pricing/)
- [VentureBeat Pro $100 launch](https://venturebeat.com/orchestration/openai-introduces-chatgpt-pro-usd100-tier-with-5x-usage-limits-for-codex)
- [Codex limits digest](https://blog.laozhang.ai/en/posts/openai-codex-usage-limits)

**Benchmarks:**
- [SWE-Bench leaderboard May 2026](https://www.marc0.dev/en/leaderboard)
- [Vellum Opus 4.7 benchmarks](https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained)
- [MindStudio GPT-5.5 vs Opus 4.7](https://www.mindstudio.ai/blog/gpt-55-vs-claude-opus-47-coding-comparison)
- [TokenMix GPT-5.5 review](https://tokenmix.ai/blog/gpt-5-5-spud-review-88-swe-bench-2026)

**Harness features:**
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- [Claude Code best practices](https://code.claude.com/docs/en/best-practices)
- [Hidekazu Konishi 2026 reference](https://hidekazu-konishi.com/entry/claude_code_features_settings_reference_2026.html)
- [Codex CLI features](https://developers.openai.com/codex/cli/features)
- [Codex hooks](https://developers.openai.com/codex/hooks)
- [Codex subagents](https://developers.openai.com/codex/subagents)
- [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md)
- [Cursor rules](https://cursor.com/docs/context/rules)
- [Cursor Composer 2.5 launch](https://cursor.com/blog/composer-2-5)
- [Aider docs](https://aider.chat/docs/)
- [Roo Code docs](https://docs.roocode.com/)
- [Windsurf pricing 2026](https://www.verdent.ai/guides/windsurf-pricing-2026)
- [Devin pricing](https://devin.ai/pricing/)
- [Kiro](https://kiro.dev/)

**Engineering discipline / patterns:**
- [Anthropic: Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic: Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Anthropic: Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Anthropic: Harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Cognition: Don't Build Multi-Agents](https://cognition.ai/blog/dont-build-multi-agents)
- [Martin Fowler: Spec-Driven Development tools](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)
- [GitHub Spec-Kit](https://github.com/github/spec-kit)
- [Ronacher on plan mode](https://lucumr.pocoo.org/2025/12/17/what-is-plan-mode/)
- [Shankar: how I use every Claude Code feature](https://blog.sshh.io/p/how-i-use-every-claude-code-feature)
- [Willison year-in-LLMs 2025](https://simonwillison.net/2025/Dec/31/the-year-in-llms/)
- [Sikkema: smaller context window, better Claude Code](https://albertsikkema.com/ai/development/tools/2026/04/23/smaller-context-window-better-claude-code.html)
- [Why LLMs write horrible code](https://noenthuda.substack.com/p/why-llms-write-horrible-code)
- [Dzombak: getting good results from Claude Code](https://www.dzombak.com/blog/2025/08/getting-good-results-from-claude-code/)
