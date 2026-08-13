# contracts

What an application monorepo can rely on from `infrastructure/`, and what
infrastructure expects from an application in return.

## What infrastructure provides

1. **Hosts.** Through `machines/hosts/<name>/`, every application can assume that
   a host is reachable on the tailnet under the name declared in
   `identity.yaml:tailscale_hostname`. `machines/scripts/ssh-ephemeral.sh`
   mediates SSH with keys from Bitwarden.

2. **Clusters.** Through `clusters/instances/<name>/`, an application can assume
   that a kubeconfig is available for `describe`, `logs` and similar commands
   from the cluster instance's ctl.sh. An application NEVER receives a raw
   kubeconfig file. It calls the cluster's `shell` or `exec` verbs.

3. **Platform services.** Through `platform/*`, an application can assume these
   cluster-level endpoints:

   - An `Ingress` controller and a cert-manager ClusterIssuer named
     `letsencrypt-prod` (and `letsencrypt-staging` in a dev cluster).
   - An `ExternalSecrets` `ClusterSecretStore`. Read its name from the manifest
     that declares it,
     `platform/core/secrets-operator/manifests/clustersecretstore.yaml`, and
     never from this document. This line read `bitwarden-tenant-default` from
     2026-04-19. The store has been named `vaultwarden` since it was created on
     2026-07-04, and it has never carried another name.
   - A Postgres control plane reachable through cnpg `Database` CRs in any
     namespace.
   - A NATS cluster at `nats://nats.messaging.svc.cluster.local:4222`.
   - Prometheus ServiceMonitor discovery for any pod with the
     `prometheus.io/scrape: "true"` annotation, or for a matching ServiceMonitor
     in any namespace.

4. **Charts.** Through `charts/*`, an application has pre-validated chart
   archetypes for stateless, stateful, ingress, job and cronjob workloads. It
   never writes its own Deployment, Service or Ingress manifests.

## What an application must do

1. **Declare every dependency.** Name the chart it consumes, the SecretStore it
   references and the cluster it targets in the application's own configuration.
   Never discover them at runtime.

2. **Use ExternalSecrets, not hardcoded Secrets.** A committed Kubernetes Secret
   manifest with real data is a policy violation.

3. **Expose `/health` and `/metrics` where they apply.** By default the
   stateless-app chart wires liveness and readiness to `/health` and Prometheus
   to `/metrics`. To opt out you must give a documented reason.

4. **Respect the cluster timezone and the resource defaults.** The default
   cluster timezone is `Europe/Madrid`. Override it per workload only with a
   justification.

## What neither party does

- Neither side reads or changes the Bitwarden vault, except through
  `machines/scripts/*`. There is no `bw` CLI in the cluster.
- Neither side commits a generated kubeconfig, a TLS certificate or an SSH key
  file to any repo.
