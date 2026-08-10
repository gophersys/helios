# platform/services/gitops — Argo CD

The GitOps reconciler for a cluster that opts in through
`clusters/instances/<c>/identity.yaml → platform_services.gitops`. Argo CD
watches this repo and reconciles the desired state onto the cluster.

> **Status: LIVE.** The `root` app-of-apps of the running Argo reconciles
> `platform/services/gitops/registry/` at `main`, with self-healing and
> recursion. This tree IS the desired state of the cluster. A new `app-*.yaml`
> file in `registry/` registers a new workload. The old location
> `kubernetes/argocd/` no longer exists. The migration history is in
> `docs/migration-homelab-to-idp.md`.

## Layout
```
bootstrap/
  values.yaml     # Argo CD Helm values (chart argo-cd 10.1.2 / app v3.4.4)
  ingress.yaml    # argocd.mateosegura.com — tailnet-private, LE DNS-01 TLS
  root-app.yaml   # the ONE hand-applied app-of-apps entrypoint
registry/
  projects/       # AppProjects: platform, media, ci, workspaces, embedded, apps, argocd (tenancy limits)
  argocd-self.yaml    # Argo manages its own Helm install
  app-*.yaml          # child Applications (media stack, minio, ARC, workspaces, eden, cloudflared, ...)
```

## Decisions — see docs/migration-homelab-to-idp.md
- The namespace stays **`argocd`**. This is a documented exception, because a
  move of the namespace needs a reinstall of the controller.
- The bootstrap file `root-app.yaml` is the one approved break-glass file that
  you apply by hand. Git reconciles everything else.
