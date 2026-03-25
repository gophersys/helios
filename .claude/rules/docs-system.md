# Documentation System

Concord uses a function-first documentation structure. Documents are organized by **what kind of document they are**, not by domain. Domain is a subfolder within each layer.

## Layer Map

```
docs/
├── vision/              WHY — thesis, philosophy, principles
├── architecture/        WHAT — system design and decisions
│   ├── platform/        Cross-cutting infrastructure
│   ├── validation/      Five-stage validation system
│   └── build/           Firmware build orchestrator
├── reference/           LOOKUP — specs, APIs, procedures, hardware
├── guides/              HOW-TO — step-by-step walkthroughs
├── research/            FINDINGS — investigation notes and analysis
├── journals/            LOGS — development progress
├── diagrams/            VISUAL — draw.io system diagrams
└── _archive/            HISTORY — completed plans, superseded docs
```

## Where Does a New Document Go?

| Question the doc answers | Layer | Example |
|--------------------------|-------|---------|
| Why does this exist? What problem are we solving? | `vision/` | Embedded CD thesis, validation philosophy |
| How is the system designed? What are the components? | `architecture/{domain}/` | Stage specs, build service, CI pipeline |
| What's the exact API/spec/procedure for X? | `reference/` | FUOTA workflow, test case catalog, HIL reference |
| How do I do X step-by-step? | `guides/{product}/` | Alpha stage walkthroughs |
| What did we learn investigating X? | `research/` | Firmware analysis, CoreCloud integration |
| What changed between date A and date B? | `journals/` | Development progress logs |

## Naming Conventions

- **Filenames**: lowercase kebab-case, descriptive (`stage4-fuota-flow.md` not `04-fuota.md`)
- **Index files**: every directory has an `index.md` with a table of contents
- **New domains**: create a subfolder under the appropriate layer (`architecture/manufacturing/`, `guides/sigma5/`)
- **ADRs** (Architecture Decision Records): use prefix `ADR-NNN-` when created (`ADR-001-database-choice.md`)

## Cross-References

When referencing another doc, use relative paths from the current file:

```markdown
See [the build service](../build/build-service.md) for artifact storage details.
```

## Zensical

Documentation is served via Zensical (next-gen static site generator from the Material for MkDocs team). Config lives at the repo root: `mkdocs.yml`.

```bash
npx nx serve docs      # http://localhost:4000
npx nx run docs:build  # static site in apps/docs/site/
```

When adding a new document, also add it to `mkdocs.yml` in the `nav:` section.

## Rules

1. **Every new doc gets an index entry.** Update the parent `index.md` and `mkdocs.yml` nav.
2. **No orphan docs.** Every doc must be reachable from the layer index.
3. **One source of truth.** If the same information exists in two places, one must link to the other as the authority. Do not maintain parallel copies.
4. **Archive, don't delete.** Move superseded docs to `_archive/` with a note about what replaced them.
5. **Domain goes under function.** `architecture/validation/` not `validation/architecture/`. The layer (function) is the top-level organizer.
