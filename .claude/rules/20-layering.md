# infrastructure — layering

Claude, when you work in this repo, you MUST classify the change against the
seven layers below and keep each change within its layer. Cross-layer
changes are legitimate but must be **explicit**, not accidental.

## The layers (authoritative)

1. **`machines/`** — individually-managed hosts. Ansible owns them.
   - `machines/development/<name>/` — dev workstations.
   - `machines/services/<name>/` — standalone servers, bastions, builders.
   - NOT cluster nodes.

2. **`clusters/`** — Kubernetes clusters. Kubernetes owns the nodes once
   bootstrapped.
   - `clusters/instances/<name>/identity.yaml` — the cluster declaration.
   - `clusters/instances/<name>/nodes/<host>/identity.yaml` — cluster
     member hosts (same identity shape as `machines/`).
   - `clusters/instances/<name>/overlays/` — per-cluster value overrides
     for `platform/*`.

3. **`providers/`** — Terraform. How compute is created.
   - `providers/compute-unit/` — the cloud-neutral interface.
   - `providers/<cloud>/modules/` — per-cloud implementations.
   - Pure libraries; providers do NOT carry state.

4. **`platform/`** — what runs ON clusters.
   - `platform/core/<component>/` — non-negotiable (every cluster gets
     every core component at bring-up).
   - `platform/services/<category>/<impl>/` — opt-in, version-pinned.

5. **`charts/`** — Helm archetypes apps adopt to shape themselves.

6. **`contracts/`** — the app–platform interface. Apps consume the
   platform via these; implementations under `platform/` can change
   without breaking apps as long as contracts are preserved.

7. **`docs/`** — big-picture architecture, runbooks, onboarding guides.

## Cross-layer rules

- A machine (1) or cluster-node (2) may declare `provider:` pointing at a
  concrete implementation (3). That's the one allowed cross-layer reference
  in identity.yaml.
- A cluster (2) opts into `platform/services/*` (4) via its identity.yaml.
  Never the other way around — platform components don't know which
  clusters will consume them.
- Apps (outside this repo) consume `contracts/*` (6) only. They never
  reference `platform/*` (4) paths directly.
- `charts/*` (5) may reference `contracts/*` (6) to document which
  contracts an archetype satisfies. Never the other way around.

## Where new content goes

Before writing a file, ask which layer it belongs in. Common mistakes:

- "This script manages a specific host" → `machines/<kind>/<host>/scripts/`.
  NOT `machines/scripts/` (that's for fleet-wide).
- "This is a Helm manifest for Cilium" → `platform/core/cni/` (never
  `providers/` — Helm isn't Terraform).
- "This is a cluster node declaration" → `clusters/instances/<c>/nodes/<host>/`.
  NOT `machines/services/<host>/`.
- "This is the app-facing CRD schema" → `contracts/*.md` (describe), plus
  `platform/services/<impl>/` (implement).

## When to add a new layer

Never, for now. Seven layers is enough. If you find yourself wanting an
eighth, first ask whether the new concern fits into an existing layer —
usually it does. Adding a layer is an architectural change that requires
explicit discussion.
