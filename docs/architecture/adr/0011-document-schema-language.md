# ADR-0011: Document schemas in JSON Schema 2020-12, dual-surface canonical form

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo

## Context

Doc 11 (the project document system) makes invariant E2 concrete: every project document
validates against a hard schema. Three rulings were needed: the schema language, the canonical
authoring form (git-native vs dashboard-native), and where the schemas live. Alternatives
considered: CUE-authored compiled to JSON Schema (richer constraints, one more toolchain from
day 1); Protobuf via `libs/protocols` (shares the wire source of truth, poor fit for
prose-bearing documents).

## Decision

1. **JSON Schema 2020-12** is the schema language for project documents. Validators exist in
   every ecosystem, CI integration is trivial, and agents are heavily trained on it — the
   authoring-loop benefit (08 §1, agents retried against structured diagnostics) is largest
   here. CUE remains the documented escalation path if constraints outgrow JSON Schema.
2. **Dual-surface canonical form** (doc 11 §5): narrative documents are markdown + YAML
   frontmatter; registry documents are YAML; both project to one JSON shape
   (`{meta, data, sections}`) and the **projection** is what validates and what every surface
   (git/HTML, dashboards, AssistantSessions) consumes. Neither surface is an export of the other.
3. **Placement:** schemas live at `schemas/document/v1/` in the eden monorepo, semver'd,
   versioned with the platform release (06 §3). `$id` uses the logical URI scheme
   `eden://document/v1/<name>` until a resolvable host exists (doc 11 Q2).
4. The design-system artifact stays a **separate F6 chain**, linked from the product tier's
   `design-brief` via `informs` (doc 11 §2).

## Consequences

- The validator (first home: `tools/documentvalidator`, Go) must preload the schema directory to
  resolve cross-file `$ref`s against logical `$id`s; it graduates into the engine's phase-boundary
  check and the CI gate (doc 11 §8).
- Wire entities remain Protobuf-owned (02 §5); document schemas never duplicate proto messages —
  `service-contracts` carries references into code, not definitions.
- Breaking schema changes are platform migrations (06 §3); documents pin `schema_version`.
