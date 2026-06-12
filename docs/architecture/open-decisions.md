# Open Decisions Register

> Living document · created 2026-06-12. The only blocking human-interaction pattern (P13): items
> land here with options + a recommendation; rulings become ADRs and the row moves to Resolved.

## Open

| # | Decision | Options (recommendation first) | Needed by |
|---|---|---|---|
| OD-1 | **Svelte behavior layer** for photosphere re-founding | Bits UI (headless, Svelte 5-native) · Melt UI builders · hand-rolled on Svelte 5 runes. Needs a data pass of photosphere-ADR-0004 rigor (a11y matrix, maintenance, LLM legibility) before ruling. | WS4 spike |
| OD-2 | **Svelte app framework**: SvelteKit vs Vite SPA (Tauri wraps the same bundle either way) | SvelteKit (routing/SSR story, ecosystem default) vs SPA (simpler Tauri parity). | M3 frontend skeleton |
| OD-3 | **Client state/query layers** post-React: replaces the zustand/jotai/xstate/TanStack-Query choices of the former `/LIBRARIES.md` (now 10 §12) | Svelte 5 runes + TanStack Svelte Query; XState's Svelte adapter only if machine-mirroring of backend lifecycle survives review. | M3 |
| OD-4 | **CI executor v1 shape**: own runner on docker/kubernetes from day 1, or wrap an existing runner behind the executor port first | own runner (contract purity, content-aware caching) vs wrap (speed). | L2 |
| OD-5 | **BYO-GitHub-as-authority** (Eden git as mirror instead of authority) — explicitly not offered in v1 (05 §2) | revisit when adoption pipeline (BYO repos) is scoped. | hosted/BYO milestone |
| OD-6 | **Hosted-tier billing**: Stripe adapter scope and metering granularity | defer until hosted milestone; F3 contract designed to carry it. | hosted milestone |
| OD-7 | **agentconfiguration open items** inherited from upstream (CLI module split, yaml v3 vs v4, harness plugin model, per-call key rotation, content-based routing) | per upstream agentcfg-architecture §open-questions; rule during WS2. | WS2 |
| OD-8 | **External corpus migration**: when/how the upstream Helios-named corpus (`~/Documents/...`) gets renamed/folded — the in-repo half was executed by ADR-0010 | lazily on touch (recommended). | ongoing |
| OD-9 | **Transcript retention & privacy policy** (per-project retention, redaction verification) | needs ruling before any non-Mateo user exists. | L4 |
| OD-10 | **Visual editor scope** for v1 dashboard (read-only pipeline/artifact viewer first vs editable canvas) | viewer-first recommended; editing re-enters via phase artifacts, not canvas mutation — this constraint is the editor's architectural contract regardless of scope ruling. | L2/L4 |
| OD-11 | **S6 observability stack composition** (trace/metric/log storage, dashboarding) — the one v1 subsystem whose concrete components are unpinned while buf/Connect/kind/etc. are | candidates to be evaluated (e.g. Grafana LGTM stack, ClickHouse-backed, openobserve); must be minimally live by L1 exit (06 §2). | L0/L1 |
| OD-12 | **First managed-cloud adapter scheduling** (EKS/GKE/AKS/DO) — the ladder can complete on local substrates, leaving cloud adapters, billing polling, and cloud drift unexercised | schedule one managed-kubernetes adapter + its billing/drift surface immediately post-L4 (recommended), or accept all four as unscheduled backlog with explicit sign-off. | post-L4 planning |

## Resolved (ruling → ADR)

| # | Decision | Ruling | ADR |
|---|---|---|---|
| RD-1 | System name | Eden, fully and everywhere; gophersys org kept; repos renamed | 0002 |
| RD-2 | Go floor | 1.26 (supersedes corpus 1.24) | 0003 |
| RD-3 | UI stack | Re-platform on Svelte; supersedes React 19/React Aria/vanilla-extract decisions at Eden level | 0004 |
| RD-4 | Photosphere fate | Re-founded on Svelte as the same standalone asset; theming engine retained | 0005 |
| RD-5 | Hosting posture | Local-first (`eden up`), hosted tier later on same ports | 0006 |
| RD-6 | Bootstrap path | Kernel-first ladder L0–L4 | 0007 |
| RD-7 | First agent connector | Claude Code; pi/omp+DeepSeek second (proves abstraction + cheap arm) | 0008 |
| RD-8 | Library-system open decisions A–F (10 §11) | dependencies slug · eden module root · root gitignored go.work · U1 as gated donor material · bare-host · docs-first | 0009 |
| RD-9 | Documentation scheme + in-repo migration pass | four doc classes, kebab-case naming, attic policy; root planning docs absorbed into doc 10 | 0010 |
| RD-10 | Project document schemas | JSON Schema 2020-12 · dual-surface canonical form (md+frontmatter / yaml → one JSON projection) · `schemas/document/v1/` · design system stays a separate linked F6 artifact | 0011 |
