# clusters — conventions

A cluster instance is `clusters/instances/<name>/` and contains:

```
clusters/instances/<name>/
├── cluster.yaml           # required — descriptor
├── project.json           # Nx wiring (two-file pattern)
├── ctl.sh                 # cluster-specific control
├── terraform/             # terraform roots using providers/*
└── kustomize/             # (optional) overlays for platform services
```

`cluster.yaml` must contain at least:

```yaml
name: <cluster-name>
provider: aws | oracle | azure | kubernetes-manual
region: <string>
kubernetes_version: "1.30"
node_pools: []
status: planned | active | retired
owner: mateo.segura413@gmail.com
```

## Instance ctl.sh

Every cluster instance has the full verb set from the verb catalog for
infrastructure/clusters (`status`, `describe`, `plan`, `apply`, `destroy`,
`shell`, `logs`, etc.). Add verbs as the cluster grows; do not pre-declare
unimplemented ones.

## Templates

Templates under `clusters/templates/<name>/` are currently stubs. A real
template should contain the tree structure above (minus `instances/`),
including example terraform that references modules in
`../../../providers/<provider>/`.
