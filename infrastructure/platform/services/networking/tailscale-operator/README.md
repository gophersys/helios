# platform/services/networking/tailscale-operator

The Tailscale Kubernetes operator. It exposes an in-cluster Service on the
tailnet, with a MagicDNS name and reachability from the tailnet only. It can also
give subnet-router and API-server proxy functions at a later date.

## Purpose

Give a workload its own **tailnet identity per Service**, with no change to
MetalLB and no change to ingress-nginx. Any Service with `type: LoadBalancer` and
`loadBalancerClass: tailscale` gets its own Tailscale node — a proxy pod that the
operator creates — and a MagicDNS hostname from the `tailscale.com/hostname`
annotation. The first consumer is the set of temporary Zephyr embedded dev
environments (`apps/embedded/`). Each env gets its own `ssh zephyr-<env>`
MagicDNS name.

## Default implementation

The upstream Helm chart `tailscale-operator` from
`https://pkgs.tailscale.com/helmcharts`. The Argo Application that drives the
install pins the version per cluster. For the homelab that Application is
`platform/services/gitops/registry/app-tailscale-operator.yaml`, with chart
`1.98.4`, namespace `tailscale` and the operator hostname
`homelab-ts-operator`. The repo uses the same pattern for every helm service;
**and** the values. This directory documents the service, and it does not repeat
the values.

## The bootstrap secret (NOT in git)

The operator authenticates to the Tailscale control plane with an OAuth client.
It expects a Secret named `operator-oauth` in the `tailscale` namespace. The
ESO-to-Vaultwarden bridge does not work at present, so you create the Secret
**imperatively**, exactly as for `media/gluetun-wireguard`:

1. Tailscale admin console → Settings → OAuth clients → create a new client with
   the **Devices: write** scope and the tag `tag:k8s-operator`, which owns
   `tag:k8s`. Check that the tailnet ACL declares:

   ```jsonc
   "tagOwners": {
     "tag:k8s-operator": [],
     "tag:k8s": ["tag:k8s-operator"],
   }
   ```

2. Store the client id and the client secret in Vaultwarden as
   `tailscale-oauth-k8s-operator`.
3. Create the Secret. You can do this before or after the Application syncs. The
   operator pod stays in a crash loop until the Secret exists, and that causes no
   other problem:

   ```bash
   kubectl -n tailscale create secret generic operator-oauth \
     --from-literal=client_id="$(bw get username tailscale-oauth-k8s-operator)" \
     --from-literal=client_secret="$(bw get password tailscale-oauth-k8s-operator)"
   ```

## Dependencies

- `platform/services/gitops/` — the Argo Application drives the install.
- Admin access to the tailnet, for the OAuth client and the ACL tagOwners. This
  is a one-time action, and it happens outside this repo.

## Pod-security note

The operator's proxy pods need the tun device and `NET_ADMIN`, which restricted
PodSecurity rejects. **Nothing excludes or exempts this namespace today, because
nothing enforces pod security at admission**: the sentence that stood here named
`platform/core/policy/policies/pod-security-baseline.yaml`, a Kyverno file that
was deleted with Kyverno on 2026-08-09 and whose own paragraph had already lost
its opening clause. The in-tree mechanism is a `pod-security.kubernetes.io/*`
label on the `tailscale` namespace; only `metallb-system` carries such labels on
the live cluster. See `.claude/rules/50-cluster-architecture.md` §4 and §7.

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

This is a new install for `homelab`. Nothing related to Tailscale existed in the
cluster before it. The cluster opts in through
`clusters/instances/homelab/identity.yaml → platform_services.networking`.
