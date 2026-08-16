# external-secrets — the Vaultwarden bridge

How every secret in the cluster flows from the **cloud Vaultwarden**
(`secrets.mateosegura.com`) into Kubernetes declaratively. Only non-secret
`ExternalSecret` CRs live in git, and Vaultwarden stays the single source of
truth.

```
Vaultwarden (OCI)  ──►  bw-serve bridge (this ns)  ──►  ESO ClusterSecretStore
                          (Bitwarden CLI, unlocked)      (webhook provider)
                                                              │
   ExternalSecret CR (in git)  ──────────────────────────────┘
                                                              ▼
                          k8s Secret (ESO-owned, NEVER in git) ──► consumed by pods
```

Vaultwarden does **not** implement the Bitwarden Secrets Manager API, so the
native ESO provider does not work. Instead a small in-cluster `bw serve` bridge
exposes the REST API of the Bitwarden CLI, and the **webhook** provider of ESO
queries that bridge. Exactly 1 secret outside this chain anchors the whole chain.

## The one seed secret — you create it; the master password never leaves your shell

The bridge authenticates to Vaultwarden with your **personal API key** (the
client_id and the client secret, from Vaultwarden → Account Settings → Security →
Keys → API Key) and with your **master password**, which unlocks the vault.
Create the secret by hand. It is the only secret that ESO does not manage:

```bash
kubectl create ns external-secrets 2>/dev/null
kubectl -n external-secrets create secret generic bw-cli-credentials \
  --from-literal=BW_HOST="https://secrets.mateosegura.com" \
  --from-literal=BW_CLIENTID="user.xxxxxxxx" \
  --from-literal=BW_CLIENTSECRET="xxxxxxxx" \
  --from-literal=BW_PASSWORD="<your master password>"
```

> Security: this secret holds the master password of the vault. The enforced
> default-deny NetworkPolicy protects it, so only the ESO pod can reach the
> bridge. We verified that kube-router in k3s enforces the NetworkPolicy. The
> secret lives only in etcd, never in git. Consider a dedicated Vaultwarden user
> or organization key with the least privilege at a later date.

## Activation, after the seed secret exists

1. The Argo Application `secrets-bridge` (project platform, path
   `platform/core/secrets-operator/manifests`, registered at
   `platform/services/gitops/registry/app-secrets-bridge.yaml`) deploys bw-serve,
   the NetworkPolicy and the ClusterSecretStore.
2. Verify that the bridge unlocks
   (`kubectl -n external-secrets logs deploy/bw-serve`), and that the
   ClusterSecretStore reports `Ready`.
3. Migrate a real secret. Write an `ExternalSecret` — for example provision
   `gluetun-wireguard` again from the vault item `shared/protonvpn/wireguard`.
   Confirm that the derived k8s Secret matches byte for byte, then move the app
   onto it.

## Files
- `bw-serve.yaml` — the Deployment and Service of the Bitwarden CLI bridge (an
  unlocked `bw serve`)
- `networkpolicy.yaml` — default-deny, and it allows ESO to reach the bridge on
  port 8087
- `clustersecretstore.yaml` — the ESO webhook store that points at the bridge
- `bw-serve-sync.yaml` — a CronJob that sends POST /sync to the bridge every 10
  minutes, plus the NetworkPolicy allow for it. The bridge caches the vault at
  login and never syncs on its own; without this, a new or rotated item stays
  invisible to ESO until the pod restarts (build ledger #89)

## Status and findings (2026-07-05)

The seed secret **exists** and is valid: the token endpoint
`/identity/connect/token` returns 200 with the API key. The ESO operator is
deployed. The **bw-serve bridge does NOT work yet**. The findings:

- **The bw CLI version matters.**
  `charlesthomas/bitwarden-cli:2026.6.0` authenticates, then crashes on
  `toWrappedAccountCryptographicState` (null). The 2026.x CLI expects an
  account-crypto format that Vaultwarden does not serve. We need an **older CLI
  that Vaultwarden supports**. **Match the CLI to the running Vaultwarden
  version** before you choose one.
- **Rate limit.** The Vaultwarden ingress limits the rate to about 10 requests
  per second. A bridge in a crash loop sends many requests to
  `/identity/connect/token` and hits the limit, and that makes further tests
  fail. **Test with a SINGLE one-shot pod and a pause between attempts. Never use
  a Deployment in a crash loop.**

**The next attempt to activate the bridge:** (1) check the version of
Vaultwarden, (2) choose a matching bw CLI tag, (3) test with one shot
(`kubectl run --restart=Never`) after a pause for the rate limit, (4) once it
serves, add the `external-secrets-bridge` Argo app, verify that the
ClusterSecretStore is `Ready`, and migrate 1 real secret.

**This does not block other work:** the imperative flow
`bw get … | kubectl create secret` works today. The bridge is an improvement in
automation, not a dependency.
