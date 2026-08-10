# charts/ingress-app

A `stateless-app` that is always public, through an Ingress with automatic TLS.
This archetype is an opinionated wrapper. It picks sensible ingress defaults, so
that every public app presents the same surface to an operator and to an
attacker.

## When to pick this

- A public HTTP or HTTPS endpoint: an API, a dashboard, a marketing site with an
  app server, or a frontend for a static site with rewrites.
- Any app that needs a stable `*.cluster-domain` hostname with automatic
  certificate renewal, the standard rate limit, and the standard security
  headers.

If the app is internal only, on the tailnet, prefer `stateless-app` with
`ingress.enabled: false`. It then renders no Ingress resource at all.

## What the chart emits

Everything that `stateless-app` emits, **plus** the mandatory ingress wiring:

- `Ingress` — `ingressClassName: platform`, the cert-manager annotation for
  `letsencrypt-prod`, a redirect from HTTP to HTTPS, the standard security
  headers, and the rate-limit middleware.
- `Certificate` — the cert-manager CR for each declared host.
- `Middleware` (a Traefik CRD) — the security headers, the rate limit, and an
  optional SSO gate when `contracts/identity.md` is active.

## Security headers (the Traefik middleware)

The chart applies these to every `ingress-app` by default:

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

An app overrides them through `values.ingress.headers.*`.

## Rate limiting

Every ingress-app gets a baseline rate limit, through a Traefik middleware:

```yaml
rateLimit:
  average: 100                  # requests/second average
  burst: 200                    # burst capacity
  period: 1s
```

These defaults are low. An app that needs more throughput overrides them for its
own ingress, through `values.ingress.rateLimit.*`. An app that expects little
traffic, or traffic in short peaks, can lower the value to `average: 10` to
reject an abusive load.

## The SSO gate (prepared for the future)

```yaml
ingress:
  sso:
    enabled: false                             # requires platform/services/identity-sso
    requiredGroups: ["admins"]
```

When `platform/services/identity-sso/` is installed and
`ingress.sso.enabled` is `true`, the chart adds the annotation for the SSO
middleware, and the ingress is then gated. See `contracts/identity.md`.

## Redirect and canonical host

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
| `ingress.enabled`                  | `true` — this archetype exists for the ingress                 |
| `ingress.ingressClassName`         | `platform`                                                     |
| `ingress.tls.clusterIssuer`        | `letsencrypt-prod`                                             |
| `ingress.tls.secretSuffix`         | `-tls` (full secret name: `<release>-tls`)                     |
| `ingress.redirectToHttps`          | `true`                                                         |
| `ingress.headers.stsSeconds`       | `63072000`                                                     |
| `ingress.rateLimit.average`        | `100`                                                          |
| `ingress.sso.enabled`              | `false` (opt-in when identity-sso lands)                       |

## Example values

Install as release `codectl-dashboard` in namespace `codectl-prod`:

```yaml
project: codectl                    # namespace: codectl-prod
env: prod
app:
  name: dashboard                   # full identifier: codectl-dashboard
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

Skeleton. The templates are stubs. There are 2 differences against
`stateless-app`: the ingress block is mandatory, and the defaults are stricter.
`_common` supplies all the same helpers and conventions.
