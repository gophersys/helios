# prod

Production Kubernetes cluster. Identity at `./identity.yaml`.

## Members — populated at a later date

A node definition lives at `nodes/<name>/identity.yaml`. This cluster is expected
to enroll these nodes:

| Node          | Cloud        | Shape                  | K3s role |
|---------------|--------------|------------------------|----------|
| `server-00`   | OCI Phoenix  | A1.Flex ARM 2/12       | server   |
| `agent-00`    | OCI Phoenix  | A1.Flex ARM 2/12       | agent    |
| `agent-01`    | OCI Phoenix  | E4.Flex x86 1/16       | agent    |
| `agent-02`    | AWS Oregon   | t4g.small ARM 2/2      | agent    |

The `sentinel-00` and `sentinel-01` bastions were **terminated on 2026-08-09**.
They ran nothing but `tailscaled`, and they became unnecessary once Tailscale SSH
reached every node directly. Their 94 GB of boot volumes were also what stopped
the provisioning of a data volume inside the Always Free allowance. See
docs/cloud-cluster.md.

## Overlays for this cluster

The value overrides for a platform component live at
`overlays/<tier>/<path>/values.yaml`, for example
`overlays/core/ingress/values.yaml` and
`overlays/services/observability/values.yaml`. The apply step of the platform
merges them over the baseline values in
`platform/<tier>/<path>/helm/values.yaml`.

## Lifecycle

- Bring-up: run `clusters/ctl.sh new-cluster-node prod linux-k3s-node <name>`
  for each node, then apply `platform/core/*` in order.
- Upgrade: pin a new K3s `distribution_version` in `identity.yaml`. The Ansible
  `k3s-upgrade` playbook then drains each node.
- Teardown: **this is not a routine operation.** The A1.Flex nodes are
  irreplaceable. See `infrastructure/.claude/rules/` for the non-negotiable
  protections.
