# infrastructure — platform & contracts discipline

Rules for touching `platform/*` and `contracts/*`. These layers are
load-bearing for every app in the ecosystem.

## Core (`platform/core/*`) rules

- **Non-negotiable.** Every cluster installs every core component at
  bring-up. There's no per-cluster opt-out.
- **Pin versions repo-wide.** A single Helm chart version per core
  component applies to every cluster. Bumping is a deliberate, staged op.
- **Install order is fixed.** See `platform/core/README.md`.
- **Adding a core component is rare.** If it's not strictly needed by
  every cluster, it belongs in `platform/services/`.
- **Version bumps must go through the shared-change approval flow** — a
  breaking bump affects every cluster.

## Services (`platform/services/*`) rules

- **Opt-in per cluster** via `clusters/instances/<c>/identity.yaml`.
- **Version-pinnable per cluster.** A cluster's identity.yaml pins the
  version it wants; overlay supplies per-cluster values.
- **Adding a service is lower-stakes.** No cluster is affected unless it
  opts in.
- **One category, multiple implementations is OK** (e.g.,
  `databases/postgresql/` + `databases/redis/`).

## Contracts (`contracts/*`) rules

- **Contracts describe the app-facing surface.** Changes affect every app
  consuming the contract.
- **Backward-compatible additions** (new optional fields) are a minor
  version bump.
- **Breaking changes** (renaming fields, changing semantics, removing
  fields) require:
  - a `version:` bump in the contract's front-matter,
  - a migration note inline in the contract,
  - a corresponding change in every `charts/*` archetype that emits this
    contract's manifests,
  - a release cycle coordinated with consumer projects.
- **Never invent a contract that isn't backed by at least one
  `platform/*` component** — contracts without implementations are
  promises we can't keep.

## Cross-cutting: where the switch happens

Swapping `platform/services/databases/postgresql/` from CNPG to Neon (or
anything else) should touch:

- `platform/services/databases/postgresql/` — new implementation.
- `contracts/databases.md` — only if the app-facing interface changes
  (Secret shape, CR kind, annotations). Keep it stable if at all possible.

Apps MUST NOT need to change. If they do, the contract changed and that's
a breaking event.

## CI expectations

The `.ci/` layer should eventually validate:
- Every `platform/<tier>/<path>/` has a README.md with the required sections.
- Every `contracts/*.md` parses the front-matter and has the five sections
  (Abstract, Interface, Guarantees, Caveats, Example).
- Every claim that "this service fulfills contract X" matches a real file.

Until populated, these checks are aspirational but specified.
