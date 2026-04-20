# infrastructure — onboarding procedures

Canonical "how to add a new X" procedures. Future-Claude: when the user
asks to onboard a machine / cluster / service / app, follow the procedure
below for the matching kind.

## Onboard a new machine (individually-managed)

1. Decide category: `development` (workstation) or `services` (standalone
   server — bastion, builder, edge).
2. Pick a template:
   - Workstations: `templates/development/{linux,macOS,windows,wsl}-*`.
   - Services: `templates/services/linux-server-bastion` or
     (when populated) `linux-service-generic`.
3. Scaffold:
   ```
   bash machines/ctl.sh new-host <category> <template> <host-name>
   ```
4. Edit `machines/<category>/<host-name>/identity.yaml` — every TODO.
5. If the host has host-local scripts (e.g. `arm-builder`), put them at
   `machines/<category>/<host-name>/scripts/`.
6. Regenerate index:
   ```
   bash machines/ctl.sh generate-index
   ```
7. Commit: `feat(machines): enroll <category>/<host-name>`.

## Onboard a new cluster

1. Pick a template from `clusters/templates/`:
   - `cluster-kubernetes-manual-k3s` — self-managed K3s on tailnet hosts.
   - `cluster-cloud-{aws-eks,azure-aks,oracle-oke}` — managed K8s.
2. Scaffold (future verb; for now, do manually):
   ```
   mkdir -p clusters/instances/<name>/{nodes,overlays}
   cp clusters/templates/<template>/cluster-identity.yaml \
      clusters/instances/<name>/identity.yaml
   # substitute __CLUSTER_NAME__ with <name>
   ```
3. Edit `clusters/instances/<name>/identity.yaml` — every TODO, including
   the `platform_services` opt-in list.
4. For self-managed (manual-k3s): declare members under
   `clusters/instances/<name>/nodes/<host>/identity.yaml`. Use the
   template at `clusters/templates/cluster-kubernetes-manual-k3s/nodes/`.
5. For managed (EKS/AKS/OKE): no `nodes/` entries; node lifecycle is
   owned by the cloud via `providers/<cloud>/modules/`.
6. Commit: `feat(clusters): onboard <name>`.

## Onboard a new platform/core component

Core components are non-negotiable — adding one means EVERY cluster will
install it. This should be rare.

1. Justify: the new component must be strictly necessary for EVERY cluster.
   If not, it belongs in `platform/services/`.
2. Create `platform/core/<name>/README.md` describing purpose, default
   impl, dependencies, contracts fulfilled.
3. When populating: add `ctl.sh`, `project.json`, `helm/` or `manifests/`.
4. Update `platform/core/README.md`'s install-order list.
5. Commit: `feat(platform/core): add <component>`.

## Onboard a new platform/services component

Services are opt-in — onboarding one means future clusters can request it
via `platform_services:` in their identity.yaml.

1. Create `platform/services/<category>/<impl>/README.md` describing
   purpose, default impl, dependencies, contracts fulfilled.
2. If it fulfills a contract, link to the `contracts/*.md` file.
3. When populating: add `ctl.sh`, `project.json`, Helm/kustomize.
4. Update `platform/services/README.md`'s table.
5. Commit: `feat(platform/services): add <category>/<impl>`.

## Onboard a new contract

Contracts define what apps see. Changing a contract affects every app
consuming it. Add contracts sparingly.

1. Create `contracts/<name>.md` using the outline in `contracts/README.md`.
2. Wire the fulfilling `platform/*` component(s) in the contract doc.
3. If any chart archetype emits the contract's manifests, update the
   relevant chart in `charts/`.
4. Mark the contract's `version:` in its front-matter.
5. Commit: `feat(contracts): add <name>`.

## Onboard a new provider

1. Create `providers/<name>/README.md` describing which cloud / substrate
   it targets and which `compute-unit` requests it will fulfill.
2. When populating: add Terraform modules under
   `providers/<name>/modules/<thing>/`.
3. Update `providers/README.md`'s table + the fulfillment matrix in
   `providers/compute-unit/README.md`.
4. Commit: `feat(providers): add <name>`.
