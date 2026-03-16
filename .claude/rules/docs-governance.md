# Documentation Governance

Rules for maintaining documentation cohesion as the system grows. These apply to both AI and human editors.

## Editor Protocol

When creating or modifying documentation:

1. **Check the layer map** (see `docs-system.md`). Place the doc in the correct layer.
2. **Update the index.** Add the doc to the parent `index.md` table.
3. **Update MkDocs nav.** Add the doc to `apps/docs/mkdocs.yml` under the correct section.
4. **Add cross-references.** If the doc relates to other docs, add relative links.
5. **Update `.instrumentation.json`** if you created a new rule or skill based on doc content.

## Freshness

Every architecture and reference document should include at the top:

```markdown
**Last reviewed:** YYYY-MM-DD
**Status:** Draft | Active | Superseded
```

- **Draft**: Work in progress, may change significantly
- **Active**: Current and authoritative
- **Superseded**: Replaced by another doc (link to replacement, then move to `_archive/`)

Review interval: architecture docs every 90 days, reference docs every 60 days.

## Cohesion Checks

Before any large documentation change, verify:

1. **No duplicates.** Search for the topic across all layers. If it exists elsewhere, link — don't copy.
2. **No orphans.** Every doc must appear in its layer's `index.md` and in `mkdocs.yml`.
3. **No stale references.** If you move or rename a doc, grep for the old path and update all references.
4. **Archive has a reason.** Every `_archive/` entry should have a note about why it was archived.

## Architecture Decision Records (ADRs)

For significant design decisions:

1. Create `architecture/{domain}/ADR-NNN-short-title.md`
2. Use sequential numbering within the domain
3. Include: Context, Decision, Consequences, Status (Proposed/Accepted/Superseded)
4. **Accepted ADRs are immutable.** To change a decision, create a new ADR that supersedes the old one.

## When AI Creates Documentation

When Claude or any AI agent creates or modifies docs:

1. Follow the same layer map and naming conventions as human authors
2. Update `.instrumentation.json` with the source files that informed the content
3. Do not add AI attribution to the document content
4. Flag any docs that appear to contradict existing documentation
5. When in doubt about placement, check `docs-system.md` layer map
