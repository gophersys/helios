# infrastructure — layering

When you work in this repo, you MUST classify each change against the 7 layers
below, and keep each change inside its layer. A cross-layer change is legitimate,
but it must be **deliberate**, not accidental.

## The layers (authoritative)

1. **`machines/`** — individually-managed hosts. Ansible owns them.
   - `machines/development/<name>/` — dev workstations.
   - `machines/services/<name>/` — standalone servers, bastions, builders.
   - These are NOT cluster nodes.

2. **`clusters/`** — Kubernetes clusters. Kubernetes owns the nodes after the
   bootstrap.
   - `clusters/instances/<name>/identity.yaml` — the cluster declaration.
   - `clusters/instances/<name>/nodes/<host>/identity.yaml` — the member hosts of
     the cluster. They use the same identity shape as `machines/`.
   - `clusters/instances/<name>/overlays/` — value overrides for `platform/*`,
     per cluster.

3. **`providers/`** — Terraform. How compute is created.
   - `providers/compute-unit/` — the cloud-neutral interface.
   - `providers/<cloud>/modules/` — the implementation per cloud.
   - These are pure libraries. A provider does NOT carry state.

4. **`platform/`** — what runs ON a cluster.
   - `platform/core/<component>/` — non-negotiable. Every cluster gets every core
     component at bring-up.
   - `platform/services/<category>/<impl>/` — opt-in and version-pinned.

5. **`charts/`** — the Helm archetypes that an app adopts to shape itself.

6. **`contracts/`** — the interface between an app and the platform. An app
   consumes the platform through these. An implementation under `platform/` can
   change without a break to an app, as long as the contracts stay the same.

7. **`docs/`** — the whole-picture architecture, the runbooks and the onboarding
   guides.

## Cross-layer rules

- A machine (1) or a cluster node (2) may declare `provider:` and point at a
  concrete implementation (3). That is the one cross-layer reference allowed in
  identity.yaml.
- A cluster (2) opts into `platform/services/*` (4) through its identity.yaml.
  Never the other way round. A platform component does not know which clusters
  will consume it.
- An app (outside this repo) consumes `contracts/*` (6) only. It never references
  a `platform/*` (4) path directly.
- A chart in `charts/*` (5) may reference `contracts/*` (6) to document which
  contracts the archetype satisfies. Never the other way round.

## Where new content goes

Before you write a file, ask which layer it belongs in. Common mistakes:

- "This script manages a specific host" → `machines/<kind>/<host>/scripts/`. NOT
  `machines/scripts/`, which is for scripts that apply to every host.
- "This is a Helm manifest for Cilium" → `platform/core/cni/`. Never
  `providers/`, because Helm is not Terraform.
- "This is a cluster node declaration" →
  `clusters/instances/<c>/nodes/<host>/`. NOT `machines/services/<host>/`.
- "This is the app-facing CRD schema" → `contracts/*.md` to describe it, plus
  `platform/services/<impl>/` to implement it.

## When to add a new layer

Never, for now. 7 layers is enough. If you want an eighth layer, first ask
whether the new concern fits into an existing layer. Usually it does. Adding a
layer is an architectural change, and it needs an explicit discussion.
