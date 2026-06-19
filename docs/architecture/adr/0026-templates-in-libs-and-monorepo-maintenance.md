# ADR-0026: Templates fold into `libs`; the monorepo versioning, update & migration model

- **Status:** Accepted
- **Date:** 2026-06-19
- **Deciders:** Mateo (ratified 2026-06-19)
- **Amends:** ADR-0023 (application-template system — *location* only; the 5-files-per-route /
  libs-assembly / phase-gate engineering bar is unchanged), ADR-0009 (submodule layout).

## Context

Eden must be able to **regenerate itself** — "create Eden inside Eden" — from a *golden* monorepo
template (`gophersys/template`). Two problems block that today:

1. **The template is a thin TS scaffold** that captures ~10% of what eden actually is (no Go
   workspace, no `.githooks`/`.claude` enforcement, no `docs` scheme, no `deploy`, no `tools`, stale
   submodule pins, and a confused `monorepo/`-nested layout). A repo generated from it is not "all
   the goods."
2. **The hard part isn't files — it's keeping spawned monorepos alive.** N generated monorepos all
   drift the moment a shared foundation (a lib, the devcontainer, a template) moves. Without a
   deliberate versioning / update / migration model, every foundation change becomes hand-surgery
   across the fleet.

A specific instance of (2): **application-templates was a separate 4th submodule**, but a template's
whole job is to ASSEMBLE the shared `libs/go/*` libraries — so a lib API change breaking its template
is the *normal* case, not an edge case. Two repos turned every such change into a cross-repo dance
(bump lib → release → re-pin in templates → hope they agree).

## Decision

### A. Templates fold into `libs` as `libs/templates/` (and drop the 4th submodule)

`gophersys/application-templates` is merged into `gophersys/libs` as a new subtree
`libs/templates/` — a sibling of `libs/go/` and `libs/typescript/`. The standalone
`application-templates` submodule is removed; the monorepo drops from **4 submodules → 3** (`libs`,
`.devcontainer`, `infrastructure`).

- **Rationale.** Templates are lib-assemblies and the same *kind* of artifact (gated, versioned,
  four-phase). Co-locating them makes a lib change and its template update **one atomic commit, one
  gate run** — they are physically never out of sync. This eliminates the #1 break source.
- **Module path.** `github.com/gophersys/application-templates/go/http-gateway` →
  `github.com/gophersys/libs/templates/go/http-gateway`.
- **Independent versioning preserved.** *One repo ≠ one version.* Each project (`libs/go/<lib>`,
  `libs/typescript/<lib>`, `libs/templates/go/<template>`) keeps **independent semver** via Nx
  release / path-based tags, so bumping a template never force-bumps every consumer of a sibling lib.
  Atomic-change benefit, independent-cadence benefit, no downside.

### B. The golden monorepo template ships the *maintenance machinery*, not just files

"Golden" is defined by **updatability**, not by a nice file tree. Every monorepo generated from the
template carries the mechanism to be versioned, updated, and migrated:

1. **Version everything, with a breaking signal.** Semver tag + changelog per artifact. Libs already
   have the load-bearing trick — the frozen `.apibaseline` (exported-surface break = major). The
   template, `.devcontainer`, and each `libs/templates/*` carry the same honest major/minor/patch.
2. **A monorepo BOM (bill-of-materials / lock).** One manifest at the instance root recording the
   exact versions it is pinned to (`template@`, `libs@`, `.devcontainer@`, toolchain pins — extending
   the existing `harnesses/versions.env` precedent). The single source of truth for "where am I," and
   what an update diffs against.
3. **The template-owned vs instance-owned boundary.** Every path is exactly one of: **template-managed**
   (synced from upstream, never hand-edited — `.devcontainer`▸, `.githooks`, `.ci`, `.claude` rules,
   `harnesses`, root configs, the doc *scheme*, the migrate runner), **instance-owned** (the user's
   product — `apps/*`, the instance's own docs/deploy; sync never touches it), or **submodule**
   (versioned independently, pinned by the BOM). This split decides, for every folder, whether updates
   flow into it.
4. **Update / sync, two channels.** Submodules bump to a newer *released* version (not "whatever main
   is"). Template-managed scaffold files get a **3-way merge** from the template upstream (the
   copier/cruft pattern: the instance remembers its template version; `template sync` re-applies
   upstream changes while preserving local edits).
5. **Migrations.** A bump is not enough when something *breaks* (a lib goes major, a config format
   changes, a folder moves). The breaking change ships a **migration**: a versioned, ordered,
   idempotent codemod/script that lives *with the release that introduced it*; the instance runs it on
   update. Nx already models this (`migrations.json` → `nx migrate --run-migrations`); we extend the
   same idea to Go + the monorepo layout (a `migrations/` tree + a runner).
6. **Verify — incoherence is un-shippable.** After bump+migrate, re-run the *uniform* gates (the CI
   contract / `cictl`). "Green" means the same thing in every instance, so an update is provably safe
   or it does not land.
7. **Fleet propagation (agentic).** A foundation release fires an **automated PR into every dependent**
   that bumps the pin, runs the migrations, re-runs the gates, and **auto-merges on green** — a human
   is pulled in only when a migration needs judgment (the open knob: always-human on *major* bumps).
   This is the propagation-graph DAG: foundation change cascades → dependents re-verify → incoherence
   cannot ship.

### C. The template is flat

The template's `monorepo/`-nesting + duplicate `apps/.gitkeep` is removed; the template mirrors
eden's actual flat layout. (Folder-by-folder content is decided separately, under this contract.)

## Consequences

- One fewer repo/submodule to version, pin, and propagate; lib+template changes are atomic.
- ADR-0023's location ("a 4th submodule") is superseded; its engineering bar is untouched. The
  canonical spec `16-application-template-system.md` is updated to the `libs/templates/` home.
- The golden template gains first-class, to-be-built machinery: a **BOM manifest**, a
  **`migrations/`** tree + runner, a **managed-paths manifest** (template-owned vs instance-owned), and
  a **sync** tool. These are designed alongside the folder-by-folder pass, not after it.
- Open knob to settle during build-out: how aggressive auto-merge-on-green is vs. always-human on
  majors.
