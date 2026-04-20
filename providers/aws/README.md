# providers/aws

AWS Terraform modules. Fulfill the `compute-unit` interface for AWS.

## Planned modules

- `modules/vpc/` — VPC with public + private subnets, NAT, endpoints.
- `modules/compute/` — EC2 instances, security groups, launch templates.
  Honors the `compute_unit` interface (picks t4g.* for ARM, t3a.* for x86).
- `modules/eks/` — EKS control plane + managed node groups (when using
  `cluster-cloud-aws-eks` template). IRSA + OIDC provider enabled.
- `modules/ecr/` — container registries per app with lifecycle policies.
- `modules/iam/` — assume-role and service-account role factories.
- `modules/route53/` — hosted zones + records.
- `modules/acm/` — certificates (when not using cert-manager).
- `modules/s3/` — buckets for backups / state.

## Free-tier leverage

- `t4g.small` — free-tier eligible through 2026-12 (used by `agent-02` and
  `arm-builder` today).
- Recompute free-tier usage via `platform/services/cost/` (OpenCost) once
  populated; move beyond free-tier only with an explicit envelope bump in
  the consuming cluster's identity.yaml.

## Status

STUB. Populate with modules ported from the pre-rebuild `cloud/aws/` tree,
refactored to the `compute_unit` interface.
