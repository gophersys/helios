# platform/services/gitops — Argo CD

The GitOps reconciler for clusters that opt in via
`clusters/instances/<c>/identity.yaml → platform_services.gitops`. Argo CD
watches this repo and reconciles the desired state onto the cluster.

> **Migration status (Phase 1 — DORMANT).** These are the live Argo manifests,
> relocated byte-identical from `kubernetes/argocd/`. **Nothing here is live yet:**
> the running Argo still reconciles from `kubernetes/argocd/` on branch
> `feat/argocd-phase0`. In Phase 2–3 the running Argo is repointed here and the
> internal path/branch references below are updated. See
> `docs/migration-homelab-to-idp.md`.

## Layout
```
bootstrap/
  values.yaml     # Argo CD Helm values (chart argo-cd 10.1.2 / app v3.4.4)
  ingress.yaml    # argocd.mateosegura.com — tailnet-private, LE DNS-01 TLS
  root-app.yaml   # the ONE hand-applied app-of-apps entrypoint
registry/
  projects/       # AppProjects: platform, media, argocd, apps (tenancy fences)
  argocd-self.yaml    # Argo manages its own Helm install
  app-*.yaml          # child Applications (qbittorrent, external-secrets)
```

## References to update on repoint (Phase 2–3, not now)
- `bootstrap/root-app.yaml` → `source.path` (`kubernetes/argocd/registry` →
  `platform/services/gitops/registry`) and `targetRevision` (`feat/...` → `main`).
- `registry/argocd-self.yaml` → `$values` source path + `targetRevision`.
- `registry/app-qbittorrent.yaml`, `app-external-secrets.yaml` → `path` +
  `targetRevision`, once the media/secrets homes exist (later Phase-1 components).

## Decisions (see docs/migration-homelab-to-idp.md)
- Namespace stays **`argocd`** (documented exception; moving it = controller reinstall).
- Bootstrap `root-app.yaml` is the sanctioned break-glass hand-apply; everything
  else is git-reconciled.
