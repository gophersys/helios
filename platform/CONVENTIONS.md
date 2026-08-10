# platform — conventions

## The 2 tiers

- **`platform/core/<component>/`** — non-negotiable. Every cluster installs every
  core component during bring-up. The versions are pinned across the repo.
- **`platform/services/<category>/<impl>/`** — opt-in. The `identity.yaml` of a
  cluster declares which services that cluster wants, and at which versions.

Both tiers follow the same project layout.

## The layout of a component, when it is populated

```
platform/<tier>/<path>/
├── project.json              # Nx wiring — verbs: apply, destroy, status, values, logs, rollback
├── ctl.sh                    # thin wrapper around helm/kustomize
├── helm/                     # (if Helm-based)
│   ├── values.yaml           # baseline values — applied to every cluster
│   └── Chart.lock            # pinned chart version
├── manifests/                # (if raw kustomize/yaml)
│   └── base/
├── contracts/                # (optional) which contracts this component fulfills
│   └── <contract>.md         # a brief mapping explaining how the contract maps to this impl
└── README.md                 # purpose, default impl, deps, contract linkage, status
```

The value overrides for one cluster live at
`clusters/instances/<c>/overlays/<tier>/<path>/values.yaml`.

## Generic verb catalog

| Verb        | Scope                                                              |
|-------------|--------------------------------------------------------------------|
| `status`    | print what's installed in each consuming cluster                   |
| `describe`  | full describe of the component (chart ver, values, CRDs)           |
| `apply`     | install or upgrade, honoring cluster overlay                       |
| `destroy`   | uninstall from a cluster (gated — never from prod without approval)|
| `values`    | print the merged values a specific cluster would receive           |
| `logs`      | tail logs for the component's pods                                 |
| `rollback`  | helm rollback to prior revision                                    |

## Install order on a new cluster

The install order of the core components is fixed. It runs from the top to the
bottom of `core/`, as the README lists them. You can install the services in any
order, after the core components are healthy.

1. `core/cni` — pod networking (required for anything else to run)
2. `core/ingress` — ingress controller
3. `core/cert-manager` — TLS issuance
4. `core/storage` — persistent volume provisioner
5. `core/secrets-operator` — ESO + Bitwarden (needed for app secrets)
6. `core/metrics-server` — baseline metrics
7. `core/network-policies` — default-deny templates
8. any `services/*` the cluster's identity.yaml opts into

## Status today

Every leaf holds a stub `README.md` and nothing else. An implementation lands
when the first cluster that brings up that component is ready. This follows the
progressive disclosure rule in `infrastructure/README.md`.
