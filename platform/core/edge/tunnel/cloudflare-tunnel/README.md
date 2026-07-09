# edge/tunnel/cloudflare-tunnel

Public-traffic entry for clusters with no public IP: Cloudflare's edge accepts
traffic and a `cloudflared` pod keeps outbound persistent connections to CF,
tunnelling public requests through to the in-cluster ingress controller. No
inbound firewall holes; DDoS/WAF soak at CF's edge; works behind NAT.

---

## Deployed today (homelab) — the source of truth

The live homelab edge is **not** the operator-based design described under
"Target design" below. What actually runs:

- **`deployment.yaml`** — a plain `cloudflared` Deployment (2 replicas) in ns
  `cloudflare-tunnel`, image `cloudflare/cloudflared:2026.6.1`, hardened
  (non-root 65532, read-only rootfs, all caps dropped). Vendored here so the
  edge is reproducible from git. Registered as the `cloudflared` Argo
  Application (`registry/app-cloudflared.yaml`) with **manual sync** — Argo
  makes it visible/git-owned but never mutates the edge on its own. Adopt with
  `argocd app sync cloudflared` (a no-op rollout; the spec matches live).
- **Tunnel type:** a Zero-Trust **token** tunnel (`eden-home`). The token is the
  imperative `tunnel-token` Secret (see `docs/runtime-secrets.md`).
- **Routing + SSO live in the CF dashboard, not git.** A single catch-all rule
  forwards to `ingress-nginx:80`; per-hostname routes and Cloudflare Access
  (Google SSO) apps are configured in the CF Zero-Trust dashboard — out-of-band
  by design for a token tunnel. Only `home.` and `workspaces.` are public
  through the tunnel; everything else (`argocd.`, `files.`, `prowlarr.`,
  `torrent.`, `grafana.`) is tailnet-private via the MetalLB nginx VIP. The
  authoritative map is **`docs/cluster-topology.md` → "Exposure model at a
  glance."**

There is **no** `cloudflare-operator`, no `cloudflare-api-token`, and TLS is
**not** terminated here (the tunnel enters nginx on `:80`).

---

## Target design (prod, not yet deployed)

For a future managed/prod cluster, the intended shape is an operator that turns
`Ingress` objects into CF tunnel routes automatically
(`strrl.dev/cloudflare-tunnel-ingress-controller`), with the tunnel token +
a scoped `cloudflare-api-token` sourced from Bitwarden via ESO. Compatibility:
CF Tunnel requires CF DNS (route53/ACM won't pair); TLS pairs naturally with
`cloudflare-origin` or cluster-issued `letsencrypt-dns01`. Free plan limits (as
of 2026-04): 100 hostnames/tunnel, unlimited bandwidth, +10–30ms edge latency.
This operator wiring lands when a `prod` cluster bootstraps its public edge.
