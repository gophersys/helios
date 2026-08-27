# Eden Documentation

> Status: Living · 2026-06-12 · The map of everything under `docs/` and the documentation scheme
> (ADR-0010) every document must follow.

## 1. The scheme — five document classes

| Class                | Location                  | Naming                                                           | Rules                                                                                                                                                                                                                                                                                              |
| -------------------- | ------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Canonical specs**  | `docs/architecture/`      | `NN-slug.md`, numbered reading order; ADRs in `adr/NNNN-slug.md` | The source of truth. Status header, epistemic tags (✅🔶⚠️🧩), cohesion contract (one concept, one home), every ruling an ADR. Reviewed; changes propagate.                                                                                                                                        |
| **Research notes**   | `docs/research/`          | `NN-slug.md`, numbered chronologically                           | Point-in-time findings with a research date and sources. Never canonical: findings are **promoted** into specs (with a citation), not edited in place. Supersession is noted at the top, content left intact.                                                                                      |
| **Operational docs** | `README.md` per directory | `README.md` only                                                 | Orientation for the directory they sit in: what this is, how to use it, where the canon lives. No decisions, no specs — they cite. Exception: `docs/architecture/README.md` belongs to the canonical-spec class (it is the set's index and carries its legend, invariants, and cohesion contract). |
| **Attic**            | `docs/attic/`             | `YYYY-MM-DD-original-slug.md`                                    | Superseded/absorbed documents preserved **verbatim** (pre-commit history cannot protect untracked work). Append-only; every entry logged below with its absorption target. Never cite the attic as authority.                                                                                      |
| **Upstream corpus**  | `docs/upstream/`          | verbatim imports, original filenames                             | Point-in-time references imported whole (ADR-0014); Helios-era naming preserved; never edited in place — corrections happen in the canonical set, which supersedes upstream on conflict.                                                                                                           |

Engineering operations have a separate, intentionally small index at
[`engineering/README.md`](engineering/README.md). Its schema-backed system map
routes agents and developers to existing canonical homes and to named processes;
it does not create product or architecture decisions.

**Naming rules (all classes):** filenames are lowercase kebab-case. The only uppercase filenames
are tool-imposed conventions (`README.md`, `CLAUDE.md`, `LICENSE`). One H1 per document — the
title. Specs carry a status header (`Status · date · canonical-home statement`).

**Generated artifacts** (e.g. `docs/architecture/eden-architecture.html`) are reading copies:
gitignored, regenerable via `docs/tools/`, never edited by hand.

## 2. Map

```
docs/
├── README.md                ← this file: the scheme + map
├── architecture/            ← canonical specs: README (doc map) · 00–10 · open-decisions · adr/
│   └── eden-architecture.html   (generated reading copy — see docs/tools/)
├── research/                ← research notes 00–03 (see its README for the index)
├── engineering/             ← small operational map + named engineering processes
├── upstream/                ← verbatim upstream corpus: agentic-engineering/ · build-system/ (ADR-0014)
├── attic/                   ← preserved superseded documents (see §3)
└── tools/                   ← doc tooling (render-html.mjs)
```

Start at [`architecture/README.md`](architecture/README.md) — it owns the reading order, the
epistemic legend, the source registry for the external corpus, and the Eden-level invariants.

## 3. Attic log

| Archived file                                                                | Original             | Absorbed into                                                                                                                                                                                                                                                                                                                                                                                 |
| ---------------------------------------------------------------------------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `attic/2026-06-03-helios-library-system.md`                                  | `/LIBRARY-SYSTEM.md` | `architecture/10-library-system.md` §1–§9, §11 (updated per ADR-0002/0003/0004/0009)                                                                                                                                                                                                                                                                                                          |
| `attic/2026-06-03-helios-library-manifest.md`                                | `/LIBRARIES.md`      | `architecture/10-library-system.md` §10, §12                                                                                                                                                                                                                                                                                                                                                  |
| **DELETED, not archived** — `architecture/13-versioning-and-git-workflow.md` | —                    | `.claude/rules/git-process.md` (ADR-0032). Deleted rather than moved to the attic under Mateo's no-legacy ruling D6 of 2026-08-25, quoted in that ADR. Its §7 per-class-versioning synthesis has **no successor by decision**; the four homes it pointed at survive (11 §4, 10 §8, 06 §3, 09 §4/ADR-0016). Git history holds the content. |
