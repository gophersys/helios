# oauth2-proxy gating on the prod cluster

This is imperative state, recorded here so that it is reproducible. Argo does
**not** reconcile the prod cluster, because `platform/services/gitops/` drives
the homelab only. These changes were therefore applied with `kubectl`, and this
file is the source of truth for an application of them again.

They were applied on 2026-08-09, to close the `notes` and `obsv` findings from
`contracts/exposure.yaml`. Both hosts were reachable from the internet behind
nothing but CouchDB basic auth and Grafana's own login.

## 1. Widen the oauth2-proxy cookie to the whole zone

Without this change the cookie is scoped to `secrets.mateosegura.com` alone, and
any other host behind the same proxy loops on the redirect with no end. That host
authenticates, comes back, finds no cookie for its own hostname, and starts
again.

```sh
kubectl -n shared-services patch deploy oauth2-proxy --type json -p '[
 {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--cookie-domain=.mateosegura.com"},
 {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--whitelist-domain=.mateosegura.com"}
]'
```

`--whitelist-domain` lets oauth2-proxy redirect back to a host other than its own
after the login. Without it, oauth2-proxy rejects the `rd=` parameter.

The Google OAuth callback stays
`https://secrets.mateosegura.com/oauth2/callback`, so the Google side needs no
change.

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

`secrets.mateosegura.com` serves 2 ingresses on purpose:

- `secrets-manager-web` (`/`) — behind oauth2-proxy.
- `secrets-manager-noauth` (`/oauth2`, `/api`, `/identity`, `/notifications`,
  `/icons`) — **deliberately not gated.**

The second ingress lets the `bw` CLI reach the vault with the master password
only. Recovery therefore works when Google, Cloudflare, Tailscale and the homelab
are all unavailable. A gate on those paths would break the recovery procedure
that `docs/cloud-cluster.md` describes. Do not add one.

## Verify

```sh
bash ctl.sh verify-exposure     # notes / obsv / secrets must all report gate=oauth2-proxy
```

To reverse the deployment patch, run
`kubectl -n shared-services edit deploy oauth2-proxy` and remove the 2 arguments.
Remove the ingress annotations the same way.
