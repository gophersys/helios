# Upstream: Build-System Corpus

> **Verbatim point-in-time upstream references — copied 2026-06-12.** The original tree lives in
> `~/Documents/Claude/Projects/Helios/` and remains the canonical home; these are read-only
> snapshots (ADR-0014). Helios-era naming is preserved by design — do not rename, do not edit. To
> revise content, change it upstream and re-snapshot. Never cite this directory as Eden canon.

This is the **agentic build-system** thread imported into Eden: market survey → portable config
schema → the Go configuration library → the spec-driven "how" that sits above it. The Eden
architecture set cites these constantly — most often the two flagged below.

## Index

| File | One-line summary |
|---|---|
| [`helios-corpus-readme.md`](helios-corpus-readme.md) | **Corpus index & cohesion contract — HOLDS THE 12 BUILD-SYSTEM INVARIANTS I1–I12 (§5).** Also owns the layering map, the single-source-of-truth concept table (§4), the epistemic legend, and the status dashboard. This is the upstream `README.md`, preserved verbatim under its Helios-era name. |
| [`spec-driven-implementation-system.md`](spec-driven-implementation-system.md) | **The architecture "how" — the doc the Eden set cites alongside the invariants.** Strong model writes a Spec = {Contract, Template, Tests, Gate}; cheap model fills the template until a clean-room test harness emits Evidence and a gate promotes. Defines the Evidence interface, inner/outer test loop, two-IR rule, and the v0.1 (web/Go) build cut. 🔶 design hypothesis. |
| [`agentcfg-architecture.md`](agentcfg-architecture.md) | Design of the `agentcfg` Go library: parse `agents.yaml` → one immutable IR → compile native harness configs + route/resolve model+auth at runtime. Configuration only, never orchestration. |
| [`portable-agent-config-2026-06.md`](portable-agent-config-2026-06.md) | The portable `agents.yaml` schema — composes routing, modes, and subagents as three orthogonal layers — and how each field compiles to ten harnesses' native configs (Claude Code, Aider, Cline, Roo/Kilo, OpenCode, Crush, Continue, Goose, Codex). |
| [`agentic-coding-landscape-2026-06.md`](agentic-coding-landscape-2026-06.md) | June-2026 market snapshot of harnesses, models, and benchmarks; argues harness and model have decoupled into config via a translation layer. All numbers are directional, not load-bearing (invariant I2) — don't cite a decimal. |

## Pointers

- **The 12 invariants I1–I12** live in [`helios-corpus-readme.md`](helios-corpus-readme.md) §5.
- **The architecture "how"** is [`spec-driven-implementation-system.md`](spec-driven-implementation-system.md).
- Reading order, the source-of-truth concept map, and the epistemic legend are all in
  [`helios-corpus-readme.md`](helios-corpus-readme.md) (§3, §4, §6).

> Note: the upstream corpus README references a sibling research tree
> (`Documents/research/agentic-engineering/`, e.g. doc 04 / 04a). That substrate is snapshotted
> separately under [`../agentic-engineering/`](../agentic-engineering/).
