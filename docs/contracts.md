# contracts

What an application monorepo can rely on from `infrastructure/`, and what
infrastructure expects from applications in return.

## What infrastructure provides

1. **Hosts.** Via `machines/hosts/<name>/`, every application can assume
   hosts are reachable on the tailnet under the name declared in
   `identity.yaml:tailscale_hostname`. SSH is mediated by
   `machines/scripts/ssh-ephemeral.sh` with BW-backed keys.

2. **Clusters.** Via `clusters/instances/<name>/`, applications can assume
   a kubeconfig is available for `describe`/`logs`/etc. from the cluster
   instance's ctl.sh. Applications NEVER receive raw kubeconfig files —
   they invoke the cluster's `shell` or `exec` verbs.

3. **Platform services.** Via `platform/*`, applications can assume the
   following cluster-level endpoints:

   - An `Ingress` controller + cert-manager ClusterIssuer named
     `letsencrypt-prod` (and `letsencrypt-staging` in dev clusters).
   - An `ExternalSecrets` SecretStore named `bitwarden-tenant-default`
     pointing at the tenant's Bitwarden org.
   - A Postgres control plane accessible via cnpg `Database` CRs in any
     namespace.
   - A NATS cluster reachable at `nats://nats.messaging.svc.cluster.local:4222`.
   - Prometheus ServiceMonitor discovery for any pod with the
     `prometheus.io/scrape: "true"` annotation or a matching
     ServiceMonitor in any namespace.

4. **Charts.** Via `charts/*`, applications have pre-validated chart
   archetypes for stateless/stateful/ingress/job/cronjob workloads. They
   never write their own Deployment/Service/Ingress manifests.

## What applications must do

1. **Declare dependencies explicitly.** The chart being consumed, the
   SecretStore being referenced, the cluster being targeted — all named
   in the application's own config, never discovered at runtime.

2. **Use ExternalSecrets, not hardcoded Secrets.** Committing a Kubernetes
   Secret manifest with non-dummy data is a policy violation.

3. **Expose `/health` and `/metrics` if applicable.** The stateless-app
   chart wires liveness/readiness to `/health` and Prometheus to
   `/metrics` by default. Opt-out requires a documented reason.

4. **Respect cluster timezone and resource defaults.** Cluster default
   timezone is `Europe/Madrid`; override per workload only when justified.

## What neither party does

- Neither side reads or mutates the Bitwarden vault except through
  `machines/scripts/*`. No in-cluster `bw` CLI.
- Neither side commits generated kubeconfig, TLS cert, or SSH key files
  to any repo.
