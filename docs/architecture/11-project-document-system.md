# 11 — Project Document System

> Status: Draft · 2026-06-12 · Canonical home for: the document tiers (product → architecture →
> implementation), the identifier grammar and link model, the document envelope, canonical forms
> and the dual rendering contract, the traceability rules, and document-schema versioning.
> This is invariant **E2 made concrete**: the hard schemas that 04 §4 promised. Decision basis:
> ADR-0011 (JSON Schema 2020-12; dual-surface canonical form; repo placement).

## 1. Purpose

When a user creates a project, an intake agent converses with them and fills a standardized
document chain. The conversation's entire job is to move what is in the user's head into
schema-valid documents up front, so that downstream work is gated, not supervised (P13/T3).
Every document validates against a versioned JSON Schema before it is accepted (E2); documents
link to each other through typed, checkable references, so any deployed line of code walks back
to the user's words, and any requirement walks forward to its verifying evidence.

Eden's own `docs/architecture/` set is the hand-built prototype of this discipline; this system
is that discipline schematized for every project Eden manages — including, eventually, project #1
(Eden itself, 06 L2).

## 2. The tiers

| Tier | Documents | Authored by | Pipeline phase (04 §1) |
|---|---|---|---|
| **P — Product** (what/why) | product-charter · requirements · user-workflows · design-brief | intake agent from the creation conversation; user gates `edit` | Specify |
| **A — Architecture** (how) | domain-model · system-design · service-contracts · architecture-decisions | architecture agents from tier P; user gates `approve` at contract freeze | Specify→Author |
| **I — Implementation** (build against) | implementation-plan · specification (per work package) | planning agents from tier A | Author |
| *(records)* | SourceChange, Evidence, ReleaseCandidate, DeploymentRecord, Observation | emitted by the pipeline, not authored | Build→Observe |

Pipeline **records** are schema-governed too but are machine emissions (04 §4), not documents a
conversation produces; they are out of this document's inventory and in its link graph (Evidence
verifies specifications, §7). The **design system** itself (DTCG ThemeDoc + component manifest)
is a separate F6 artifact (05 §2); the product tier carries a `design-brief` that links to it 🧩
(ruled: separate-but-linked).

## 3. Identifier grammar and link model

Stable identifiers are the join keys of the whole system (the HNS-1 move, applied to documents):

```
item id   := PREFIX "-" NNNN          e.g. REQ-0007, WF-0002, CMP-0003
document id := <type slug>            e.g. product-charter, requirements (one per project,
                                      versioned; multi-instance types add -NNNN: adr-0004, spec-0012)
```

| Prefix | Item | Lives in |
|---|---|---|
| PER | persona | product-charter |
| REQ | requirement | requirements |
| WF | user workflow | user-workflows |
| ENT / INV | domain entity / invariant | domain-model |
| CMP | component (cell-typed) | system-design |
| CTR | contract | service-contracts |
| ADR | architecture decision | architecture-decisions |
| WP | work package | implementation-plan |
| SPEC | specification | specification documents |

**Link types** (typed edges, declared in the envelope): `realizes` (downstream item → the
upstream items it serves), `refines` (same-tier elaboration), `verifies` (evidence → SPEC/REQ),
`supersedes` (new version → old), `informs` (design-brief → F6 artifact reference).

**Direction rule:** documents cite **upstream only** (I cites A cites P); reverse edges are
derived by tooling, never written. This keeps authorship single-writer per edge and makes
coverage a pure graph query.

## 4. The envelope

Every document carries the same machine frontmatter, validated by
`schemas/document/v1/envelope.schema.json`:

```yaml
id: requirements                # document id (§3 grammar)
type: requirements              # selects the schema
schema_version: 1.0.0           # version of the document's schema
project: <project-slug>
status: draft | review | approved | superseded
version: 3                      # document revision, monotonic
created: 2026-06-12             # dates ISO-8601
updated: 2026-06-12
authors:                        # provenance — agent runs and humans
  - run: <run-id>               # agent authorship (links to transcript, P9)
  - human: mateo
links:                          # typed edges, upstream only (§3)
  realizes: [REQ-0001, WF-0002]
  supersedes: null
  informs: []
source:                         # product tier only: grounding in the conversation
  - run: <run-id>
    span: "messages 12-31"
```

Status lifecycle: `draft → review → approved → superseded`, moved only by gates (04 §5 policy
table: tier P defaults `edit`, contract freeze and tier A `approve`). An `approved` document is
immutable; changes create `version+1` in `draft`, linked `supersedes` (append-only history — the
ADR discipline generalized).

## 5. Canonical forms and the dual rendering contract

Two canonical forms, one JSON projection 🧩 (ruled: both surfaces, equal priority):

- **Narrative documents** (`.md`): YAML frontmatter (the envelope + a `data:` block for
  structured lists) + required markdown sections with stable heading ids. For: product-charter,
  design-brief, architecture-decisions.
- **Registry documents** (`.yaml`): wholly structured; prose fields are markdown strings. For:
  requirements, user-workflows, domain-model, system-design, service-contracts,
  implementation-plan, specification.

The validator projects both to the same JSON shape — `{meta, data, sections}` — and validates
**the projection** against the schema. Consequences: git review and HTML rendering read the
files as-written (the `docs/tools/render-html.mjs` pattern generalizes); dashboards and the
non-technical views (T8) consume the projection through the gateway; neither surface is an
export of the other. A document is the projection — the file is just its authoring format.

## 6. Document inventory (v1)

| Document | Form | Core content (beyond the envelope) |
|---|---|---|
| `product-charter` | md | sections: vision · problem · success-criteria · non-goals; data: personas `[{id: PER-, name, description}]` |
| `requirements` | yaml | `items[{id: REQ-, statement (EARS-style), kind: functional\|quality\|constraint, priority: P1-P3, rationale, acceptance[], links, source}]` |
| `user-workflows` | yaml | `items[{id: WF-, name, persona: PER-, trigger, steps[], outcome, links}]` |
| `design-brief` | md | sections: intent · audience-and-tone · constraints; data: `design_system_reference` (F6 artifact ref or null), token hints |
| `domain-model` | yaml | `entities[{id: ENT-, name, description, attributes[], relationships[{to: ENT-, kind, cardinality}]}]`, `invariants[{id: INV-, statement, links}]` |
| `system-design` | yaml | `components[{id: CMP-, name, responsibility, cell (02 §2), depends_on[CMP-], connectors[], links}]`, environments × substrate plan (P6 axes) |
| `service-contracts` | yaml | `contracts[{id: CTR-, name, kind: connect-service\|library-interface\|event, definition_reference (path), summary, status: draft\|frozen, links}]` — the definition itself lives in code (proto/Go); the document carries the frozen reference + rationale |
| `architecture-decisions` | md (one per decision: `adr-NNNN.md`) | sections: context · decision · consequences (the ADR-0001 format, schema'd) |
| `implementation-plan` | yaml | `packages[{id: WP-, title, scope, file_leases[] (02 §2), depends_on[WP-], budget{tokens, escalation}, links}]` |
| `specification` | yaml (one per WP: `spec-NNNN.yaml`) | the Spec envelope (02 §2): `{work_package: WP-, contract: CTR-, template_reference, tests_reference, gate{policy, evidence_required[], thresholds}}` |

## 7. Traceability rules (what gates enforce beyond shape)

| # | Rule |
|---|---|
| T1 | No dangling references: every linked id resolves within the project corpus. |
| T2 | Direction: links point upstream only (§3); violations are schema-level errors. |
| T3 | Every tier-A item carries ≥1 `realizes` edge into tier P (no unmotivated architecture). |
| T4 | Every WP carries ≥1 `realizes` edge to a CTR or REQ; every SPEC cites exactly one WP and one CTR. |
| T5 | Supersession is append-only; an `approved` document never mutates (new version supersedes). |
| T6 | Coverage: every P1 requirement reaches ≥1 SPEC through the graph — and, from L2 on, ≥1 verifying Evidence record. Reported, and gate-blocking at Deliver for P1 gaps. |
| T7 | Frozen contracts (`status: frozen`) follow the negotiation gate (09 §4); editing a frozen CTR is a new negotiation, mechanically refused otherwise. |

## 8. Enforcement

Four checkpoints, deterministic at each (P8 — no model in the enforcement path):

1. **Authoring loop** — agents receive the schema + one exemplar in context; validator failures
   return as structured diagnostics for bounded retry (04 §8). The schema shrinks the output
   space before enforcement ever fires (P5).
2. **Phase boundary** — the engine validates shape (JSON Schema) + links (T-rules) before any
   artifact flows downstream (E2).
3. **CI** — the identical validation re-runs server-side on every push (client-side checks are
   bypassable; the server gate is not — 10 §8's defense-in-depth, applied to documents).
4. **Gates** — status transitions require the policy table's human action (04 §5) plus a green
   validation + traceability report.

**Schema versioning:** schemas are semver'd; documents pin `schema_version`. Breaking schema
changes ship with migrations and ride the platform migration pipeline (06 §3) — a project
upgrade migrates its documents like any other artifact. The schemas live in the eden monorepo
(`schemas/document/v1/`, ADR-0011) and version with the platform release (06 §3 pinning).

## 9. Consumption

- **Technical:** the documents live in the project monorepo (git history = document history),
  render through the standard HTML pipeline, and are reviewable as ordinary diffs.
- **Non-technical:** dashboards render the same projection — charter view, requirement coverage,
  workflow maps, decision log — with status and gate queues surfaced (T8). The visual editor's
  contract (OD-10) holds: edits re-enter as document versions through gates, never as canvas
  mutations.
- **Conversational:** AssistantSessions (02 §1) answer over the projection + link graph ("which
  requirements does this component serve?", "what's unverified?").
- **The user's edit loop** is the gate loop: `edit`-policy documents are amendable in place
  before approval; everything after approval is supersession.

## 10. Open questions

| # | Question | Disposition |
|---|---|---|
| Q1 | EARS strictness for `requirements.statement` — enforce the template grammar or recommend-only in v1? | recommend-only v1; revisit with intake-agent eval data 🔶 |
| Q2 | `$id` hosting — schemas use the logical URI scheme `eden://document/v1/<name>`; publish resolvable URLs when the gateway exists? | logical now; OD entry when hosted tier is scoped |
| Q3 | Do pipeline records (04 §4) migrate into this envelope or keep their own? | own schemas, same id/link grammar — revisit at engine build |
