# ADR-0009: Library-system open decisions A–F, ruled

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo (delegated: "whatever is more architecturally correct"); rulings drafted by
  the architecture session with rationale below

## Context

The library-system document (then `/LIBRARY-SYSTEM.md` §11; since migrated to 10 §11 per
ADR-0010) left six decisions open with recommendations. Mateo delegated the rulings to
architectural merit. Each ruling below states the rationale that carried it.

## Decision

| # | Ruling | Rationale |
|---|---|---|
| A | Hexagon slug = **`dependencies`** | Matches the constructor contract `New(configuration, dependencies)` literally; `ports` is the architectural concept the record *contains*, exposable as a namespace within, and collides with networking vocabulary in Go. |
| B | Module roots: **`github.com/gophersys/eden/...`** for apps; **`github.com/gophersys/libs/go/<library>`** for libraries (per ADR-0002) | Two repos = two module roots is what mechanically forces published-version consumption (10 §3) — preserved through the rename. |
| C | **Root-level gitignored `go.work`** spanning `apps/*` + `libs/go/*` | The override must link apps *and* the libs submodule; a `libs/go/go.work` cannot reach apps. Gitignored so it can never reach `main`; release builds run `GOWORK=off` regardless (defense in depth). |
| D | **agentd U1 is donor material, salvaged through gates** — resurrect the branch, rename per HNS-1, but every piece enters `main` only through the same conformance suites and gates as new code | The architecturally correct synthesis of "resurrect" vs "rebuild": gates make code origin irrelevant (the same property that makes agent code safe makes salvage safe). What passes, ships; what doesn't, gets rebuilt. No grandfathering. |
| E | Non-container substrate adapter = **`bare-host`** | The adapter's contract is "runs on a host OS without a container runtime"; whether that host is physical or a VM guest is invisible to the contract. `bare-metal` would encode a claim the adapter cannot verify. |
| F | **Docs first, then scaffold** | Executed: this document set is F. Scaffolding begins at WS1 (09 §2) once the set survives Mateo's review. |

## Consequences

- 10 §11 records the rulings; the migration that absorbed the source document was executed under
  ADR-0010.
- Ruling D defines the general **salvage doctrine**: prior art (`poc/agents`, `poc/knowledge`,
  the U1 branch) is donor material everywhere — referenced freely, merged only through gates.
