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
| 04 | [platform-ui-paradigms](04-platform-ui-paradigms.md) — deep-tool depth & learnability, doc-as-data, diagrams-as-runtime (C10), onboarding, desktop/web parity, multi-altitude nav | 2026-06-12 | presentation layer (12, theses U1–U10); doc 12 §2 altitude model, §3 diagram-as-projection, §4 command-palette/nav, §6 learnability |
| 05 | [design-foundations](05-design-foundations.md) — Apple/HIG human-feel principles + the generative proportion/type/spacing/OKLCH-color/contrast/motion/density math tables; the `generateTheme` pipeline with the WCAG contrast gate as a hard constraint | 2026-06-14 | the `@eden/theme` generative engine + the UI design-correctness test dimension (ADR-0024); the 10 Part-D forks → OD-17-* |
| 06 | [codebase-insight-visualization](06-codebase-insight-visualization.md) — metrics catalog (formula·threshold·SDLC point), behavioral/temporal git mining (hotspots, logical coupling, churn, bus factor), Caserta-Zendra viz taxonomy, the 8-primitive widget asset set | 2026-06-17 | the proposed `codeinsight` analyzer + payload contract + the `@eden/visualization` lib (Eden self-feeding) |
| 07 | [read-only-editor-substrate](07-read-only-editor-substrate.md) — read-only VS Code over a project worktree: the substrate-agnostic `GET /sessions/{id}/editor` contract (BUILT), the local docker code-server sibling (BUILT), and the k8s editor-sidecar + desktop ssh-remote designs (the `WorkspaceSpec` surface change, ingress routing, OD-EDITOR-1..3) | 2026-06-23 | a `workspaceprovider` editor-sidecar capability (ADR) + the agentgateway editor contract |
