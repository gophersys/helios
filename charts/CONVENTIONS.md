# charts — conventions

Every blessed chart follows the same structure (once implemented):

```
charts/<chart>/
├── Chart.yaml             # apiVersion: v2, appVersion: derived from consumer
├── values.yaml            # sensible defaults
├── values.schema.json     # enforced schema
├── templates/
│   ├── _helpers.tpl
│   ├── deployment.yaml    # or statefulset.yaml, job.yaml, cronjob.yaml
│   ├── service.yaml       # if applicable
│   ├── ingress.yaml       # if applicable, guarded by .Values.ingress.enabled
│   ├── hpa.yaml           # guarded by .Values.autoscaling.enabled
│   ├── servicemonitor.yaml  # guarded by .Values.metrics.enabled
│   └── externalsecret.yaml  # guarded by .Values.externalSecrets.enabled
├── project.json           # targets: render, validate, docs-generate
└── ctl.sh
```

Chart verbs (per the verb catalog): `render`, `validate`, `docs-generate`.

## values.yaml contract

Every chart exposes at minimum:

```yaml
image:
  repository: <image>
  tag: <tag>
  pullPolicy: IfNotPresent

replicas: 1

resources: {}          # always overridden by consumers

env: []                # plain env vars
envFromSecret: []      # names of Kubernetes secrets to pull envFrom

externalSecrets:
  enabled: false
  items: []            # ExternalSecret specs

metrics:
  enabled: false
  port: 9090
  path: /metrics

ingress:               # only when the chart supports ingress
  enabled: false
  className: nginx
  hosts: []
  tls: true

autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

Anything beyond this set must be justified in the chart README.

## Validation

`helm lint` + `values.schema.json` run on every PR via the chart's
`validate` verb. `render` produces rendered YAML for review and is cached
against the chart's `values/` fixtures.

Status: charts are not yet implemented. The first chart (`stateless-app`)
arrives when the first app in a project monorepo declares an infrastructure
dependency.
