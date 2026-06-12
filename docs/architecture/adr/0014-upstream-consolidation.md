# ADR-0014: Consolidate the upstream corpus into the repo; human-first entry layer

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo (directive: one place, human-approachable, reduce reading burden)

## Context

The canonical set cited reference material living outside the repo
(`~/Documents/research/agentic-engineering/`, `~/Documents/Claude/Projects/Helios/`) — outside
version control, invisible to the atlas, and confusing at the entry point (the layering diagram
opened with home-directory paths). Separately, the corpus had grown to a volume where the
structure — which exists (ADR-0010 scheme, doc 11 types, doc 04 process) — was no longer
*experienced* as structure: the entry surfaces presented everything instead of a path. OD-8 had
recommended lazy on-touch migration; consumption pain overruled it.

## Decision

1. **One repo.** The two upstream trees are copied verbatim into `docs/upstream/agentic-engineering/`
   and `docs/upstream/build-system/`, each with a compact index README. Originals remain in
   `~/Documents` as historical copies; the in-repo copies are what the canonical set cites.
2. **A fifth document class — upstream corpus** (amends the ADR-0010 scheme): verbatim
   point-in-time imports, Helios-era naming preserved, never edited in place; the canonical set
   supersedes upstream on every conflict. Exempt from register/naming sweeps like the attic.
3. **All citations repoint** to the in-repo paths; the architecture README's layering diagram and
   source registry reference only repo-relative locations.
4. **The root README is the human front door**: plain language, the development loop in six
   steps, the five document classes in one line each, an explicit three-document reading list,
   and explicit permission to treat everything else as reference. Reference density is for
   agents; the entry layer is for humans.

## Consequences

- OD-8's external half is resolved (this supersedes the lazy-on-touch lean); the only remaining
  Helios-named material is inside verbatim-preserved classes (upstream, attic, intake), by design.
- The repo is self-contained: a fresh clone carries every document the canon cites.
- The reading burden is unchanged in volume but tiered at every entry point: read three, skim the
  atlas, consult the rest. Future documents must preserve this tiering (a new doc must either be
  on a reading path or be reference — stated in its status header is sufficient).
