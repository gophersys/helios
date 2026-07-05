# external-secrets — the Vaultwarden bridge

How every secret in the cluster flows from the **cloud Vaultwarden**
(`secrets.mateosegura.com`) into Kubernetes declaratively, so only non-secret
`ExternalSecret` CRs live in git and Vaultwarden stays the single source of truth.

```
Vaultwarden (OCI)  ──►  bw-serve bridge (this ns)  ──►  ESO ClusterSecretStore
                          (Bitwarden CLI, unlocked)      (webhook provider)
                                                              │
   ExternalSecret CR (in git)  ──────────────────────────────┘
                                                              ▼
                          k8s Secret (ESO-owned, NEVER in git) ──► consumed by pods
```

Vaultwarden does **not** implement the Bitwarden Secrets Manager API, so ESO's
native provider is unusable. Instead a small in-cluster `bw serve` bridge exposes
the Bitwarden CLI's REST API, and ESO's **webhook** provider queries it. The whole
chain is anchored by exactly ONE out-of-band secret.

## The one seed secret (you create this — master password never leaves your shell)

The bridge authenticates to Vaultwarden with your **personal API key**
(client_id/secret, from Vaultwarden → Account Settings → Security → Keys → API Key)
and your **master password** (to unlock). Create it by hand — it is the only
secret not managed by ESO:

```bash
kubectl create ns external-secrets 2>/dev/null
kubectl -n external-secrets create secret generic bw-cli-credentials \
  --from-literal=BW_HOST="https://secrets.mateosegura.com" \
  --from-literal=BW_CLIENTID="user.xxxxxxxx" \
  --from-literal=BW_CLIENTSECRET="xxxxxxxx" \
  --from-literal=BW_PASSWORD="<your master password>"
```

> Security: this secret holds the vault master password. It is protected by the
> enforced default-deny NetworkPolicy (only the ESO pod can reach the bridge —
> verified: k3s kube-router enforces NetworkPolicy) and lives only in etcd, never
> in git. Consider a dedicated least-privilege Vaultwarden user/org key later.

## Activation (after the seed secret exists)

1. Add an Argo Application `external-secrets-bridge` (project platform, path
   `kubernetes/apps/external-secrets`) — deploys bw-serve + NetworkPolicy + the
   ClusterSecretStore.
2. Verify the bridge unlocks (`kubectl -n external-secrets logs deploy/bw-serve`)
   and the ClusterSecretStore reports `Ready`.
3. Migrate a real secret: write an `ExternalSecret` (e.g. re-provision
   `gluetun-wireguard` from vault item `shared/protonvpn/wireguard`), confirm the
   derived k8s Secret matches byte-for-byte, then cut the app over.

## Files
- `bw-serve.yaml` — the Bitwarden-CLI bridge Deployment + Service (unlocked `bw serve`)
- `networkpolicy.yaml` — default-deny + allow only ESO → bridge:8087
- `clustersecretstore.yaml` — ESO webhook store pointing at the bridge

## Status / findings (2026-07-05)

Seed secret **exists** and is valid (token endpoint `/identity/connect/token`
returns 200 with the API key). ESO operator is deployed. The **bw-serve bridge is
NOT yet working** — findings:

- **bw CLI version sensitivity:** `charlesthomas/bitwarden-cli:2026.6.0` authenticates
  but crashes on `toWrappedAccountCryptographicState` (null) — the 2026.x CLI expects
  an account-crypto format Vaultwarden doesn't serve. Need an **older, Vaultwarden-
  compatible** CLI. **Match the CLI to the running Vaultwarden version** before picking.
- **Rate limit:** Vaultwarden ingress rate-limits (~10 req/s). A crashlooping bridge
  hammers `/identity/connect/token` and trips it, poisoning further tests. **Test with a
  SINGLE one-shot pod, with cooldowns — never a crashlooping Deployment.**

**Next activation attempt:** (1) check Vaultwarden's version, (2) pick a matching bw CLI
tag, (3) test one-shot (`kubectl run --restart=Never`) after a rate-limit cooldown,
(4) once it serves, add the `external-secrets-bridge` Argo app + verify the
ClusterSecretStore is `Ready` + migrate one real secret.

**Not a blocker:** the imperative `bw get … | kubectl create secret` flow works today;
the bridge is an automation upgrade, not a dependency.
