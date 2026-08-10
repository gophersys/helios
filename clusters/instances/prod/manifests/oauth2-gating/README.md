# oauth2-proxy gating on the prod cluster

Imperative state, recorded here so it is reproducible. The prod cluster is **not**
GitOps-reconciled — `platform/services/gitops/` drives the homelab only — so these
were applied with `kubectl` and this file is the source of truth for reapplying them.

Applied 2026-08-09 to close the `notes` and `obsv` findings from
`contracts/exposure.yaml`: both were internet-reachable behind nothing but
CouchDB basic auth and Grafana's own login.

## 1. Widen the oauth2-proxy cookie to the whole zone

Without this the cookie is scoped to `secrets.mateosegura.com` alone, and any
other host gated by the same proxy redirect-loops forever — it authenticates,
comes back, sees no cookie for its own hostname, and starts again.

```sh
kubectl -n shared-services patch deploy oauth2-proxy --type json -p '[
 {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--cookie-domain=.mateosegura.com"},
 {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--whitelist-domain=.mateosegura.com"}
]'
```

`--whitelist-domain` is what allows oauth2-proxy to redirect back to a host other
than its own after login. Without it the `rd=` parameter is rejected.

The Google OAuth callback stays `https://secrets.mateosegura.com/oauth2/callback`,
so no change is needed on the Google side.

## 2. Gate each additional host

```sh
for pair in "couchdb notes" "grafana obsv"; do
  ing=${pair%% *}; host=${pair##* }
  kubectl -n shared-services patch ing "$ing" --type merge -p "{\\"metadata\\":{\\"annotations\\":{
    \\"nginx.ingress.kubernetes.io/auth-url\\":\\"http://oauth2-proxy.shared-services.svc.cluster.local:4180/oauth2/auth\\",
    \\"nginx.ingress.kubernetes.io/auth-signin\\":\\"https://secrets.mateosegura.com/oauth2/start?rd=https://\${host}.mateosegura.com\\$escaped_request_uri\\"}}}"
done
```

## What must NOT be gated

`secrets.mateosegura.com` serves two ingresses on purpose:

- `secrets-manager-web` (`/`) — behind oauth2-proxy.
- `secrets-manager-noauth` (`/oauth2`, `/api`, `/identity`, `/notifications`,
  `/icons`) — **deliberately not gated.**

The second is what lets the `bw` CLI reach the vault with only the master
password, so recovery works when Google, Cloudflare, Tailscale and the homelab
are all unavailable. Gating those paths would break the recovery story described
in `docs/cloud-cluster.md`. Do not "harden" them.

## Verify

```sh
bash ctl.sh verify-exposure     # notes / obsv / secrets must all report gate=oauth2-proxy
```

Rollback for the deployment patch is a plain `kubectl -n shared-services edit
deploy oauth2-proxy` removing the two args; the ingress annotations can be
dropped the same way.
