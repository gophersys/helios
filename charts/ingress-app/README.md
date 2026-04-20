# charts/ingress-app

A `stateless-app` that's always publicly exposed via Ingress + automatic
TLS. Opinionated wrapper — picks sane ingress defaults so every
public-facing app looks the same to operators and attackers.

## When to pick this

- Public HTTP(S) endpoints: APIs, dashboards, marketing sites with an app
  server, static-site-with-rewrites frontends.
- Any app that needs a stable `*.cluster-domain` hostname with automatic
  cert renewal, standard rate limiting, standard security headers.

If the app is purely internal (tailnet-only), prefer `stateless-app` with
`ingress.enabled: false` — no Ingress resource at all.

## What the chart emits

Everything `stateless-app` emits, **plus** mandatory ingress wiring:

- `Ingress` — `ingressClassName: platform`, cert-manager annotation for
  `letsencrypt-prod`, redirect HTTP → HTTPS, standard security headers,
  rate-limit middleware.
- `Certificate` — cert-manager CR for the declared host(s).
- `Middleware` (Traefik CRD) — security headers + rate limit +
  optional SSO gate (when `contracts/identity.md` is active).

## Security headers (Traefik middleware)

Applied to every `ingress-app` by default:

```yaml
headers:
  stsSeconds: 63072000                       # 2 years HSTS
  stsIncludeSubdomains: true
  stsPreload: true
  contentTypeNosniff: true                   # X-Content-Type-Options: nosniff
  browserXssFilter: true                     # X-XSS-Protection: 1; mode=block
  frameDeny: true                            # X-Frame-Options: DENY
  referrerPolicy: "strict-origin-when-cross-origin"
  permissionsPolicy: "geolocation=(), microphone=(), camera=()"
  customResponseHeaders:
    Server: ""                               # strip server signature
```

Apps override via `values.ingress.headers.*`.

## Rate limiting

Every ingress-app gets a baseline rate limit (Traefik middleware):

```yaml
rateLimit:
  average: 100                  # requests/second average
  burst: 200                    # burst capacity
  period: 1s
```

These are conservative defaults. Apps that need higher throughput
override per-ingress via `values.ingress.rateLimit.*`. Apps that
expect low/spiky traffic can lower to `average: 10` to shed abuse.

## SSO gate (future-friendly)

```yaml
ingress:
  sso:
    enabled: false                             # requires platform/services/identity-sso
    requiredGroups: ["admins"]
```

When `platform/services/identity-sso/` is installed and
`ingress.sso.enabled: true`, the chart adds the SSO-middleware annotation
and the ingress becomes gated. See `contracts/identity.md`.

## Redirect + canonical host

```yaml
ingress:
  host: codectl.brain.mateosegura.com
  canonicalHost: true            # redirects www., trailing slashes, etc.
  paths:
    - path: /
      pathType: Prefix
      port: http
```

## Opinionated defaults

| Knob                               | Default                                                        |
|------------------------------------|----------------------------------------------------------------|
| `ingress.enabled`                  | `true` (this archetype is for ingress — duh)                   |
| `ingress.ingressClassName`         | `platform`                                                     |
| `ingress.tls.clusterIssuer`        | `letsencrypt-prod`                                             |
| `ingress.tls.secretSuffix`         | `-tls` (full secret name: `<release>-tls`)                     |
| `ingress.redirectToHttps`          | `true`                                                         |
| `ingress.headers.stsSeconds`       | `63072000`                                                     |
| `ingress.rateLimit.average`        | `100`                                                          |
| `ingress.sso.enabled`              | `false` (opt-in when identity-sso lands)                       |

## Example values

```yaml
app:
  name: codectl-dashboard
  partOf: codectl
env: prod
nodeRole: apps

image:
  repository: ghcr.io/mateosegura/codectl-dashboard
  tag: v1.42.0

replicas: 2

ingress:
  host: dashboard.brain.mateosegura.com
  canonicalHost: true
  tls: { enabled: true, clusterIssuer: letsencrypt-prod }
  paths:
    - { path: /, pathType: Prefix, port: http }
  rateLimit: { average: 50, burst: 100 }
  headers:
    customResponseHeaders:
      X-App: codectl-dashboard
  sso:
    enabled: false            # public dashboard today

resources:
  requests: { cpu: 100m, memory: 128Mi }
  limits:   { cpu: 500m, memory: 128Mi }

observability:
  metrics: { enabled: true, port: 9090 }

slo:
  tier: high
  availability: { target: 99.9, window: 30d }
  latency:      { target_ms: 400, window: 7d }
```

## Status

Skeleton. Templates are stubs. The primary difference vs `stateless-app`
is that the ingress block is mandatory and defaults are stricter —
otherwise all helpers and conventions are shared via `_common`.
