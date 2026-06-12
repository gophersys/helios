# ADR-0001: Record Architecture Decisions

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo

## Context

Eden's corpus spans four repositories and an external research tree; decisions made
conversationally (including by agents) evaporate from context windows. Photosphere already
adopted ADRs (its ADR-0001) with good results; Eden-level decisions need the same durability,
and the process model (04 §5) needs a concrete artifact for `approve`-gate rulings.

## Decision

Record architecturally significant decisions for Eden as ADRs in `docs/architecture/adr/`,
numbered, one per file, format per `template.md`. Every 🧩 tag in the document set that gets
ruled becomes an ADR; the open-decisions register tracks the queue. ADRs are append-only:
supersede, never delete. Photosphere keeps its own chain; cross-repo supersessions cite the
other repo's ADR explicitly.

## Consequences

Decisions are auditable and teachable; "why" survives sessions and agents. Cost: discipline to
actually write them — mitigated by the register pattern making rulings cheap to capture.
