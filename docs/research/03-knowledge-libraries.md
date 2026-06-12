# Knowledge Libraries — testing whether curated knowledge beats model priors

> Research date: June 6, 2026 · Companion POC: `poc/knowledge/` (omp + DeepSeek V4 Flash)

## Thesis

> **A rule without an oracle is an opinion. An opinion without a citation is slop.**
> Treat knowledge like libraries: versioned, sourced, compiled to checkers, gated,
> and merged only once it proves uplift over the bare model.

The goal is a *knowledge-making skill*: a pipeline that turns authoritative sources
(Go docs/release notes, books, talks) into rule libraries an agent (claude / pi /
codex / deepseek) consumes — and an eval harness proving each rule earns its tokens.

## A. Testing that an agent follows an architecture

Decompose the knowledge base into atomic rules, each with a checkability class:

| Class | Covers | Oracle |
|---|---|---|
| C1 decidable | import boundaries, naming, constructor purity, env confinement, post-cutoff APIs | AST/types checkers (deterministic, non-gameable) |
| C2 property | adapter≡fake conformance, "tests actually test" | contract suites, mutation testing |
| C3 judgment | consumer-defined interfaces, layering taste | blind rubric-anchored judges (excluded from the POC: nondeterministic) |

Design rules: **applicability predicates** (score over applicable rules only) and
**artifact over process** (check the code, not whether the agent cited the guide).
Every rule must ship with its oracle — the same move as the helios `evidence` envelope.

## B. Arms and comparison protocol

Arms: baseline (control) · monolithic guide · retrieval/skill · **checker-feedback**
(knowledge only via deterministic findings + fix hints) · exemplar · **hybrid**
(compact core + checkers). Protocol: **temptation tasks** (each task makes the
violation the lazy path), held-out rule split against overfitting, N≥3 seeds/cell,
paired comparisons, and **second-task velocity** (architecture quality = a fresh
agent's cost to extend the codebase) as the long-horizon metric.

## C. The knowledge-making skill (pipeline)

ASSEMBLE (tiered sources) → EXTRACT (rule schema below) → REFUTE (adversarial
skeptics vs source; staleness check) → DECONFLICT (contested → human ruling, the
Open-Decisions pattern) → COMPILE (rule → checker / property / rubric) →
VALIDATE (eval harness; a rule earns its place by measured uplift) → RENDER
(DB → core-context, skills, linter configs — pure functions of the DB).

Rule schema = the `evidence` envelope wearing a different hat:
`{id, statement, rationale, applicability, exceptions[], example{good,bad},
oracle{class,ref}, fix_hint, provenance[{source,tier}], staleness{go_minimum,review_by},
status: CANDIDATE→VERIFIED→COMPILED→PROVEN→DEPRECATED, hypothesis_baseline_violation}`

## D. Anti-slop mechanics

1. **Prior-delta filter** — measure baseline violation per rule; if the bare model
   already complies, the rule is dead weight: demote to checker-only or cut.
   `value(rule) = baseline_violation_rate × cost_of_violation`.
2. **Provenance or it doesn't ship** — no citation, no rule.
3. **Falsifiability** — a rule that can't be violated detectably is rejected.
4. **Mandatory exceptions** — no unconditional platitudes.
5. **Mine the post-cutoff seam** — release-notes-driven extraction (Go 1.24–1.26:
   `errors.AsType`, `slog.NewMultiHandler`, `B.Loop`, `WaitGroup.Go`, `new(expr)`,
   self-referential generics) is the highest-uplift-per-token knowledge: the model
   *cannot* know it.
6. **Compression pressure** — hard token budgets per rendering; enforced by test.

## Go 1.26 (released Feb 2026) — the post-cutoff seam used by the POC

- `errors.AsType[E](err)` — type-safe generic replacement for `errors.As`
- `log/slog.NewMultiHandler` — stdlib fan-out handler
- `new(expr)`, self-referential generic constraints
- `testing.B.Loop` no longer inhibits inlining (B.Loop itself is 1.24; `WaitGroup.Go` is 1.25)
- Green Tea GC default, `go fix` modernizers, `crypto/hpke`, experimental `simd/archsimd`,
  `runtime/secret`, goroutine-leak profile, `T.ArtifactDir`, `testing/cryptotest`

## POC (poc/knowledge) — design summary

10 rules (2 architecture, 4 idiom, 4 post-cutoff) · 6 temptation tasks with exact
contracts + held-out verify suites + rule-clean references · 10 deterministic
oracles · 4 arms · 72-run matrix (4×6×3 seeds) on `deepseek-v4-flash` through omp
headless, fully isolated and provenance-stamped. Pre-registered hypotheses live in
the rule YAMLs; `harness report` confirms/refutes them mechanically.

**Results:** see `poc/knowledge/results/report.md` (generated; summary to be
appended after the matrix completes).

## Sources

- [Go 1.26 Release Notes](https://go.dev/doc/go1.26) · [Go 1.26 blog](https://go.dev/blog/go1.26)
- [Oh My Pi](https://github.com/can1357/oh-my-pi) · [DeepSeek × Oh My Pi](https://api-docs.deepseek.com/quick_start/agent_integrations/oh_my_pi)
- `docs/research/00-deepseek-models.md`, `01-pi-harness.md`
- helios `LIBRARY-SYSTEM.md` §9 (knowledge ≠ enforcement), `LIBRARIES.md` (evidence/gate model)
