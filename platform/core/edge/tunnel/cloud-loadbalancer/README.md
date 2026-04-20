# edge/tunnel/cloud-loadbalancer

Cloud-native load balancers (AWS ELB, OCI LB, Azure LB) as the public
traffic entry. The cluster requests a `Service` of `type: LoadBalancer`;
the cloud-controller-manager provisions the LB.

## When to use

- Cluster has outgrown free-tier or needs managed-LB SLAs.
- Workload requires raw TCP/UDP passthrough, not just HTTP.
- Regulatory constraint requires traffic to never traverse a
  third-party network (e.g., CF).
- Tight integration with cloud WAF / DDoS (AWS Shield, OCI WAF).

## How it works

The `ingress-controller` Service (traefik) is created with
`type: LoadBalancer`. The cloud-controller-manager provisions:

- **AWS:** Classic ELB (default) or NLB / ALB via annotations. Pairs
  with ACM for TLS termination at the LB, Route53 for DNS.
- **OCI:** OCI LB. Pairs with OCI Certificates or cert-manager for TLS.
- **Azure:** Azure LB (standard) or Application Gateway via annotations.

## Costs

- AWS Classic ELB: $16/mo + data transfer.
- AWS NLB: $16/mo + LCU billing.
- AWS ALB: $16/mo + LCU billing.
- OCI LB Flexible: from $10/mo.
- Azure LB Standard: from $18/mo.

One LB per cluster is standard; per-app LBs multiply cost fast.

## Compatibility

| DNS provider  | TLS provider           | Cloud                    |
|---------------|------------------------|--------------------------|
| `route53`     | `acm`                  | AWS (recommended)        |
| `route53`     | `letsencrypt-dns01`    | AWS (if ACM unavailable) |
| `cloudflare`  | `letsencrypt-dns01`    | Any (CF as DNS only)     |

## Status

STUB. Default for cloud-managed clusters once one is provisioned.
