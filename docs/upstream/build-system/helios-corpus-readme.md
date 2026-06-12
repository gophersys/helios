# Helios Agentic Build-System — Corpus Index & Cohesion Contract

> **Read this first.** Every doc and every agent that touches this corpus answers to the contract
> below: the layering, the single-source-of-truth map, and the cross-doc **invariants**. The point
> is correctness and cohesiveness *from the start* — when you change a shared concept, you change it
> at its canonical home and check the invariants, so the corpus can't silently drift.
>
> **How to use:** this is a *lookup*, not a read-through — jump to the table you need (§3 reading
> order, §4 source-of-truth map, §5 invariants). Don't read it cover-to-cover.
>
> Status: living. Last cohesion pass **2026-06-01** (two-tree review + fixes; see §8).

---

## 1. What this corpus is

The **agentic build-system** thread: tooling and methodology for a world where a *strong* model
designs a spec and a *cheap* model implements it under verification. It spans **two trees**, by
design and by ownership:

- **`Documents/Claude/Projects/Helios/`** (this folder) — the build-system: market → schema →
  library → spec-driven implementation. *This README owns these.*
- **`Documents/research/agentic-engineering/`** — the research substrate: the discipline-layer
  thesis, Bender's failure modes, and the universal SDLC spine. *Owned by its own
  [README](../../../research/agentic-engineering/README.md); we reference it, we don't restate it.*

Related but **separate**: `/Users/mateo/helios/HELIOS.md` (the product charter — the CDE that would
*consume* this), and the UI design-system thread (the `photosphere` repo). This corpus is the
*how-we-build*, not the product.

---

## 2. The map (layering — lower never depends on higher)

```
   research/agentic-engineering/                  ← WHY + the process spine (substrate)
     00 discipline-layer thesis · 01 failure modes · 02/03 ecosystem
     04  universal SDLC spine (10 phases, 5 disciplines, product altitude)
     04a stress test → H1′ (spine + per-category parameter vector + topology selector)
                                   │ feeds
                                   ▼
   Claude/Projects/Helios/        ← WHAT we build, concretely
     agentic-coding-landscape  →  the market (harnesses, models, benchmarks)   [directional]
     portable-agent-config     →  the agents.yaml schema → 10 harnesses' configs
     agentcfg-architecture     →  the Go library: schema → immutable IR → compile + route
     spec-driven-implementation-system → the "how": spec+template+TDD+Evidence ABOVE agentcfg
```

**Read in this order.** Nothing lower re-derives a claim that lives higher; it links to it (§4).

---

## 3. Reading order by goal

| Your goal | Read |
|---|---|
| **Start the v0.1 Go build** | `spec-driven §10` → `agentcfg-architecture` → this README §5 (invariants) |
| Understand the architecture of the "how" | `spec-driven` (whole) |
| Configure / compile harness configs | `portable-agent-config` |
| Understand *why* this shape (discipline layer, SDLC spine) | agentic-engineering `README` → `04` → `04a` |
| Pick / route models | `agentic-coding-landscape` (treat numbers as directional — Invariant I2) |

---

## 4. Single source of truth (concept → canonical home → who references it)

Change a concept **only** at its canonical home; update referencers via link. Drift = a concept
edited in two places.

| Concept | Canonical home | Also referenced in |
|---|---|---|
| agentcfg scope (config/routing/LLM-call only) | `agentcfg-architecture §1, §19` | spec-driven §3 |
| `agents.yaml` schema | `portable-agent-config §2` | agentcfg-architecture §12 |
| Per-harness native config + capability matrix | `portable-agent-config §3, §4` | landscape Part 5 |
| Routing Kinds (`think`/`default`/`background`/`longContext`/`webSearch`) | `agentcfg-architecture §9` | portable-config §3; spec-driven §1 |
| **Evidence** (implementable interface) | `spec-driven §4` | doc 04 Part IV (currency form); 04a Part 3 (widening) |
| Gate as policy over Evidence | `spec-driven §5` | doc 04 Part III/IV |
| The four senses of "harness" | `spec-driven §2` | doc 04 Part III/VI; agentcfg §7 |
| Inner/outer test loop + clean-env | `spec-driven §2` | landscape Part 4 (reward-hack) |
| coding-harness vs test-harness + port mapping | `spec-driven §2, §8` | doc 04 Part III, X |
| Two IRs (Resolved static / run-state mutable) | `spec-driven §3` | agentcfg §5, §16 |
| Spec = {Contract, Template, Tests, Gate} | `spec-driven §1, §8` | doc 04 Part IV |
| Template factoring (envelope + per-cell plugin) | `spec-driven §7` | doc 04 Part XII (cells); 04a Part 2 |
| Spec-determinacy metric (+ mutation score) | `spec-driven §6` | — |
| Bootstrap kernel + order | `spec-driven §8` | — |
| v0.1 cut (web/Go) | `spec-driven §10` | this README §5 (I11) |
| Universal SDLC spine (10 phases) | `doc 04 Part III` | spec-driven (instantiates Specify/Author/Exercise/Gate) |
| **H1′** (spine + parameter vector + topology selector) | `doc 04a` | doc 04 Part II (H1, now superseded) |
| Fidelity ladder (our coinage) | `doc 04 Part V` | spec-driven §10 |
| Two altitudes / recursion | `doc 04 Reframe B, Part VII` | spec-driven §8, §10 (deferred to end-state) |
| Provenance triple | `doc 04 Part IX` | — |
| Model landscape (directional) | `landscape` (whole) | agentic-eng 00 |

---

## 5. Cross-corpus invariants (the contract — these MUST hold)

Every conflict the cohesion review found was a violated invariant. When you touch a doc, check these.

- **I1 — Layering & scope.** Order is landscape → portable-config → agentcfg → spec-driven, atop the
  doc 04/04a spine. Lower layers never depend on higher. **`agentcfg` is configuration, never
  orchestration** (its §1/§19): it answers "which model + auth," not "which harness runs."
- **I2 — Model-agnostic.** No design or code decision depends on a model benchmark number. Per-model
  data (price, context, dialect, tool-parser, caching) is editable config. Benchmark numbers are
  **directional annotation only**; cross-doc contradictions in them are never load-bearing.
- **I3 — Evidence is an interface**, not a flat schema: a universal envelope (gates read only this) +
  an opaque, method-typed payload. It must hold **non-deterministic / stochastic / graded /
  statistical** results, not just pass/fail (independently forced by 04a's currency-typing finding).
- **I4 — "Harness" has four senses; never conflate:** (1) *coding harness* drives a model→code;
  (2) *test harness* = doc 04's Exercise port, runs artifact→Evidence; (3) agentcfg's `Harness` =
  config-emission adapter; (4) landscape "harness" = the whole agent loop. Disambiguation: spec-driven §2.
- **I5 — Inner vs outer loop.** The **outer** test harness is authoritative and runs in a **clean
  environment the coding model never wrote to** (anti-reward-hack). The **inner** loop (the coding
  harness's own test runs) is advisory and untrusted.
- **I6 — Two IRs, never merged:** agentcfg's `Resolved` (static, immutable, concurrent-read) vs the
  engine's run-state (mutable, persisted, has a lifecycle).
- **I7 — One concept, three names, kept aligned:** a **cell** = doc 04 Part XII parameter vector =
  04a's H1′ category vector = spec-driven §7's per-cell plugin target. `testharness` = doc 04
  Provision + Exercise (fused); `codingharness` = the engine for doc 04 phase 2 (Author), which the
  spine leaves unbound.
- **I8 — The spine is invariant; the standing hypothesis is H1′, not H1.** Uniform 10 phase-concerns
  + the Observe→Specify feedback edge; everything else is a per-category 5-parameter vector + a
  topology selector. IaC needs the **reconciliation-loop** topology; **scale** is an orthogonal axis.
  Do not cite the falsified H1 as current.
- **I9 — Provenance triple.** Every piece of Evidence is pinned to `(source-version, process-version,
  fidelity-rung)`.
- **I10 — Verified terminology is locked.** "signal-injection fixture" (NOT "signal twister") ·
  Connect = gRPC + gRPC-Web + Connect(HTTP/JSON), **not REST** · "fidelity ladder" = our coinage,
  not an established named model · Go floor = **1.24**.
- **I11 — Build-scope discipline.** v0.1 = **one cell (web/Go)**; no engine-DAG, recursion,
  altitudes, or discipline-plugin system until the loop closes on a non-gameable gate over ~50 tasks.
- **I12 — Epistemic tagging is mandatory.** Every load-bearing claim carries a §6 tag.

---

## 6. Epistemic-status legend (corpus-wide, from doc 04)

Every load-bearing claim, in every doc, carries one:

- ✅ **Verified** — confirmed against an external source (cite it).
- 🔶 **Hypothesis** — a design/modeling claim that survived a stated pressure-test; falsifiable; not proven.
- ⚠️ **Corrected** — a claim verification showed wrong/overstated; the corrected form is given.
- 🧩 **Design choice** — an architectural decision with named alternatives, not a fact.

Rationale: the legend makes it impossible to *silently* promote a hypothesis to a fact — which is
how drift begins. The benchmark numbers (I2) are the canonical 🔶/directional case.

---

## 7. Coordination & drift discipline (how we stay cohesive)

1. **Single-writer-per-file.** At most one window/agent edits a given file at a time. The two trees
   have two effective owners (this thread → `Projects/Helios/`; the sibling thread →
   `research/agentic-engineering/`). Cross-tree edits stay minimal and attributed (e.g., the
   2026-06-01 annotations to the series README). *This is the live drift risk; respect it.*
2. **Canonical-home rule.** A shared concept is defined once (§4) and linked everywhere else. Never
   restate a definition in a second doc — link it.
3. **Two-pass verification before building on a "Complete" doc:** (1) fan-out fact-check →
   confirmed / refuted / unverifiable, annotate; (2) cohesion pass against the §5 invariants.
4. **Re-verify triggers:** an invariant the doc touches changed · time-sensitive facts age (harness
   configs, model data — weeks, not months) · a dependent doc is about to be built.

---

## 8. Status dashboard

| Doc | Tree | Role | Last verified | Status |
|---|---|---|---|---|
| `agentic-coding-landscape-2026-06` | Helios | Market survey | 2026-06-01 | ✅ verified; numbers directional (I2) |
| `portable-agent-config-2026-06` | Helios | Schema → harness configs | 2026-06-01 | ✅ verified; drift-prone harnesses flagged |
| `agentcfg-architecture` | Helios | Go library design | 2026-06-01 | ✅ verified; Go floor 1.24 |
| `spec-driven-implementation-system` | Helios | The "how" (build-system) | 2026-06-01 | 🔶 design; reviewed, build-ready |
| `04-universal-sdlc-process-model` | research | SDLC spine | 2026-06-01 | ✅/🔶 (own log); actively evolving |
| `04a-stress-test-and-hardened-model` | research | H1→H1′ stress test | 2026-06-01 | ✅/🔶 (own log) |
| `00`–`03` series | research | Substrate (thesis, Bender) | 2026-05-25 | Complete (May snapshot) |

---

## 9. Open cross-corpus questions (known, tracked, not blocking)

- **Canonical benchmark attribution** (SWE-bench Pro 58.6% → Kimi K2.6 vs GPT-5.5): unverifiable;
  left annotated in both trees rather than forcing fake precision (I2 makes it harmless).
- **Evidence field gap:** doc 04's currency envelope still shows `result: …measurement` and lacks
  reproducibility/cost/staleness; spec-driven §4's interface adds them. Framed as conceptual-vs-
  implementable (acceptable); converge when the engine is built.
- **IaC reconciliation-loop topology** (04a) and the **scale axis** (04a) are not yet modeled in the
  build-system — correctly out of v0.1 scope; revisit after the web/Go cell closes.
- **Placement of `spec-driven`:** intentionally in `Projects/Helios/` (it's the build-system bridge
  above agentcfg), not as series doc 05. Revisit only if it grows into the series' planned 06/07.

---

## 10. The next concrete step

The corpus is cohesive enough to build from. Next: the **v0.1 (web service, Go) slice** —
`spec-driven §10`. First and largest sub-piece: the `codingharness` agent loop (`agentcfg.Client`
+ tool dispatch + budget). Hold the line on I11 (one cell) and I5 (clean-env gate) from the first commit.
