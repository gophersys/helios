# ADR-0002: Rename Helios to Eden, fully and everywhere

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo

## Context

The platform was developed under the codename Helios across the monorepo, libs, research corpus,
and ADRs. Mateo ruled the product is named **Eden** — not as a second name layered over Helios,
but as a full rename. Alternatives considered: keep Helios everywhere; Eden-as-product over
Helios-as-codename; Eden-platform vs Helios-first-instance. All rejected — split naming breeds
exactly the concept drift the cohesion contract exists to prevent.

## Decision

The system is **Eden** in all documents, code, identifiers, and product surfaces.
Naming root: GitHub org stays `gophersys`; repositories rename (`gophersys/helios` →
`gophersys/eden`); npm scope `@helios/*` → `@eden/*`; Go module roots
`github.com/gophersys/eden/...` (apps) and `github.com/gophersys/libs/go/<library>` (libraries,
repo name unchanged). Photosphere keeps its name (own asset). HNS-1 worked examples re-render
under the `eden` scope.

## Consequences

- Invariant E7: no `helios` identifier in new code or documents.
- Upstream corpus documents (`~/Documents/Claude/Projects/Helios/`) and `docs/research/` still
  say Helios — corrected as touched; silent partial renames are forbidden. (The former root
  planning docs were migrated under Eden naming into doc 10 — ADR-0010.)
- Rename execution is one gated LSC-style change (09 §7): repo rename, module paths, scope,
  CI references. The local checkout directory (`~/helios`) renames with the repo.
- `poc/` artifacts are historical; not renamed.
