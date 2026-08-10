# Expose a service — never touch the Cloudflare dashboard

When `rayne.mateosegura.com` was published, the hostname was added by hand in the
Cloudflare Zero Trust dashboard. That should never be necessary again. This is the
whole workflow.

## Why it was manual

The `eden-home` tunnel is **dashboard-managed** (a token tunnel), so its ingress
rules live in Cloudflare's control plane rather than in git. Clicking *Add public
hostname* did two things: appended an ingress rule, and — the part that actually
mattered — created the proxied `CNAME`.

The tunnel already has a **catch-all** rule:

```
home.mateosegura.com        -> ingress-nginx:80
workspaces.mateosegura.com  -> ingress-nginx:80
rayne.mateosegura.com       -> ingress-nginx:80
(catch-all)                 -> ingress-nginx:80        <-- serves ANY hostname
```

Because of that catch-all, a new tunnel-backed host needs **no tunnel change at
all**. It needs one DNS record. That is a single API call, and `cf-expose.py`
makes it.

## The workflow

### 1. Declare it

Add the hostname to `contracts/exposure.yaml` with a class and a reason:

```yaml
  myapp:
    class: tailnet          # tailnet | public-access | public-open | direct-auth
    cluster: homelab
    why: "admin surface, no reason to be public"
```

Class decides everything downstream — see the decision tree in
`contracts/ingress.md`. Default to `tailnet`; make something public only when
someone outside the tailnet genuinely needs it.

### 2. Ship the Ingress

Normal GitOps: add the manifest under `apps/`, Argo reconciles it.

- **tailnet** → `cert-manager.io/cluster-issuer: letsencrypt-homelab` plus a
  `tls:` block. Normal redirect behaviour.
- **public-access / public-open** → same annotations **plus**
  `nginx.ingress.kubernetes.io/ssl-redirect: "false"`. The tunnel connects to
  nginx on **:80**; an HTTP→HTTPS redirect there loops against cloudflared
  forever.

### 3. Reconcile DNS

```sh
python3 scripts/cf-expose.py check     # read-only: what would change
python3 scripts/cf-expose.py apply     # make Cloudflare match the declaration
```

It maps class → record automatically:

| Class | Record |
| --- | --- |
| `tailnet` | `A → 10.168.0.240`, not proxied |
| `public-access`, `public-open` | `CNAME → <tunnel>.cfargotunnel.com`, proxied |
| `direct-auth` | `A → 144.24.23.2`, not proxied |

### 4. Verify

```sh
bash scripts/verify-exposure.sh        # or: bash ctl.sh verify-exposure
```

Resolves every declared host, follows redirects, asserts the gate matches. Runs
in CI, so drift fails the build rather than waiting to be noticed.

## The wildcard

`*.mateosegura.com → 144.24.23.2` is a deliberate catch-all to the prod cluster.
Explicit records always win over it, so it never overrides anything declared.

It means an undeclared name still resolves — but nothing answers, because the
prod ingress only serves hostnames it has rules for and there is no certificate
for anything else. Convenience without exposure.

## What is still manual — one thing

**Cloudflare Access applications.** The API token can read DNS and the tunnel, but
listing Access apps returns empty at account scope and fails at zone scope, so it
lacks *Access: Apps and Policies*. Adding `public-access` to a **new** hostname
therefore still needs one dashboard visit to create the Access app.

To close this permanently, edit the token at
**dash.cloudflare.com → My Profile → API Tokens → the token used here** and add:

```
Account · Access: Apps and Policies · Edit
```

Then `cf-expose.py` can create the Access app too, and nothing about publishing a
service requires a browser. The token currently expires **2027-06-17**.

Existing `public-access` hosts (`home`, `workspaces`) already have their Access
apps, so this only affects new ones.

## Related

- `contracts/exposure.yaml` — the declaration, and the sanctioned exception
- `contracts/ingress.md` — class definitions and the decision tree
- `docs/cloud-cluster.md` — why `secrets.` deliberately bypasses Cloudflare
