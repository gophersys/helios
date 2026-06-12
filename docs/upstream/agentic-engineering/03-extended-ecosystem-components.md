# 03 — Extending the Ecosystem Diagram

**Series:** Agentic Engineering Research (May 2026) — [README](README.md)  
**Doc:** 03 — 8 defended additions to Bender's graph (25 nodes, ~75 edges)  
**Status:** Complete · **Last updated:** 2026-05-25 · **Reads in:** ~12 min  
**Depends on:** [02 — Developer Ecosystem: Components, Connections, and What Bender Said About Each](02-ecosystem-components-and-connections.md)  
**Read next:** _Forthcoming: 04 architectural validation, 05 three-tier scalable design, 06 parallel-dev contracts, 07 verification strategy_

## Summary

This document adds eight nodes to Bender's diagram, each defended against a specific 10x failure mode he named: Spec/Requirements, Knowledge/Skills repository, Hook/Policy spine, Agent memory, Code intelligence/Semantic index, MCP/Tool layer, Dependency/Supply chain, and Human/Approval gate.

Nine other candidates were rejected with explicit reasons — cost mgmt, secrets, IDE, telemetry, storage, eval, docs, compute orchestration, and agent-to-agent communication. The cohesion test: would removing this cause a specific 10x failure Bender named? If no, don't add.

The biggest structural change is the agentic harness. It was degree 3 in Bender's original diagram and degree 9 in the extension. The harness is now the center of mass. Picking the right one (Claude Code vs Codex CLI vs Cursor) becomes the highest-leverage architectural decision in the stack.

Two new spines emerge. Hooks are the deterministic, token-free enforcement spine. Knowledge/Memory is the model-readable context spine. Both are required. Hooks without knowledge produce a rigid agent; knowledge without hooks produces an advisory one.

One insight only becomes visible in the extended graph: Token mgmt edges do not touch the Hooks spine. That's deliberate — the "no load-bearing token engines" rule from doc 01, made geometric. Anything safety-critical routes through hooks, not through agents that pay tokens to act.

Adding Spec/Requirements completes a verification triangle with Code review and Testing tools. Bender's graph had only two corners. L2 spec-driven development (Spec-Kit) works because the third corner is finally there.

The solution shape that follows: three concentric rings. The inner ring is the AI runtime (harness + hooks + knowledge + memory + context/token + MCP). The middle ring is the artifacts the runtime produces and consumes (spec + code + tests + deps). The outer ring is the delivery and observation surface (build/test/release + review + observability + human approval). Design inward-out; skipping inward is what produces the vibe-coding outcome.

---

**Purpose:** Bender's diagram captures the *traditional dev ecosystem with AI-era nodes bolted on* (Agentic harness, Context mgmt, Token mgmt). For a disciplined agentic setup, several load-bearing nodes are missing or only implicit in his talk. This document extends his graph with **8 additional nodes** — each defended explicitly. No bloat: things I considered but rejected are listed at the end.

Builds on:
- [01 — Software ecology problems](01-software-ecology-problems.md)
- [02 — Ecosystem components and connections](02-ecosystem-components-and-connections.md)

---

## The diagnostic question

For each candidate addition, ask: **"Would removing this from a disciplined agentic setup cause a specific failure mode that Bender flagged as a 10x problem?"**

- Yes → add the node.
- No → it's nice-to-have, not load-bearing; reject.

Eight additions pass this test. Each one is mapped to (a) a Bender failure mode it addresses, (b) concrete tooling that realizes it, and (c) its specific connections in the extended graph.

---

## The 8 additions

### A. Spec / Requirements layer

| | |
|---|---|
| **One-line definition** | Versioned, machine-readable description of *what the system should do*, distinct from the code that does it. |
| **Why missing from Bender** | His diagram nodes "what we produce" but has no node for "what we're trying to produce." He talks about decisions and trade-offs but the *artifact* of intent isn't shown. |
| **Failure if absent** | "Solving the literal problem, not the actual one" (LLM pathology #3); no way to detect drift between intent and implementation; review has nothing to check against; 10x more code means 10x more drift from unstated intent. |
| **Concrete tooling** | GitHub Spec-Kit, Kiro, Tessl; `requirements.md` in EARS notation, `design.md`, `tasks.md`. |
| **Edges** | → Source code (implementation target), Code review (review against spec), Testing tools (acceptance tests bind to requirements), Knowledge/Skills (spec uses framework conventions), Agentic harness (agent reads spec, writes code), Human/Approval (spec is the human-decision artifact) |

### B. Knowledge / Skills repository

| | |
|---|---|
| **One-line definition** | Authored, versioned, on-demand-loadable codification of conventions, patterns, and "how things are done here." |
| **Why missing from Bender** | He literally asks "where are your engineering practices documented?" — and his diagram has no node for the answer. Frameworks ≠ conventions; Static analysis ≠ patterns. Conventions live in prose. |
| **Failure if absent** | Convention drift in long sessions (LLM pathology #5); agents reinventing the same helper in three places; no way to scale senior intuition to junior + agents. Bender's mentorship-gap problem (14.x) is unsolvable without this. |
| **Concrete tooling** | `AGENTS.md` (project), `.claude/skills/*/SKILL.md`, `CONVENTIONS.md` (Aider), Cursor rules in `.cursor/rules/`. Progressive disclosure: name in system prompt, full content only when relevant. |
| **Edges** | → Agentic harness (skills are loaded on demand), Frameworks (knowledge codifies framework usage), Source code (conventions describe how code should look), Static analysis (knowledge informs lint rules), Code review (reviewer checks against conventions), Spec (spec templates live in knowledge) |

### C. Hook / Policy spine

| | |
|---|---|
| **One-line definition** | Deterministic, model-free enforcement layer that fires automatically on lifecycle events (file write, commit, tool use, session end). |
| **Why missing from Bender** | He preaches "automation over toil" and warns against "load-bearing token engines" — but his diagram has no node for the automation that ISN'T behind a token budget. Hooks are the answer to "what's your safety net when the agent runs out of tokens?" |
| **Failure if absent** | Rules in AGENTS.md become advisory (LLM follows them ~80% of the time); load-bearing safety put behind agents (Bender's 11.7); no way to enforce "tests were run" or "no secrets committed" without trusting the model. |
| **Concrete tooling** | Claude Code hooks (29 events: PostToolUse, PreToolUse, Stop, etc.); Codex hooks (11 events); pre-commit; ruff/prettier/swift-format auto-runs; gitleaks. |
| **Edges** | → Source code (PostToolUse on Edit/Write), Version control (pre-commit), Agentic harness (intercepts tool use), Build compute (triggers format/typecheck on edit), Static analysis (invokes lint), Testing tools (Stop hook test gate), Code review (gates at commit boundary) |

### D. Agent memory (cross-session state)

| | |
|---|---|
| **One-line definition** | Durable, *learned* state persisted between sessions — distinct from authored knowledge. |
| **Why missing from Bender** | His "Context mgmt" node is per-session. He has no node for "what survives when the session ends." Without this, every session starts from zero re: project history, preferences, prior decisions. |
| **Failure if absent** | "No one understands the codebase" (4.6 from Bender) becomes "even the agent forgets between sessions"; same questions re-asked; same mistakes re-made; the mentorship gap (14.x) widens. |
| **Concrete tooling** | Claude Code auto-memory (`~/.claude/projects/<workspace>/memory/`, indexed by `MEMORY.md`); Codex `codex resume` + goals; Cline Memory Bank pattern. |
| **Edges** | → Agentic harness (loaded on session start), Context mgmt (memory consumes context budget), Source code (memory references files), Knowledge/Skills (memory may link to skills), Spec (memory may link to spec sections) |

### E. Code intelligence / Semantic index

| | |
|---|---|
| **One-line definition** | Whole-repository semantic understanding — symbols, references, call graph, type relationships — queryable as a first-class tool. |
| **Why missing from Bender** | He has Static analysis (per-file lint) and Frameworks (libraries) but no node for *whole-repo semantic search*. His "agents writing all the code → who paying attention to the codebase" (4.6) and "dependency graph grows quadratically" (5.3) both require an index, not just file-by-file analysis. |
| **Failure if absent** | Agents grep-walk the codebase token-by-token instead of querying a graph; quadratic blowup of investigation costs; cross-language refactors miss callers; "convention drift" goes undetected because there's no semantic comparison surface. |
| **Concrete tooling** | Sourcegraph, Greptile, tree-sitter symbol maps (Aider, Plandex), LSP-backed indexers. For multi-language projects: one language server per language, plus a unifying cross-language index. |
| **Edges** | → Source code (indexes source), Agentic harness (provides queries / symbol lookup as a tool), Code review (review surfaces semantic impact), Static analysis (overlap, different scope), Frameworks (indexes framework code too) |

### F. MCP / Tool integration layer

| | |
|---|---|
| **One-line definition** | The set of external tool servers the agent can call — distinct from the harness that runs the agent. |
| **Why missing from Bender** | His Agentic harness node treats agent + tools as one. But MCP servers are separate processes with separate lifecycles, auth, and costs. Skipping this node hides the API-surface-as-attack-surface problem he raises in 10.x. |
| **Failure if absent** | "All internal APIs effectively just became public" (10.x) is invisible if you don't model the layer that exposes them to the agent. Token costs from MCP calls are unaccounted for. No clean way to swap tool implementations. |
| **Concrete tooling** | MCP stdio + streamable-HTTP servers; `~/.codex/config.toml`, `.claude.json` `mcpServers`. Common choices: filesystem MCP, source-control MCP (GitHub/GitLab), domain-specific MCP servers built for the project. |
| **Edges** | → Agentic harness (harness orchestrates MCP), Production compute (MCP may call prod APIs), Security infra (MCP needs auth/permissions), Token mgmt (MCP responses consume tokens), Dependency/Supply chain (MCP servers are third-party code with supply chain implications) |

### G. Dependency / Supply chain

| | |
|---|---|
| **One-line definition** | Third-party packages, their transitive closure, lockfiles, and provenance. |
| **Why missing from Bender** | His Frameworks node is "what we adopt." He doesn't node "what we pull in." With agents adding deps at 10x rate, supply chain becomes a security AND maintenance node. His "APIs become public" warning (10.x) has a sibling: "deps become a malware surface." |
| **Failure if absent** | Agents add packages without scrutiny; supply-chain attacks land via auto-suggested deps; lockfile churn becomes review-illegible; version pinning drifts; license compliance breaks. |
| **Concrete tooling** | Package-manager-native scanners (npm + `npm audit`, pip + pip-audit, Cargo + cargo-audit, etc.); Snyk / Renovate for cross-ecosystem updates; Socket.dev or similar for supply-chain provenance; SBOM generation. |
| **Edges** | → Source code (deps imported in code), Build tools (build resolves deps), Build compute (deps inflate build time), Security infra (supply chain scanning), Version control (lockfiles tracked), MCP/Tool layer (MCP servers are deps too) |

### H. Human / Approval layer

| | |
|---|---|
| **One-line definition** | The synchronous human-in-the-loop layer: plan approvals, permission requests, release gates, design reviews. |
| **Why missing from Bender** | He says "human attention is the most precious resource" — but his diagram doesn't node it. For a single-developer setup this is THE bottleneck and must be modeled explicitly to be budgeted. |
| **Failure if absent** | "We can now create more trouble than we can pay attention to" (15.x) goes unmeasured; approval becomes either ceremony (always yes) or paralysis (gridlock); agents act faster than human review cadence. |
| **Concrete tooling** | Claude Code plan mode, PermissionRequest hooks; Codex approval modes (Read-only / Auto / Full Access); GitHub PR approvals; Spec-Kit approval gates between phases. |
| **Edges** | → Spec (humans approve specs at L2 gates), Code review (humans approve PRs), Release tooling (humans approve deploys), Agentic harness (plan mode, permission prompts), Observability (humans watch the dashboards) |

---

## Things I considered but rejected

These were candidates but didn't pass the diagnostic question — they're nice-to-have, not load-bearing, OR they fold cleanly into an existing node.

| Candidate | Why rejected |
|---|---|
| **Cost / Budget management** | Folds into Token mgmt. Bender's "load-bearing token engines" warning is already covered. Splitting it gains no insight at single-dev scale. |
| **Configuration / Secrets management** | Folds into Security infra. At single-developer scale, `.env` + OS keychain + a secrets manager cover it; not a distinct ecosystem layer. |
| **IDE / local dev environment** | Important for UX, but it's a UI surface on top of the existing nodes — not its own ecosystem component. (If the agent took the IDE over completely, this might earn a node. Not there yet.) |
| **Telemetry / Audit log** | Extension of Observability. Bender's Observability node already covers "what happened" — agent telemetry is just another input to the same hub. |
| **Data store / Storage** | Application-specific (not part of the *dev* ecosystem). Belongs in product architecture, not ecology. |
| **Evaluation / Benchmarking** | Operates on the stack as a whole, not within it. A meta-layer worth designing for *after* the stack is in place. |
| **Documentation generation** | Folds into Knowledge/Skills. Generated docs are an output, not a node — they live in the same surface as authored knowledge. |
| **Compute orchestration** | Already covered by Build compute / Test compute / Production compute. Adding a generic node doesn't help. |
| **Agent-to-agent communication** | Premature — multi-agent is mostly anti-pattern per Cognition (and per our [01 doc](01-software-ecology-problems.md) analysis). Don't node things you're explicitly avoiding. |

---

## The extended graph

### Updated adjacency (new edges only)

```
Spec / Requirements   — Source code
Spec / Requirements   — Code review
Spec / Requirements   — Testing tools
Spec / Requirements   — Knowledge / Skills
Spec / Requirements   — Agentic harness
Spec / Requirements   — Human / Approval

Knowledge / Skills    — Agentic harness
Knowledge / Skills    — Frameworks
Knowledge / Skills    — Source code
Knowledge / Skills    — Static analysis
Knowledge / Skills    — Code review

Hook / Policy spine   — Source code
Hook / Policy spine   — Version control
Hook / Policy spine   — Agentic harness
Hook / Policy spine   — Build compute
Hook / Policy spine   — Static analysis
Hook / Policy spine   — Testing tools
Hook / Policy spine   — Code review

Agent memory          — Agentic harness
Agent memory          — Context mgmt
Agent memory          — Source code
Agent memory          — Knowledge / Skills

Code intelligence     — Source code
Code intelligence     — Agentic harness
Code intelligence     — Code review
Code intelligence     — Static analysis
Code intelligence     — Frameworks

MCP / Tool layer      — Agentic harness
MCP / Tool layer      — Production compute
MCP / Tool layer      — Security infra
MCP / Tool layer      — Token mgmt
MCP / Tool layer      — Dependency / Supply chain

Dependency / Supply   — Source code
Dependency / Supply   — Build tools
Dependency / Supply   — Build compute
Dependency / Supply   — Security infra
Dependency / Supply   — Version control

Human / Approval      — Code review
Human / Approval      — Release tooling
Human / Approval      — Agentic harness
Human / Approval      — Observability
```

**~40 new edges across 8 new nodes.** Combined with the original 35 → ~75 edges across 25 nodes. Average degree rises from ~4 to ~6.

### How the hub map shifts (degree, descending)

| Node | Original | Extended | Notes |
|---|---|---|---|
| Agentic harness 🆕 | 3 | **9** | From peripheral to *central hub*. Connects to harness extensions (MCP, hooks, memory, knowledge) and process artifacts (spec). This is the new center of mass. |
| Source code | 5 | **9** | Stays a root, but more entry-points to it (spec, knowledge, code intelligence, hooks, deps). |
| Code review | 6 | **9** | Reinforced as the quality hub — now also fed by spec, knowledge, code intelligence, hooks, human approval. |
| Observability | 6 | 7 | Slight increase (human approval feeds it). Still high. |
| Release tooling | 6 | 7 | Adds Human/Approval. |
| Hook / Policy spine 🆕 | — | **7** | New high-leverage node. Touches edit path, commit path, agent path. |
| Knowledge / Skills 🆕 | — | **6** | Codified intuition; rich connections. |
| Token mgmt | 5 | 6 | Adds MCP. Stays transversal. |
| Spec / Requirements 🆕 | — | **6** | The new upstream. |
| Dependency / Supply 🆕 | — | **6** | New cross-cutting concern. |
| Frameworks | 3 | 5 | Gains Knowledge + Code intelligence. |
| Static analysis | 4 | 6 | Gains Knowledge + Hooks + Code intelligence. |
| MCP / Tool layer 🆕 | — | 5 | New extension surface. |
| Agent memory 🆕 | — | 4 | Modest hub but load-bearing. |
| Code intelligence 🆕 | — | 5 | New navigation surface. |
| Human / Approval 🆕 | — | 5 | New gating layer. |
| (others unchanged) | | | |

### Suggested visual layout (layer-based)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PROCESS / INTENT LAYER                                                       │
│   ┌──────────────────┐         ┌─────────────────┐                          │
│   │  Spec /          │◄────────│  Human /        │                          │
│   │  Requirements    │         │  Approval        │                          │
│   └────────┬─────────┘         └────────┬─────────┘                          │
└────────────┼────────────────────────────┼──────────────────────────────────┘
             │                            │
┌────────────┼────────────────────────────┼──────────────────────────────────┐
│ KNOWLEDGE  │ + MEMORY LAYER             │                                   │
│   ┌────────▼────────┐  ┌───────────────┐                                    │
│   │  Knowledge /     │  │  Agent        │                                    │
│   │  Skills          │  │  memory        │                                    │
│   └────────┬─────────┘  └────────┬──────┘                                    │
└────────────┼─────────────────────┼─────────────────────────────────────────┘
             │                     │
┌────────────┼─────────────────────┼─────────────────────────────────────────┐
│ AI RUNTIME LAYER                  │                                          │
│   ┌────────▼─────────┐  ┌────────▼──────┐  ┌──────────┐  ┌──────────┐      │
│   │  Agentic         │◄─┤  Context      │◄─┤  Token   │  │  MCP /   │      │
│   │  harness         │  │  mgmt          │  │  mgmt    │◄─┤  Tools   │      │
│   └────────┬─────────┘  └───────────────┘  └────┬─────┘  └─────┬────┘      │
└────────────┼──────────────────────────────────────┼──────────────┼──────────┘
             │                                       │              │
┌────────────┼───────────────────────────────────────┼──────────────┼─────────┐
│ DETERMINISTIC SPINE                                 │              │         │
│   ┌────────▼─────────┐                              │              │         │
│   │  Hook /          │──────────────────────────────┘              │         │
│   │  Policy spine    │                                              │         │
│   └────────┬─────────┘                                              │         │
└────────────┼────────────────────────────────────────────────────────┼─────────┘
             │                                                        │
┌────────────┼────────────────────────────────────────────────────────┼─────────┐
│ CODE + BUILD + TEST LAYER                                            │         │
│ ┌──────────▼──────┐ ┌──────────────┐ ┌────────────┐ ┌────────────┐ │         │
│ │ Source code     │ │ Frameworks    │ │ Static     │ │ Code       │ │         │
│ │                 │ │              │ │ analysis    │ │ intel       │ │         │
│ └─────────┬───────┘ └──────────────┘ └────────────┘ └────────────┘ │         │
│           │                                                          │         │
│ ┌─────────▼────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────┐    │         │
│ │ Build tools  │ │ Build compute │ │ Testing  │ │ Testing       │    │         │
│ │              │ │              │ │ tools 🟢 │ │ compute 🟢    │    │         │
│ └──────────────┘ └──────────────┘ └──────────┘ └──────────────┘    │         │
│           ┌──────────────┐ ┌────────────────────┐                   │         │
│           │ Version      │ │ Dependency / Supply │◄──────────────────┘         │
│           │ control 🟢   │ │ chain               │                             │
│           └──────────────┘ └────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────────┘
             │
┌────────────┼─────────────────────────────────────────────────────────────────┐
│ DELIVERY + RUNTIME LAYER                                                      │
│ ┌──────────▼──────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐ ┌─────────┐│
│ │ Code review     │ │ Release  │ │ Security   │ │ Production    │ │ Exp.    ││
│ │                 │ │ tooling  │ │ infra      │ │ compute       │ │ infra   ││
│ └─────────────────┘ └──────────┘ └────────────┘ └──────────────┘ └─────────┘│
│                                  ┌─────────────────────┐                      │
│                                  │  Observability       │                      │
│                                  └─────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

(Layout is conceptual — exact edges are in the adjacency list above. Key insight: the **AI runtime layer** is bridged to everything else via **two spines** — Hooks for deterministic enforcement, Knowledge/Memory for context.)

---

## Structural insights from the extended graph

1. **Agentic harness is now the highest-degree node (9).** That matches reality: in an AI-era dev environment, the harness is what touches everything. Bender's original diagram understated this by giving it only 3 edges. **Implication:** harness choice (Claude Code vs Codex CLI vs Cursor) is the highest-leverage decision in the stack.

2. **Two new spines emerge: Hooks and Knowledge/Memory.** They sit *between* the harness and the rest of the system.
   - **Hooks = enforcement spine** (deterministic, no tokens, fast). What you wire to *guarantee* behavior.
   - **Knowledge/Memory = context spine** (loaded on demand, model-readable). What you wire to *teach* behavior.
   - Both are necessary. Hooks without knowledge = rigid agent. Knowledge without hooks = advisory agent.

3. **Spec → Code review → Testing tools forms a verification triangle.** Each side of the triangle checks against another. Without Spec as a node, this triangle has only two corners and review/testing have nothing to align to. The L2 spec-driven pattern works because it completes this triangle.

4. **Human/Approval is purposefully low-degree (5).** Good — humans should be a gating layer at well-defined points, not a touchpoint at every node. The 5 edges are exactly the right ones: Spec (intent), Code review (quality), Release (delivery), Agentic harness (plan mode), Observability (situational awareness).

5. **The "load-bearing token engine" anti-pattern becomes visible.** Token mgmt edges go to Build compute, Code review, Testing compute, Observability, Context mgmt, MCP — but **NOT** to Hook / Policy spine. That's the design rule: hooks are token-free. Anything safety-critical must route through hooks, not through token-paying agents.

6. **Dependency / Supply chain is the most under-modeled risk surface.** Connected to Source code, Build, Security, VCS, AND MCP — but typically gets no dedicated tooling at single-developer scale. For projects spanning multiple package ecosystems, this is often the node most likely to fail silently (a transitive dep gets compromised; a system package shifts under you).

7. **Code intelligence is the bottleneck for "intellectual control."** Bender's open question — can humans still reason about the system? — depends on having a queryable semantic surface. Static analysis isn't enough (it's per-file). For agents *and* humans to navigate growing codebases, this node has to exist.

8. **Observability connects to Human/Approval but Hooks do not.** Subtle but important: humans need awareness (Observability) before they can approve (Human/Approval). Hooks bypass humans entirely — they enforce policy without asking. That asymmetry is the whole point of the deterministic spine.

---

## Preview: how this shapes the solution

The extended graph suggests the solution doc should be organized as **three concentric rings**:

- **Inner ring (the AI runtime):** Agentic harness + Hooks + Knowledge/Memory + Context/Token mgmt + MCP. This is what you install and configure first.
- **Middle ring (the artifacts):** Spec + Source code + Tests + Dependencies. This is what you produce and version.
- **Outer ring (the delivery + observation):** Build/Test/Release + Code review + Observability + Human approval. This is what gates and measures.

Each ring should be designed before the next: install the runtime, then define the artifact discipline, then wire the delivery loop. Skipping inward (e.g., picking deploy tools before defining hook policy) is what causes the "vibe coding" outcome.

---

Ready for task 4 (or whatever comes next).
