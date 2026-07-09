# platform/services/gitops — Argo CD

The GitOps reconciler for clusters that opt in via
`clusters/instances/<c>/identity.yaml → platform_services.gitops`. Argo CD
watches this repo and reconciles the desired state onto the cluster.

> **Status: LIVE.** The running Argo's `root` app-of-apps reconciles
> `platform/services/gitops/registry/` @ `main` (self-healing, recursive) — this
> tree IS the cluster's desired state. Dropping an `app-*.yaml` into `registry/`
> registers a new workload. The old `kubernetes/argocd/` location no longer
> exists (migration history: `docs/migration-homelab-to-idp.md`).

## Layout
```
bootstrap/
  values.yaml     # Argo CD Helm values (chart argo-cd 10.1.2 / app v3.4.4)
  ingress.yaml    # argocd.mateosegura.com — tailnet-private, LE DNS-01 TLS
  root-app.yaml   # the ONE hand-applied app-of-apps entrypoint
registry/
  projects/       # AppProjects: platform, media, ci, workspaces, embedded, apps, argocd (tenancy fences)
  argocd-self.yaml    # Argo manages its own Helm install
  app-*.yaml          # child Applications (media stack, minio, ARC, workspaces, eden, cloudflared, ...)
```

## Decisions (see docs/migration-homelab-to-idp.md)
- Namespace stays **`argocd`** (documented exception; moving it = controller reinstall).
- Bootstrap `root-app.yaml` is the sanctioned break-glass hand-apply; everything
  else is git-reconciled.
