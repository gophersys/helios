# docs/research — research notes

Point-in-time research with sources and a research date (class: **research note**, docs/README.md
§1). Never canonical: findings are promoted into `docs/architecture/` specs with a citation, not
edited here. These predate the Eden rename and intentionally keep their original wording
(ADR-0002: corrected as touched).

| # | Note | Date | Promoted into |
|---|---|---|---|
| 00 | [deepseek-models](00-deepseek-models.md) — V4 Pro vs Flash benchmarks, pricing, routing matrix | 2026-06-05 | routing economics (04 §6), ADR-0008 second-adapter rationale |
| 01 | [pi-harness](01-pi-harness.md) — pi/oh-my-pi extension system, RPC mode, DeepSeek integration, RLM subagents | 2026-06-05 | F4 connector design (05 §2), ADR-0008 |
| 02 | [agent-instrumentation](02-agent-instrumentation.md) — Go architecture for spawning/controlling coding agents in sandboxes | 2026-06-05 | F4 contract + `agentconfiguration` layering (05 §2, 10 §12) |
| 03 | [knowledge-libraries](03-knowledge-libraries.md) — curated-knowledge-vs-priors thesis, rule schema, anti-slop mechanics, PoC design | 2026-06-06 | P7, 08 §4, the knowledge pipeline |
