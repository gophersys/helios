# edge/dns/route53

AWS Route53 as the public DNS provider. Pairs naturally with
`cloud-loadbalancer` on AWS + `acm`.

## Setup

1. Hosted zones declared in cluster identity.
2. NS delegation configured at the registrar.
3. IAM role with `route53:ChangeResourceRecordSets` on the zones, assumed
   by external-dns via IRSA (EKS) or static credentials from Bitwarden.
4. external-dns operator installed with the Route53 provider.

## Status

STUB.
