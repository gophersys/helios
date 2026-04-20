# platform — conventions

Each platform service is a Nx project (two-file pattern) when implemented:

```
platform/<service>/
├── project.json
├── ctl.sh
├── values/                # per-cluster values overrides
│   └── <cluster-name>.yaml
└── README.md              # service-local — status + knobs
```

Verbs follow `infrastructure/platform-services/*` in the verb catalog:
`status`, `describe`, `apply`, `destroy`, `logs`, `values`, `rollback`.

Currently every `platform/<service>/` is just a README, not a full Nx
project — implement the two-file pattern when the first cluster is ready
to receive the service.

## Install order

Ingress + cert-manager always first (everything else depends on TLS).
secrets-external-operator next (applications need it before they start).
observability, databases, messaging after — in any order.
