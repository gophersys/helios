# infrastructure — onboarding procedures

The canonical procedures to add a new thing. When the user asks you to onboard a
machine, a cluster, a service or an app, follow the procedure below for that
kind.

## Onboard a new machine (individually managed)

1. Choose the category: `development` (a workstation) or `services` (a standalone
   server, for example a bastion, a builder or an edge host).
2. Choose a template:
   - Workstations: `templates/development/{linux,macOS,windows,wsl}-*`.
   - Services: `templates/services/linux-server-bastion`, or
     `linux-service-generic` when that template is populated.
3. Scaffold:
   ```
   bash machines/ctl.sh new-host <category> <template> <host-name>
   ```
4. Edit `machines/<category>/<host-name>/identity.yaml` and resolve every TODO.
5. If the host has scripts that are local to it, put
   them at `machines/<category>/<host-name>/scripts/`.
6. Regenerate the index:
   ```
   bash machines/ctl.sh generate-index
   ```
7. Commit: `feat(machines): enroll <category>/<host-name>`.

## Onboard a new cluster

1. Choose a template from `clusters/templates/`:
   - `cluster-kubernetes-manual-k3s` — self-managed K3s on tailnet hosts.
   - `cluster-cloud-{aws-eks,azure-aks,oracle-oke}` — managed Kubernetes.
2. Scaffold. A verb will do this in the future; today do it by hand:
   ```
   mkdir -p clusters/instances/<name>/{nodes,overlays}
   cp clusters/templates/<template>/cluster-identity.yaml \
      clusters/instances/<name>/identity.yaml
   # substitute __CLUSTER_NAME__ with <name>
   ```
3. Edit `clusters/instances/<name>/identity.yaml` and resolve every TODO,
   including the `platform_services` opt-in list.
4. For a self-managed cluster (manual-k3s), declare the members under
   `clusters/instances/<name>/nodes/<host>/identity.yaml`. Use the template at
   `clusters/templates/cluster-kubernetes-manual-k3s/nodes/`.
5. For a managed cluster (EKS, AKS, OKE), create no `nodes/` entries. The cloud
   owns the node lifecycle through `providers/<cloud>/modules/`.
6. Commit: `feat(clusters): onboard <name>`.

## Onboard a new platform/core component

A core component is non-negotiable: to add one means that EVERY cluster will
install it. This should be rare.

1. Justify it. The new component must be strictly necessary for EVERY cluster. If
   it is not, it belongs in `platform/services/`.
2. Create `platform/core/<name>/README.md`. Describe the purpose, the default
   implementation, the dependencies and the contracts it fulfills.
3. When you populate it, add `ctl.sh`, `project.json`, and `helm/` or
   `manifests/`.
4. Update the install-order list in `platform/core/README.md`.
5. Commit: `feat(platform/core): add <component>`.

## Onboard a new platform/services component

A service is opt-in. To onboard one means that a future cluster can request it
through `platform_services:` in its identity.yaml.

1. Create `platform/services/<category>/<impl>/README.md`. Describe the purpose,
   the default implementation, the dependencies and the contracts it fulfills.
2. If it fulfills a contract, link to the `contracts/*.md` file.
3. When you populate it, add `ctl.sh`, `project.json`, and Helm or kustomize.
4. Update the table in `platform/services/README.md`.
5. Commit: `feat(platform/services): add <category>/<impl>`.

## Onboard a new contract

A contract defines what an app sees. A change to a contract affects every app
that consumes it. Add a contract only when it is necessary.

1. Create `contracts/<name>.md` with the outline in `contracts/README.md`.
2. Wire the `platform/*` component or components that fulfill it into the
   contract document.
3. If a chart archetype emits the manifests of the contract, update that chart in
   `charts/`.
4. Set the contract's `version:` in its front-matter.
5. Commit: `feat(contracts): add <name>`.

## Onboard a new provider

1. Create `providers/<name>/README.md`. Describe which cloud or substrate it
   targets, and which `compute-unit` requests it will fulfill.
2. When you populate it, add Terraform modules under
   `providers/<name>/modules/<thing>/`.
3. Update the table in `providers/README.md` and the fulfillment matrix in
   `providers/compute-unit/README.md`.
4. Commit: `feat(providers): add <name>`.
