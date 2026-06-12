# Spec-Driven Implementation System — the "how"

> **TL;DR.** A strong model writes a **Spec = {Contract, Template, Tests, Gate}**; a cheap model
> fills the template until tests pass; a clean-room **test harness** emits **Evidence**; a **gate**
> promotes. Built above `agentcfg` (config/routing). **Everything here is 🔶 design hypothesis, not
> verified fact** — the §10 v0.1 slice (one web/Go cell) is the experiment that confirms or kills
> it. Don't build past one cell until the loop closes on a gate the coding model can't game.
>
> **Tags:** 🔶 hypothesis (most of this) · ✅ externally verified · ⚠️ corrected · 🧩 design choice.
> **Corpus contract & invariants:** `./README.md`. **Wide process spine:** doc 04 / 04a.

**Where it sits.** Above `agentcfg`; the deep, buildable instantiation of doc 04's inner loop
(Specify → Author → Exercise → Gate) for one cell. Doc 04 is the wide spine; this is the deep slice.
(`/Users/mateo/Documents/research/agentic-engineering/04-universal-sdlc-process-model.md`)

---

## 1. Core idea
Spec = compressed design thinking; template+tests = its executable form; implementation =
decompression under verification. The economics *are* `agentcfg`'s routing split: `think` → strong
model authors, `default` → cheap model fills. **Templates+tests are what make cheap-model
implementation safe** — the cheap model isn't trusted to reason, only to fill and pass.

🔶 **Honest limit (the weakest seam).** "Tight spec ⇒ mechanical implementation" is a *target*, not a
guarantee. If tests fully pin behavior you've written the impl in test form; if they don't, the
cheap model has latitude = thinking. We can't *directly* measure "thinking relocated"; §6 measures a
proxy. We instrument the proxy and plan for the miss (§9).

## 2. Two things called "harness" — never conflate

| | **Coding harness** | **Test harness** |
|---|---|---|
| Job | drive a model to *produce* code | *execute* artifact → emit **Evidence** |
| Trust | implements; untrusted self-report | authoritative; **the gate** |
| Examples | our own LLM loop; Claude Code; Aider | `go test`; ephemeral k8s; HIL rig |

Four corpus senses of "harness" (Invariant I4): coding harness · test harness (= doc 04's Exercise
port) · `agentcfg.Harness` (a config-emission adapter — unrelated) · landscape "harness" (the whole
agent loop).

**Inner vs outer loop.** A coding harness runs tests *inside* its own loop — that's **advisory,
untrusted**. The authoritative **test harness runs in a clean environment the coding model never
wrote to** (anti-reward-hack; the landscape doc's `conftest.py`-planting threat is real). Inner =
developer feedback; outer = promotion.

## 3. The `agentcfg` boundary
`agentcfg` is config/routing/LLM-call **only** (its §1/§19), never orchestration. It binds
*model + auth* per phase; the new `codingharness` (above it) binds *which loop runs*.

🧩 **Decision (v0.1): our own loop calling `agentcfg.Client`** (not spawning an external harness) —
full control of iteration, budget, escalation, clean-env. ⚠️ **`Call` is the bare wire** (agentcfg
§19: no tool-loop). So `codingharness` = `Call` **+ a hand-written agent loop** (parse `tool_use`,
dispatch read/edit/run-tests, feed back, enforce budget). *That loop is the largest v0.1 component,
not a wrapper.*

⚠️ **Two IRs, never merged:** `agentcfg.Resolved` (static, immutable) vs the engine's run-state
(mutable, persisted). Merging would break the immutability that makes routing safe.

## 4. Evidence = an interface, not a flat schema ⚠️

```go
type Evidence interface {
    Claim()           string            // what was asserted
    Verdict()         Verdict           // pass | fail | inconclusive  (NOT "measurement")
    Confidence()      Confidence        // deterministic | flaky(p) | sampled | measured(±)
    Reproducibility() Reproducibility   // deterministic | stochastic | one-shot-physical
    CostToReproduce() Cost              // free | minutes-of-cluster | a-human-with-a-probe
    Provenance()      Fingerprint       // artifact hash, env fingerprint, who/what/when
    Staleness()       StalenessPolicy   // when does this stop counting?
    Payload()         json.RawMessage   // discipline-specific detail, incl. raw measurements
}
```
A flat record can't carry the uncertainty/cost/reproducibility a gate needs across disciplines. The
**gate reads only the envelope**; `Payload` is opaque/method-typed. A raw measurement is *not* a
verdict until the gate thresholds it (→ `inconclusive`). `Confidence`/`Reproducibility` are tagged
structs (Go has no sum types). 🔶 **Reconciles with** doc 04 Part IV (its flat record = conceptual
currency; this = implementable form) and **04a** (which independently found the currencies "too
narrowly typed" — must hold stochastic/graded results). **Conformance test from day one:** three
heterogeneous impls; if the gate writes generically against the interface, the claim holds.

## 5. Gate = policy over Evidence + a test-power check
Promote iff `Verdict==pass` **AND** `Confidence > θ` **AND** not stale **AND** reproducibility class
acceptable — `θ` and class are **per-gate**. Plus an independent **mutation score**: without it,
"all pass" can't distinguish "correct" from "tests can't tell." ⚠️ Scoped to the (web, Go) cell
(in-process, ms tests; `gremlins`/`go-mutesting` cheap); for one-shot-physical disciplines mutation
testing is a research problem, not a checkbox.

## 6. Spec-quality metric (de-circularized) 🔶
Naive "iterations-to-green = tightness" is non-monotonic — low iterations can mean a tight spec **or
a blind gate**. Use **spec-determinacy** = variance across *N* runs of a **frozen (spec, model,
test-harness) triple**, read *jointly* with the mutation score:

| variance | mutation | reading |
|---|---|---|
| low | high | spec genuinely tight ✅ |
| low | **low** | **gate is blind** — the false positive the naive metric hides ❌ |
| high | high | loose spec **or** model noise — ambiguous until you pin sampling & compare spec-vs-spec on a fixed task |
| high | low | both broken |

⚠️ **Residual confound:** freezing the model doesn't freeze its sampling noise — pin temperature/seed,
and treat *same-task / varying-spec* as the only fully-controlled comparison.

## 7. Template — no `⊕` 🔶
`Core ⊕ Lang ⊕ Discipline` doesn't factor: (web, Go) and (embedded, C/Zephyr) share only the *word*
"invariant," and embedded adds a 4th axis (board/devicetree). What survives: a **shared Spec
envelope** (Contract, Template, Tests, Gate as four roles behind interfaces) **+ a per-cell plugin**.
That "cell" = doc 04 Part XII's cell = 04a's H1′ category vector. Ship **one** cell; don't design
others until web/Go runs ~50 tasks.

✅ **A "typed hole" in Go** = an interface (the Contract) + stub functions bodied `panic("unimplemented")`
+ a `_test.go` **written first**. Decompress = replace the panics until `go test` is green.
(Go has no first-class hole; this is standard practice.)

## 8. Libraries + bootstrap

| Library | Owns |
|---|---|
| `spec` | Contract + Template-ref + Tests + Gate (four roles) |
| `evidence` | the §4 interface + concrete impls |
| `template` | per-cell scaffolds (one to start) + a per-cell plugin |
| `codingharness` | the implementing loop — v0.1 = own loop on `agentcfg.Client` (§3) |
| `testharness` | clean-env provision + exercise + emit Evidence; later, the scarce-resource scheduler |
| `engine` | walks the phase chain; binds phase→model via `agentcfg`; holds the mutable run-state |

**Maps to doc 04:** `testharness` = its Provision + Exercise ports (fused) + scarcity/leasing model;
`codingharness` = the engine for its phase 2 (Author), which the spine leaves unbound. Recursion /
altitudes (Reframe B) accepted as end-state, deferred.

🔶 **The system can't build itself from zero.** Hand-built kernel (~4 + a human; the strong model
can't author the harness that runs it): `agentcfg` → `evidence` + 1 impl → `testharness` (1
discipline) → `codingharness` (1 loop) → spec/template format + 1 worked spec → `engine` (linear).
Arrows are *build priority*, not strict acyclic — `codingharness` and the spec format co-emerge.

## 9. First-class failure paths (were missing)
- **Non-termination** → hard iteration **+ cost** budget; escalate to `think` to fix impl *or amend the spec*.
- **Spec is fallible** → versioned, invalidatable by Evidence; amending tests is governed, not a cheap-model freedom.
- **Reward-hacking** → the clean outer-loop env (§2), as a security property.
- **Cost** → cheap × N iterations can exceed one strong pass (+ lost prompt cache); escalation is cost-aware.
- **Author non-determinism** → a spec is frozen for the duration of an experiment.

## 10. v0.1 — build exactly this
**(web service, Go).** Prove the loop closes on a non-gameable gate over ~50 tasks before generalizing.
1. `agentcfg` as-is.
2. `Evidence` interface + one impl: `GoTestEvidence` (parse `go test -json`).
3. One `testharness`: clean temp dir + `go test -json`, env the coding model never wrote to.
4. One `codingharness`: own loop on `agentcfg.Client` — **the biggest item** (§3).
5. Iteration + cost budget + escalation to `think`.
6. `Template` = a Go package (interface + `panic("unimplemented")` stub + `_test.go` first).
7. **NO engine *DAG*, recursion, altitudes, or plugins.** The linear chain author→fill→gate→done/escalate **is** the v0.1 engine (degenerate form), not "no engine."

Instrument **variance + mutation score** from run 1 (§6). Low variance + low mutation = blind gate — the failure the naive design can't see.

## 11. What verification corrected (don't relapse)
Evidence flat→interface · iterations-metric→spec-determinacy + mutation · `⊕`→envelope + per-cell ·
agentcfg binds model-not-harness · one→inner/outer loop · one→two IRs · happy-path→failure-paths
first-class. **Terminology (✅):** "signal-injection fixture" (not "signal twister") · Connect =
gRPC + gRPC-Web + Connect-HTTP-JSON (not REST) · "fidelity ladder" = our coinage · Go floor **1.24**.

## 12. Cohesion with the concrete instance (photosphere) — verified 2026-06-01
The `photosphere` repo's `.claude/` is a near-instance of this design (spec-as-work-unit, frozen
contract, generator/evaluator role split, evidence-gated promotion, human gates, one slice first) —
and is *more* developed in places (a G1 interface-freeze gate + enforcing hook; a G3 self-improvement
loop; a `cell.json` mapping to the SDLC spine). Three real **divergences** — treat as open forks, not
settled:
- 🧩 **Order:** photosphere is **contract-first, tests-after** (black-box against the frozen
  interface), not strict test-first. The invariant that actually matters is "tests pin the
  *contract*, not the impl's accidents" — TDD-vs-contract-first-blackbox is a design choice. **Soften
  this doc's TDD claim accordingly.**
- 🔶 **Clean-room is declared, not enforced** there (implementer-authored stories double as the
  verification target). Our §2 makes it a *mechanical* requirement — keep that as the stronger stance.
- 🔶 **No template-with-holes and no explicit strong/cheap split** in photosphere — both are
  *unvalidated hypotheses* of this doc, not yet proven by the one working instance.
