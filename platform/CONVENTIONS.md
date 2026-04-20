# platform — conventions

## Two tiers

- **`platform/core/<component>/`** — non-negotiable. Every cluster installs
  every core component during bring-up. Versions are pinned repo-wide.
- **`platform/services/<category>/<impl>/`** — opt-in. A cluster's
  `identity.yaml` declares which services it wants, at which versions.

Both follow the same project layout.

## Per-component layout (when populated)

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

Per-cluster value overrides live at
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

## Install order (on a fresh cluster)

Core install order is fixed (top to bottom of `core/` as listed in README).
Services install in any order after core is healthy.

1. `core/cni` — pod networking (required for anything else to run)
2. `core/ingress` — ingress controller
3. `core/cert-manager` — TLS issuance
4. `core/storage` — persistent volume provisioner
5. `core/secrets-operator` — ESO + Bitwarden (needed for app secrets)
6. `core/metrics-server` — baseline metrics
7. `core/network-policies` — default-deny templates
8. any `services/*` the cluster's identity.yaml opts into

## Status today

Every leaf has a stub `README.md` only. Implementations land when the first
cluster bringing up that component is ready — progressive disclosure per
`infrastructure/README.md`.
