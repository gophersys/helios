# platform/services/networking/tailscale-operator

Tailscale Kubernetes operator — exposes in-cluster Services on the tailnet
(MagicDNS names, tailnet-only reachability) and can provide subnet-router /
API-server proxy functionality later.

## Purpose

Give workloads a **per-Service tailnet identity** without touching MetalLB or
ingress-nginx: any Service with `type: LoadBalancer` +
`loadBalancerClass: tailscale` gets its own Tailscale node (a proxy pod the
operator creates) and a MagicDNS hostname taken from the
`tailscale.com/hostname` annotation. First consumer: the ephemeral Zephyr
embedded dev environments (`apps/embedded/`) — each env gets its own
`ssh zephyr-<env>` MagicDNS name.

## Default implementation

Upstream Helm chart `tailscale-operator` from
`https://pkgs.tailscale.com/helmcharts`, pinned per-cluster in the driving
Argo Application (homelab:
`platform/services/gitops/registry/app-tailscale-operator.yaml`, chart
`1.98.4`, namespace `tailscale`, operator hostname `homelab-ts-operator`).
Following the repo's helm-service pattern (see `app-kyverno.yaml`), the
registry Application carries the chart reference **and** the values — this
directory documents the service; it does not duplicate the values.

## Bootstrap secret (NOT in git)

The operator authenticates to the Tailscale control plane with an OAuth
client. It expects a Secret `operator-oauth` in the `tailscale` namespace.
ESO/Vaultwarden bridge is currently broken, so — exactly like
`media/gluetun-wireguard` — the Secret is created **imperatively**:

1. Tailscale admin console → Settings → OAuth clients → new client with the
   **Devices: write** scope, tags `tag:k8s-operator` (owner of `tag:k8s`).
   Ensure the tailnet ACL declares:

   ```jsonc
   "tagOwners": {
     "tag:k8s-operator": [],
     "tag:k8s": ["tag:k8s-operator"],
   }
   ```

2. Store the client id/secret in Vaultwarden as
   `tailscale-oauth-k8s-operator`.
3. Create the Secret (before or after the Application syncs — the operator
   pod crash-loops harmlessly until it exists):

   ```bash
   kubectl -n tailscale create secret generic operator-oauth \
     --from-literal=client_id="$(bw get username tailscale-oauth-k8s-operator)" \
     --from-literal=client_secret="$(bw get password tailscale-oauth-k8s-operator)"
   ```

## Dependencies

- `platform/services/gitops/` — the Argo Application drives the install.
- Tailnet admin access (OAuth client + ACL tagOwners) — out-of-band, one-time.
- Kyverno exclusion: the operator's proxy pods need elevated capabilities
  (tun device, NET_ADMIN), so the `tailscale` namespace is excluded in
  `platform/core/policy/policies/pod-security-baseline.yaml` and in
  `app-kyverno.yaml`'s `resourceFiltersExcludeNamespaces`.

## Consumer interface

```yaml
apiVersion: v1
kind: Service
metadata:
  annotations:
    tailscale.com/hostname: my-thing        # MagicDNS name on the tailnet
spec:
  type: LoadBalancer
  loadBalancerClass: tailscale              # NOT the MetalLB pool
```

## Status

Greenfield install for `homelab` (nothing Tailscale-related existed in the
cluster before this). Opt-in via
`clusters/instances/homelab/identity.yaml → platform_services.networking`.
