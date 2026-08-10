# Expose a service — never touch the Cloudflare dashboard

When `rayne.mateosegura.com` was published, the hostname was added by hand in the
Cloudflare Zero Trust dashboard. That must never be necessary again. This is the
whole workflow.

## Why it was manual

The `eden-home` tunnel is **managed by the dashboard** (it is a token tunnel), so
its ingress rules live in Cloudflare's control plane, not in git. A click on *Add
public hostname* did 2 things: it appended an ingress rule, and — the part that
mattered — it created the proxied `CNAME`.

The tunnel already has a **catch-all** rule:

```
home.mateosegura.com        -> ingress-nginx:80
workspaces.mateosegura.com  -> ingress-nginx:80
rayne.mateosegura.com       -> ingress-nginx:80
(catch-all)                 -> ingress-nginx:80        <-- serves ANY hostname
```

Because of that catch-all rule, a new host behind the tunnel needs **no change to
the tunnel**. It needs 1 DNS record. That is a single API call, and
`cf-expose.py` makes it.

## The workflow

### 1. Declare it

Add the hostname to `contracts/exposure.yaml` with a class and a reason:

```yaml
  myapp:
    class: tailnet          # tailnet | public-access | public-open | direct-auth
    cluster: homelab
    why: "admin surface, no reason to be public"
```

The class decides everything after this step. See the decision tree in
`contracts/ingress.md`. Use `tailnet` by default. Make something public only when
a person outside the tailnet genuinely needs it.

### 2. Ship the Ingress

Use normal GitOps: add the manifest under `apps/`, and Argo reconciles it.

- **tailnet** → `cert-manager.io/cluster-issuer: letsencrypt-homelab` plus a
  `tls:` block. The redirect behaviour is normal.
- **public-access / public-open** → the same annotations, **plus**
  `nginx.ingress.kubernetes.io/ssl-redirect: "false"`. The tunnel connects to
  nginx on **:80**, and an HTTP-to-HTTPS redirect there loops against cloudflared
  for ever.

### 3. Reconcile DNS

```sh
python3 scripts/cf-expose.py check     # read-only: what would change
python3 scripts/cf-expose.py apply     # make Cloudflare match the declaration
```

It maps the class to the record automatically:

| Class | Record |
| --- | --- |
| `tailnet` | `A → 10.168.0.240`, not proxied |
| `public-access`, `public-open` | `CNAME → <tunnel>.cfargotunnel.com`, proxied |
| `direct-auth` | `A → 144.24.23.2`, not proxied |

### 4. Verify

```sh
bash scripts/verify-exposure.sh        # or: bash ctl.sh verify-exposure
```

It resolves every declared host, follows the redirects, and asserts that the gate
matches. It runs in CI, so drift fails the build instead of waiting for somebody
to notice it.

## The wildcard record

`*.mateosegura.com → 144.24.23.2` is a deliberate catch-all to the prod cluster.
An explicit record always wins over it, so it never overrides a declaration.

An undeclared name therefore still resolves, but nothing answers: the prod
ingress serves only the hostnames it has rules for, and there is no certificate
for any other name. That gives convenience without exposure.

## What is still manual — one thing

**Cloudflare Access applications.** The API token can read DNS and the tunnel,
but a list of the Access apps returns empty at account scope and fails at zone
scope, so the token lacks *Access: Apps and Policies*. To add `public-access` to
a **new** hostname you must therefore still open the dashboard once to create the
Access app.

To close this permanently, edit the token at **dash.cloudflare.com → My Profile →
API Tokens → the token used here** and add:

```
Account · Access: Apps and Policies · Edit
```

`cf-expose.py` can then create the Access app too, and no part of the
publication of a service needs a browser. The token expires **2027-06-17**.

The existing `public-access` hosts (`home`, `workspaces`) already have their
Access apps, so this affects new hosts only.

## Related

- `contracts/exposure.yaml` — the declaration, and the approved exception
- `contracts/ingress.md` — the class definitions and the decision tree
- `docs/cloud-cluster.md` — why `secrets.` deliberately bypasses Cloudflare
