# edge/tunnel/cloudflare-tunnel

The entry point for public traffic into a cluster that has no public IP. The
Cloudflare edge accepts the traffic. A `cloudflared` pod keeps persistent
outbound connections to Cloudflare, and the tunnel carries the public requests to
the in-cluster ingress controller. There is no inbound hole in the firewall, the
Cloudflare edge absorbs DDoS traffic and runs the WAF, and the tunnel works
behind NAT.

---

## What is deployed today on the homelab — the source of truth

The live homelab edge is **not** the design based on an operator that the
"Target design" section below describes. This is what runs:

- **`deployment.yaml`** — a plain `cloudflared` Deployment with 2 replicas, in
  the namespace `cloudflare-tunnel`, image
  `cloudflare/cloudflared:2026.6.1`, hardened (non-root user 65532, a read-only
  root filesystem, all capabilities dropped). It is vendored here, so that the
  edge is reproducible from git. It is registered as the `cloudflared` Argo
  Application (`registry/app-cloudflared.yaml`) with **manual sync**. Argo makes
  the edge visible and owned by git, and Argo never changes the edge on its own.
  Adopt it with `argocd app sync cloudflared`. That command changes nothing,
  because the spec matches the live state.
- **Tunnel type:** a Zero Trust **token** tunnel named `eden-home`. The token is
  the imperative `tunnel-token` Secret. See `docs/runtime-secrets.md`.
- **The routing and the SSO live in the Cloudflare dashboard, not in git.** A
  single catch-all rule forwards to `ingress-nginx:80`. The route for each
  hostname and the Cloudflare Access apps for Google SSO are configured in the
  Cloudflare Zero Trust dashboard. That is outside this repo by design, because
  this is a token tunnel. Only `home.` is public through the tunnel:
  `workspaces.` was removed on 2026-08-19, and its dashboard rule, CNAME and
  Access app outlived it because nothing in git reaches them
  (`docs/runbooks/expose-a-service.md`). Everything else (`argocd.`, `files.`,
  `prowlarr.`, `torrent.`) is tailnet-private through the MetalLB nginx VIP. The
  authoritative map is **`docs/cluster-topology.md` → "The exposure model."**

There is **no** `cloudflare-operator` and no `cloudflare-api-token`, and TLS is
**not** terminated here, because the tunnel enters nginx on `:80`.

---

## Target design (for prod, not deployed yet)

For a future managed or prod cluster, the intended shape is an operator that
turns an `Ingress` object into a Cloudflare tunnel route automatically
(`strrl.dev/cloudflare-tunnel-ingress-controller`). The tunnel token and a
scoped `cloudflare-api-token` then come from Bitwarden through ESO.

Compatibility: a Cloudflare Tunnel requires Cloudflare DNS, so it does not pair
with route53 or ACM. It pairs naturally with `cloudflare-origin` for TLS, or with
`letsencrypt-dns01` issued by the cluster.

The limits of the free plan, as of 2026-04: 100 hostnames per tunnel, unlimited
bandwidth, and 10 to 30ms of extra latency at the edge.

This operator wiring lands when a `prod` cluster bootstraps its public edge.
