# cluster-cloud-aws-eks

Template for AWS-managed Kubernetes (EKS). AWS runs the control plane;
we declare node groups or Fargate profiles via Terraform under
`providers/aws/`.

## When to use

- AWS-resident workloads.
- Need AWS-native integrations (ALB, EBS, EFS, IAM for service accounts).
- Managed control plane is worth the ~$73/mo per cluster.

## Not a fit

- If cost is the primary constraint, use `cluster-kubernetes-manual-k3s`
  on an AWS EC2 (or OCI Always-Free) instead.
- If you want tight Tailscale mesh integration, manual K3s is friendlier.

## What gets created

```
clusters/instances/<name>/
├── identity.yaml             # from cluster-identity.yaml template
└── overlays/
```

No `nodes/` subdir — node lifecycle is owned by EKS's node groups, managed
via `providers/aws/` Terraform modules at apply time.

## Status

Stub. No real EKS cluster is planned today; populate only when an
EKS-worthy workload arrives.
