# ADR-0010: Documentation scheme and repository housekeeping

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo (directive: one standard, cohesive, simplified); rulings drafted by the
  architecture session

## Context

Documents accumulated across many sessions with inconsistent conventions: SCREAMING-case planning
docs at the repo root (`LIBRARIES.md`, `LIBRARY-SYSTEM.md`) beside kebab-case sets under `docs/`,
an empty `go/` directory tree, template boilerplate still named helios, no CLAUDE.md, and no
stated rule for where a new document belongs. Much of this content is untracked, so deletion is
unrecoverable — "remove" needs a preservation policy.

## Decision

1. **Four document classes** — canonical specs (`docs/architecture/`), research notes
   (`docs/research/`), operational READMEs (one per directory), and the attic (`docs/attic/`) —
   with the naming and behavioral rules specified in `docs/README.md` §1 (the scheme's canonical
   home).
2. **Lowercase kebab-case filenames** everywhere; uppercase only for tool-imposed names
   (`README.md`, `CLAUDE.md`, `LICENSE`).
3. **Attic policy:** superseded or absorbed documents are moved to `docs/attic/` verbatim under
   `YYYY-MM-DD-original-slug.md` and logged in `docs/README.md` §3 — never deleted while
   untracked, never cited as authority.
4. **The in-repo half of OD-8 resolved as "one migration pass"** (the external corpus stays
   lazy-on-touch):
   `/LIBRARY-SYSTEM.md` + `/LIBRARIES.md` are absorbed into `architecture/10-library-system.md`,
   updated for ADR-0002 (Eden), ADR-0003 (Go 1.26), ADR-0004/0005 (Svelte), and ADR-0009 (A–F).
   Doc 10 preserves the source's §1–§9 numbering so existing "§N" citations remain stable.
5. **Generated artifacts are gitignored reading copies**, regenerable from `docs/tools/`.
6. **Template-seed conventions ratified** (previously stated only in the seed README):
   Conventional Commits, and Nx Cloud disabled (`neverConnectToCloud`). Operational
   docs cite this ruling. **AMENDED 2026-08-25 by [ADR-0032](0032-git-process-single-home.md):**
   this clause read "Conventional Commits with **no AI/LLM attribution lines**".
   That half is REVERSED — attribution is identity, and
   `.claude/rules/git-process.md` §13 is its single home: an agent authors as
   `Claude <claude-agent@gophersys.noreply>`, joint work carries
   `Co-Authored-By: Claude`. The Conventional Commits half stands.
7. **Repo identifier cleanup under E7:** root `README.md` rewritten for Eden; `package.json` name
   `@helios/source` → `@eden/source`; the empty `go/` tree removed; regenerable PoC binaries
   removed. `poc/` content itself is retained as donor material (ADR-0009 D) and deliberately not
   renamed (ADR-0002: historical artifacts keep their names).

## Consequences

- Every future document has exactly one correct home and name; "where does this go" is a lookup,
  not a judgment call.
- The architecture set's external-source registry now points at doc 10 instead of the root files;
  all `LIBRARY-SYSTEM §N` citations across the set become `10 §N`.
- The upstream corpus was outside the repo and outside this scheme at the time of this ruling; its
  migration was then lazy-on-touch. **Superseded by ADR-0014:** the corpus is now imported verbatim
  into `docs/upstream/` as a fifth document class.
- The repo/origin rename to `gophersys/eden` remains the separately-gated LSC (ADR-0002,
  Consequences); this ADR cleans only in-repo identifiers.
