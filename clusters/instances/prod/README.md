# prod

Production Kubernetes cluster. Identity at `./identity.yaml`.

## Members (populated later)

Node definitions live at `nodes/<name>/identity.yaml`. This cluster is
expected to enroll:

| Node          | Cloud        | Shape                  | K3s role |
|---------------|--------------|------------------------|----------|
| `server-00`   | OCI Phoenix  | A1.Flex ARM 2/12       | server   |
| `agent-00`    | OCI Phoenix  | A1.Flex ARM 2/12       | agent    |
| `agent-01`    | OCI Phoenix  | E4.Flex x86 1/16       | agent    |
| `agent-02`    | AWS Oregon   | t4g.small ARM 2/2      | agent    |

Bastions (`sentinel-00`, `sentinel-01`) are NOT cluster members — they
live at `machines/services/sentinel-*/`.

## Per-cluster overlays

Platform component value overrides live at `overlays/<tier>/<path>/values.yaml`
(e.g., `overlays/core/ingress/values.yaml`,
`overlays/services/observability/values.yaml`). The platform's apply step
merges these over the baseline values in `platform/<tier>/<path>/helm/values.yaml`.

## Lifecycle

- Bring-up: `clusters/ctl.sh new-cluster-node prod linux-k3s-node <name>`
  for each node + apply `platform/core/*` in order.
- Upgrades: pin a new K3s `distribution_version` in `identity.yaml`, then
  Ansible `k3s-upgrade` playbook drains each node.
- Teardown: **not a routine operation**. A1.Flex nodes are irreplaceable
  — see `infrastructure/.claude/rules/` for the non-negotiable guards.
