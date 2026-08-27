# edge/tls/acm

AWS Certificate Manager. Terminates TLS at the ELB, not at the cluster.

## When to use

Only when the cluster uses `cloud-loadbalancer` tunnel on AWS.

## How it works

1. Cert requested in ACM for the target hostname(s).
2. DNS validation record added to Route53 automatically.
3. ELB's HTTPS listener uses the ACM cert ARN — no cert ever reaches the
   cluster.

## Cluster-side impact

Zero. traefik (in-cluster) sees plain HTTP; ELB handles TLS termination.
The chart's `Ingress.spec.tls[]` block is ignored when the cluster uses
ACM — platform admission warns + strips it during render.

## Status

STUB.
