# infrastructure — platform and contracts discipline

Rules for changes to `platform/*` and `contracts/*`. These layers are
load-bearing for every app in the ecosystem.

## Rules for `platform/core/*`

- **Non-negotiable.** Every cluster installs every core component at bring-up.
  There is no opt-out per cluster.
- **Pin the versions across the repo.** A single Helm chart version per core
  component applies to every cluster. A bump is a deliberate, staged operation.
- **The install order is fixed.** See `platform/core/README.md`.
- **A new core component is rare.** If every cluster does not strictly need it,
  it belongs in `platform/services/`.
- **A version bump must go through the approval flow for shared changes**,
  because a breaking bump affects every cluster.

## Rules for `platform/services/*`

- **A cluster opts in** through `clusters/instances/<c>/identity.yaml`.
- **The version is pinnable per cluster.** The identity.yaml of a cluster pins
  the version it wants, and the overlay supplies the values for that cluster.
- **A new service carries a lower risk.** No cluster is affected until it opts
  in.
- **One category may hold several implementations**, for example
  `databases/postgresql/` and `databases/redis/`.

## Rules for `contracts/*`

- **A contract describes the app-facing surface.** A change affects every app
  that consumes the contract.
- **A backward-compatible addition** (a new optional field) is a minor version
  bump.
- **A breaking change** (a renamed field, changed semantics, or a removed field)
  requires all of the following:
  - a `version:` bump in the contract's front-matter,
  - a migration note in the contract,
  - a matching change in every `charts/*` archetype that emits the manifests of
    this contract,
  - a release cycle coordinated with the consumer projects.
- **Never invent a contract that no `platform/*` component backs.** A contract
  with no implementation is a promise we cannot keep.

## Cross-cutting: where the switch happens

To swap `platform/services/databases/postgresql/` from CNPG to Neon, or to
anything else, you should touch:

- `platform/services/databases/postgresql/` — the new implementation.
- `contracts/databases.md` — only if the app-facing interface changes (the Secret
  shape, the CR kind, or the annotations). Keep it stable if you can.

An app MUST NOT need a change. If it does, then the contract changed, and that is
a breaking event.

## CI expectations

`scripts/verify-structure.sh` runs on every pull request, from
`.github/workflows/validate.yml`. Run it locally with
`bash ctl.sh verify-structure`. It asserts:

- Every `contracts/*.md` opens with front-matter and carries the 5 sections
  (Abstract, Interface, Guarantees, Caveats, Example).
- Every `charts/<archetype>/` has a README.md.

**Not built, and deliberately not built:** a README-presence rule over
`platform/<tier>/<path>/`. The deleted `.ci/` layer had one. It demanded a README
in every directory, including directories that hold only a script or only Argo
AppProject YAML, so it reported 9 errors that were all the rule being wrong.
A rule that fires on a correct tree trains people to ignore red.

**Still not built:** the assertion that a "fulfills contract X" claim matches a
real file. Nothing checks it today.
